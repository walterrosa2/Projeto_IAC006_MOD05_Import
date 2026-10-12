"""Tela de validação de lançamentos (Tarefas 6.1 e 6.2).

É aqui que a regra contábil principal se cumpre: a IA sugere, o contador aprova.
Nenhum lançamento sai daqui para exportação sem aprovação humana.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    current_user,
    error_box,
    format_currency,
    page_header,
    require_company,
    setup_page,
    status_badge,
    warning_box,
)
from core.accounting.accounting_validator import validate_manual_entry  # noqa: E402
from core.constants import EntryStatus  # noqa: E402
from core.documents.metadata_extractor import mask_cpf  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import (  # noqa: E402
    accounting_entry_repository,
    company_repository,
    document_repository,
)

setup_page("Validação de Lançamentos", icon="✅")
page_header(
    "✅ Validação de Lançamentos",
    "A IA sugere, o contador aprova. Toda alteração é registrada como memória operacional.",
)

company = require_company()
user = current_user()

accounts = [a for a in company_repository.list_accounts(company.id, only_active=True) if a.accepts_entries]
histories = company_repository.list_histories(company.id, only_active=True)
cost_centers = company_repository.list_cost_centers(company.id, only_active=True)

_account_codes = [a.account_code for a in accounts]
_account_label = {a.account_code: f"{a.account_code} — {a.description}" for a in accounts}
_NONE = "— nenhum —"
_history_codes = [_NONE] + [h.history_code for h in histories]
_history_label = {h.history_code: f"{h.history_code} — {h.description}" for h in histories}
_cc_codes = [_NONE] + [c.cost_center_code for c in cost_centers]
_cc_label = {c.cost_center_code: f"{c.cost_center_code} — {c.description}" for c in cost_centers}

if not _account_codes:
    error_box("Empresa sem contas ativas que aceitem lançamento. Cadastre o plano de contas.")
    st.page_link("pages/03_plano_contas.py", label="Plano de Contas", icon="📋")
    st.stop()

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #

columns = st.columns([2, 1, 1])
status_filter = columns[0].multiselect(
    "Status",
    [s.value for s in EntryStatus],
    default=[EntryStatus.PENDING_REVIEW.value, EntryStatus.ERROR.value],
)
page_size = columns[1].selectbox("Por página", [5, 10, 20, 50], index=1)
reload_clicked = columns[2].button("Atualizar", use_container_width=True)

if reload_clicked:
    st.rerun()

entries = accounting_entry_repository.search_entries(
    company_id=company.id,
    statuses=status_filter or None,
    limit=1000,
)

if not entries:
    st.info("Nenhum lançamento encontrado para os filtros selecionados.")
    st.page_link("pages/08_processar_pasta.py", label="Processar documentos", icon="⚙️")
    st.stop()

total_pages = (len(entries) - 1) // page_size + 1
page_number = st.number_input(
    f"Página (de {total_pages}) — {len(entries)} lançamento(s)",
    min_value=1,
    max_value=total_pages,
    value=1,
    step=1,
)
start = (page_number - 1) * page_size
visible = entries[start : start + page_size]

st.divider()


def _option_index(options: list[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def _account_index(code: str | None) -> int:
    return _account_codes.index(code) if code in _account_codes else 0


def _render_source_document(entry) -> None:
    """Mostra a origem do lançamento: arquivo, tipo e dados extraídos."""
    document = document_repository.get_document(entry.document_id)
    if document is None:
        warning_box("Documento de origem não encontrado.")
        return

    columns = st.columns([2, 1, 1])
    columns[0].markdown(f"**Arquivo:** `{document.original_file_name}`")
    columns[1].markdown(f"**Tipo:** {document.document_type}")
    columns[2].markdown(
        f"**Competência:** {document.competence_month:02d}/{document.competence_year}"
        if document.competence_year and document.competence_month
        else "**Competência:** —"
    )

    if document.stored_file_path:
        st.caption(f"Arquivo organizado em: `{document.stored_file_path}`")

    if document.duplicate_reason:
        warning_box(document.duplicate_reason)

    with st.expander("Dados extraídos do documento"):
        structured = document_repository.get_structured_data(document.id)
        if structured:
            safe = dict(structured)
            for key in ("payer_cnpj_cpf", "beneficiary_cnpj_cpf"):
                if safe.get(key):
                    safe[key] = mask_cpf(str(safe[key]))
            st.json(safe)
        else:
            st.caption("Sem dados estruturados.")

        record = document_repository.get_extracted_data(document.id)
        if record and record.raw_text:
            st.text_area(
                "Texto do documento",
                value=record.raw_text[:4000],
                height=200,
                disabled=True,
                key=f"raw_{entry.id}",
            )


def _render_ai_analysis(entry) -> None:
    """Justificativa, confiança, avisos e pendências de validação."""
    columns = st.columns([1, 3])
    confidence = entry.ai_confidence
    if confidence is not None:
        color = "#2DD4A7" if confidence >= 0.8 else "#F5A524" if confidence >= 0.6 else "#FF6B7A"
        columns[0].markdown(
            f"<div class='cc-metric-label'>Confiança da IA</div>"
            f"<div class='cc-metric-value' style='color:{color}'>{confidence:.0%}</div>",
            unsafe_allow_html=True,
        )
    if entry.ai_justification:
        columns[1].markdown(f"**Justificativa da IA:** {entry.ai_justification}")

    if entry.base_document_reason:
        st.caption(f"**Documento base:** {entry.base_document_reason}")

    if entry.validation_issues:
        try:
            for issue in json.loads(entry.validation_issues):
                error_box(issue)
        except json.JSONDecodeError:
            error_box(entry.validation_issues)

    if entry.ai_warnings:
        try:
            for warning in json.loads(entry.ai_warnings):
                warning_box(warning)
        except json.JSONDecodeError:
            warning_box(entry.ai_warnings)


for entry in visible:
    document = document_repository.get_document(entry.document_id)
    header = (
        f"#{entry.id} · {entry.entry_date.strftime('%d/%m/%Y') if entry.entry_date else 'sem data'} · "
        f"{format_currency(entry.amount)} · {document.original_file_name if document else '—'}"
    )

    with st.container(border=True):
        columns = st.columns([4, 1])
        columns[0].markdown(f"### {header}")
        columns[1].markdown(status_badge(entry.status), unsafe_allow_html=True)

        _render_source_document(entry)
        st.divider()
        _render_ai_analysis(entry)
        st.divider()

        original_snapshot = accounting_entry_repository.entry_to_dict(entry)

        with st.form(f"form_entry_{entry.id}"):
            st.markdown("##### Lançamento")

            columns = st.columns([1, 1])
            entry_date = columns[0].date_input(
                "Data *", value=entry.entry_date, format="DD/MM/YYYY", key=f"date_{entry.id}"
            )
            amount = columns[1].number_input(
                "Valor *",
                value=float(entry.amount or 0.0),
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key=f"amount_{entry.id}",
            )

            columns = st.columns(2)
            debit = columns[0].selectbox(
                "Conta débito *",
                _account_codes,
                index=_account_index(entry.debit_account_code),
                format_func=lambda code: _account_label.get(code, code),
                key=f"debit_{entry.id}",
            )
            credit = columns[1].selectbox(
                "Conta crédito *",
                _account_codes,
                index=_account_index(entry.credit_account_code),
                format_func=lambda code: _account_label.get(code, code),
                key=f"credit_{entry.id}",
            )

            columns = st.columns([1, 1, 1])
            history_code = columns[0].selectbox(
                "Cód. histórico",
                _history_codes,
                index=_option_index(_history_codes, entry.history_code),
                format_func=lambda code: _history_label.get(code, code),
                key=f"hist_{entry.id}",
            )
            debit_cc = columns[1].selectbox(
                "C. custo débito",
                _cc_codes,
                index=_option_index(_cc_codes, entry.debit_cost_center_code),
                format_func=lambda code: _cc_label.get(code, code),
                key=f"dcc_{entry.id}",
            )
            credit_cc = columns[2].selectbox(
                "C. custo crédito",
                _cc_codes,
                index=_option_index(_cc_codes, entry.credit_cost_center_code),
                format_func=lambda code: _cc_label.get(code, code),
                key=f"ccc_{entry.id}",
            )

            history_complement = st.text_input(
                "Complemento do histórico *",
                value=entry.history_complement or "",
                key=f"hcomp_{entry.id}",
            )

            st.markdown("##### Orientação para evitar este erro no futuro")
            corrective_guidance = st.text_area(
                "Preencha apenas se alterou algo acima",
                height=80,
                key=f"guidance_{entry.id}",
                placeholder=(
                    "Ex.: pagamentos a este fornecedor devem sempre debitar serviços de terceiros, "
                    "não material de consumo."
                ),
                label_visibility="collapsed",
            )
            convert_to_example = st.checkbox(
                "Converter esta correção em exemplo de lançamento",
                key=f"convert_{entry.id}",
                help="O exemplo é criado depois, com sua confirmação, na tela Correções e Aprendizado.",
            )

            columns = st.columns([1, 1, 1, 3])
            approve = columns[0].form_submit_button("Aprovar", type="primary")
            reject = columns[1].form_submit_button("Rejeitar")
            mark_duplicate = columns[2].form_submit_button("Marcar duplicado")

        # --- Ações ---------------------------------------------------------

        if approve:
            edited = {
                "entry_date": entry_date,
                "debit_account_code": debit,
                "credit_account_code": credit,
                "amount": amount,
                "history_code": None if history_code == _NONE else history_code,
                "history_complement": history_complement.strip(),
                "debit_cost_center_code": None if debit_cc == _NONE else debit_cc,
                "credit_cost_center_code": None if credit_cc == _NONE else credit_cc,
            }

            validation = validate_manual_entry(edited, company_id=company.id)
            if not validation.is_valid:
                for error in validation.errors:
                    error_box(error)
            else:
                new_snapshot = {
                    "entry_date": entry_date.isoformat() if entry_date else None,
                    "debit_account_code": debit,
                    "credit_account_code": credit,
                    "amount": amount,
                    "history_code": edited["history_code"],
                    "history_complement": edited["history_complement"],
                    "debit_cost_center_code": edited["debit_cost_center_code"],
                    "credit_cost_center_code": edited["credit_cost_center_code"],
                }
                was_corrected = new_snapshot != original_snapshot

                accounting_entry_repository.update_entry(entry.id, edited)
                accounting_entry_repository.approve_entry(entry.id, user, corrected=was_corrected)

                if was_corrected:
                    accounting_entry_repository.create_correction(
                        entry_id=entry.id,
                        company_id=company.id,
                        document_id=entry.document_id,
                        document_type=document.document_type if document else None,
                        counterparty=document.counterparty if document else None,
                        original=original_snapshot,
                        corrected=new_snapshot,
                        corrective_guidance=corrective_guidance.strip() or None,
                        convert_to_example=convert_to_example,
                        created_by=user,
                    )

                log_audit(
                    "entry_approved",
                    actor=user,
                    target=f"lancamento:{entry.id}",
                    outcome="success",
                    data={
                        "corrigido": was_corrected,
                        "debito": debit,
                        "credito": credit,
                        "valor": amount,
                        "orientacao_registrada": bool(corrective_guidance.strip()),
                    },
                )

                message = "Lançamento aprovado com correção." if was_corrected else "Lançamento aprovado."
                if corrective_guidance.strip():
                    message += " Orientação corretiva registrada."
                st.success(message)
                st.rerun()

        if reject:
            accounting_entry_repository.set_entry_status(
                entry.id, EntryStatus.REJECTED, actor=user
            )
            log_audit(
                "entry_rejected",
                actor=user,
                target=f"lancamento:{entry.id}",
                outcome="blocked",
                data={"motivo": corrective_guidance.strip() or "não informado"},
            )
            st.warning(f"Lançamento #{entry.id} rejeitado — não será exportado.")
            st.rerun()

        if mark_duplicate:
            accounting_entry_repository.set_entry_status(
                entry.id, EntryStatus.DUPLICATE, actor=user
            )
            log_audit(
                "entry_marked_duplicate",
                actor=user,
                target=f"lancamento:{entry.id}",
                outcome="blocked",
            )
            st.warning(f"Lançamento #{entry.id} marcado como duplicado — não será exportado.")
            st.rerun()
