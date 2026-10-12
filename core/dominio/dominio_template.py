"""Layout de importação do Domínio Contábil (PRD seção 19)."""

from __future__ import annotations

from datetime import date
from typing import Any

from core.constants import DOMINIO_COLUMNS
from db.models import AccountingEntry

#: Formato de data esperado pelo Domínio.
DATE_FORMAT = "%d/%m/%Y"

#: Marca que abre um novo lote na importação.
BATCH_START_MARK = "1"


def format_date(value: date | None) -> str:
    return value.strftime(DATE_FORMAT) if value else ""


def format_amount(value: float | None) -> float:
    """Valor numérico com 2 casas — o Domínio espera número, não texto."""
    return round(float(value), 2) if value is not None else 0.0


def entry_to_row(entry: AccountingEntry, *, is_first: bool = False) -> dict[str, Any]:
    """Converte um lançamento em uma linha do layout Domínio.

    `is_first` marca o início do lote na primeira linha do arquivo.
    """
    return {
        "Data": format_date(entry.entry_date),
        "Cód. Conta Debito": entry.debit_account_code or "",
        "Cód. Conta Credito": entry.credit_account_code or "",
        "Valor": format_amount(entry.amount),
        "Cód. Histórico": entry.history_code or "",
        "Complemento Histórico": entry.history_complement or "",
        "Inicia Lote": entry.batch_start or (BATCH_START_MARK if is_first else ""),
        "Código Matriz/Filial": entry.branch_code or "",
        "Centro de Custo Débito": entry.debit_cost_center_code or "",
        "Centro de Custo Crédito": entry.credit_cost_center_code or "",
    }


def entries_to_rows(entries: list[AccountingEntry]) -> list[dict[str, Any]]:
    """Todas as linhas do arquivo, na ordem de exportação."""
    return [entry_to_row(entry, is_first=(index == 0)) for index, entry in enumerate(entries)]


def empty_row() -> dict[str, Any]:
    """Linha em branco com todas as colunas — usada em prévias vazias."""
    return dict.fromkeys(DOMINIO_COLUMNS, "")
