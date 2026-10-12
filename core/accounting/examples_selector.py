"""Seleção dos exemplos de lançamento mais relevantes para o prompt (Tarefa 2.3).

Pontua por empresa, tipo documental, contraparte, palavras-chave e prioridade.
O limite de exemplos vem do .env para conter o tamanho do contexto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from core.config import get_settings
from core.documents.metadata_extractor import normalize
from db.models import AccountingExample
from db.repositories import example_repository

#: Pesos dos critérios (Arquitetura seção 11).
_SAME_TYPE_WEIGHT = 3.0
_COUNTERPARTY_WEIGHT = 2.5
_KEYWORD_WEIGHT = 0.8
_EXCERPT_WEIGHT = 1.0
_PRIORITY_WEIGHT = {"Alta": 1.0, "Média": 0.5, "Baixa": 0.0}

#: Similaridade mínima para considerar duas contrapartes a mesma.
_COUNTERPARTY_THRESHOLD = 0.72


@dataclass(frozen=True)
class ScoredExample:
    """Exemplo com sua pontuação e as razões da escolha."""

    example: AccountingExample
    score: float
    reasons: tuple[str, ...]


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def _split_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[;,\n]", raw)
    return [normalize(part) for part in parts if part.strip()]


def score_example(
    example: AccountingExample,
    *,
    document_type: str | None,
    counterparty: str | None,
    document_text: str,
) -> ScoredExample:
    """Pontua um exemplo contra o documento em análise."""
    score = 0.0
    reasons: list[str] = []
    normalized_text = normalize(document_text or "")

    if document_type and example.document_type == document_type:
        score += _SAME_TYPE_WEIGHT
        reasons.append("mesmo tipo documental")

    if counterparty and example.counterparty:
        ratio = _similarity(counterparty, example.counterparty)
        if ratio >= _COUNTERPARTY_THRESHOLD:
            score += _COUNTERPARTY_WEIGHT * ratio
            reasons.append(f"contraparte semelhante ({ratio:.0%})")
        elif normalize(example.counterparty) in normalized_text:
            score += _COUNTERPARTY_WEIGHT * 0.8
            reasons.append("contraparte citada no documento")

    matched_keywords = [kw for kw in _split_keywords(example.keywords) if kw and kw in normalized_text]
    if matched_keywords:
        score += _KEYWORD_WEIGHT * len(matched_keywords)
        reasons.append(f"palavras-chave: {', '.join(matched_keywords[:3])}")

    if example.document_excerpt and normalized_text:
        ratio = _similarity(example.document_excerpt[:400], document_text[:400])
        if ratio >= 0.5:
            score += _EXCERPT_WEIGHT * ratio
            reasons.append(f"trecho semelhante ({ratio:.0%})")

    score += _PRIORITY_WEIGHT.get(example.priority, 0.0)

    return ScoredExample(example=example, score=round(score, 3), reasons=tuple(reasons))


def select_relevant_examples(
    company_id: int,
    *,
    document_type: str | None,
    counterparty: str | None = None,
    document_text: str = "",
    limit: int | None = None,
) -> list[ScoredExample]:
    """Exemplos ativos da empresa, do mais ao menos relevante.

    Só entram exemplos com alguma aderência (score > 0) — um exemplo de outro
    tipo documental e outra contraparte só polui o prompt.
    """
    max_items = limit if limit is not None else get_settings().max_examples_in_prompt

    candidates = example_repository.list_examples(company_id, only_active=True)
    if not candidates:
        return []

    scored = [
        score_example(
            example,
            document_type=document_type,
            counterparty=counterparty,
            document_text=document_text,
        )
        for example in candidates
    ]
    relevant = [item for item in scored if item.score > 0]
    relevant.sort(key=lambda item: (-item.score, item.example.id))
    return relevant[:max_items]


def to_prompt_payload(scored: list[ScoredExample]) -> list[dict]:
    """Formato enviado à IA (Arquitetura seção 11)."""
    payload = []
    for item in scored:
        example = item.example
        payload.append(
            {
                "title": example.title,
                "document_type": example.document_type,
                "base_document": example.base_document,
                "counterparty": example.counterparty,
                "expected_debit": example.debit_account_code,
                "expected_credit": example.credit_account_code,
                "history_code": example.history_code,
                "history_model": example.history_complement_template,
                "debit_cost_center": example.debit_cost_center_code,
                "credit_cost_center": example.credit_cost_center_code,
                "explanation": example.accounting_explanation,
                "priority": example.priority,
            }
        )
    return payload
