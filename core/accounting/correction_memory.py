"""Memória de correções: transforma o que o contador corrigiu em contexto para a IA
e, quando confirmado, em exemplo de lançamento (Tarefa 6.3 / PRD seção 15).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from core.config import get_settings
from core.documents.metadata_extractor import normalize
from db.models import EntryCorrection
from db.repositories import accounting_entry_repository, example_repository

_COUNTERPARTY_THRESHOLD = 0.72


@dataclass(frozen=True)
class ScoredCorrection:
    correction: EntryCorrection
    score: float


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def select_relevant_corrections(
    company_id: int,
    *,
    document_type: str | None,
    counterparty: str | None = None,
    limit: int | None = None,
) -> list[EntryCorrection]:
    """Correções mais relevantes para o documento em análise.

    Prioriza mesmo tipo documental e contraparte semelhante; correções mais
    recentes desempatam, por refletirem a orientação atual do contador.
    """
    max_items = limit if limit is not None else get_settings().max_corrections_in_prompt

    candidates = accounting_entry_repository.list_corrections(company_id, limit=200)
    if not candidates:
        return []

    scored: list[ScoredCorrection] = []
    for correction in candidates:
        score = 0.0
        if document_type and correction.document_type == document_type:
            score += 3.0
        if counterparty and correction.counterparty:
            ratio = SequenceMatcher(
                None, normalize(counterparty), normalize(correction.counterparty)
            ).ratio()
            if ratio >= _COUNTERPARTY_THRESHOLD:
                score += 2.5 * ratio
        if correction.corrective_guidance:
            score += 1.0
        if score > 0:
            scored.append(ScoredCorrection(correction=correction, score=score))

    scored.sort(key=lambda item: (-item.score, -item.correction.id))
    return [item.correction for item in scored[:max_items]]


def to_prompt_payload(corrections: list[EntryCorrection]) -> list[dict]:
    """Formato enviado à IA — o que foi sugerido, o que o contador aprovou e por quê."""
    payload = []
    for correction in corrections:
        original = _loads(correction.original_json)
        corrected = _loads(correction.corrected_json)
        payload.append(
            {
                "document_type": correction.document_type,
                "counterparty": correction.counterparty,
                "ia_sugeriu": {
                    "debito": original.get("debit_account_code"),
                    "credito": original.get("credit_account_code"),
                    "historico": original.get("history_complement"),
                },
                "contador_aprovou": {
                    "debito": corrected.get("debit_account_code"),
                    "credito": corrected.get("credit_account_code"),
                    "historico": corrected.get("history_complement"),
                },
                "orientacao_corretiva": correction.corrective_guidance,
            }
        )
    return payload


def build_example_from_correction(correction: EntryCorrection) -> dict[str, Any]:
    """Rascunho de exemplo a partir de uma correção, para o contador revisar.

    Nada é gravado aqui: a conversão só acontece após confirmação explícita
    (AGENTS.md — "correções podem virar exemplos após confirmação").
    """
    corrected = _loads(correction.corrected_json)
    document_type = correction.document_type or "OUTRO"
    counterparty = correction.counterparty or "—"

    return {
        "title": f"Correção aprovada — {document_type} — {counterparty}"[:200],
        "document_type": document_type,
        "base_document": document_type,
        "counterparty": correction.counterparty,
        "keywords": correction.counterparty,
        "document_excerpt": None,
        "debit_account_code": corrected.get("debit_account_code") or "",
        "credit_account_code": corrected.get("credit_account_code") or "",
        "history_code": corrected.get("history_code"),
        "history_complement_template": corrected.get("history_complement") or "",
        "debit_cost_center_code": corrected.get("debit_cost_center_code"),
        "credit_cost_center_code": corrected.get("credit_cost_center_code"),
        "accounting_explanation": (
            correction.corrective_guidance
            or "Exemplo gerado a partir de correção aprovada pelo contador."
        ),
        "priority": "Alta",
        "active": True,
        "created_by": correction.created_by,
    }


def convert_correction_to_example(correction: EntryCorrection, overrides: dict | None = None) -> int:
    """Cria o exemplo a partir da correção e marca a correção como convertida.

    Returns:
        id do exemplo criado.
    """
    data = build_example_from_correction(correction)
    if overrides:
        data.update(overrides)
    example = example_repository.create_example(correction.company_id, data)
    accounting_entry_repository.mark_correction_converted(correction.id, example.id)
    return example.id
