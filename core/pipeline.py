"""Esteira de processamento documental.

Encadeia scanner -> hash -> duplicidade -> extração de texto -> classificação ->
organização em pastas -> extração de dados -> persistência.

Nenhuma exceção escapa por documento: falha técnica vira status ERROR, arquivo
copiado para ERROS e marcador .json com o motivo (PRD 8.3 / CA02).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.constants import DocumentStatus, DocumentType, ErrorType
from core.documents.document_classifier import classify_document
from core.documents.document_types import get_extractor
from core.documents.folder_organizer import organize_document, write_error_marker
from core.exceptions import ClassificadorError, ExtractionError
from core.extractors.base_extractor import ExtractionResult
from core.extractors.pdf_text_extractor import extract_text_any, text_came_from_ocr
from core.logging_config import get_logger, log_audit
from core.scanner import duplicate_detector
from core.scanner.file_hash import compute_file_hash
from core.scanner.file_scanner import ScannedFile, scan_folder
from db.models import Company, ProcessedDocument
from db.repositories import document_repository

logger = get_logger()


@dataclass
class DocumentProcessingResult:
    """Desfecho do processamento de um arquivo."""

    file_name: str
    status: str
    document_type: str
    document_id: int | None = None
    destination_path: str | None = None
    confidence: float | None = None
    message: str = ""
    error_type: str | None = None

    @property
    def is_error(self) -> bool:
        return self.status == DocumentStatus.ERROR

    @property
    def is_duplicate(self) -> bool:
        return self.status == DocumentStatus.DUPLICATE

    @property
    def is_unknown(self) -> bool:
        return self.document_type == DocumentType.OUTRO


@dataclass
class BatchProcessingResult:
    """Consolidado do lote (tela Processar Pasta)."""

    results: list[DocumentProcessingResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def classified(self) -> list[DocumentProcessingResult]:
        return [r for r in self.results if not r.is_error and not r.is_duplicate and not r.is_unknown]

    @property
    def unknown(self) -> list[DocumentProcessingResult]:
        return [r for r in self.results if r.is_unknown and not r.is_error]

    @property
    def duplicates(self) -> list[DocumentProcessingResult]:
        return [r for r in self.results if r.is_duplicate]

    @property
    def errors(self) -> list[DocumentProcessingResult]:
        return [r for r in self.results if r.is_error]

    def summary(self) -> dict[str, int]:
        return {
            "total": self.total,
            "classificados": len(self.classified),
            "outros": len(self.unknown),
            "duplicados": len(self.duplicates),
            "erros": len(self.errors),
        }


# --------------------------------------------------------------------------- #
# Etapas
# --------------------------------------------------------------------------- #


def _copy_and_register_error(
    *,
    company: Company,
    scanned: ScannedFile,
    file_hash: str,
    error_type: str,
    error_message: str,
    detail: str | None = None,
) -> DocumentProcessingResult:
    """Copia o arquivo para ERROS, grava o marcador .json e registra no banco."""
    destination_path: str | None = None
    try:
        organized = organize_document(
            source_path=scanned.path,
            destination_root=company.destination_folder_path,
            company_name=company.name,
            document_type=DocumentType.ERROR,
            competence_year=None,
            competence_month=None,
        )
        destination_path = str(organized.destination_path)
        write_error_marker(
            destination_path=organized.destination_path,
            original_file_name=scanned.name,
            company_name=company.name,
            error_type=error_type,
            error_message=error_message,
        )
    except ClassificadorError as exc:
        logger.error(f"Falha ao copiar {scanned.name} para ERROS: {exc.message}")

    document = document_repository.create_document(
        {
            "company_id": company.id,
            "original_file_name": scanned.name,
            "original_file_path": str(scanned.path),
            "stored_file_path": destination_path,
            "file_hash": file_hash,
            "file_extension": scanned.extension,
            "file_size_bytes": scanned.size_bytes,
            "document_type": DocumentType.ERROR,
            "processing_status": DocumentStatus.ERROR,
            "error_type": error_type,
            "error_message": error_message,
        }
    )

    log_audit(
        "document_error",
        target=f"documento:{document.id}",
        outcome="failure",
        data={
            "arquivo": scanned.name,
            "erro_tipo": error_type,
            "erro_mensagem": error_message,
            "detalhe": detail,
        },
    )

    return DocumentProcessingResult(
        file_name=scanned.name,
        status=DocumentStatus.ERROR,
        document_type=DocumentType.ERROR,
        document_id=document.id,
        destination_path=destination_path,
        message=error_message,
        error_type=error_type,
    )


def _register_duplicate(
    *,
    company: Company,
    scanned: ScannedFile,
    file_hash: str,
    check: duplicate_detector.DuplicateCheck,
    document_type: str = DocumentType.DUPLICATE,
    competence: tuple[int | None, int | None] = (None, None),
) -> DocumentProcessingResult:
    """Copia para DUPLICADOS e registra sem gerar lançamento (CA04)."""
    destination_path: str | None = None
    try:
        organized = organize_document(
            source_path=scanned.path,
            destination_root=company.destination_folder_path,
            company_name=company.name,
            document_type=DocumentType.DUPLICATE,
            competence_year=competence[0],
            competence_month=competence[1],
        )
        destination_path = str(organized.destination_path)
    except ClassificadorError as exc:
        logger.error(f"Falha ao copiar duplicado {scanned.name}: {exc.message}")

    document = document_repository.create_document(
        {
            "company_id": company.id,
            "original_file_name": scanned.name,
            "original_file_path": str(scanned.path),
            "stored_file_path": destination_path,
            "file_hash": file_hash,
            "file_extension": scanned.extension,
            "file_size_bytes": scanned.size_bytes,
            "document_type": document_type,
            "competence_year": competence[0],
            "competence_month": competence[1],
            "processing_status": DocumentStatus.DUPLICATE,
            "duplicate_of_id": check.original_document_id,
            "duplicate_reason": check.reason,
        }
    )

    log_audit(
        "document_duplicate",
        target=f"documento:{document.id}",
        outcome="blocked",
        data={
            "arquivo": scanned.name,
            "match_type": check.match_type,
            "original_document_id": check.original_document_id,
        },
    )

    return DocumentProcessingResult(
        file_name=scanned.name,
        status=DocumentStatus.DUPLICATE,
        document_type=document_type,
        document_id=document.id,
        destination_path=destination_path,
        message=check.reason or "Documento duplicado.",
    )


def _run_extractor(document_type: str, file_path: Path, text: str) -> ExtractionResult | None:
    """Executa o extrator do tipo, sem deixar falha de extração derrubar a esteira."""
    extractor = get_extractor(document_type)
    if extractor is None:
        return None
    try:
        return extractor.extract(file_path, text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Extrator '{document_type}' falhou em {file_path.name}: {exc}")
        return None


def process_single_file(
    scanned: ScannedFile,
    company: Company,
    *,
    fallback_year: int | None = None,
    fallback_month: int | None = None,
) -> DocumentProcessingResult:
    """Processa um arquivo da entrada até ficar pronto para a IA.

    `fallback_year`/`fallback_month`: competência escolhida pelo usuário, usada
    quando o documento não traz data identificável (Arquitetura 7.3).
    """
    # 1. Hash ---------------------------------------------------------------
    try:
        file_hash = compute_file_hash(scanned.path)
    except ClassificadorError as exc:
        return DocumentProcessingResult(
            file_name=scanned.name,
            status=DocumentStatus.ERROR,
            document_type=DocumentType.ERROR,
            message=exc.message,
            error_type=exc.error_type,
        )

    # 2. Duplicidade por hash ----------------------------------------------
    hash_check = duplicate_detector.check_by_hash(company.id, file_hash)
    if hash_check.is_duplicate:
        return _register_duplicate(
            company=company, scanned=scanned, file_hash=file_hash, check=hash_check
        )

    # 3. Extensão suportada -------------------------------------------------
    if not scanned.supported:
        return _copy_and_register_error(
            company=company,
            scanned=scanned,
            file_hash=file_hash,
            error_type=ErrorType.EXTRACAO_FALHOU,
            error_message=f"Extensão '{scanned.extension or 'sem extensão'}' não suportada pela esteira.",
        )

    # 4. Texto --------------------------------------------------------------
    # OCR entra só se habilitado no .env e apenas quando não há camada de texto.
    try:
        text = extract_text_any(scanned.path, allow_ocr=get_settings().ocr_enabled)
    except ExtractionError as exc:
        return _copy_and_register_error(
            company=company,
            scanned=scanned,
            file_hash=file_hash,
            error_type=exc.error_type,
            error_message=exc.message,
            detail=exc.detail,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Erro inesperado lendo {scanned.name}")
        return _copy_and_register_error(
            company=company,
            scanned=scanned,
            file_hash=file_hash,
            error_type=ErrorType.ERRO_INESPERADO,
            error_message=f"Erro inesperado ao ler o arquivo: {exc}",
        )

    # 5. Classificação ------------------------------------------------------
    from_ocr = text_came_from_ocr(text)
    classification = classify_document(
        file_name=scanned.name, extension=scanned.extension, text=text
    )

    # 6. Extração de dados --------------------------------------------------
    extraction = _run_extractor(classification.document_type, scanned.path, text)

    document_date = (extraction.document_date if extraction else None) or classification.document_date
    year = document_date.year if document_date else (classification.competence_year or fallback_year)
    month = document_date.month if document_date else (classification.competence_month or fallback_month)

    counterparty = extraction.counterparty if extraction else None
    document_number = extraction.document_number if extraction else None
    amount = extraction.amount if extraction else None

    # 7. Duplicidade por dados essenciais ----------------------------------
    business_check = duplicate_detector.check_by_business_data(
        company.id,
        document_date=document_date,
        amount=amount,
        counterparty=counterparty,
        document_number=document_number,
        document_type=classification.document_type,
    )
    if business_check.is_duplicate:
        return _register_duplicate(
            company=company,
            scanned=scanned,
            file_hash=file_hash,
            check=business_check,
            document_type=classification.document_type,
            competence=(year, month),
        )

    # 8. Organização em pastas ---------------------------------------------
    try:
        organized = organize_document(
            source_path=scanned.path,
            destination_root=company.destination_folder_path,
            company_name=company.name,
            document_type=classification.document_type,
            competence_year=year,
            competence_month=month,
        )
        destination_path = str(organized.destination_path)
    except ClassificadorError as exc:
        return _copy_and_register_error(
            company=company,
            scanned=scanned,
            file_hash=file_hash,
            error_type=ErrorType.ERRO_INESPERADO,
            error_message=exc.message,
            detail=exc.detail,
        )

    # 9. Persistência -------------------------------------------------------
    is_unknown = classification.document_type == DocumentType.OUTRO
    status = DocumentStatus.UNKNOWN if is_unknown else DocumentStatus.EXTRACTED

    document = document_repository.create_document(
        {
            "company_id": company.id,
            "original_file_name": scanned.name,
            "original_file_path": str(scanned.path),
            "stored_file_path": destination_path,
            "file_hash": file_hash,
            "file_extension": scanned.extension,
            "file_size_bytes": scanned.size_bytes,
            "document_type": classification.document_type,
            "document_date": document_date,
            "competence_year": year,
            "competence_month": month,
            "counterparty": counterparty,
            "document_number": document_number,
            "amount": amount,
            "classification_confidence": classification.confidence,
            "classification_reason": (
                f"{classification.reason} [Texto obtido por OCR — conferir com o original.]"
                if from_ocr
                else classification.reason
            ),
            "processing_status": status,
        }
    )

    document_repository.save_extracted_data(
        document.id,
        raw_text=text,
        structured=extraction.as_structured_payload() if extraction else None,
        extractor_name=(
            f"{extraction.extractor_name}+ocr" if extraction and from_ocr else
            (extraction.extractor_name if extraction else ("ocr" if from_ocr else None))
        ),
        confidence=extraction.confidence if extraction else None,
    )

    log_audit(
        "document_classified",
        target=f"documento:{document.id}",
        outcome="success",
        data={
            "arquivo": scanned.name,
            "tipo": classification.document_type,
            "confianca": classification.confidence,
            "competencia": f"{year}-{month}" if year and month else None,
            "destino": destination_path,
            "ocr": from_ocr,
        },
    )

    message = classification.reason
    if from_ocr:
        message = f"⚠ Texto obtido por OCR — conferir com o original. {message}"
    if extraction and extraction.warnings:
        message = f"{message} Avisos da extração: {'; '.join(extraction.warnings)}"

    return DocumentProcessingResult(
        file_name=scanned.name,
        status=status,
        document_type=classification.document_type,
        document_id=document.id,
        destination_path=destination_path,
        confidence=classification.confidence,
        message=message,
    )


def process_company_folder(
    company: Company,
    *,
    files: list[ScannedFile] | None = None,
    fallback_year: int | None = None,
    fallback_month: int | None = None,
    progress_callback=None,
) -> BatchProcessingResult:
    """Processa a pasta de entrada da empresa.

    Args:
        files: subconjunto selecionado na tela; None varre a pasta inteira.
        progress_callback: chamado como (índice, total, resultado).
    """
    scanned_files = files if files is not None else scan_folder(company.input_folder_path)
    batch = BatchProcessingResult()
    total = len(scanned_files)

    for index, scanned in enumerate(scanned_files, start=1):
        try:
            result = process_single_file(
                scanned, company, fallback_year=fallback_year, fallback_month=fallback_month
            )
        except Exception as exc:  # noqa: BLE001 - um arquivo ruim não para o lote
            logger.exception(f"Erro inesperado processando {scanned.name}")
            result = DocumentProcessingResult(
                file_name=scanned.name,
                status=DocumentStatus.ERROR,
                document_type=DocumentType.ERROR,
                message=f"Erro inesperado: {exc}",
                error_type=ErrorType.ERRO_INESPERADO,
            )

        batch.results.append(result)
        if progress_callback:
            progress_callback(index, total, result)

    log_audit(
        "folder_processed",
        actor="user",
        target=f"empresa:{company.id}",
        outcome="success",
        data=batch.summary(),
    )
    return batch


def documents_ready_for_ai(company_id: int, *, limit: int = 500) -> list[ProcessedDocument]:
    """Documentos classificados e extraídos que ainda não têm lançamento."""
    candidates = document_repository.search_documents(
        company_id=company_id, status=DocumentStatus.EXTRACTED, limit=limit
    )
    return [doc for doc in candidates if doc.document_type != DocumentType.OUTRO]


def build_processing_summary(batch: BatchProcessingResult) -> list[dict[str, Any]]:
    """Linhas da tabela de resultado exibida na tela Processar Pasta."""
    return [
        {
            "Arquivo": r.file_name,
            "Tipo": r.document_type,
            "Status": r.status,
            "Confiança": f"{r.confidence:.0%}" if r.confidence is not None else "—",
            "Destino": Path(r.destination_path).parent.name if r.destination_path else "—",
            "Observação": r.message[:160] if r.message else "",
        }
        for r in batch.results
    ]
