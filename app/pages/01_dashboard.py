"""Dashboard com indicadores por empresa (Tarefa 8.3 / PRD 18.1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    company_selector,
    format_currency,
    metric_card,
    page_header,
    setup_page,
)
from core.constants import DocumentStatus, EntryStatus  # noqa: E402
from db.repositories import (  # noqa: E402
    accounting_entry_repository,
    company_repository,
    document_repository,
    export_repository,
)

setup_page("Dashboard", icon="📊")
page_header("📊 Dashboard", "Situação dos documentos e lançamentos por empresa.")

companies = company_repository.list_companies()
if not companies:
    st.info("Nenhuma empresa cadastrada.")
    st.page_link("pages/02_empresas.py", label="Cadastrar empresa", icon="🏢")
    st.stop()

scope_all = st.sidebar.checkbox("Ver todas as empresas", value=False)
company = None if scope_all else company_selector(only_active=False)
company_id = company.id if company else None

document_counts = document_repository.count_documents_by_status(company_id)
entry_counts = accounting_entry_repository.count_entries_by_status(company_id)
batch_count = export_repository.count_batches(company_id)

scope_label = "todas as empresas" if scope_all else (company.name if company else "—")
st.caption(f"Escopo: **{scope_label}**")

# --------------------------------------------------------------------------- #
# Documentos
# --------------------------------------------------------------------------- #

st.markdown("#### Documentos")

pending_documents = sum(
    document_counts.get(status, 0)
    for status in (DocumentStatus.NEW, DocumentStatus.EXTRACTED, DocumentStatus.CLASSIFIED)
)
classified = sum(
    count
    for status, count in document_counts.items()
    if status
    not in (DocumentStatus.ERROR, DocumentStatus.DUPLICATE, DocumentStatus.UNKNOWN)
)

columns = st.columns(5)
with columns[0]:
    metric_card("Total", sum(document_counts.values()))
with columns[1]:
    metric_card("Aguardando lançamento", pending_documents, color="#F5A524")
with columns[2]:
    metric_card("Classificados", classified, color="#00D1FF")
with columns[3]:
    metric_card(
        "Não classificados",
        document_counts.get(DocumentStatus.UNKNOWN, 0),
        color="#F5A524",
        hint="Pasta OUTROS",
    )
with columns[4]:
    metric_card(
        "Com erro",
        document_counts.get(DocumentStatus.ERROR, 0),
        color="#FF6B7A",
        hint="Pasta ERROS",
    )

# --------------------------------------------------------------------------- #
# Lançamentos
# --------------------------------------------------------------------------- #

st.markdown("#### Lançamentos")

approved = entry_counts.get(EntryStatus.APPROVED, 0) + entry_counts.get(
    EntryStatus.CORRECTED_APPROVED, 0
)

columns = st.columns(5)
with columns[0]:
    metric_card(
        "Pendentes de revisão",
        entry_counts.get(EntryStatus.PENDING_REVIEW, 0),
        color="#F5A524",
    )
with columns[1]:
    metric_card("Aprovados", approved, color="#2DD4A7", hint="Prontos para exportar")
with columns[2]:
    metric_card("Exportados", entry_counts.get(EntryStatus.EXPORTED, 0), color="#8B8FA3")
with columns[3]:
    metric_card("Rejeitados", entry_counts.get(EntryStatus.REJECTED, 0), color="#FF6B7A")
with columns[4]:
    metric_card("Lotes exportados", batch_count, color="#B57BEE")

if entry_counts.get(EntryStatus.ERROR):
    st.warning(
        f"{entry_counts[EntryStatus.ERROR]} lançamento(s) com erro de validação "
        "(ex.: conta inexistente). Verifique na tela de validação.",
        icon="⚠️",
    )

# --------------------------------------------------------------------------- #
# Distribuições
# --------------------------------------------------------------------------- #

st.divider()
left, right = st.columns(2)

with left:
    st.markdown("##### Documentos por status")
    if document_counts:
        frame = pd.DataFrame(
            sorted(document_counts.items(), key=lambda item: -item[1]),
            columns=["Status", "Quantidade"],
        )
        st.bar_chart(frame.set_index("Status"), color="#00D1FF")
    else:
        st.caption("Sem documentos processados.")

with right:
    st.markdown("##### Lançamentos por status")
    if entry_counts:
        frame = pd.DataFrame(
            sorted(entry_counts.items(), key=lambda item: -item[1]),
            columns=["Status", "Quantidade"],
        )
        st.bar_chart(frame.set_index("Status"), color="#2DD4A7")
    else:
        st.caption("Sem lançamentos gerados.")

# --------------------------------------------------------------------------- #
# Fila de trabalho
# --------------------------------------------------------------------------- #

if company_id:
    st.divider()
    st.markdown("#### Próximas ações")

    pending_entries = accounting_entry_repository.search_entries(
        company_id=company_id, status=EntryStatus.PENDING_REVIEW, limit=10
    )

    if pending_entries:
        st.markdown(f"**{len(pending_entries)} lançamento(s) aguardando sua revisão:**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Lançamento": e.id,
                        "Data": e.entry_date.strftime("%d/%m/%Y") if e.entry_date else "—",
                        "Débito": e.debit_account_code or "—",
                        "Crédito": e.credit_account_code or "—",
                        "Valor": format_currency(e.amount),
                        "Confiança IA": f"{e.ai_confidence:.0%}"
                        if e.ai_confidence is not None
                        else "—",
                    }
                    for e in pending_entries
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.page_link("pages/10_validacao_lancamentos.py", label="Revisar agora", icon="✅")
    elif approved:
        st.success(f"{approved} lançamento(s) aprovados prontos para exportação.")
        st.page_link("pages/11_exportacao_dominio.py", label="Exportar para o Domínio", icon="📤")
    else:
        st.info("Nada pendente. Processe uma pasta para começar.")
        st.page_link("pages/08_processar_pasta.py", label="Processar pasta", icon="⚙️")
