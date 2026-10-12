"""Acesso a dados dos cadastros base: empresa, plano de contas, históricos,
centros de custo e orientações contábeis."""

from __future__ import annotations

from sqlalchemy import select

from db.database import session_scope
from db.models import (
    ChartOfAccount,
    Company,
    CompanyGuideline,
    CostCenter,
    StandardHistory,
)

# --------------------------------------------------------------------------- #
# Empresas
# --------------------------------------------------------------------------- #


def list_companies(only_active: bool = False) -> list[Company]:
    """Empresas ordenadas por nome."""
    with session_scope() as session:
        stmt = select(Company).order_by(Company.name)
        if only_active:
            stmt = stmt.where(Company.status == "Ativa")
        return list(session.scalars(stmt))


def get_company(company_id: int) -> Company | None:
    with session_scope() as session:
        return session.get(Company, company_id)


def get_company_by_name(name: str) -> Company | None:
    with session_scope() as session:
        return session.scalar(select(Company).where(Company.name == name))


def create_company(data: dict) -> Company:
    with session_scope() as session:
        company = Company(**data)
        session.add(company)
        session.flush()
        return company


def update_company(company_id: int, data: dict) -> Company | None:
    with session_scope() as session:
        company = session.get(Company, company_id)
        if company is None:
            return None
        for key, value in data.items():
            setattr(company, key, value)
        session.flush()
        return company


def delete_company(company_id: int) -> bool:
    with session_scope() as session:
        company = session.get(Company, company_id)
        if company is None:
            return False
        session.delete(company)
        return True


# --------------------------------------------------------------------------- #
# Plano de contas
# --------------------------------------------------------------------------- #


def list_accounts(company_id: int, only_active: bool = False) -> list[ChartOfAccount]:
    with session_scope() as session:
        stmt = (
            select(ChartOfAccount)
            .where(ChartOfAccount.company_id == company_id)
            .order_by(ChartOfAccount.account_code)
        )
        if only_active:
            stmt = stmt.where(ChartOfAccount.active.is_(True))
        return list(session.scalars(stmt))


def get_account(company_id: int, account_code: str) -> ChartOfAccount | None:
    """Conta pelo código, dentro da empresa."""
    with session_scope() as session:
        return session.scalar(
            select(ChartOfAccount).where(
                ChartOfAccount.company_id == company_id,
                ChartOfAccount.account_code == str(account_code).strip(),
            )
        )


def account_exists(company_id: int, account_code: str, *, must_accept_entries: bool = True) -> bool:
    """True se a conta existe, está ativa e (opcionalmente) aceita lançamento.

    Usado pelo validador contábil para impedir que a IA invente contas.
    """
    account = get_account(company_id, account_code)
    if account is None or not account.active:
        return False
    if must_accept_entries and not account.accepts_entries:
        return False
    return True


def upsert_account(company_id: int, data: dict) -> ChartOfAccount:
    """Cria a conta ou atualiza a existente com o mesmo código."""
    code = str(data["account_code"]).strip()
    with session_scope() as session:
        account = session.scalar(
            select(ChartOfAccount).where(
                ChartOfAccount.company_id == company_id,
                ChartOfAccount.account_code == code,
            )
        )
        if account is None:
            account = ChartOfAccount(company_id=company_id, **{**data, "account_code": code})
            session.add(account)
        else:
            for key, value in data.items():
                setattr(account, key, value)
        session.flush()
        return account


def bulk_upsert_accounts(company_id: int, rows: list[dict]) -> tuple[int, int]:
    """Importa plano de contas em lote. Retorna (criadas, atualizadas)."""
    created = updated = 0
    with session_scope() as session:
        for row in rows:
            code = str(row["account_code"]).strip()
            if not code:
                continue
            account = session.scalar(
                select(ChartOfAccount).where(
                    ChartOfAccount.company_id == company_id,
                    ChartOfAccount.account_code == code,
                )
            )
            if account is None:
                session.add(ChartOfAccount(company_id=company_id, **{**row, "account_code": code}))
                created += 1
            else:
                for key, value in row.items():
                    setattr(account, key, value)
                updated += 1
    return created, updated


def delete_account(account_id: int) -> bool:
    with session_scope() as session:
        account = session.get(ChartOfAccount, account_id)
        if account is None:
            return False
        session.delete(account)
        return True


# --------------------------------------------------------------------------- #
# Históricos padrão
# --------------------------------------------------------------------------- #


def list_histories(company_id: int, only_active: bool = False) -> list[StandardHistory]:
    with session_scope() as session:
        stmt = (
            select(StandardHistory)
            .where(StandardHistory.company_id == company_id)
            .order_by(StandardHistory.history_code)
        )
        if only_active:
            stmt = stmt.where(StandardHistory.active.is_(True))
        return list(session.scalars(stmt))


def history_exists(company_id: int, history_code: str) -> bool:
    if not history_code:
        return False
    with session_scope() as session:
        history = session.scalar(
            select(StandardHistory).where(
                StandardHistory.company_id == company_id,
                StandardHistory.history_code == str(history_code).strip(),
            )
        )
        return history is not None and history.active


def upsert_history(company_id: int, data: dict) -> StandardHistory:
    code = str(data["history_code"]).strip()
    with session_scope() as session:
        history = session.scalar(
            select(StandardHistory).where(
                StandardHistory.company_id == company_id,
                StandardHistory.history_code == code,
            )
        )
        if history is None:
            history = StandardHistory(company_id=company_id, **{**data, "history_code": code})
            session.add(history)
        else:
            for key, value in data.items():
                setattr(history, key, value)
        session.flush()
        return history


def delete_history(history_id: int) -> bool:
    with session_scope() as session:
        history = session.get(StandardHistory, history_id)
        if history is None:
            return False
        session.delete(history)
        return True


# --------------------------------------------------------------------------- #
# Centros de custo
# --------------------------------------------------------------------------- #


def list_cost_centers(company_id: int, only_active: bool = False) -> list[CostCenter]:
    with session_scope() as session:
        stmt = (
            select(CostCenter)
            .where(CostCenter.company_id == company_id)
            .order_by(CostCenter.cost_center_code)
        )
        if only_active:
            stmt = stmt.where(CostCenter.active.is_(True))
        return list(session.scalars(stmt))


def cost_center_exists(company_id: int, code: str) -> bool:
    if not code:
        return False
    with session_scope() as session:
        center = session.scalar(
            select(CostCenter).where(
                CostCenter.company_id == company_id,
                CostCenter.cost_center_code == str(code).strip(),
            )
        )
        return center is not None and center.active


def upsert_cost_center(company_id: int, data: dict) -> CostCenter:
    code = str(data["cost_center_code"]).strip()
    with session_scope() as session:
        center = session.scalar(
            select(CostCenter).where(
                CostCenter.company_id == company_id,
                CostCenter.cost_center_code == code,
            )
        )
        if center is None:
            center = CostCenter(company_id=company_id, **{**data, "cost_center_code": code})
            session.add(center)
        else:
            for key, value in data.items():
                setattr(center, key, value)
        session.flush()
        return center


def delete_cost_center(cost_center_id: int) -> bool:
    with session_scope() as session:
        center = session.get(CostCenter, cost_center_id)
        if center is None:
            return False
        session.delete(center)
        return True


# --------------------------------------------------------------------------- #
# Orientações contábeis
# --------------------------------------------------------------------------- #

_PRIORITY_ORDER = {"Alta": 0, "Média": 1, "Baixa": 2}


def list_guidelines(
    company_id: int,
    *,
    document_type: str | None = None,
    only_active: bool = False,
) -> list[CompanyGuideline]:
    """Orientações da empresa, ordenadas por prioridade.

    Quando `document_type` é informado, inclui as orientações gerais
    (sem tipo aplicável) e as específicas daquele tipo.
    """
    with session_scope() as session:
        stmt = select(CompanyGuideline).where(CompanyGuideline.company_id == company_id)
        if only_active:
            stmt = stmt.where(CompanyGuideline.active.is_(True))
        if document_type:
            stmt = stmt.where(
                (CompanyGuideline.applicable_document_type.is_(None))
                | (CompanyGuideline.applicable_document_type == "")
                | (CompanyGuideline.applicable_document_type == document_type)
            )
        guidelines = list(session.scalars(stmt))

    guidelines.sort(key=lambda g: (_PRIORITY_ORDER.get(g.priority, 3), g.title))
    return guidelines


def create_guideline(company_id: int, data: dict) -> CompanyGuideline:
    with session_scope() as session:
        guideline = CompanyGuideline(company_id=company_id, **data)
        session.add(guideline)
        session.flush()
        return guideline


def update_guideline(guideline_id: int, data: dict) -> CompanyGuideline | None:
    with session_scope() as session:
        guideline = session.get(CompanyGuideline, guideline_id)
        if guideline is None:
            return None
        for key, value in data.items():
            setattr(guideline, key, value)
        session.flush()
        return guideline


def delete_guideline(guideline_id: int) -> bool:
    with session_scope() as session:
        guideline = session.get(CompanyGuideline, guideline_id)
        if guideline is None:
            return False
        session.delete(guideline)
        return True
