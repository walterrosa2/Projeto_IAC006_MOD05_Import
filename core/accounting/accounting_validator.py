"""Validação do retorno da IA antes de virar lançamento (Tarefa 5.3).

Nenhuma sugestão chega ao banco sem passar por aqui. Erro bloqueante impede a
criação do lançamento; aviso permite criar, mas sinaliza na tela de revisão.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from core.config import get_settings
from core.documents.metadata_extractor import parse_amount_br, parse_date_br
from db.repositories import company_repository

#: Campos que a IA é obrigada a retornar.
REQUIRED_FIELDS: tuple[str, ...] = (
    "should_generate_entry",
    "base_document_reason",
    "entry_date",
    "debit_account_code",
    "credit_account_code",
    "amount",
    "history_complement",
    "confidence",
    "justification",
)


@dataclass
class ValidationResult:
    """Resultado da validação, com o payload já normalizado."""

    is_valid: bool
    should_generate_entry: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    @property
    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append("Erros: " + "; ".join(self.errors))
        if self.warnings:
            parts.append("Avisos: " + "; ".join(self.warnings))
        return " | ".join(parts) or "Sem pendências."


def _coerce_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if not raw:
        return None
    text = str(raw).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return parse_date_br(text)


def _coerce_amount(raw: Any) -> float | None:
    value = parse_amount_br(raw) if not isinstance(raw, (int, float)) else float(raw)
    return value


def _clean_optional(raw: Any) -> str | None:
    """Normaliza campos opcionais: '', 'null' e 'None' viram None."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"null", "none", "n/a", "-"}:
        return None
    return text


def validate_ai_payload(
    payload: dict[str, Any],
    *,
    company_id: int,
    document_amount: float | None = None,
    min_confidence: float | None = None,
) -> ValidationResult:
    """Valida schema, contas, histórico, centros de custo, data e valor.

    Args:
        document_amount: valor extraído do documento; divergência grande em
            relação ao valor sugerido pela IA vira aviso.
    """
    settings = get_settings()
    threshold = min_confidence if min_confidence is not None else settings.min_accounting_confidence

    result = ValidationResult(is_valid=True, should_generate_entry=False)

    if not isinstance(payload, dict):
        result.add_error("Retorno da IA não é um objeto JSON.")
        return result

    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in payload]
    if missing:
        result.add_error(f"Campos obrigatórios ausentes no JSON da IA: {', '.join(missing)}.")

    should_generate = bool(payload.get("should_generate_entry"))
    result.should_generate_entry = should_generate

    base_reason = _clean_optional(payload.get("base_document_reason"))
    justification = _clean_optional(payload.get("justification"))

    # IA indicou que não há lançamento: nada mais a validar.
    if not should_generate:
        result.normalized = {
            "should_generate_entry": False,
            "base_document_reason": base_reason,
            "justification": justification,
            "warnings": list(payload.get("warnings") or []),
        }
        result.add_warning(
            "A IA indicou que este documento não deve gerar lançamento: "
            f"{base_reason or justification or 'sem motivo informado'}."
        )
        return result

    # --- Contas -----------------------------------------------------------
    debit = _clean_optional(payload.get("debit_account_code"))
    credit = _clean_optional(payload.get("credit_account_code"))

    if not debit:
        result.add_error("Conta débito não informada pela IA.")
    elif not company_repository.account_exists(company_id, debit):
        result.add_error(
            f"Conta débito '{debit}' não existe, está inativa ou não aceita lançamento "
            "no plano de contas da empresa."
        )

    if not credit:
        result.add_error("Conta crédito não informada pela IA.")
    elif not company_repository.account_exists(company_id, credit):
        result.add_error(
            f"Conta crédito '{credit}' não existe, está inativa ou não aceita lançamento "
            "no plano de contas da empresa."
        )

    if debit and credit and debit == credit:
        result.add_error(f"Conta débito e crédito são iguais ('{debit}').")

    # --- Valor ------------------------------------------------------------
    amount = _coerce_amount(payload.get("amount"))
    if amount is None:
        result.add_error("Valor do lançamento ausente ou não numérico.")
    elif amount <= 0:
        result.add_error(f"Valor do lançamento deve ser positivo (recebido: {amount}).")
    elif document_amount is not None and document_amount > 0:
        divergence = abs(amount - document_amount)
        if divergence > 0.01:
            result.add_warning(
                f"Valor sugerido ({amount:.2f}) difere do valor extraído do documento "
                f"({document_amount:.2f})."
            )

    # --- Data -------------------------------------------------------------
    entry_date = _coerce_date(payload.get("entry_date"))
    if entry_date is None:
        result.add_error("Data do lançamento ausente ou em formato inválido.")
    elif entry_date > date.today():
        result.add_warning(f"Data do lançamento ({entry_date.isoformat()}) é futura.")

    # --- Histórico --------------------------------------------------------
    history_code = _clean_optional(payload.get("history_code"))
    if history_code and not company_repository.history_exists(company_id, history_code):
        result.add_warning(
            f"Código de histórico '{history_code}' não cadastrado para a empresa; "
            "foi descartado."
        )
        history_code = None

    history_complement = _clean_optional(payload.get("history_complement"))
    if not history_complement:
        result.add_error("Complemento de histórico não informado.")

    # --- Centros de custo -------------------------------------------------
    debit_cc = _clean_optional(payload.get("debit_cost_center_code"))
    if debit_cc and not company_repository.cost_center_exists(company_id, debit_cc):
        result.add_warning(f"Centro de custo débito '{debit_cc}' não cadastrado; foi descartado.")
        debit_cc = None

    credit_cc = _clean_optional(payload.get("credit_cost_center_code"))
    if credit_cc and not company_repository.cost_center_exists(company_id, credit_cc):
        result.add_warning(f"Centro de custo crédito '{credit_cc}' não cadastrado; foi descartado.")
        credit_cc = None

    # --- Confiança --------------------------------------------------------
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
        result.add_warning("Confiança da IA ausente ou inválida; assumida como 0.")
    confidence = max(0.0, min(confidence, 1.0))
    if confidence < threshold:
        result.add_warning(
            f"Confiança da IA ({confidence:.2f}) abaixo do mínimo configurado ({threshold:.2f}). "
            "Revise com atenção."
        )

    # --- Avisos da própria IA ---------------------------------------------
    for warning in payload.get("warnings") or []:
        text = _clean_optional(warning)
        if text:
            result.add_warning(f"IA: {text}")

    result.normalized = {
        "should_generate_entry": True,
        "base_document_reason": base_reason,
        "entry_date": entry_date,
        "debit_account_code": debit,
        "credit_account_code": credit,
        "amount": amount,
        "history_code": history_code,
        "history_complement": history_complement,
        "debit_cost_center_code": debit_cc,
        "credit_cost_center_code": credit_cc,
        "confidence": confidence,
        "justification": justification,
    }
    return result


def validate_manual_entry(data: dict[str, Any], *, company_id: int) -> ValidationResult:
    """Valida um lançamento editado à mão na tela de revisão.

    Mesmas regras de conta/valor/data da validação da IA — o contador também
    não pode aprovar conta inexistente (PRD seção 21).
    """
    payload = {
        "should_generate_entry": True,
        "base_document_reason": data.get("base_document_reason") or "Lançamento revisado manualmente.",
        "justification": data.get("justification") or "Revisão humana.",
        "confidence": data.get("confidence") or 1.0,
        "warnings": [],
        **data,
    }
    return validate_ai_payload(payload, company_id=company_id, min_confidence=0.0)
