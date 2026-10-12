"""Tela de consulta de documentos processados (Tarefa 8.1 / RF17)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    competence_filter,
    document_status_options,
    document_type_options,
    format_currency,
    page_header,
    require_company,
    setup_page,
    status_badge,
    warning_box,
)
from core.documents.metadata_extractor import mask_cpf  # noqa: E402
from db.repositories import accounting_entry_repository, document_repository  # noqa: E402

setup_page("Documentos Processados", icon="🗂️")
page_header(
    "🗂️ Documentos Processados",
    "Rastreabilidade entre arquivo original, documento classificado e lançamento gerado.",
)

company = require_company()

with st.expander("Filtros", expanded=True):
    year, month = competence_filter(key_prefix="doc")

    columns = st.columns([1, 1, 2])
    document_type = columns[0].selectbox("Tipo documental", document_type_options())
    status = columns[1].selectbox("Status", document_status_options())
    file_name = columns[2].text_input("Nome do arquivo contém")

documents = document_repository.search_documents(
    company_id=company.id,
    year=year,
    month=month,
    document_type=None if document_type == "Todos" else document_type,
    status=None if status == "Todos" else status,
    file_name=file_name.strip() or None,
)

if not documents:
    st.info("Nenhum documento encontrado com esses filtros.")
    st.page_link("pages/08_processar_pasta.py", label="Processar pasta", icon="⚙️")
    st.stop()

st.caption(f"{len(documents)} documento(s).")

st.dataframe(
    pd.DataFrame(
        [
            {
                "ID": d.id,
                "Arquivo": d.original_file_name,
                "Tipo": d.document_type,
                "Status": d.processing_status,
                "Data": d.document_date.strftime("%d/%m/%Y") if d.document_date else "—",
                "Competência": f"{d.competence_month:02d}/{d.competence_year}"
                if d.competence_year and d.competence_month
                else "—",
                "Contraparte": d.counterparty or "—",
                "Valor": format_currency(d.amount),
                "Confiança": f"{d.classification_confidence:.0%}"
                if d.classification_confidence is not None
                else "—",
            }
            for d in documents
        ]
    ),
    use_container_width=True,
    hide_index=True,
    height=420,
)

st.divider()
st.markdown("#### Detalhe do documento")

selected_id = st.selectbox(
    "Documento",
    options=[d.id for d in documents],
    format_func=lambda did: next(
        f"#{d.id} — {d.original_file_name}" for d in documents if d.id == did
    ),
)
document = next(d for d in documents if d.id == selected_id)

columns = st.columns([2, 1, 1])
columns[0].markdown(f"**Arquivo original:** `{document.original_file_name}`")
columns[1].markdown(f"**Tipo:** {document.document_type}")
columns[2].markdown(status_badge(document.processing_status), unsafe_allow_html=True)

st.caption(f"Origem: `{document.original_file_path}`")
if document.stored_file_path:
    st.caption(f"Destino: `{document.stored_file_path}`")
    if not Path(document.stored_file_path).exists():
        warning_box("O arquivo não está mais no caminho de destino registrado.")

if document.classification_reason:
    st.info(f"**Classificação:** {document.classification_reason}")

if document.error_type or document.error_message:
    st.error(f"**{document.error_type or 'ERRO'}** — {document.error_message or 'sem detalhe'}")

if document.duplicate_reason:
    warning_box(
        f"{document.duplicate_reason}"
        + (
            f" (documento original: #{document.duplicate_of_id})"
            if document.duplicate_of_id
            else ""
        )
    )

tab_data, tab_text, tab_entries = st.tabs(["Dados extraídos", "Texto", "Lançamentos"])

with tab_data:
    structured = document_repository.get_structured_data(document.id)
    if structured:
        safe = dict(structured)
        for key in ("payer_cnpj_cpf", "beneficiary_cnpj_cpf"):
            if safe.get(key):
                safe[key] = mask_cpf(str(safe[key]))
        st.json(safe)
    else:
        st.caption("Nenhum dado estruturado extraído deste documento.")

with tab_text:
    record = document_repository.get_extracted_data(document.id)
    if record and record.raw_text:
        st.caption(f"Extrator: {record.extractor_name or '—'} · {len(record.raw_text)} caracteres")
        st.text_area("Texto extraído", value=record.raw_text[:8000], height=360, disabled=True)
    else:
        st.caption("Nenhum texto extraído.")

with tab_entries:
    entries = accounting_entry_repository.list_entries_by_document(document.id)
    if not entries:
        st.caption("Nenhum lançamento gerado para este documento.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": e.id,
                        "Status": e.status,
                        "Data": e.entry_date.strftime("%d/%m/%Y") if e.entry_date else "—",
                        "Débito": e.debit_account_code or "—",
                        "Crédito": e.credit_account_code or "—",
                        "Valor": format_currency(e.amount),
                        "Histórico": (e.history_complement or "")[:60],
                        "Lote": e.export_batch_id or "—",
                        "Aprovado por": e.approved_by or "—",
                    }
                    for e in entries
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.page_link(
            "pages/10_validacao_lancamentos.py", label="Ir para validação", icon="✅"
        )
