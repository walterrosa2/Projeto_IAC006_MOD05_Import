"""Tela de correções e aprendizado (Tarefas 6.2 e 6.3 / PRD 18.11).

Correções viram exemplos apenas após confirmação explícita do contador.
"""

from __future__ import annotations

import json
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
from core.accounting import correction_memory  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import accounting_entry_repository, company_repository  # noqa: E402

setup_page("Correções e Aprendizado", icon="🧠")
page_header(
    "🧠 Correções e Aprendizado",
    "Cada correção do contador vira contexto para as próximas sugestões da IA. "
    "As marcadas para conversão podem virar exemplos permanentes.",
)

company = require_company()
user = current_user()


def _loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


columns = st.columns([2, 2, 1])
document_type = columns[0].selectbox("Tipo documental", document_type_options())
only_pending = columns[1].checkbox(
    "Apenas marcadas para virar exemplo (ainda não convertidas)", value=False
)

corrections = accounting_entry_repository.list_corrections(
    company.id,
    document_type=None if document_type == "Todos" else document_type,
    pending_conversion_only=only_pending,
)

if not corrections:
    st.info("Nenhuma correção registrada com esses filtros.")
    st.page_link("pages/10_validacao_lancamentos.py", label="Ir para validação", icon="✅")
    st.stop()

st.caption(f"{len(corrections)} correção(ões).")

st.dataframe(
    pd.DataFrame(
        [
            {
                "ID": c.id,
                "Lançamento": c.entry_id,
                "Tipo": c.document_type or "—",
                "Contraparte": c.counterparty or "—",
                "Orientação": (c.corrective_guidance or "—")[:70],
                "Virar exemplo": "Sim" if c.convert_to_example else "Não",
                "Convertida": f"#{c.converted_example_id}" if c.converted_example_id else "—",
                "Por": c.created_by or "—",
                "Data": c.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for c in corrections
        ]
    ),
    use_container_width=True,
    hide_index=True,
    height=360,
)

st.divider()
st.markdown("#### Detalhe da correção")

selected_id = st.selectbox(
    "Correção",
    options=[c.id for c in corrections],
    format_func=lambda cid: next(
        f"#{c.id} — lançamento {c.entry_id} — {c.document_type or 'sem tipo'}"
        for c in corrections
        if c.id == cid
    ),
)
correction = next(c for c in corrections if c.id == selected_id)

original = _loads(correction.original_json)
corrected = _loads(correction.corrected_json)

left, right = st.columns(2)
with left:
    st.markdown("##### A IA sugeriu")
    st.json(original)
with right:
    st.markdown("##### O contador aprovou")
    st.json(corrected)

changed = [key for key in corrected if original.get(key) != corrected.get(key)]
if changed:
    st.caption("**Campos alterados:** " + ", ".join(changed))

if correction.corrective_guidance:
    st.info(f"**Orientação corretiva:** {correction.corrective_guidance}")
else:
    st.caption("Nenhuma orientação corretiva foi escrita nesta correção.")

# --------------------------------------------------------------------------- #
# Conversão em exemplo
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Converter em exemplo de lançamento")

if correction.converted_example_id:
    st.success(
        f"Esta correção já foi convertida no exemplo #{correction.converted_example_id}."
    )
    st.page_link("pages/07_exemplos_lancamentos.py", label="Ver exemplos", icon="💡")
    st.stop()

if not correction.convert_to_example:
    st.caption(
        "Esta correção não foi marcada como candidata a exemplo na tela de validação. "
        "Você ainda pode convertê-la manualmente abaixo."
    )

draft = correction_memory.build_example_from_correction(correction)

debit_ok = company_repository.account_exists(company.id, draft["debit_account_code"])
credit_ok = company_repository.account_exists(company.id, draft["credit_account_code"])

if not debit_ok or not credit_ok:
    st.error(
        "As contas desta correção não estão mais válidas no plano de contas. "
        "Ajuste o plano antes de converter em exemplo."
    )
    st.stop()

with st.form("form_convert_example"):
    title = st.text_input("Título do exemplo *", value=draft["title"])
    base_document = st.text_input("Documento base *", value=draft["base_document"])
    keywords = st.text_input("Palavras-chave", value=draft["keywords"] or "")
    history_template = st.text_input(
        "Modelo de complemento de histórico *", value=draft["history_complement_template"]
    )
    explanation = st.text_area(
        "Explicação contábil *", value=draft["accounting_explanation"], height=110
    )

    columns = st.columns(3)
    columns[0].text_input("Conta débito", value=draft["debit_account_code"], disabled=True)
    columns[1].text_input("Conta crédito", value=draft["credit_account_code"], disabled=True)
    columns[2].selectbox("Prioridade", ["Alta", "Média", "Baixa"], index=0)

    confirm = st.form_submit_button("Criar exemplo a partir desta correção", type="primary")

if confirm:
    if not title.strip() or not history_template.strip() or not explanation.strip():
        st.error("Título, modelo de histórico e explicação contábil são obrigatórios.")
    else:
        example_id = correction_memory.convert_correction_to_example(
            correction,
            overrides={
                "title": title.strip(),
                "base_document": base_document.strip(),
                "keywords": keywords.strip() or None,
                "history_complement_template": history_template.strip(),
                "accounting_explanation": explanation.strip(),
                "created_by": user,
            },
        )
        log_audit(
            "correction_converted_to_example",
            actor=user,
            target=f"correcao:{correction.id}",
            outcome="success",
            data={"exemplo_id": example_id},
        )
        st.success(f"Exemplo #{example_id} criado a partir da correção #{correction.id}.")
        st.rerun()
