"""Acesso a dados dos exemplos de lançamento (memória operacional da IA)."""

from __future__ import annotations

from sqlalchemy import select

from db.database import session_scope
from db.models import AccountingExample


def list_examples(
    company_id: int,
    *,
    document_type: str | None = None,
    only_active: bool = False,
) -> list[AccountingExample]:
    with session_scope() as session:
        stmt = select(AccountingExample).where(AccountingExample.company_id == company_id)
        if document_type:
            stmt = stmt.where(AccountingExample.document_type == document_type)
        if only_active:
            stmt = stmt.where(AccountingExample.active.is_(True))
        return list(session.scalars(stmt.order_by(AccountingExample.id.desc())))


def get_example(example_id: int) -> AccountingExample | None:
    with session_scope() as session:
        return session.get(AccountingExample, example_id)


def create_example(company_id: int, data: dict) -> AccountingExample:
    with session_scope() as session:
        example = AccountingExample(company_id=company_id, **data)
        session.add(example)
        session.flush()
        return example


def update_example(example_id: int, data: dict) -> AccountingExample | None:
    with session_scope() as session:
        example = session.get(AccountingExample, example_id)
        if example is None:
            return None
        for key, value in data.items():
            setattr(example, key, value)
        session.flush()
        return example


def delete_example(example_id: int) -> bool:
    with session_scope() as session:
        example = session.get(AccountingExample, example_id)
        if example is None:
            return False
        session.delete(example)
        return True
