"""Tela de plano de contas por empresa (Tarefa 1.3 / RF02)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import current_user, page_header, require_company, setup_page  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from db.repositories import company_repository  # noqa: E402

setup_page("Plano de Contas", icon="📋")
page_header(
    "📋 Plano de Contas",
    "A IA só pode sugerir contas que existam aqui, estejam ativas e aceitem lançamento.",
)

company = require_company()

#: Nomes de coluna aceitos na importação, por campo do modelo.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "account_code": ("codigo", "código", "conta", "codigo_conta", "código conta", "account_code", "cod", "cod conta"),
    "description": ("descricao", "descrição", "nome", "titulo", "título", "description"),
    "account_type": ("tipo", "natureza", "account_type", "grupo"),
    "accepts_entries": ("aceita_lancamento", "aceita lançamento", "aceita", "analitica", "analítica", "accepts_entries"),
    "active": ("ativo", "ativa", "situacao", "situação", "active"),
}

_TRUTHY = {"1", "sim", "s", "true", "verdadeiro", "ativo", "ativa", "x", "analitica", "analítica"}
_FALSY = {"0", "nao", "não", "n", "false", "falso", "inativo", "inativa", "sintetica", "sintética"}


def _to_bool(value, default: bool = True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return default


def _map_columns(frame: pd.DataFrame) -> dict[str, str]:
    """Casa as colunas da planilha com os campos do modelo, ignorando caixa/acentos."""
    mapping: dict[str, str] = {}
    normalized = {str(col).strip().lower(): col for col in frame.columns}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
    return mapping


accounts = company_repository.list_accounts(company.id)

tab_list, tab_new, tab_import = st.tabs(["Contas cadastradas", "Nova conta", "Importar planilha"])

# --------------------------------------------------------------------------- #

with tab_list:
    if not accounts:
        st.info("Nenhuma conta cadastrada para esta empresa.")
    else:
        columns = st.columns([2, 1, 1])
        search = columns[0].text_input("Buscar por código ou descrição", key="search_account")
        only_active = columns[1].checkbox("Somente ativas", value=False)
        only_analytic = columns[2].checkbox("Somente que aceitam lançamento", value=False)

        filtered = accounts
        if search:
            term = search.strip().lower()
            filtered = [
                a for a in filtered if term in a.account_code.lower() or term in a.description.lower()
            ]
        if only_active:
            filtered = [a for a in filtered if a.active]
        if only_analytic:
            filtered = [a for a in filtered if a.accepts_entries]

        st.caption(f"{len(filtered)} de {len(accounts)} conta(s).")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": a.id,
                        "Código": a.account_code,
                        "Descrição": a.description,
                        "Tipo": a.account_type or "—",
                        "Aceita lançamento": "Sim" if a.accepts_entries else "Não",
                        "Ativa": "Sim" if a.active else "Não",
                    }
                    for a in filtered
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

        st.divider()
        st.markdown("#### Editar conta")
        selected_id = st.selectbox(
            "Conta",
            options=[a.id for a in accounts],
            format_func=lambda aid: next(
                f"{a.account_code} — {a.description}" for a in accounts if a.id == aid
            ),
            key="edit_account_select",
        )
        account = next(a for a in accounts if a.id == selected_id)

        with st.form("form_edit_account"):
            columns = st.columns([1, 2, 1])
            code = columns[0].text_input("Código *", value=account.account_code)
            description = columns[1].text_input("Descrição *", value=account.description)
            account_type = columns[2].text_input("Tipo", value=account.account_type or "")

            columns = st.columns(2)
            accepts = columns[0].checkbox("Aceita lançamento", value=account.accepts_entries)
            active = columns[1].checkbox("Ativa", value=account.active)

            columns = st.columns([1, 1, 4])
            save = columns[0].form_submit_button("Salvar", type="primary")
            remove = columns[1].form_submit_button("Excluir")

        if save:
            if not code.strip() or not description.strip():
                st.error("Código e descrição são obrigatórios.")
            else:
                company_repository.upsert_account(
                    company.id,
                    {
                        "account_code": code.strip(),
                        "description": description.strip(),
                        "account_type": account_type.strip() or None,
                        "accepts_entries": accepts,
                        "active": active,
                    },
                )
                st.success(f"Conta {code.strip()} atualizada.")
                st.rerun()

        if remove:
            company_repository.delete_account(account.id)
            log_audit(
                "account_deleted",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"conta": account.account_code},
            )
            st.success(f"Conta {account.account_code} excluída.")
            st.rerun()

# --------------------------------------------------------------------------- #

with tab_new:
    with st.form("form_new_account", clear_on_submit=True):
        columns = st.columns([1, 2, 1])
        code = columns[0].text_input("Código *", placeholder="1.1.01.001")
        description = columns[1].text_input("Descrição *", placeholder="Banco conta movimento")
        account_type = columns[2].text_input("Tipo", placeholder="Ativo circulante")

        columns = st.columns(2)
        accepts = columns[0].checkbox(
            "Aceita lançamento", value=True, help="Contas sintéticas devem ficar desmarcadas."
        )
        active = columns[1].checkbox("Ativa", value=True)

        submitted = st.form_submit_button("Cadastrar conta", type="primary")

    if submitted:
        if not code.strip() or not description.strip():
            st.error("Código e descrição são obrigatórios.")
        else:
            company_repository.upsert_account(
                company.id,
                {
                    "account_code": code.strip(),
                    "description": description.strip(),
                    "account_type": account_type.strip() or None,
                    "accepts_entries": accepts,
                    "active": active,
                },
            )
            log_audit(
                "account_created",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"conta": code.strip()},
            )
            st.success(f"Conta {code.strip()} cadastrada.")
            st.rerun()

# --------------------------------------------------------------------------- #

with tab_import:
    st.markdown(
        "Envie um **XLSX ou CSV** com o plano de contas. "
        "Colunas reconhecidas (em qualquer ordem, sem distinção de acento ou caixa):"
    )
    st.code(
        "codigo | descricao | tipo | aceita_lancamento | ativo",
        language="text",
    )
    st.caption(
        "Apenas `codigo` e `descricao` são obrigatórios. "
        "Contas já existentes são atualizadas, não duplicadas."
    )

    uploaded = st.file_uploader("Arquivo do plano de contas", type=["xlsx", "xls", "csv"])

    if uploaded is not None:
        try:
            if uploaded.name.lower().endswith(".csv"):
                frame = pd.read_csv(uploaded, sep=None, engine="python", dtype=str)
            else:
                frame = pd.read_excel(uploaded, dtype=str)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Não foi possível ler o arquivo: {exc}")
            frame = None

        if frame is not None:
            mapping = _map_columns(frame)
            missing = [f for f in ("account_code", "description") if f not in mapping]

            if missing:
                st.error(
                    "Colunas obrigatórias não encontradas: "
                    + ", ".join("código" if m == "account_code" else "descrição" for m in missing)
                    + f". Colunas do arquivo: {', '.join(str(c) for c in frame.columns)}"
                )
            else:
                st.markdown("**Prévia (10 primeiras linhas):**")
                st.dataframe(frame.head(10), use_container_width=True, hide_index=True)

                rows: list[dict] = []
                skipped = 0
                for _, raw in frame.iterrows():
                    code = str(raw.get(mapping["account_code"], "") or "").strip()
                    description = str(raw.get(mapping["description"], "") or "").strip()
                    if not code or code.lower() == "nan":
                        skipped += 1
                        continue
                    rows.append(
                        {
                            "account_code": code,
                            "description": description or code,
                            "account_type": (
                                str(raw.get(mapping["account_type"], "") or "").strip() or None
                                if "account_type" in mapping
                                else None
                            ),
                            "accepts_entries": _to_bool(
                                raw.get(mapping["accepts_entries"]) if "accepts_entries" in mapping else None
                            ),
                            "active": _to_bool(
                                raw.get(mapping["active"]) if "active" in mapping else None
                            ),
                        }
                    )

                st.info(f"{len(rows)} conta(s) prontas para importar." + (f" {skipped} linha(s) ignorada(s) por código vazio." if skipped else ""))

                if st.button("Importar plano de contas", type="primary", disabled=not rows):
                    created, updated = company_repository.bulk_upsert_accounts(company.id, rows)
                    log_audit(
                        "chart_of_accounts_imported",
                        actor=current_user(),
                        target=f"empresa:{company.id}",
                        data={"criadas": created, "atualizadas": updated, "arquivo": uploaded.name},
                    )
                    st.success(f"Importação concluída: {created} criada(s), {updated} atualizada(s).")
                    st.rerun()
