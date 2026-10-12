"""Tela de exportação para o Domínio Contábil (Tarefa 7.3 / RF19)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    competence_filter,
    current_user,
    error_box,
    format_currency,
    metric_card,
    page_header,
    require_company,
    setup_page,
    warning_box,
)
from core.dominio.dominio_exporter import export_entries, preview_export  # noqa: E402
from core.exceptions import ExportBlockedError  # noqa: E402
from db.repositories import accounting_entry_repository  # noqa: E402

setup_page("Exportação Domínio", icon="📤")
page_header(
    "📤 Exportação para o Domínio Contábil",
    "Somente lançamentos **aprovados** entram no arquivo. Pendentes, rejeitados, "
    "duplicados e com erro são bloqueados.",
)

company = require_company()
user = current_user()

st.markdown("#### Filtro de competência")
year, month = competence_filter(key_prefix="export")

rows, validation = preview_export(company.id, year=year, month=month)

pending = accounting_entry_repository.search_entries(
    company_id=company.id, status="PENDING_REVIEW", year=year, month=month, limit=1000
)

columns = st.columns(4)
with columns[0]:
    metric_card("Prontos", len(validation.valid_entries), color="#2DD4A7")
with columns[1]:
    metric_card("Bloqueados", validation.blocked_count, color="#FF6B7A")
with columns[2]:
    metric_card("Aguardando revisão", len(pending), color="#F5A524")
with columns[3]:
    total = sum(e.amount or 0.0 for e in validation.valid_entries)
    metric_card("Valor total", format_currency(total))

if pending:
    warning_box(
        f"{len(pending)} lançamento(s) ainda aguardam revisão nesta competência e "
        "não entrarão no arquivo."
    )

for warning in validation.warnings:
    warning_box(warning)

# --------------------------------------------------------------------------- #
# Bloqueios
# --------------------------------------------------------------------------- #

if validation.blocked:
    st.divider()
    st.markdown("#### Lançamentos bloqueados")
    error_box(
        f"{validation.blocked_count} lançamento(s) com pendência. "
        "Corrija na tela de validação ou exporte apenas os liberados."
    )
    st.dataframe(
        pd.DataFrame(
            [
                {"Lançamento": issue.entry_id, "Motivos": "; ".join(issue.reasons)}
                for issue in validation.blocked
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.page_link("pages/10_validacao_lancamentos.py", label="Ir para validação", icon="✅")

# --------------------------------------------------------------------------- #
# Prévia
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Prévia do arquivo")

if not rows:
    st.info(
        "Nenhum lançamento aprovado para esta competência. "
        "Aprove lançamentos antes de exportar."
    )
    st.stop()

st.caption(f"{len(rows)} linha(s) no layout Domínio.")
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)

# --------------------------------------------------------------------------- #
# Exportar
# --------------------------------------------------------------------------- #

st.divider()

allow_partial = False
if validation.blocked:
    allow_partial = st.checkbox(
        f"Exportar apenas os {len(validation.valid_entries)} liberados, ignorando os bloqueados",
        value=False,
    )

columns = st.columns([1, 3])
export_clicked = columns[0].button(
    "Gerar XLSX",
    type="primary",
    disabled=bool(validation.blocked) and not allow_partial,
)

if export_clicked:
    try:
        result = export_entries(
            company,
            year=year,
            month=month,
            exported_by=user,
            allow_partial=allow_partial,
        )
    except ExportBlockedError as exc:
        error_box(f"{exc.message} {exc.detail or ''}")
    else:
        st.success(
            f"Lote **#{result.batch_id}** gerado: {result.entry_count} lançamento(s), "
            f"total {format_currency(result.total_amount)}."
        )
        st.caption(f"Arquivo salvo em: `{result.file_path}`")

        try:
            st.download_button(
                "Baixar planilha",
                data=result.file_path.read_bytes(),
                file_name=result.file_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except OSError as exc:
            error_box(f"Arquivo gerado, mas não pôde ser lido para download: {exc}")

        st.page_link(
            "pages/12_historico_exportacoes.py",
            label="Ver histórico de exportações",
            icon="📚",
        )
