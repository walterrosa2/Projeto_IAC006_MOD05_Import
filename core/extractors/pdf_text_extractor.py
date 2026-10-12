"""Leitura de texto de PDF: PyMuPDF como principal, pdfplumber como reserva."""

from __future__ import annotations

from pathlib import Path

from core.exceptions import (
    CorruptedFileError,
    ExtractionError,
    PdfProtectedError,
    PdfWithoutTextError,
)

#: Abaixo disso o PDF é tratado como digitalizado/sem camada de texto.
MIN_TEXT_LENGTH = 30


def _extract_with_pymupdf(path: Path) -> str:
    import pymupdf

    document = pymupdf.open(path)
    try:
        if document.needs_pass:
            raise PdfProtectedError(
                f"PDF protegido por senha: {path.name}",
                detail="Solicitar ao cliente o arquivo sem proteção.",
            )
        return "\n".join(page.get_text("text") for page in document)
    finally:
        document.close()


def _extract_with_pdfplumber(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_pdf_text(file_path: str | Path, *, allow_ocr: bool = False) -> str:
    """Texto completo do PDF.

    Args:
        allow_ocr: quando o PDF não tem camada de texto, tenta OCR via IA
            multimodal antes de desistir. Exige `OCR_ENABLED=true` e um
            provedor real configurado; do contrário a exceção original é
            mantida. O OCR custa tokens, por isso não é o padrão.

    Raises:
        PdfProtectedError: PDF com senha.
        PdfWithoutTextError: PDF sem camada de texto e sem OCR disponível.
        CorruptedFileError: arquivo ilegível pelos dois leitores.
    """
    path = Path(file_path)
    if not path.is_file():
        raise CorruptedFileError(f"Arquivo não encontrado: {path.name}", detail=str(path))

    text = ""
    errors: list[str] = []

    try:
        text = _extract_with_pymupdf(path)
    except PdfProtectedError:
        raise
    except Exception as exc:  # noqa: BLE001 - qualquer falha cai para o leitor reserva
        errors.append(f"PyMuPDF: {exc}")

    if len(text.strip()) < MIN_TEXT_LENGTH:
        try:
            fallback = _extract_with_pdfplumber(path)
            if len(fallback.strip()) > len(text.strip()):
                text = fallback
        except Exception as exc:  # noqa: BLE001
            errors.append(f"pdfplumber: {exc}")

    if len(text.strip()) >= MIN_TEXT_LENGTH:
        return text

    # Sem camada de texto utilizável: OCR é a última tentativa.
    if allow_ocr:
        ocr_text = _try_ocr(path)
        if ocr_text is not None:
            return ocr_text

    if not text.strip():
        if errors:
            raise CorruptedFileError(
                f"Não foi possível abrir o PDF: {path.name}",
                detail=" | ".join(errors),
            )
        raise PdfWithoutTextError(
            f"PDF sem texto extraível (provável digitalização): {path.name}",
            detail="Ative o OCR (OCR_ENABLED=true) ou solicite o arquivo digital ao cliente.",
        )

    raise PdfWithoutTextError(
        f"PDF com texto insuficiente para classificação: {path.name}",
        detail=f"Apenas {len(text.strip())} caracteres extraídos.",
    )


def _try_ocr(path: Path) -> str | None:
    """Tenta OCR e devolve o texto, ou None para manter o erro original.

    Falha de OCR nunca substitui o diagnóstico do PDF: é registrada e o
    chamador segue com a exceção que já teria levantado.
    """
    from core.extractors.ocr_extractor import ocr_is_available, ocr_pdf
    from core.logging_config import get_logger

    logger = get_logger()
    available, reason = ocr_is_available()
    if not available:
        logger.info(f"OCR não aplicado em {path.name}: {reason}")
        return None

    try:
        result = ocr_pdf(path)
    except Exception as exc:  # noqa: BLE001 - OCR é best-effort
        logger.warning(f"OCR falhou em {path.name}: {type(exc).__name__}")
        return None

    logger.info(
        f"OCR aplicado em {path.name}: {result.char_count} caracteres "
        f"de {result.pages} página(s) via {result.provider}."
    )
    return f"{OCR_MARKER}\n{result.text}"


#: Prefixo que identifica um texto vindo de OCR (usado pelo pipeline para
#: sinalizar o documento e reduzir a confiança da classificação).
OCR_MARKER = "[TEXTO OBTIDO POR OCR — TRANSCRIÇÃO AUTOMÁTICA, CONFERIR COM O ORIGINAL]"


def text_came_from_ocr(text: str) -> bool:
    """True quando o texto foi produzido por OCR."""
    return bool(text) and text.lstrip().startswith(OCR_MARKER)


def extract_text_any(file_path: str | Path, *, allow_ocr: bool = False) -> str:
    """Texto de qualquer formato suportado (PDF, XML, planilha, texto puro).

    Args:
        allow_ocr: repassado a `extract_pdf_text`; sem efeito nos demais formatos.

    Raises:
        ExtractionError: extensão não suportada ou falha de leitura.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(path, allow_ocr=allow_ocr)

    if extension in {".xlsx", ".xls", ".csv"}:
        from core.extractors.spreadsheet_extractor import extract_spreadsheet_text

        return extract_spreadsheet_text(path)

    if extension in {".xml", ".txt"}:
        for encoding in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                raise CorruptedFileError(
                    f"Não foi possível ler o arquivo: {path.name}", detail=str(exc)
                ) from exc
        raise CorruptedFileError(
            f"Codificação não reconhecida: {path.name}",
            detail="Tentado UTF-8 e Latin-1.",
        )

    raise ExtractionError(
        f"Extensão não suportada: {extension or 'sem extensão'}",
        detail=f"Arquivo {path.name} não pode ser processado pela esteira.",
    )
