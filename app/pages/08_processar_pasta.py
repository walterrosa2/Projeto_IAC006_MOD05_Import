"""Tela Processar Pasta (Tarefa 3.5).

Varre DADOS_A_CLASSIFICAR, classifica, organiza em pastas, extrai dados e,
opcionalmente, dispara a IA para gerar os lançamentos pendentes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import (  # noqa: E402
    current_user,
    error_box,
    metric_card,
    page_header,
    require_company,
    setup_page,
    warning_box,
)
from core.accounting.ai_accounting_classifier import check_provider_health  # noqa: E402
from core.accounting.entry_generator import generate_entries_for_documents  # noqa: E402
from core.config import get_settings  # noqa: E402
from core.constants import MONTH_NAMES_PT  # noqa: E402
from core.pipeline import (  # noqa: E402
    build_processing_summary,
    documents_ready_for_ai,
    process_company_folder,
)
from core.scanner.file_scanner import resolve_input_folder, scan_folder  # noqa: E402

setup_page("Processar Pasta", icon="⚙️")
page_header(
    "⚙️ Processar Pasta",
    "Os arquivos são **copiados** para a estrutura de destino. A pasta de entrada permanece intacta.",
)

company = require_company()
settings = get_settings()

input_folder = resolve_input_folder(company.input_folder_path)

# --------------------------------------------------------------------------- #
# 1. Arquivos encontrados
# --------------------------------------------------------------------------- #

st.markdown("#### 1. Arquivos na pasta de entrada")
st.caption(f"Pasta: `{input_folder}`")

if not input_folder.is_dir():
    error_box(
        f"A pasta de entrada não existe: `{input_folder}`. "
        "Ajuste o cadastro da empresa ou crie a pasta."
    )
    st.page_link("pages/02_empresas.py", label="Editar empresa", icon="🏢")
    st.stop()

files = scan_folder(company.input_folder_path)

if not files:
    st.info("Nenhum arquivo encontrado na pasta de entrada.")
    if st.button("Atualizar lista"):
        st.rerun()
    st.stop()

unsupported = [f for f in files if not f.supported]
frame = pd.DataFrame(
    [
        {
            "Processar": f.supported,
            "Arquivo": f.name,
            "Extensão": f.extension or "—",
            "KB": f.size_kb,
            "Modificado": f.modified_at.strftime("%d/%m/%Y %H:%M"),
            "Suportado": "Sim" if f.supported else "Não",
        }
        for f in files
    ]
)

edited = st.data_editor(
    frame,
    use_container_width=True,
    hide_index=True,
    height=min(420, 80 + 36 * len(files)),
    column_config={
        "Processar": st.column_config.CheckboxColumn("Processar", default=True),
        "Arquivo": st.column_config.TextColumn("Arquivo", disabled=True),
        "Extensão": st.column_config.TextColumn("Ext.", disabled=True, width="small"),
        "KB": st.column_config.NumberColumn("KB", disabled=True, width="small"),
        "Modificado": st.column_config.TextColumn("Modificado", disabled=True),
        "Suportado": st.column_config.TextColumn("Suportado", disabled=True, width="small"),
    },
    key="file_selection",
)

selected_names = set(edited[edited["Processar"]]["Arquivo"].tolist())
selected_files = [f for f in files if f.name in selected_names]

if unsupported:
    warning_box(
        f"{len(unsupported)} arquivo(s) com extensão não suportada. Se marcados, "
        "serão copiados para **ERROS** com o motivo registrado."
    )

# --------------------------------------------------------------------------- #
# 2. Opções
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### 2. Opções de processamento")

columns = st.columns([1, 1, 2])
use_fallback = columns[0].checkbox(
    "Definir competência padrão",
    value=False,
    help="Aplicada apenas a documentos sem data identificável no conteúdo.",
)

fallback_year = fallback_month = None
if use_fallback:
    from datetime import date

    current_year = date.today().year
    fallback_year = columns[1].selectbox(
        "Ano", list(range(current_year + 1, current_year - 6, -1)), index=1
    )
    fallback_month = columns[2].selectbox(
        "Mês", list(range(1, 13)), format_func=lambda m: f"{m:02d} - {MONTH_NAMES_PT[m]}"
    )

healthy, health_message = check_provider_health()
generate_entries = st.checkbox(
    "Gerar lançamentos com IA após a classificação",
    value=False,
    help="Pode ser feito depois, nesta mesma tela ou na tela de validação.",
)

if generate_entries:
    if settings.ai_provider == "mock":
        warning_box(f"Provedor MOCK ativo. {health_message}")
    elif not healthy:
        error_box(health_message)

# --------------------------------------------------------------------------- #
# 3. Processar
# --------------------------------------------------------------------------- #

st.divider()
columns = st.columns([1, 3])
start = columns[0].button(
    f"Processar {len(selected_files)} arquivo(s)",
    type="primary",
    disabled=not selected_files,
)

if start:
    progress = st.progress(0.0, text="Iniciando...")
    status_area = st.empty()

    def _on_progress(index: int, total: int, result) -> None:
        progress.progress(index / total, text=f"{index}/{total} — {result.file_name}")
        status_area.caption(f"Último: **{result.file_name}** → {result.document_type} ({result.status})")

    batch = process_company_folder(
        company,
        files=selected_files,
        fallback_year=fallback_year,
        fallback_month=fallback_month,
        progress_callback=_on_progress,
    )
    progress.empty()
    status_area.empty()

    st.session_state["last_batch_summary"] = build_processing_summary(batch)
    st.session_state["last_batch_counts"] = batch.summary()

    if generate_entries and healthy:
        pending = documents_ready_for_ai(company.id)
        if pending:
            ai_progress = st.progress(0.0, text="Gerando lançamentos com IA...")

            def _on_ai_progress(index: int, total: int, result) -> None:
                ai_progress.progress(index / total, text=f"IA {index}/{total}")

            ai_results = generate_entries_for_documents(
                pending, company, progress_callback=_on_ai_progress
            )
            ai_progress.empty()
            st.session_state["last_ai_summary"] = [
                {
                    "Documento": r.document_id,
                    "Resultado": r.status_label,
                    "Lançamento": r.entry.id if r.entry else "—",
                    "Confiança": f"{r.entry.ai_confidence:.0%}"
                    if r.entry and r.entry.ai_confidence is not None
                    else "—",
                    "Observação": (r.error or r.skipped_reason or "")[:160],
                }
                for r in ai_results
            ]
        else:
            st.session_state["last_ai_summary"] = []

    st.rerun()

# --------------------------------------------------------------------------- #
# 4. Resultado
# --------------------------------------------------------------------------- #

counts = st.session_state.get("last_batch_counts")
summary = st.session_state.get("last_batch_summary")

if counts and summary:
    st.markdown("#### Resultado do último processamento")

    columns = st.columns(5)
    with columns[0]:
        metric_card("Total", counts["total"])
    with columns[1]:
        metric_card("Classificados", counts["classificados"], color="#2DD4A7")
    with columns[2]:
        metric_card("Outros", counts["outros"], color="#F5A524", hint="Sem tipo reconhecido")
    with columns[3]:
        metric_card("Duplicados", counts["duplicados"], color="#B57BEE")
    with columns[4]:
        metric_card("Erros", counts["erros"], color="#FF6B7A")

    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

    ai_summary = st.session_state.get("last_ai_summary")
    if ai_summary is not None:
        st.markdown("#### Lançamentos gerados pela IA")
        if not ai_summary:
            st.info("Nenhum documento elegível para geração de lançamento.")
        else:
            st.dataframe(pd.DataFrame(ai_summary), use_container_width=True, hide_index=True)
            st.page_link(
                "pages/10_validacao_lancamentos.py",
                label="Ir para Validação de Lançamentos",
                icon="✅",
            )

# --------------------------------------------------------------------------- #
# 5. Gerar lançamentos separadamente
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Gerar lançamentos dos documentos já classificados")

pending = documents_ready_for_ai(company.id)
if not pending:
    st.caption("Nenhum documento classificado aguardando geração de lançamento.")
else:
    st.caption(f"{len(pending)} documento(s) classificado(s) ainda sem lançamento.")
    if st.button("Gerar lançamentos com IA", disabled=not healthy):
        progress = st.progress(0.0, text="Gerando...")

        def _on_progress(index: int, total: int, result) -> None:
            progress.progress(index / total, text=f"{index}/{total}")

        results = generate_entries_for_documents(pending, company, progress_callback=_on_progress)
        progress.empty()

        generated = sum(1 for r in results if r.generated)
        skipped = sum(1 for r in results if r.skipped_reason)
        failed = sum(1 for r in results if r.error)

        st.success(
            f"{generated} lançamento(s) gerado(s), {skipped} sem lançamento, {failed} com erro. "
            f"Revisão por: {current_user()}."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Documento": r.document_id,
                        "Resultado": r.status_label,
                        "Lançamento": r.entry.id if r.entry else "—",
                        "Observação": (r.error or r.skipped_reason or "")[:160],
                    }
                    for r in results
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
