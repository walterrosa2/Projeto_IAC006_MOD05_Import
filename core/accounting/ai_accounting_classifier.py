"""Cliente de IA para classificação contábil (Tarefa 5.2).

Provedor configurável por .env: mock | anthropic | openai | gemini.
Inclui timeout, retries com backoff exponencial e gravação de evidência
(prompt e resposta brutos, já redigidos) antes de qualquer pós-processamento.

A chave de API nunca é logada, nem entra em mensagem de erro.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from core.accounting.prompt_builder import PromptContext
from core.config import get_settings
from core.exceptions import AIProviderError, AIResponseError
from core.logging_config import get_logger, log_audit, redact

logger = get_logger()

#: Onde ficam as evidências de prompt/resposta (fora do versionamento).
EVIDENCE_DIRNAME = "ai_evidence"


@dataclass
class AIResponse:
    """Resposta da IA já desserializada, com metadados da chamada."""

    payload: dict[str, Any]
    raw_text: str
    provider: str
    model: str
    attempts: int = 1
    elapsed_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    evidence_path: str | None = None
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Parsing defensivo do retorno
# --------------------------------------------------------------------------- #

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_ai_json(raw_text: str) -> dict[str, Any]:
    """Extrai o objeto JSON da resposta, mesmo com cercas ou texto ao redor.

    Raises:
        AIResponseError: nada parseável na resposta.
    """
    if not raw_text or not raw_text.strip():
        raise AIResponseError("A IA retornou resposta vazia.")

    text = raw_text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = _JSON_FENCE.search(text)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise AIResponseError(
        "A IA não retornou um JSON válido.",
        detail=redact(text[:500]),
    )


# --------------------------------------------------------------------------- #
# Evidência
# --------------------------------------------------------------------------- #


def _save_evidence(
    *, context: PromptContext, raw_response: str, provider: str, model: str, document_id: int | None
) -> str | None:
    """Grava prompt e resposta brutos (redigidos) para auditoria."""
    try:
        settings = get_settings()
        folder = settings.log_dir / EVIDENCE_DIRNAME
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix = f"doc{document_id}" if document_id else "sem_doc"
        path = folder / f"{stamp}_{suffix}.json"
        path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "provider": provider,
                    "model": model,
                    "document_id": document_id,
                    "system_instruction": context.system_instruction,
                    "user_prompt": context.user_prompt,
                    "raw_response": redact(raw_response),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(path)
    except OSError as exc:
        logger.warning(f"Não foi possível gravar evidência de IA: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Provedores
# --------------------------------------------------------------------------- #


def _call_anthropic(context: PromptContext, settings) -> tuple[str, int | None, int | None]:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise AIProviderError("Pacote 'anthropic' não instalado.", detail=str(exc)) from exc

    client = anthropic.Anthropic(api_key=settings.api_key, timeout=settings.ai_timeout_seconds)
    message = client.messages.create(
        model=settings.ai_model,
        max_tokens=2000,
        system=context.system_instruction,
        messages=[{"role": "user", "content": context.user_prompt}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = getattr(message, "usage", None)
    return text, getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)


def _call_openai(context: PromptContext, settings) -> tuple[str, int | None, int | None]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIProviderError(
            "Pacote 'openai' não instalado. Rode: pip install openai", detail=str(exc)
        ) from exc

    client = OpenAI(api_key=settings.api_key, timeout=settings.ai_timeout_seconds)
    completion = client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {"role": "system", "content": context.system_instruction},
            {"role": "user", "content": context.user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    text = completion.choices[0].message.content or ""
    usage = getattr(completion, "usage", None)
    return text, getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)


def _call_gemini(context: PromptContext, settings) -> tuple[str, int | None, int | None]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AIProviderError(
            "Pacote 'google-genai' não instalado. Rode: pip install google-genai", detail=str(exc)
        ) from exc

    client = genai.Client(api_key=settings.api_key)
    response = client.models.generate_content(
        model=settings.ai_model,
        contents=context.user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=context.system_instruction,
            response_mime_type="application/json",
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    return (
        response.text or "",
        getattr(usage, "prompt_token_count", None),
        getattr(usage, "candidates_token_count", None),
    )


def _call_mock(context: PromptContext, settings) -> tuple[str, int | None, int | None]:
    """Provedor determinístico para desenvolvimento e testes.

    Não inventa contas: usa as duas primeiras do plano presente no prompt e
    devolve confiança baixa, deixando claro que a revisão humana é obrigatória.
    """
    accounts = re.findall(r"^([\w.\-]+) \| ", context.user_prompt, flags=re.MULTILINE)
    debit = accounts[0] if accounts else ""
    credit = accounts[1] if len(accounts) > 1 else debit

    amount_match = re.search(r'"amount":\s*([\d.]+)', context.user_prompt)
    amount = float(amount_match.group(1)) if amount_match else 0.0

    date_match = re.search(r'"document_date":\s*"(\d{4}-\d{2}-\d{2})"', context.user_prompt)
    entry_date = date_match.group(1) if date_match else date.today().isoformat()

    counterparty_match = re.search(r'"counterparty":\s*"([^"]+)"', context.user_prompt)
    counterparty = counterparty_match.group(1) if counterparty_match else "contraparte não identificada"

    payload = {
        "should_generate_entry": bool(debit and credit and amount),
        "base_document_reason": "Sugestão gerada pelo provedor MOCK, sem consulta a modelo real.",
        "entry_date": entry_date,
        "debit_account_code": debit,
        "credit_account_code": credit,
        "amount": amount,
        "history_code": None,
        "history_complement": f"Lançamento preliminar referente a {counterparty}",
        "debit_cost_center_code": None,
        "credit_cost_center_code": None,
        "confidence": 0.35,
        "justification": (
            "Provedor MOCK ativo (AI_PROVIDER=mock). Esta sugestão é um placeholder "
            "para validar a esteira e NÃO tem valor contábil."
        ),
        "warnings": [
            "Provedor MOCK: configure AI_PROVIDER e a chave de API para sugestões reais."
        ],
    }
    return json.dumps(payload, ensure_ascii=False), None, None


_PROVIDERS = {
    "mock": _call_mock,
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "gemini": _call_gemini,
}


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #


def classify_accounting(
    context: PromptContext,
    *,
    document_id: int | None = None,
    save_evidence: bool = True,
) -> AIResponse:
    """Chama a IA e devolve o JSON já parseado.

    Faz retry com backoff exponencial para falhas transitórias do provedor e
    para respostas fora do schema. Erros de configuração não são repetidos.

    Raises:
        AIProviderError: provedor indisponível ou não configurado.
        AIResponseError: resposta fora do formato JSON após todas as tentativas.
    """
    settings = get_settings()
    provider = settings.ai_provider

    caller = _PROVIDERS.get(provider)
    if caller is None:
        raise AIProviderError(
            f"Provedor de IA desconhecido: '{provider}'.",
            detail="Valores aceitos: mock, anthropic, openai, gemini.",
        )
    if provider != "mock" and not settings.api_key:
        raise AIProviderError(
            f"Chave de API do provedor '{provider}' não configurada.",
            detail="Preencha a variável correspondente no arquivo .env.",
        )

    started = time.monotonic()
    last_error: Exception | None = None
    raw_text = ""

    for attempt in range(1, settings.ai_max_retries + 1):
        try:
            raw_text, input_tokens, output_tokens = caller(context, settings)
            payload = parse_ai_json(raw_text)

            elapsed = round(time.monotonic() - started, 2)
            evidence_path = (
                _save_evidence(
                    context=context,
                    raw_response=raw_text,
                    provider=provider,
                    model=settings.ai_model,
                    document_id=document_id,
                )
                if save_evidence
                else None
            )

            log_audit(
                "llm_request",
                actor="agent",
                target=f"documento:{document_id}" if document_id else "documento:novo",
                outcome="success",
                data={
                    "provider": provider,
                    "model": settings.ai_model,
                    "attempts": attempt,
                    "elapsed_seconds": elapsed,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "approx_prompt_tokens": context.approximate_tokens,
                    "examples_used": len(context.examples_used),
                    "corrections_used": len(context.corrections_used),
                    "evidence_path": evidence_path,
                },
            )

            return AIResponse(
                payload=payload,
                raw_text=raw_text,
                provider=provider,
                model=settings.ai_model,
                attempts=attempt,
                elapsed_seconds=elapsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                evidence_path=evidence_path,
            )

        except AIResponseError as exc:
            last_error = exc
            logger.warning(f"Retorno inválido da IA (tentativa {attempt}/{settings.ai_max_retries}).")
        except Exception as exc:  # noqa: BLE001 - erro do SDK do provedor
            last_error = exc
            logger.warning(
                f"Falha na chamada de IA (tentativa {attempt}/{settings.ai_max_retries}): "
                f"{redact(type(exc).__name__ + ': ' + str(exc))}"
            )

        if attempt < settings.ai_max_retries:
            backoff = (2 ** (attempt - 1)) + random.uniform(0, 0.4)
            time.sleep(backoff)

    if save_evidence and raw_text:
        _save_evidence(
            context=context,
            raw_response=raw_text,
            provider=provider,
            model=settings.ai_model,
            document_id=document_id,
        )

    log_audit(
        "llm_request",
        actor="agent",
        target=f"documento:{document_id}" if document_id else "documento:novo",
        outcome="failure",
        data={
            "provider": provider,
            "model": settings.ai_model,
            "attempts": settings.ai_max_retries,
            "error": redact(str(last_error))[:300],
        },
    )

    if isinstance(last_error, AIResponseError):
        raise last_error
    raise AIProviderError(
        f"Não foi possível obter resposta da IA após {settings.ai_max_retries} tentativas.",
        detail=redact(str(last_error))[:300] if last_error else None,
    )


def check_provider_health() -> tuple[bool, str]:
    """Diagnóstico exibido na tela de configuração."""
    settings = get_settings()
    if settings.ai_provider == "mock":
        return True, "Provedor MOCK ativo — sugestões simuladas, sem valor contábil."
    if not settings.api_key:
        return False, f"Chave de API do provedor '{settings.ai_provider}' ausente no .env."
    if settings.ai_provider not in _PROVIDERS:
        return False, f"Provedor '{settings.ai_provider}' não suportado."
    return True, f"Provedor '{settings.ai_provider}' configurado com o modelo '{settings.ai_model}'."
