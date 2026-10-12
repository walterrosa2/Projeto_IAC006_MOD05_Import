"""Tela de cadastro de empresas (Tarefa 1.2 / RF01)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import re  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import current_user, page_header, setup_page, warning_box  # noqa: E402
from core.logging_config import log_audit  # noqa: E402
from core.scanner.file_scanner import (  # noqa: E402
    INPUT_FOLDER_NAME,
    ensure_input_folder,
    resolve_input_folder,
    scan_folder,
)
from db.repositories import company_repository  # noqa: E402

setup_page("Empresas", icon="🏢")
page_header(
    "🏢 Empresas",
    "Cadastro dos clientes do escritório, com as pastas de entrada e destino dos documentos.",
)


def _clean_cnpj(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) != 14:
        return raw.strip()
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _validate(data: dict, *, editing_id: int | None = None) -> list[str]:
    """Regras mínimas antes de gravar (PRD seção 11)."""
    errors: list[str] = []

    if not data["name"].strip():
        errors.append("Nome da empresa é obrigatório.")
    if not data["legal_name"].strip():
        errors.append("Razão social é obrigatória.")

    digits = re.sub(r"\D", "", data["cnpj"])
    if len(digits) != 14:
        errors.append("CNPJ deve ter 14 dígitos.")

    if not data["input_folder_path"].strip():
        errors.append("Pasta de entrada é obrigatória.")
    if not data["destination_folder_path"].strip():
        errors.append("Pasta de destino é obrigatória.")

    existing = company_repository.get_company_by_name(data["name"].strip())
    if existing and existing.id != editing_id:
        errors.append(f"Já existe uma empresa chamada '{data['name'].strip()}'.")

    return errors


def _folder_status(raw_path: str) -> tuple[bool, str]:
    """Diagnóstico da pasta informada, exibido abaixo do campo."""
    if not raw_path.strip():
        return False, "Informe o caminho."
    path = Path(raw_path.strip()).expanduser()
    if not path.exists():
        return False, f"Pasta não existe: `{path}`"
    if not path.is_dir():
        return False, f"O caminho não é uma pasta: `{path}`"
    return True, f"Pasta encontrada: `{path}`"


# --------------------------------------------------------------------------- #
# Listagem
# --------------------------------------------------------------------------- #

companies = company_repository.list_companies()

tab_list, tab_new = st.tabs(["Empresas cadastradas", "Nova empresa"])

with tab_list:
    if not companies:
        st.info("Nenhuma empresa cadastrada. Use a aba **Nova empresa**.")
    else:
        frame = pd.DataFrame(
            [
                {
                    "ID": c.id,
                    "Empresa": c.name,
                    "CNPJ": c.cnpj,
                    "Status": c.status,
                    "Responsável": c.responsible_accountant or "—",
                    "Pasta de entrada": c.input_folder_path,
                }
                for c in companies
            ]
        )
        st.dataframe(frame, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Editar empresa")

        selected_id = st.selectbox(
            "Selecione a empresa",
            options=[c.id for c in companies],
            format_func=lambda cid: next(c.name for c in companies if c.id == cid),
            key="edit_company_select",
        )
        company = next(c for c in companies if c.id == selected_id)

        with st.form("form_edit_company"):
            columns = st.columns(2)
            name = columns[0].text_input("Nome da empresa *", value=company.name)
            legal_name = columns[1].text_input("Razão social *", value=company.legal_name)

            columns = st.columns(3)
            cnpj = columns[0].text_input("CNPJ *", value=company.cnpj)
            status = columns[1].selectbox(
                "Status *", ["Ativa", "Inativa"], index=0 if company.status == "Ativa" else 1
            )
            branch_code = columns[2].text_input(
                "Código Matriz/Filial",
                value=company.branch_code or "",
                help="Preenche a coluna 'Código Matriz/Filial' na exportação do Domínio.",
            )

            input_folder = st.text_input(
                f"Pasta de entrada ({INPUT_FOLDER_NAME}) *", value=company.input_folder_path
            )
            ok, message = _folder_status(input_folder)
            st.caption(("✅ " if ok else "⚠️ ") + message)

            destination_folder = st.text_input(
                "Pasta de destino (raiz CLIENTES) *", value=company.destination_folder_path
            )
            ok, message = _folder_status(destination_folder)
            st.caption(("✅ " if ok else "⚠️ ") + message)

            accountant = st.text_input(
                "Contador responsável", value=company.responsible_accountant or ""
            )
            notes = st.text_area("Observações", value=company.notes or "", height=80)

            columns = st.columns([1, 1, 4])
            submitted = columns[0].form_submit_button("Salvar alterações", type="primary")
            delete_requested = columns[1].form_submit_button("Excluir empresa")

        if submitted:
            data = {
                "name": name.strip(),
                "legal_name": legal_name.strip(),
                "cnpj": _clean_cnpj(cnpj),
                "input_folder_path": input_folder.strip(),
                "destination_folder_path": destination_folder.strip(),
                "responsible_accountant": accountant.strip() or None,
                "notes": notes.strip() or None,
                "branch_code": branch_code.strip() or None,
                "status": status,
            }
            errors = _validate(data, editing_id=company.id)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                company_repository.update_company(company.id, data)
                log_audit(
                    "company_updated",
                    actor=current_user(),
                    target=f"empresa:{company.id}",
                    data={"nome": data["name"]},
                )
                st.success(f"Empresa '{data['name']}' atualizada.")
                st.rerun()

        if delete_requested:
            st.session_state["confirm_delete_company"] = company.id

        if st.session_state.get("confirm_delete_company") == company.id:
            warning_box(
                f"Excluir **{company.name}** remove também plano de contas, documentos "
                "processados, lançamentos e lotes de exportação desta empresa no banco. "
                "Os arquivos em disco não são apagados."
            )
            columns = st.columns([1, 1, 4])
            if columns[0].button("Confirmar exclusão", type="primary", key="confirm_del_yes"):
                company_repository.delete_company(company.id)
                log_audit(
                    "company_deleted",
                    actor=current_user(),
                    target=f"empresa:{company.id}",
                    outcome="success",
                    data={"nome": company.name},
                )
                st.session_state.pop("confirm_delete_company", None)
                st.success("Empresa excluída.")
                st.rerun()
            if columns[1].button("Cancelar", key="confirm_del_no"):
                st.session_state.pop("confirm_delete_company", None)
                st.rerun()

        st.divider()
        st.markdown("#### Pasta de entrada")
        columns = st.columns([1, 1, 3])
        if columns[0].button("Criar estrutura de entrada"):
            created = ensure_input_folder(company.input_folder_path)
            st.success(f"Pasta pronta: `{created}`")
        if columns[1].button("Listar arquivos"):
            files = scan_folder(company.input_folder_path)
            folder = resolve_input_folder(company.input_folder_path)
            if not files:
                st.info(f"Nenhum arquivo em `{folder}`.")
            else:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Arquivo": f.name,
                                "Extensão": f.extension,
                                "KB": f.size_kb,
                                "Suportado": "Sim" if f.supported else "Não",
                                "Modificado": f.modified_at.strftime("%d/%m/%Y %H:%M"),
                            }
                            for f in files
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

# --------------------------------------------------------------------------- #
# Nova empresa
# --------------------------------------------------------------------------- #

with tab_new:
    with st.form("form_new_company", clear_on_submit=False):
        columns = st.columns(2)
        name = columns[0].text_input("Nome da empresa *", placeholder="Cliente A")
        legal_name = columns[1].text_input(
            "Razão social *", placeholder="CLIENTE A COMERCIO LTDA"
        )

        columns = st.columns(3)
        cnpj = columns[0].text_input("CNPJ *", placeholder="00.000.000/0000-00")
        status = columns[1].selectbox("Status *", ["Ativa", "Inativa"])
        branch_code = columns[2].text_input("Código Matriz/Filial", placeholder="1")

        input_folder = st.text_input(
            f"Pasta de entrada ({INPUT_FOLDER_NAME}) *",
            placeholder=rf"C:\CLIENTES\Cliente A\{INPUT_FOLDER_NAME}",
            help="Onde o cliente deposita os documentos. Os arquivos são copiados, nunca movidos.",
        )
        destination_folder = st.text_input(
            "Pasta de destino (raiz CLIENTES) *",
            placeholder=r"C:\CLIENTES",
            help="Raiz onde a estrutura empresa/ano/mês/tipo será criada.",
        )

        accountant = st.text_input("Contador responsável")
        notes = st.text_area("Observações", height=80)

        create_folders = st.checkbox("Criar a pasta de entrada se não existir", value=True)
        submitted = st.form_submit_button("Cadastrar empresa", type="primary")

    if submitted:
        data = {
            "name": name.strip(),
            "legal_name": legal_name.strip(),
            "cnpj": _clean_cnpj(cnpj),
            "input_folder_path": input_folder.strip(),
            "destination_folder_path": destination_folder.strip(),
            "responsible_accountant": accountant.strip() or None,
            "notes": notes.strip() or None,
            "branch_code": branch_code.strip() or None,
            "status": status,
        }
        errors = _validate(data)
        if errors:
            for error in errors:
                st.error(error)
        else:
            company = company_repository.create_company(data)
            if create_folders:
                try:
                    ensure_input_folder(data["input_folder_path"])
                except OSError as exc:
                    st.warning(f"Empresa criada, mas a pasta de entrada não pôde ser criada: {exc}")
            log_audit(
                "company_created",
                actor=current_user(),
                target=f"empresa:{company.id}",
                data={"nome": company.name, "cnpj": company.cnpj},
            )
            st.success(f"Empresa '{company.name}' cadastrada com sucesso.")
            st.rerun()
