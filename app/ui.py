"""Componentes e helpers compartilhados pelas telas Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Permite `streamlit run app/main.py` sem depender de PYTHONPATH externo.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from core.constants import (  # noqa: E402
    MONTH_NAMES_PT,
    DocumentStatus,
    DocumentType,
    EntryStatus,
)
from db.database import init_db  # noqa: E402
from db.models import Company  # noqa: E402
from db.repositories import company_repository  # noqa: E402

APP_TITLE = "Classificador Contábil"
APP_ICON = "📒"

#: Cores por status, usadas nos badges das tabelas e cabeçalhos.
_STATUS_COLORS: dict[str, str] = {
    DocumentStatus.EXTRACTED: "#00D1FF",
    DocumentStatus.ENTRY_GENERATED: "#00D1FF",
    DocumentStatus.PENDING_REVIEW: "#F5A524",
    DocumentStatus.APPROVED: "#2DD4A7",
    DocumentStatus.EXPORTED: "#8B8FA3",
    DocumentStatus.DUPLICATE: "#B57BEE",
    DocumentStatus.UNKNOWN: "#F5A524",
    DocumentStatus.ERROR: "#FF6B7A",
    DocumentStatus.REJECTED: "#FF6B7A",
    EntryStatus.CORRECTED_APPROVED: "#2DD4A7",
}

_CSS = """
<style>
  .cc-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
  }
  .cc-metric-label { font-size: 0.78rem; color: #9BA3B4; text-transform: uppercase; letter-spacing: .06em; }
  .cc-metric-value { font-size: 1.85rem; font-weight: 650; line-height: 1.15; }
  .cc-badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.74rem; font-weight: 600; letter-spacing: .02em;
  }
  .cc-hint { color: #9BA3B4; font-size: 0.86rem; }
  .cc-warn {
    border-left: 3px solid #F5A524; background: rgba(245,165,36,0.08);
    padding: 10px 14px; border-radius: 6px; margin: 8px 0;
  }
  .cc-error {
    border-left: 3px solid #FF6B7A; background: rgba(255,107,122,0.08);
    padding: 10px 14px; border-radius: 6px; margin: 8px 0;
  }
  div[data-testid="stMetricValue"] { font-size: 1.8rem; }
</style>
"""


def setup_page(title: str, *, icon: str = APP_ICON, wide: bool = True) -> None:
    """Configuração padrão de cada página. Chame como primeira linha da tela."""
    st.set_page_config(
        page_title=f"{title} · {APP_TITLE}",
        page_icon=icon,
        layout="wide" if wide else "centered",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    init_db()


def page_header(title: str, subtitle: str = "") -> None:
    """Cabeçalho da página."""
    st.markdown(f"## {title}")
    if subtitle:
        st.markdown(f"<p class='cc-hint'>{subtitle}</p>", unsafe_allow_html=True)
    st.divider()


def status_badge(status: str) -> str:
    """HTML do badge colorido de um status."""
    color = _STATUS_COLORS.get(status, "#8B8FA3")
    return (
        f"<span class='cc-badge' style='background:{color}22;color:{color};"
        f"border:1px solid {color}55'>{status}</span>"
    )


def metric_card(label: str, value: Any, *, hint: str = "", color: str = "#FFFFFF") -> None:
    """Cartão de indicador do dashboard."""
    st.markdown(
        f"""<div class='cc-card'>
              <div class='cc-metric-label'>{label}</div>
              <div class='cc-metric-value' style='color:{color}'>{value}</div>
              {f"<div class='cc-hint'>{hint}</div>" if hint else ""}
            </div>""",
        unsafe_allow_html=True,
    )


def warning_box(message: str) -> None:
    st.markdown(f"<div class='cc-warn'>⚠️ {message}</div>", unsafe_allow_html=True)


def error_box(message: str) -> None:
    st.markdown(f"<div class='cc-error'>⛔ {message}</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Seleção de empresa (compartilhada entre telas)
# --------------------------------------------------------------------------- #

_COMPANY_KEY = "selected_company_id"


def company_selector(
    *, only_active: bool = True, key: str = "company_selector", sidebar: bool = True
) -> Company | None:
    """Seletor de empresa que mantém a escolha entre as telas.

    Returns:
        A empresa selecionada, ou None quando não há empresa cadastrada.
    """
    companies = company_repository.list_companies(only_active=only_active)
    container = st.sidebar if sidebar else st

    if not companies:
        container.warning("Nenhuma empresa cadastrada.")
        container.page_link("pages/02_empresas.py", label="Cadastrar empresa", icon="🏢")
        return None

    ids = [c.id for c in companies]
    stored = st.session_state.get(_COMPANY_KEY)
    index = ids.index(stored) if stored in ids else 0

    selected_id = container.selectbox(
        "Empresa",
        options=ids,
        index=index,
        format_func=lambda cid: next(c.name for c in companies if c.id == cid),
        key=key,
    )
    st.session_state[_COMPANY_KEY] = selected_id
    return next(c for c in companies if c.id == selected_id)


def require_company(**kwargs) -> Company | None:
    """Seletor + aviso quando não há empresa. Interrompe a página se faltar."""
    company = company_selector(**kwargs)
    if company is None:
        st.info("Cadastre uma empresa para usar esta tela.")
        st.stop()
    return company


# --------------------------------------------------------------------------- #
# Filtros comuns
# --------------------------------------------------------------------------- #


def competence_filter(
    *, key_prefix: str = "comp", container=None, allow_empty: bool = True
) -> tuple[int | None, int | None]:
    """Par de seletores ano/mês. Retorna (None, None) quando 'Todos'."""
    target = container or st
    columns = target.columns(2)

    from datetime import date

    current_year = date.today().year
    years = ["Todos"] if allow_empty else []
    years += list(range(current_year + 1, current_year - 6, -1))

    year = columns[0].selectbox("Ano", years, key=f"{key_prefix}_year")
    months = ["Todos"] if allow_empty else []
    months += list(range(1, 13))
    month = columns[1].selectbox(
        "Mês",
        months,
        key=f"{key_prefix}_month",
        format_func=lambda m: m if m == "Todos" else f"{m:02d} - {MONTH_NAMES_PT[m]}",
    )

    return (
        None if year == "Todos" else int(year),
        None if month == "Todos" else int(month),
    )


def document_type_options(include_all: bool = True) -> list[str]:
    options = [t.value for t in DocumentType]
    return (["Todos"] + options) if include_all else options


def document_status_options(include_all: bool = True) -> list[str]:
    options = [s.value for s in DocumentStatus]
    return (["Todos"] + options) if include_all else options


def entry_status_options(include_all: bool = True) -> list[str]:
    options = [s.value for s in EntryStatus]
    return (["Todos"] + options) if include_all else options


def format_currency(value: float | None) -> str:
    """Valor em reais no formato brasileiro."""
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def current_user() -> str:
    """Identificação do usuário para trilha de auditoria.

    No MVP local não há login; o nome é informado na barra lateral e fica na
    sessão. É o que alimenta `approved_by` e `created_by`.
    """
    if "current_user" not in st.session_state:
        st.session_state["current_user"] = "contador"
    return st.session_state["current_user"]


def user_input_sidebar() -> str:
    """Campo de identificação do usuário na barra lateral."""
    with st.sidebar:
        st.divider()
        name = st.text_input(
            "Seu nome (trilha de auditoria)",
            value=current_user(),
            key="user_name_input",
            help="Registrado em aprovações, correções e exportações.",
        )
        st.session_state["current_user"] = name.strip() or "contador"
    return st.session_state["current_user"]
