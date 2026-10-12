"""Tela de históricos padrão (Tarefa 1.4 / RF03)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import current_user, page_header, require_company, setup_page  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import company_repository  # noqa: E402

setup_page("Históricos", icon="🗒️")
page_header(
    "🗒️ Históricos Padrão",
    "Códigos de histórico usados na coluna 'Cód. Histórico' da exportação para o Domínio.",
)

company = require_company()
histories = company_repository.list_histories(company.id)

left, right = st.columns([3, 2])

with left:
    st.markdown("#### Cadastrados")
    if not histories:
        st.info("Nenhum histórico cadastrado para esta empresa.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": h.id,
                        "Código": h.history_code,
                        "Descrição": h.description,
                        "Ativo": "Sim" if h.active else "Não",
                    }
                    for h in histories
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=360,
        )

with right:
    st.markdown("#### Novo histórico")
    with st.form("form_new_history", clear_on_submit=True):
        code = st.text_input("Código *", placeholder="101")
        description = st.text_input(
            "Descrição *", placeholder="Pagamento a fornecedor conforme relatório"
        )
        active = st.checkbox("Ativo", value=True)
        submitted = st.form_submit_button("Cadastrar", type="primary")

    if submitted:
        if not code.strip() or not description.strip():
            st.error("Código e descrição são obrigatórios.")
        else:
            company_repository.upsert_history(
                company.id,
                {
                    "history_code": code.strip(),
                    "description": description.strip(),
                    "active": active,
                },
            )
            log_audit(
                "history_created",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"codigo": code.strip()},
            )
            st.success(f"Histórico {code.strip()} cadastrado.")
            st.rerun()

if histories:
    st.divider()
    st.markdown("#### Editar histórico")

    selected_id = st.selectbox(
        "Histórico",
        options=[h.id for h in histories],
        format_func=lambda hid: next(
            f"{h.history_code} — {h.description}" for h in histories if h.id == hid
        ),
        key="edit_history_select",
    )
    history = next(h for h in histories if h.id == selected_id)

    with st.form("form_edit_history"):
        columns = st.columns([1, 3, 1])
        code = columns[0].text_input("Código *", value=history.history_code)
        description = columns[1].text_input("Descrição *", value=history.description)
        active = columns[2].checkbox("Ativo", value=history.active)

        columns = st.columns([1, 1, 4])
        save = columns[0].form_submit_button("Salvar", type="primary")
        remove = columns[1].form_submit_button("Excluir")

    if save:
        if not code.strip() or not description.strip():
            st.error("Código e descrição são obrigatórios.")
        else:
            company_repository.upsert_history(
                company.id,
                {
                    "history_code": code.strip(),
                    "description": description.strip(),
                    "active": active,
                },
            )
            st.success("Histórico atualizado.")
            st.rerun()

    if remove:
        company_repository.delete_history(history.id)
        log_audit(
            "history_deleted",
            actor=current_user(),
            target=f"empresa:{company.id}",
            data={"codigo": history.history_code},
        )
        st.success("Histórico excluído.")
        st.rerun()
