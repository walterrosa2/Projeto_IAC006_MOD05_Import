"""Tela de histórico de exportações (Tarefa 8.2 / RF20)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    format_currency,
    page_header,
    require_company,
    setup_page,
    warning_box,
)
from core.constants import MONTH_NAMES_PT  # noqa: E402
from db.repositories import export_repository  # noqa: E402

setup_page("Histórico de Exportações", icon="📚")
page_header(
    "📚 Histórico de Exportações",
    "Cada lote registra quais lançamentos foram enviados ao Domínio, quando e por quem.",
)

company = require_company()
batches = export_repository.list_batches(company.id)

if not batches:
    st.info("Nenhuma exportação realizada para esta empresa.")
    st.page_link("pages/11_exportacao_dominio.py", label="Exportar agora", icon="📤")
    st.stop()


def _period(batch) -> str:
    if batch.period_year and batch.period_month:
        return f"{batch.period_month:02d} - {MONTH_NAMES_PT[batch.period_month]}/{batch.period_year}"
    return "Completo"


st.caption(f"{len(batches)} lote(s).")
st.dataframe(
    pd.DataFrame(
        [
            {
                "Lote": b.id,
                "Competência": _period(b),
                "Lançamentos": b.entry_count,
                "Valor total": format_currency(b.total_amount),
                "Exportado em": b.exported_at.strftime("%d/%m/%Y %H:%M"),
                "Por": b.exported_by or "—",
                "Status": b.status,
            }
            for b in batches
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.markdown("#### Detalhe do lote")

selected_id = st.selectbox(
    "Lote",
    options=[b.id for b in batches],
    format_func=lambda bid: next(
        f"#{b.id} — {_period(b)} — {b.entry_count} lançamento(s)" for b in batches if b.id == bid
    ),
)
batch = next(b for b in batches if b.id == selected_id)

columns = st.columns(4)
columns[0].metric("Lançamentos", batch.entry_count)
columns[1].metric("Valor total", format_currency(batch.total_amount))
columns[2].metric("Competência", _period(batch))
columns[3].metric("Exportado por", batch.exported_by or "—")

file_path = Path(batch.file_path)
st.caption(f"Arquivo: `{file_path}`")

if file_path.exists():
    try:
        st.download_button(
            "Baixar novamente",
            data=file_path.read_bytes(),
            file_name=file_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except OSError as exc:
        warning_box(f"Arquivo existe, mas não pôde ser lido: {exc}")
else:
    warning_box(
        "O arquivo não está mais no caminho registrado. O lote e os lançamentos "
        "permanecem no histórico, mas o XLSX precisa ser gerado novamente se for necessário."
    )

st.markdown("##### Lançamentos incluídos")
entries = export_repository.list_batch_entries(batch.id)

if not entries:
    st.caption("Nenhum lançamento vinculado a este lote.")
else:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Lançamento": e.id,
                    "Data": e.entry_date.strftime("%d/%m/%Y") if e.entry_date else "—",
                    "Débito": e.debit_account_code or "—",
                    "Crédito": e.credit_account_code or "—",
                    "Valor": format_currency(e.amount),
                    "Cód. Hist.": e.history_code or "—",
                    "Complemento": (e.history_complement or "")[:70],
                    "Documento": e.document_id,
                    "Aprovado por": e.approved_by or "—",
                }
                for e in entries
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=360,
    )
