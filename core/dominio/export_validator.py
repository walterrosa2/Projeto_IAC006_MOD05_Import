"""Validação pré-exportação (Tarefa 7.2).

Bloqueia o lote quando algum lançamento está incompleto ou fora dos status
exportáveis. A regra é dura: nada pendente, rejeitado, duplicado ou com erro
chega ao arquivo do Domínio (RNF03).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.constants import EXPORTABLE_ENTRY_STATUSES
from db.models import AccountingEntry
from db.repositories import company_repository


@dataclass
class EntryExportIssue:
    """Problema encontrado em um lançamento do lote."""

    entry_id: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class ExportValidationResult:
    """Resultado da validação do lote inteiro."""

    valid_entries: list[AccountingEntry] = field(default_factory=list)
    blocked: list[EntryExportIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.blocked and bool(self.valid_entries)

    @property
    def blocked_count(self) -> int:
        return len(self.blocked)

    def summary(self) -> str:
        if self.is_valid:
            return f"{len(self.valid_entries)} lançamento(s) prontos para exportação."
        if not self.valid_entries and not self.blocked:
            return "Nenhum lançamento aprovado no filtro selecionado."
        return (
            f"{len(self.valid_entries)} liberado(s), {self.blocked_count} bloqueado(s). "
            "Corrija os bloqueios antes de exportar."
        )


def validate_entry_for_export(entry: AccountingEntry) -> list[str]:
    """Motivos que impedem a exportação de um lançamento. Lista vazia = liberado."""
    reasons: list[str] = []

    if entry.status not in EXPORTABLE_ENTRY_STATUSES:
        reasons.append(f"Status '{entry.status}' não é exportável (exige aprovação).")

    if entry.entry_date is None:
        reasons.append("Data do lançamento ausente.")
    if not entry.debit_account_code:
        reasons.append("Conta débito ausente.")
    if not entry.credit_account_code:
        reasons.append("Conta crédito ausente.")
    if entry.debit_account_code and entry.debit_account_code == entry.credit_account_code:
        reasons.append("Conta débito e crédito são iguais.")
    if entry.amount is None:
        reasons.append("Valor ausente.")
    elif entry.amount <= 0:
        reasons.append(f"Valor inválido ({entry.amount}).")
    if not (entry.history_complement or "").strip():
        reasons.append("Complemento de histórico ausente.")

    return reasons


def validate_export_batch(
    entries: list[AccountingEntry], *, company_id: int, check_accounts: bool = True
) -> ExportValidationResult:
    """Valida o lote e separa liberados de bloqueados.

    Args:
        check_accounts: revalida cada conta contra o plano de contas — protege
            contra contas desativadas depois da aprovação.
    """
    result = ExportValidationResult()

    if not entries:
        result.warnings.append("Nenhum lançamento encontrado para os filtros informados.")
        return result

    for entry in entries:
        reasons = validate_entry_for_export(entry)

        if check_accounts:
            for label, code in (
                ("débito", entry.debit_account_code),
                ("crédito", entry.credit_account_code),
            ):
                if code and not company_repository.account_exists(company_id, code):
                    reasons.append(
                        f"Conta {label} '{code}' não existe mais ou foi desativada no plano de contas."
                    )

        if reasons:
            result.blocked.append(EntryExportIssue(entry_id=entry.id, reasons=reasons))
        else:
            result.valid_entries.append(entry)

    if result.valid_entries and not any(e.branch_code for e in result.valid_entries):
        result.warnings.append(
            "Nenhum lançamento possui Código Matriz/Filial. Confirme se o Domínio exige esse campo."
        )

    return result
