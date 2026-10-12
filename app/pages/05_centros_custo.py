"""Tela de centros de custo (Tarefa 1.5 / RF04)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import current_user, page_header, require_company, setup_page  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import company_repository  # noqa: E402

setup_page("Centros de Custo", icon="🏷️")
page_header(
    "🏷️ Centros de Custo",
    "Usados nas colunas de centro de custo débito/crédito da exportação Domínio.",
)

company = require_company()
centers = company_repository.list_cost_centers(company.id)

left, right = st.columns([3, 2])

with left:
    st.markdown("#### Cadastrados")
    if not centers:
        st.info("Nenhum centro de custo cadastrado para esta empresa.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": c.id,
                        "Código": c.cost_center_code,
                        "Descrição": c.description,
                        "Ativo": "Sim" if c.active else "Não",
                    }
                    for c in centers
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=360,
        )

with right:
    st.markdown("#### Novo centro de custo")
    with st.form("form_new_cost_center", clear_on_submit=True):
        code = st.text_input("Código *", placeholder="001")
        description = st.text_input("Descrição *", placeholder="Administrativo")
        active = st.checkbox("Ativo", value=True)
        submitted = st.form_submit_button("Cadastrar", type="primary")

    if submitted:
        if not code.strip() or not description.strip():
            st.error("Código e descrição são obrigatórios.")
        else:
            company_repository.upsert_cost_center(
                company.id,
                {
                    "cost_center_code": code.strip(),
                    "description": description.strip(),
                    "active": active,
                },
            )
            log_audit(
                "cost_center_created",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"codigo": code.strip()},
            )
            st.success(f"Centro de custo {code.strip()} cadastrado.")
            st.rerun()

if centers:
    st.divider()
    st.markdown("#### Editar centro de custo")

    selected_id = st.selectbox(
        "Centro de custo",
        options=[c.id for c in centers],
        format_func=lambda cid: next(
            f"{c.cost_center_code} — {c.description}" for c in centers if c.id == cid
        ),
        key="edit_cc_select",
    )
    center = next(c for c in centers if c.id == selected_id)

    with st.form("form_edit_cost_center"):
        columns = st.columns([1, 3, 1])
        code = columns[0].text_input("Código *", value=center.cost_center_code)
        description = columns[1].text_input("Descrição *", value=center.description)
        active = columns[2].checkbox("Ativo", value=center.active)

        columns = st.columns([1, 1, 4])
        save = columns[0].form_submit_button("Salvar", type="primary")
        remove = columns[1].form_submit_button("Excluir")

    if save:
        if not code.strip() or not description.strip():
            st.error("Código e descrição são obrigatórios.")
        else:
            company_repository.upsert_cost_center(
                company.id,
                {
                    "cost_center_code": code.strip(),
                    "description": description.strip(),
                    "active": active,
                },
            )
            st.success("Centro de custo atualizado.")
            st.rerun()

    if remove:
        company_repository.delete_cost_center(center.id)
        log_audit(
            "cost_center_deleted",
            actor=current_user(),
            target=f"empresa:{company.id}",
            data={"codigo": center.cost_center_code},
        )
        st.success("Centro de custo excluído.")
        st.rerun()
