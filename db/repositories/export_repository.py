"""Acesso a dados dos lotes de exportação para o Domínio."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from core.constants import EntryStatus
from db.database import session_scope
from db.models import AccountingEntry, ExportBatch, ExportBatchItem


def create_batch(
    *,
    company_id: int,
    period_year: int | None,
    period_month: int | None,
    file_path: str,
    entry_ids: list[int],
    total_amount: float,
    exported_by: str | None,
) -> ExportBatch:
    """Cria o lote, vincula os lançamentos e marca todos como EXPORTED.

    Tudo em uma transação: ou o lote inteiro é registrado, ou nada muda.
    """
    with session_scope() as session:
        batch = ExportBatch(
            company_id=company_id,
            period_year=period_year,
            period_month=period_month,
            file_path=file_path,
            entry_count=len(entry_ids),
            total_amount=total_amount,
            exported_by=exported_by,
            status="CONCLUIDO",
        )
        session.add(batch)
        session.flush()

        for entry_id in entry_ids:
            session.add(ExportBatchItem(export_batch_id=batch.id, entry_id=entry_id))
            entry = session.get(AccountingEntry, entry_id)
            if entry is not None:
                entry.status = EntryStatus.EXPORTED
                entry.export_batch_id = batch.id

        session.flush()
        return batch


def list_batches(company_id: int | None = None, limit: int = 200) -> list[ExportBatch]:
    with session_scope() as session:
        stmt = select(ExportBatch)
        if company_id:
            stmt = stmt.where(ExportBatch.company_id == company_id)
        return list(session.scalars(stmt.order_by(ExportBatch.id.desc()).limit(limit)))


def get_batch(batch_id: int) -> ExportBatch | None:
    with session_scope() as session:
        return session.get(ExportBatch, batch_id)


def list_batch_entries(batch_id: int) -> list[AccountingEntry]:
    """Lançamentos incluídos em um lote exportado."""
    with session_scope() as session:
        return list(
            session.scalars(
                select(AccountingEntry)
                .join(ExportBatchItem, ExportBatchItem.entry_id == AccountingEntry.id)
                .where(ExportBatchItem.export_batch_id == batch_id)
                .order_by(AccountingEntry.entry_date, AccountingEntry.id)
            )
        )


def count_batches(company_id: int | None = None) -> int:
    with session_scope() as session:
        stmt = select(ExportBatch)
        if company_id:
            stmt = stmt.where(ExportBatch.company_id == company_id)
        return len(list(session.scalars(stmt)))


def build_export_filename(company_name: str, year: int | None, month: int | None) -> str:
    """Nome determinístico do arquivo exportado, seguro para o filesystem."""
    safe_company = "".join(c if c.isalnum() or c in "-_" else "_" for c in company_name)[:40]
    period = f"{year:04d}-{month:02d}" if year and month else "completo"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"dominio_{safe_company}_{period}_{stamp}.xlsx"
