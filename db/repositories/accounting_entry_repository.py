"""Acesso a dados de lançamentos contábeis e correções."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select

from core.constants import EXPORTABLE_ENTRY_STATUSES, EntryStatus
from db.database import session_scope
from db.models import AccountingEntry, EntryCorrection, ProcessedDocument

# --------------------------------------------------------------------------- #
# Lançamentos
# --------------------------------------------------------------------------- #


def create_entry(data: dict) -> AccountingEntry:
    with session_scope() as session:
        entry = AccountingEntry(**data)
        session.add(entry)
        session.flush()
        return entry


def get_entry(entry_id: int) -> AccountingEntry | None:
    with session_scope() as session:
        return session.get(AccountingEntry, entry_id)


def update_entry(entry_id: int, data: dict) -> AccountingEntry | None:
    with session_scope() as session:
        entry = session.get(AccountingEntry, entry_id)
        if entry is None:
            return None
        for key, value in data.items():
            setattr(entry, key, value)
        session.flush()
        return entry


def list_entries_by_document(document_id: int) -> list[AccountingEntry]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(AccountingEntry)
                .where(AccountingEntry.document_id == document_id)
                .order_by(AccountingEntry.id)
            )
        )


def search_entries(
    *,
    company_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    limit: int = 500,
) -> list[AccountingEntry]:
    """Consulta de lançamentos (RF18) e base da exportação."""
    with session_scope() as session:
        stmt = select(AccountingEntry)
        if company_id:
            stmt = stmt.where(AccountingEntry.company_id == company_id)
        if status:
            stmt = stmt.where(AccountingEntry.status == status)
        if statuses:
            stmt = stmt.where(AccountingEntry.status.in_(statuses))
        if year or month:
            stmt = stmt.join(
                ProcessedDocument, AccountingEntry.document_id == ProcessedDocument.id
            )
            if year:
                stmt = stmt.where(ProcessedDocument.competence_year == year)
            if month:
                stmt = stmt.where(ProcessedDocument.competence_month == month)
        if date_from:
            stmt = stmt.where(AccountingEntry.entry_date >= date_from)
        if date_to:
            stmt = stmt.where(AccountingEntry.entry_date <= date_to)
        if account_code:
            code = str(account_code).strip()
            stmt = stmt.where(
                (AccountingEntry.debit_account_code == code)
                | (AccountingEntry.credit_account_code == code)
            )
        if min_amount is not None:
            stmt = stmt.where(AccountingEntry.amount >= min_amount)
        if max_amount is not None:
            stmt = stmt.where(AccountingEntry.amount <= max_amount)
        return list(session.scalars(stmt.order_by(AccountingEntry.entry_date, AccountingEntry.id).limit(limit)))


def list_exportable_entries(
    company_id: int, year: int | None = None, month: int | None = None
) -> list[AccountingEntry]:
    """Apenas lançamentos aprovados e ainda não exportados (RNF03)."""
    return search_entries(
        company_id=company_id,
        statuses=sorted(EXPORTABLE_ENTRY_STATUSES),
        year=year,
        month=month,
        limit=10_000,
    )


def approve_entry(entry_id: int, approved_by: str, *, corrected: bool = False) -> AccountingEntry | None:
    """Aprova o lançamento. `corrected=True` quando houve edição humana."""
    status = EntryStatus.CORRECTED_APPROVED if corrected else EntryStatus.APPROVED
    return update_entry(
        entry_id,
        {"status": status, "approved_by": approved_by, "approved_at": datetime.now()},
    )


def set_entry_status(entry_id: int, status: str, *, actor: str | None = None) -> AccountingEntry | None:
    data: dict[str, Any] = {"status": status}
    if actor:
        data["approved_by"] = actor
        data["approved_at"] = datetime.now()
    return update_entry(entry_id, data)


def count_entries_by_status(company_id: int | None = None) -> dict[str, int]:
    with session_scope() as session:
        stmt = select(AccountingEntry.status, func.count(AccountingEntry.id))
        if company_id:
            stmt = stmt.where(AccountingEntry.company_id == company_id)
        return dict(session.execute(stmt.group_by(AccountingEntry.status)).all())


def entry_to_dict(entry: AccountingEntry) -> dict[str, Any]:
    """Snapshot do lançamento usado no registro de correções."""
    return {
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "debit_account_code": entry.debit_account_code,
        "credit_account_code": entry.credit_account_code,
        "amount": entry.amount,
        "history_code": entry.history_code,
        "history_complement": entry.history_complement,
        "debit_cost_center_code": entry.debit_cost_center_code,
        "credit_cost_center_code": entry.credit_cost_center_code,
    }


# --------------------------------------------------------------------------- #
# Correções
# --------------------------------------------------------------------------- #


def create_correction(
    *,
    entry_id: int,
    company_id: int,
    document_id: int | None,
    document_type: str | None,
    counterparty: str | None,
    original: dict[str, Any],
    corrected: dict[str, Any],
    corrective_guidance: str | None,
    convert_to_example: bool,
    created_by: str | None,
) -> EntryCorrection:
    """Registra a correção humana + orientação corretiva (PRD seção 15)."""
    with session_scope() as session:
        correction = EntryCorrection(
            entry_id=entry_id,
            company_id=company_id,
            document_id=document_id,
            document_type=document_type,
            counterparty=counterparty,
            original_json=json.dumps(original, ensure_ascii=False, default=str),
            corrected_json=json.dumps(corrected, ensure_ascii=False, default=str),
            corrective_guidance=corrective_guidance,
            convert_to_example=convert_to_example,
            created_by=created_by,
        )
        session.add(correction)
        session.flush()
        return correction


def list_corrections(
    company_id: int,
    *,
    document_type: str | None = None,
    pending_conversion_only: bool = False,
    limit: int = 200,
) -> list[EntryCorrection]:
    with session_scope() as session:
        stmt = select(EntryCorrection).where(EntryCorrection.company_id == company_id)
        if document_type:
            stmt = stmt.where(EntryCorrection.document_type == document_type)
        if pending_conversion_only:
            stmt = stmt.where(
                EntryCorrection.convert_to_example.is_(True),
                EntryCorrection.converted_example_id.is_(None),
            )
        return list(session.scalars(stmt.order_by(EntryCorrection.id.desc()).limit(limit)))


def mark_correction_converted(correction_id: int, example_id: int) -> None:
    with session_scope() as session:
        correction = session.get(EntryCorrection, correction_id)
        if correction is not None:
            correction.converted_example_id = example_id
