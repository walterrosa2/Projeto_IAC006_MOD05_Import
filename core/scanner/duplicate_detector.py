"""Detecção de duplicidade por hash e por dados essenciais do fato contábil.

Duas camadas (PRD seção 8.3 / AGENTS.md):
  1. hash SHA-256 idêntico  -> mesmo arquivo reenviado;
  2. data + valor + contraparte/documento -> mesmo fato contábil em arquivo diferente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.constants import DOCUMENT_BASE_PRIORITY
from db.repositories import document_repository


@dataclass(frozen=True)
class DuplicateCheck:
    """Resultado da verificação de duplicidade."""

    is_duplicate: bool
    original_document_id: int | None = None
    reason: str | None = None
    match_type: str | None = None  # "HASH" | "DADOS_ESSENCIAIS"

    @classmethod
    def unique(cls) -> DuplicateCheck:
        return cls(is_duplicate=False)


def check_by_hash(company_id: int, file_hash: str) -> DuplicateCheck:
    """Camada 1 — mesmo arquivo já processado para a mesma empresa."""
    existing = document_repository.find_by_hash(company_id, file_hash)
    if existing is None:
        return DuplicateCheck.unique()
    return DuplicateCheck(
        is_duplicate=True,
        original_document_id=existing.id,
        match_type="HASH",
        reason=(
            f"Hash SHA-256 idêntico ao documento #{existing.id} "
            f"({existing.original_file_name})."
        ),
    )


def check_by_business_data(
    company_id: int,
    *,
    document_date: date | None,
    amount: float | None,
    counterparty: str | None,
    document_number: str | None,
    document_type: str | None,
    exclude_id: int | None = None,
) -> DuplicateCheck:
    """Camada 2 — mesmo fato contábil registrado por outro arquivo."""
    existing = document_repository.find_by_business_key(
        company_id,
        document_date=document_date,
        amount=amount,
        counterparty=counterparty,
        document_number=document_number,
        document_type=document_type,
        exclude_id=exclude_id,
    )
    if existing is None:
        return DuplicateCheck.unique()

    key = document_number or counterparty
    return DuplicateCheck(
        is_duplicate=True,
        original_document_id=existing.id,
        match_type="DADOS_ESSENCIAIS",
        reason=(
            f"Mesma data, valor e {'documento' if document_number else 'contraparte'} "
            f"({key}) do documento #{existing.id} ({existing.original_file_name})."
        ),
    )


@dataclass(frozen=True)
class BaseDocumentDecision:
    """Decisão sobre qual documento fundamenta o lançamento (PRD seção 10)."""

    should_generate_entry: bool
    reason: str
    base_document_id: int | None = None
    evidence_document_ids: tuple[int, ...] = ()


def decide_base_document(
    company_id: int,
    *,
    document_id: int,
    document_type: str,
    document_date: date | None,
    amount: float | None,
) -> BaseDocumentDecision:
    """Aplica a hierarquia de documento base.

    Quando vários documentos apontam para o mesmo fato (mesmo valor, datas
    próximas), só o de maior riqueza contábil gera lançamento; os demais ficam
    como evidência. Empate de prioridade é resolvido pelo menor id — o que
    chegou primeiro — para manter o resultado determinístico.
    """
    own_priority = DOCUMENT_BASE_PRIORITY.get(document_type, 9)

    related = document_repository.find_related_documents(
        company_id,
        document_date=document_date,
        amount=amount,
        exclude_id=document_id,
    )
    if not related:
        return BaseDocumentDecision(
            should_generate_entry=True,
            reason="Nenhum documento relacionado encontrado; este é o documento base.",
            base_document_id=document_id,
        )

    stronger = [
        doc
        for doc in related
        if (
            DOCUMENT_BASE_PRIORITY.get(doc.document_type, 9),
            doc.id,
        )
        < (own_priority, document_id)
    ]

    if stronger:
        winner = min(stronger, key=lambda d: (DOCUMENT_BASE_PRIORITY.get(d.document_type, 9), d.id))
        return BaseDocumentDecision(
            should_generate_entry=False,
            reason=(
                f"Documento #{winner.id} ({winner.document_type}) tem maior riqueza contábil "
                f"para o mesmo fato (valor {amount}, data {document_date}). "
                f"Este arquivo fica vinculado como evidência."
            ),
            base_document_id=winner.id,
            evidence_document_ids=(document_id,),
        )

    return BaseDocumentDecision(
        should_generate_entry=True,
        reason=(
            f"Este documento ({document_type}) é o de maior riqueza contábil entre "
            f"{len(related) + 1} relacionados ao mesmo fato."
        ),
        base_document_id=document_id,
        evidence_document_ids=tuple(doc.id for doc in related),
    )
