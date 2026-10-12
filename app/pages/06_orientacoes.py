"""Tela de orientações contábeis por empresa (Tarefa 2.1 / RF05)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    current_user,
    document_type_options,
    page_header,
    require_company,
    setup_page,
)
from core.constants import PRIORITIES  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import company_repository  # noqa: E402

setup_page("Orientações", icon="📌")
page_header(
    "📌 Orientações Contábeis da Empresa",
    "Regras em linguagem natural que entram no prompt da IA. São a primeira camada "
    "de contexto — os exemplos de lançamento são a segunda.",
)

company = require_company()

_ALL_TYPES = "Todos os tipos"
_type_options = [_ALL_TYPES] + document_type_options(include_all=False)

guidelines = company_repository.list_guidelines(company.id)

tab_list, tab_new = st.tabs(["Orientações cadastradas", "Nova orientação"])

with tab_list:
    if not guidelines:
        st.info(
            "Nenhuma orientação cadastrada. Sem orientações a IA trabalha apenas com o "
            "plano de contas e os exemplos."
        )
    else:
        active_count = sum(1 for g in guidelines if g.active)
        st.caption(f"{len(guidelines)} orientação(ões), {active_count} ativa(s).")

        for guideline in guidelines:
            state = "🟢" if guideline.active else "⚪"
            scope = guideline.applicable_document_type or "todos os tipos"
            with st.expander(
                f"{state} [{guideline.priority}] {guideline.title} · {scope}", expanded=False
            ):
                with st.form(f"form_guideline_{guideline.id}"):
                    title = st.text_input("Título *", value=guideline.title)
                    text = st.text_area(
                        "Orientação *", value=guideline.guideline_text, height=160
                    )

                    columns = st.columns(3)
                    current_scope = guideline.applicable_document_type or _ALL_TYPES
                    applicable = columns[0].selectbox(
                        "Aplica-se a",
                        _type_options,
                        index=_type_options.index(current_scope)
                        if current_scope in _type_options
                        else 0,
                        key=f"scope_{guideline.id}",
                    )
                    priority = columns[1].selectbox(
                        "Prioridade *",
                        PRIORITIES,
                        index=PRIORITIES.index(guideline.priority)
                        if guideline.priority in PRIORITIES
                        else 1,
                        key=f"prio_{guideline.id}",
                    )
                    active = columns[2].checkbox(
                        "Ativa", value=guideline.active, key=f"active_{guideline.id}"
                    )

                    st.caption(
                        f"Criada por {guideline.created_by or '—'} em "
                        f"{guideline.created_at.strftime('%d/%m/%Y %H:%M')}"
                    )

                    columns = st.columns([1, 1, 4])
                    save = columns[0].form_submit_button("Salvar", type="primary")
                    remove = columns[1].form_submit_button("Excluir")

                if save:
                    if not title.strip() or not text.strip():
                        st.error("Título e orientação são obrigatórios.")
                    else:
                        company_repository.update_guideline(
                            guideline.id,
                            {
                                "title": title.strip(),
                                "guideline_text": text.strip(),
                                "applicable_document_type": None
                                if applicable == _ALL_TYPES
                                else applicable,
                                "priority": priority,
                                "active": active,
                            },
                        )
                        st.success("Orientação atualizada.")
                        st.rerun()

                if remove:
                    company_repository.delete_guideline(guideline.id)
                    log_audit(
                        "guideline_deleted",
                        actor=current_user(),
                        target=f"empresa:{company.id}",
                        data={"titulo": guideline.title},
                    )
                    st.success("Orientação excluída.")
                    st.rerun()

with tab_new:
    st.markdown("**Exemplos do que escrever aqui:**")
    st.code(
        "Pagamentos a prestadores pessoa física devem ser classificados como serviços\n"
        "tomados, exceto quando houver descrição de adiantamento.\n\n"
        "Comprovantes PIX só devem gerar lançamento se não houver relatório de contas\n"
        "pagas correspondente.\n\n"
        "Faturamento com retenção deve separar receita bruta, impostos retidos e\n"
        "valor líquido.",
        language="text",
    )

    with st.form("form_new_guideline", clear_on_submit=True):
        title = st.text_input("Título *", placeholder="Pagamentos a prestadores PF")
        text = st.text_area(
            "Orientação *",
            height=180,
            placeholder="Descreva a regra como explicaria a um assistente contábil novo.",
        )

        columns = st.columns(3)
        applicable = columns[0].selectbox("Aplica-se a", _type_options)
        priority = columns[1].selectbox("Prioridade *", PRIORITIES, index=1)
        active = columns[2].checkbox("Ativa", value=True)

        submitted = st.form_submit_button("Cadastrar orientação", type="primary")

    if submitted:
        if not title.strip() or not text.strip():
            st.error("Título e orientação são obrigatórios.")
        else:
            guideline = company_repository.create_guideline(
                company.id,
                {
                    "title": title.strip(),
                    "guideline_text": text.strip(),
                    "applicable_document_type": None if applicable == _ALL_TYPES else applicable,
                    "priority": priority,
                    "active": active,
                    "created_by": current_user(),
                },
            )
            log_audit(
                "guideline_created",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"id": guideline.id, "titulo": guideline.title},
            )
            st.success("Orientação cadastrada.")
            st.rerun()
