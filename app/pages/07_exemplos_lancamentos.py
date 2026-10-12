"""Tela de exemplos de lançamentos por empresa (Tarefa 2.2 / RF06).

Os exemplos são a memória operacional da IA: dizem qual documento é base e qual
lançamento o contador espera em casos semelhantes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
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
from db.repositories import company_repository, example_repository  # noqa: E402

setup_page("Exemplos de Lançamentos", icon="💡")
page_header(
    "💡 Exemplos de Lançamentos",
    "Cada exemplo ensina à IA qual documento fundamenta o lançamento e como classificá-lo. "
    "Não é treinamento do modelo — é contexto auditável, controlado pelo escritório.",
)

company = require_company()

accounts = company_repository.list_accounts(company.id, only_active=True)
usable_accounts = [a for a in accounts if a.accepts_entries]
histories = company_repository.list_histories(company.id, only_active=True)
cost_centers = company_repository.list_cost_centers(company.id, only_active=True)

if not usable_accounts:
    st.warning(
        "Esta empresa não tem contas ativas que aceitem lançamento. "
        "Cadastre o plano de contas antes de criar exemplos.",
        icon="⚠️",
    )
    st.page_link("pages/03_plano_contas.py", label="Ir para Plano de Contas", icon="📋")
    st.stop()

_account_codes = [a.account_code for a in usable_accounts]
_account_label = {a.account_code: f"{a.account_code} — {a.description}" for a in usable_accounts}

_NONE = "— nenhum —"
_history_codes = [_NONE] + [h.history_code for h in histories]
_history_label = {h.history_code: f"{h.history_code} — {h.description}" for h in histories}
_cc_codes = [_NONE] + [c.cost_center_code for c in cost_centers]
_cc_label = {c.cost_center_code: f"{c.cost_center_code} — {c.description}" for c in cost_centers}

_types = document_type_options(include_all=False)


def _account_index(code: str | None) -> int:
    return _account_codes.index(code) if code in _account_codes else 0


def _option_index(options: list[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def _example_form(key: str, example=None) -> dict | None:
    """Formulário compartilhado entre criação e edição. Retorna os dados no submit."""
    is_edit = example is not None

    with st.form(key):
        columns = st.columns([3, 1])
        title = columns[0].text_input(
            "Título do exemplo *",
            value=example.title if is_edit else "",
            placeholder="Pagamento de prestador por relatório de contas pagas",
        )
        priority = columns[1].selectbox(
            "Prioridade *",
            PRIORITIES,
            index=PRIORITIES.index(example.priority) if is_edit and example.priority in PRIORITIES else 0,
        )

        columns = st.columns(2)
        document_type = columns[0].selectbox(
            "Tipo documental *",
            _types,
            index=_types.index(example.document_type) if is_edit and example.document_type in _types else 0,
        )
        base_document = columns[1].text_input(
            "Documento base *",
            value=example.base_document if is_edit else "",
            placeholder="Relatório de contas pagas",
            help="Qual documento deve fundamentar o lançamento neste caso.",
        )

        columns = st.columns(2)
        counterparty = columns[0].text_input(
            "Fornecedor / cliente",
            value=example.counterparty or "" if is_edit else "",
            placeholder="FORNECEDOR FICTICIO SERVICOS LTDA",
        )
        keywords = columns[1].text_input(
            "Palavras-chave",
            value=example.keywords or "" if is_edit else "",
            placeholder="empreiteiro; mão de obra; construção",
            help="Separadas por ponto e vírgula. Usadas para localizar o exemplo.",
        )

        excerpt = st.text_area(
            "Trecho representativo do documento",
            value=example.document_excerpt or "" if is_edit else "",
            height=80,
            help="Um pedaço do texto típico deste documento ajuda a IA a reconhecer o caso.",
        )

        st.markdown("##### Lançamento esperado")
        columns = st.columns(2)
        debit = columns[0].selectbox(
            "Conta débito *",
            _account_codes,
            index=_account_index(example.debit_account_code if is_edit else None),
            format_func=lambda code: _account_label.get(code, code),
        )
        credit = columns[1].selectbox(
            "Conta crédito *",
            _account_codes,
            index=_account_index(example.credit_account_code if is_edit else None),
            format_func=lambda code: _account_label.get(code, code),
        )

        columns = st.columns(3)
        history_code = columns[0].selectbox(
            "Código de histórico",
            _history_codes,
            index=_option_index(_history_codes, example.history_code if is_edit else None),
            format_func=lambda code: _history_label.get(code, code),
        )
        debit_cc = columns[1].selectbox(
            "Centro de custo débito",
            _cc_codes,
            index=_option_index(_cc_codes, example.debit_cost_center_code if is_edit else None),
            format_func=lambda code: _cc_label.get(code, code),
        )
        credit_cc = columns[2].selectbox(
            "Centro de custo crédito",
            _cc_codes,
            index=_option_index(_cc_codes, example.credit_cost_center_code if is_edit else None),
            format_func=lambda code: _cc_label.get(code, code),
        )

        history_template = st.text_input(
            "Modelo de complemento de histórico *",
            value=example.history_complement_template if is_edit else "",
            placeholder="Pagamento a fornecedor conforme relatório de contas pagas: {fornecedor} - {documento}",
            help="Use marcadores como {fornecedor}, {documento}, {data} para orientar a IA.",
        )

        explanation = st.text_area(
            "Explicação contábil *",
            value=example.accounting_explanation if is_edit else "",
            height=110,
            placeholder=(
                "O relatório de contas pagas possui credor, documento, data, valor bruto, "
                "desconto e líquido, sendo mais rico que o comprovante PIX do mesmo pagamento."
            ),
        )

        active = st.checkbox(
            "Ativo (usado pela IA)", value=example.active if is_edit else True
        )

        columns = st.columns([1, 1, 4])
        save = columns[0].form_submit_button(
            "Salvar alterações" if is_edit else "Cadastrar exemplo", type="primary"
        )
        remove = columns[1].form_submit_button("Excluir") if is_edit else False

    if remove:
        example_repository.delete_example(example.id)
        log_audit(
            "example_deleted",
            actor=current_user(),
            target=f"empresa:{company.id}",
            data={"id": example.id, "titulo": example.title},
        )
        st.success("Exemplo excluído.")
        st.rerun()

    if not save:
        return None

    errors = []
    if not title.strip():
        errors.append("Título é obrigatório.")
    if not base_document.strip():
        errors.append("Documento base é obrigatório.")
    if not history_template.strip():
        errors.append("Modelo de complemento de histórico é obrigatório.")
    if not explanation.strip():
        errors.append("Explicação contábil é obrigatória.")
    if debit == credit:
        errors.append("Conta débito e crédito não podem ser iguais.")

    # Revalida contra o plano de contas — protege contra conta desativada entre
    # o carregamento da página e o submit.
    for label, code in (("débito", debit), ("crédito", credit)):
        if not company_repository.account_exists(company.id, code):
            errors.append(f"Conta {label} '{code}' não existe mais ou não aceita lançamento.")

    if errors:
        for error in errors:
            st.error(error)
        return None

    return {
        "title": title.strip(),
        "document_type": document_type,
        "base_document": base_document.strip(),
        "counterparty": counterparty.strip() or None,
        "keywords": keywords.strip() or None,
        "document_excerpt": excerpt.strip() or None,
        "debit_account_code": debit,
        "credit_account_code": credit,
        "history_code": None if history_code == _NONE else history_code,
        "history_complement_template": history_template.strip(),
        "debit_cost_center_code": None if debit_cc == _NONE else debit_cc,
        "credit_cost_center_code": None if credit_cc == _NONE else credit_cc,
        "accounting_explanation": explanation.strip(),
        "priority": priority,
        "active": active,
    }


examples = example_repository.list_examples(company.id)

tab_list, tab_new = st.tabs(["Exemplos cadastrados", "Novo exemplo"])

with tab_list:
    if not examples:
        st.info("Nenhum exemplo cadastrado. Use a aba **Novo exemplo**.")
    else:
        active_count = sum(1 for e in examples if e.active)
        st.caption(f"{len(examples)} exemplo(s), {active_count} ativo(s).")

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": e.id,
                        "Título": e.title,
                        "Tipo": e.document_type,
                        "Contraparte": e.counterparty or "—",
                        "Débito": e.debit_account_code,
                        "Crédito": e.credit_account_code,
                        "Prioridade": e.priority,
                        "Ativo": "Sim" if e.active else "Não",
                    }
                    for e in examples
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown("#### Editar exemplo")
        selected_id = st.selectbox(
            "Exemplo",
            options=[e.id for e in examples],
            format_func=lambda eid: next(f"#{e.id} — {e.title}" for e in examples if e.id == eid),
            key="edit_example_select",
        )
        example = next(e for e in examples if e.id == selected_id)

        data = _example_form(f"form_edit_example_{example.id}", example)
        if data:
            example_repository.update_example(example.id, data)
            log_audit(
                "example_updated",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"id": example.id, "titulo": data["title"]},
            )
            st.success("Exemplo atualizado.")
            st.rerun()

with tab_new:
    data = _example_form("form_new_example")
    if data:
        data["created_by"] = current_user()
        example = example_repository.create_example(company.id, data)
        log_audit(
            "example_created",
            actor=current_user(),
            target=f"empresa:{company.id}",
            data={"id": example.id, "titulo": example.title, "tipo": example.document_type},
        )
        st.success("Exemplo cadastrado.")
        st.rerun()
