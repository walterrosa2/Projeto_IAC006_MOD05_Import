"""Geração do lançamento contábil a partir da sugestão validada (Tarefa 5.4).

O lançamento sempre nasce em PENDING_REVIEW: a IA sugere, o contador aprova.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.accounting.accounting_validator import ValidationResult, validate_ai_payload
from core.accounting.ai_accounting_classifier import AIResponse, classify_accounting
from core.accounting.prompt_builder import build_prompt
from core.constants import DocumentStatus, EntryStatus
from core.exceptions import AIProviderError, AIResponseError, ClassificadorError
from core.logging_config import get_logger, log_audit
from core.scanner.duplicate_detector import decide_base_document
from db.models import AccountingEntry, Company, ProcessedDocument
from db.repositories import accounting_entry_repository, document_repository

logger = get_logger()


@dataclass
class EntryGenerationResult:
    """Desfecho da tentativa de gerar um lançamento para um documento."""

    document_id: int
    entry: AccountingEntry | None
    validation: ValidationResult | None
    ai_response: AIResponse | None
    skipped_reason: str | None = None
    error: str | None = None

    @property
    def generated(self) -> bool:
        return self.entry is not None

    @property
    def status_label(self) -> str:
        if self.error:
            return "ERRO"
        if self.entry is not None:
            return "LANÇAMENTO GERADO"
        return "SEM LANÇAMENTO"


def generate_entry_for_document(
    document: ProcessedDocument,
    company: Company,
    *,
    force: bool = False,
) -> EntryGenerationResult:
    """Chama a IA e cria o lançamento pendente para um documento.

    Args:
        force: regera mesmo que o documento já possua lançamento.
    """
    existing = accounting_entry_repository.list_entries_by_document(document.id)
    if existing and not force:
        return EntryGenerationResult(
            document_id=document.id,
            entry=existing[0],
            validation=None,
            ai_response=None,
            skipped_reason="Documento já possui lançamento gerado.",
        )

    if document.processing_status in {DocumentStatus.DUPLICATE, DocumentStatus.ERROR}:
        return EntryGenerationResult(
            document_id=document.id,
            entry=None,
            validation=None,
            ai_response=None,
            skipped_reason=f"Documento com status {document.processing_status} não gera lançamento.",
        )

    # Hierarquia de documento base (PRD seção 10) antes de gastar chamada de IA.
    decision = decide_base_document(
        company.id,
        document_id=document.id,
        document_type=document.document_type,
        document_date=document.document_date,
        amount=document.amount,
    )
    if not decision.should_generate_entry:
        document_repository.update_document(
            document.id,
            {
                "processing_status": DocumentStatus.PENDING_REVIEW,
                "duplicate_of_id": decision.base_document_id,
                "duplicate_reason": decision.reason,
            },
        )
        log_audit(
            "entry_skipped_base_document",
            target=f"documento:{document.id}",
            outcome="blocked",
            data={"reason": decision.reason, "base_document_id": decision.base_document_id},
        )
        return EntryGenerationResult(
            document_id=document.id,
            entry=None,
            validation=None,
            ai_response=None,
            skipped_reason=decision.reason,
        )

    extracted = document_repository.get_structured_data(document.id)
    record = document_repository.get_extracted_data(document.id)
    document_text = record.raw_text if record and record.raw_text else ""

    context = build_prompt(
        company=company,
        document_type=document.document_type,
        extracted_data=extracted,
        document_text=document_text,
        counterparty=document.counterparty,
        base_document_note=decision.reason,
    )

    try:
        ai_response = classify_accounting(context, document_id=document.id)
    except (AIProviderError, AIResponseError) as exc:
        document_repository.update_document(
            document.id,
            {
                "processing_status": DocumentStatus.ERROR,
                "error_type": exc.error_type,
                "error_message": exc.message,
            },
        )
        log_audit(
            "entry_generation_failed",
            target=f"documento:{document.id}",
            outcome="failure",
            data={"erro_tipo": exc.error_type, "erro_mensagem": exc.message},
        )
        return EntryGenerationResult(
            document_id=document.id,
            entry=None,
            validation=None,
            ai_response=None,
            error=f"{exc.error_type}: {exc.message}",
        )

    validation = validate_ai_payload(
        ai_response.payload,
        company_id=company.id,
        document_amount=document.amount,
    )

    # IA decidiu que não há lançamento: registra e encerra sem erro.
    if not validation.should_generate_entry:
        reason = validation.normalized.get("base_document_reason") or "IA indicou que não há lançamento."
        document_repository.update_document(
            document.id,
            {"processing_status": DocumentStatus.PENDING_REVIEW, "duplicate_reason": reason},
        )
        return EntryGenerationResult(
            document_id=document.id,
            entry=None,
            validation=validation,
            ai_response=ai_response,
            skipped_reason=reason,
        )

    # Sugestão inválida (conta inexistente, valor ausente...): vira lançamento com
    # status ERROR para aparecer na revisão, em vez de sumir silenciosamente.
    status = EntryStatus.PENDING_REVIEW if validation.is_valid else EntryStatus.ERROR
    normalized = validation.normalized

    entry = accounting_entry_repository.create_entry(
        {
            "company_id": company.id,
            "document_id": document.id,
            "entry_date": normalized.get("entry_date"),
            "debit_account_code": normalized.get("debit_account_code"),
            "credit_account_code": normalized.get("credit_account_code"),
            "amount": normalized.get("amount"),
            "history_code": normalized.get("history_code"),
            "history_complement": normalized.get("history_complement"),
            "branch_code": company.branch_code,
            "debit_cost_center_code": normalized.get("debit_cost_center_code"),
            "credit_cost_center_code": normalized.get("credit_cost_center_code"),
            "ai_confidence": normalized.get("confidence"),
            "ai_justification": normalized.get("justification"),
            "ai_warnings": json.dumps(validation.warnings, ensure_ascii=False)
            if validation.warnings
            else None,
            "base_document_reason": normalized.get("base_document_reason"),
            "validation_issues": json.dumps(validation.errors, ensure_ascii=False)
            if validation.errors
            else None,
            "status": status,
        }
    )

    document_repository.update_document(
        document.id,
        {
            "processing_status": DocumentStatus.ENTRY_GENERATED
            if validation.is_valid
            else DocumentStatus.ERROR,
            "error_type": None if validation.is_valid else "CONTA_INEXISTENTE",
            "error_message": None if validation.is_valid else validation.summary,
        },
    )

    log_audit(
        "entry_generated",
        target=f"lancamento:{entry.id}",
        outcome="success" if validation.is_valid else "failure",
        data={
            "document_id": document.id,
            "status": status,
            "confidence": normalized.get("confidence"),
            "errors": validation.errors,
            "warnings_count": len(validation.warnings),
            "provider": ai_response.provider,
        },
    )

    return EntryGenerationResult(
        document_id=document.id,
        entry=entry,
        validation=validation,
        ai_response=ai_response,
    )


def generate_entries_for_documents(
    documents: list[ProcessedDocument],
    company: Company,
    *,
    force: bool = False,
    progress_callback=None,
) -> list[EntryGenerationResult]:
    """Gera lançamentos em lote.

    Uma falha em um documento não interrompe os demais — o erro fica registrado
    no próprio documento e no resultado.
    """
    results: list[EntryGenerationResult] = []
    total = len(documents)

    for index, document in enumerate(documents, start=1):
        try:
            result = generate_entry_for_document(document, company, force=force)
        except ClassificadorError as exc:
            result = EntryGenerationResult(
                document_id=document.id,
                entry=None,
                validation=None,
                ai_response=None,
                error=f"{exc.error_type}: {exc.message}",
            )
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o lote inteiro
            logger.exception(f"Erro inesperado ao gerar lançamento do documento {document.id}")
            result = EntryGenerationResult(
                document_id=document.id,
                entry=None,
                validation=None,
                ai_response=None,
                error=f"ERRO_INESPERADO: {exc}",
            )

        results.append(result)
        if progress_callback:
            progress_callback(index, total, result)

    return results
