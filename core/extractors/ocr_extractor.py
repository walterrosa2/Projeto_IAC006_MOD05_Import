"""OCR de PDFs digitalizados via IA multimodal.

Usado apenas quando o PDF não tem camada de texto. Em vez de depender de um
binário externo (Tesseract), aproveita o provedor de IA já configurado no
`.env` — Gemini e Anthropic leem PDF nativamente; para OpenAI as páginas são
rasterizadas em PNG com o PyMuPDF que já é dependência do projeto.

Custo: cada página vira tokens de imagem. Por isso o OCR é opt-in
(`OCR_ENABLED`), tem teto de páginas (`OCR_MAX_PAGES`) e grava evidência.

O texto devolvido é **transcrição**, não interpretação: o prompt proíbe
resumir, completar ou inferir valores. Ainda assim é conteúdo reconhecido por
modelo, sujeito a erro de leitura — por isso o documento recebe um aviso e
confiança reduzida (ver `pipeline`).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from core.config import get_settings
from core.exceptions import AIProviderError, ExtractionError, PdfWithoutTextError
from core.logging_config import get_logger, log_audit

logger = get_logger()

#: Resolução da rasterização, quando o provedor não aceita PDF nativo.
RENDER_DPI = 200

#: Abaixo disso o OCR é considerado infrutífero (página em branco, borrão).
MIN_OCR_TEXT_LENGTH = 20

OCR_PROMPT = (
    "Transcreva TODO o texto visível deste documento, preservando a ordem de "
    "leitura e as quebras de linha.\n"
    "Regras obrigatórias:\n"
    "- Transcreva literalmente. NÃO resuma, NÃO interprete, NÃO complete o que "
    "não estiver legível.\n"
    "- Mantenha números, datas e valores exatamente como aparecem, incluindo "
    "pontuação (1.234,56).\n"
    "- Para trechos ilegíveis, escreva [ilegível].\n"
    "- Preserve rótulos de campo (ex.: 'CNPJ:', 'Valor total:').\n"
    "- Em tabelas, separe as colunas com ' | '.\n"
    "- Responda apenas com a transcrição, sem comentários seus."
)


@dataclass
class OcrResult:
    """Texto reconhecido e metadados da chamada."""

    text: str
    provider: str
    model: str
    pages: int
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def char_count(self) -> int:
        return len(self.text)


def _page_count(path: Path) -> int:
    import pymupdf

    document = pymupdf.open(path)
    try:
        return document.page_count
    finally:
        document.close()


def _render_pages_to_png(path: Path, max_pages: int) -> list[bytes]:
    """Rasteriza as primeiras páginas do PDF em PNG."""
    import pymupdf

    images: list[bytes] = []
    document = pymupdf.open(path)
    try:
        zoom = RENDER_DPI / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        for index, page in enumerate(document):
            if index >= max_pages:
                break
            images.append(page.get_pixmap(matrix=matrix).tobytes("png"))
    finally:
        document.close()
    return images


# --------------------------------------------------------------------------- #
# Provedores
# --------------------------------------------------------------------------- #


def _ocr_gemini(path: Path, settings, max_pages: int) -> tuple[str, int | None, int | None]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.api_key)
    pages = min(_page_count(path), max_pages)

    if pages == _page_count(path):
        # PDF inteiro cabe no teto: envia o arquivo nativo (melhor fidelidade).
        parts = [
            types.Part.from_bytes(data=path.read_bytes(), mime_type="application/pdf"),
            types.Part.from_text(text=OCR_PROMPT),
        ]
    else:
        parts = [
            types.Part.from_bytes(data=image, mime_type="image/png")
            for image in _render_pages_to_png(path, max_pages)
        ]
        parts.append(types.Part.from_text(text=OCR_PROMPT))

    response = client.models.generate_content(model=settings.ai_model, contents=parts)
    usage = getattr(response, "usage_metadata", None)
    return (
        response.text or "",
        getattr(usage, "prompt_token_count", None),
        getattr(usage, "candidates_token_count", None),
    )


def _ocr_anthropic(path: Path, settings, max_pages: int) -> tuple[str, int | None, int | None]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.api_key, timeout=settings.ai_timeout_seconds)
    total = _page_count(path)

    if total <= max_pages:
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(path.read_bytes()).decode(),
                },
            }
        ]
    else:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(image).decode(),
                },
            }
            for image in _render_pages_to_png(path, max_pages)
        ]

    content.append({"type": "text", "text": OCR_PROMPT})
    message = client.messages.create(
        model=settings.ai_model,
        max_tokens=8000,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = getattr(message, "usage", None)
    return text, getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)


def _ocr_openai(path: Path, settings, max_pages: int) -> tuple[str, int | None, int | None]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.api_key, timeout=settings.ai_timeout_seconds)
    content: list[dict] = [{"type": "text", "text": OCR_PROMPT}]
    for image in _render_pages_to_png(path, max_pages):
        encoded = base64.standard_b64encode(image).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        )

    completion = client.chat.completions.create(
        model=settings.ai_model,
        messages=[{"role": "user", "content": content}],
    )
    usage = getattr(completion, "usage", None)
    return (
        completion.choices[0].message.content or "",
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


_OCR_PROVIDERS = {
    "gemini": _ocr_gemini,
    "anthropic": _ocr_anthropic,
    "openai": _ocr_openai,
}


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #


def ocr_is_available() -> tuple[bool, str]:
    """Se o OCR pode rodar agora, e o porquê quando não pode."""
    settings = get_settings()
    if not settings.ocr_enabled:
        return False, "OCR desativado (defina OCR_ENABLED=true no .env)."
    if settings.ai_provider == "mock":
        return False, "OCR indisponível no provedor MOCK: exige IA multimodal real."
    if settings.ai_provider not in _OCR_PROVIDERS:
        return False, f"Provedor '{settings.ai_provider}' não suporta OCR."
    if not settings.api_key:
        return False, f"Chave de API do provedor '{settings.ai_provider}' ausente."
    return True, f"OCR via {settings.ai_provider} / {settings.ai_model}."


def ocr_pdf(file_path: str | Path, *, document_id: int | None = None) -> OcrResult:
    """Transcreve um PDF digitalizado usando a IA multimodal configurada.

    Raises:
        ExtractionError: OCR indisponível, ou o modelo não devolveu texto útil.
        AIProviderError: falha na chamada ao provedor.
    """
    path = Path(file_path)
    settings = get_settings()

    available, reason = ocr_is_available()
    if not available:
        raise ExtractionError(f"OCR não pôde ser executado: {reason}", detail=reason)

    caller = _OCR_PROVIDERS[settings.ai_provider]
    total_pages = _page_count(path)
    pages = min(total_pages, settings.ocr_max_pages)

    try:
        text, input_tokens, output_tokens = caller(path, settings, settings.ocr_max_pages)
    except Exception as exc:  # noqa: BLE001 - erro do SDK do provedor
        log_audit(
            "ocr_failed",
            target=f"documento:{document_id}" if document_id else f"arquivo:{path.name}",
            outcome="failure",
            data={"provider": settings.ai_provider, "erro": type(exc).__name__},
        )
        raise AIProviderError(
            f"Falha no OCR de {path.name} via {settings.ai_provider}.",
            detail=str(exc)[:300],
        ) from exc

    text = (text or "").strip()
    if len(text) < MIN_OCR_TEXT_LENGTH:
        raise PdfWithoutTextError(
            f"OCR não reconheceu texto suficiente em {path.name}.",
            detail=f"Apenas {len(text)} caracteres reconhecidos. Verificar a qualidade do arquivo.",
        )

    log_audit(
        "ocr_completed",
        target=f"documento:{document_id}" if document_id else f"arquivo:{path.name}",
        outcome="success",
        data={
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "paginas_processadas": pages,
            "paginas_totais": total_pages,
            "caracteres": len(text),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    if total_pages > pages:
        logger.warning(
            f"OCR de {path.name}: processadas {pages} de {total_pages} páginas "
            f"(teto OCR_MAX_PAGES={settings.ocr_max_pages})."
        )

    return OcrResult(
        text=text,
        provider=settings.ai_provider,
        model=settings.ai_model,
        pages=pages,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
