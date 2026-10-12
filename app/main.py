"""Ponto de entrada da aplicação Streamlit.

Executar com:  streamlit run app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from app.ui import APP_ICON, APP_TITLE, setup_page, user_input_sidebar  # noqa: E402
from core.accounting.ai_accounting_classifier import check_provider_health  # noqa: E402
from core.config import get_settings  # noqa: E402
from core.logging_config import setup_logging  # noqa: E402

setup_page("Início")
setup_logging()

PAGES_DIR = Path(__file__).parent / "pages"

#: (arquivo, rótulo, ícone) — a ordem define o menu lateral.
NAVIGATION: tuple[tuple[str, str, str], ...] = (
    ("01_dashboard.py", "Dashboard", "📊"),
    ("02_empresas.py", "Empresas", "🏢"),
    ("03_plano_contas.py", "Plano de Contas", "📋"),
    ("04_historicos.py", "Históricos", "🗒️"),
    ("05_centros_custo.py", "Centros de Custo", "🏷️"),
    ("06_orientacoes.py", "Orientações", "📌"),
    ("07_exemplos_lancamentos.py", "Exemplos de Lançamentos", "💡"),
    ("08_processar_pasta.py", "Processar Pasta", "⚙️"),
    ("09_documentos.py", "Documentos Processados", "🗂️"),
    ("10_validacao_lancamentos.py", "Validação de Lançamentos", "✅"),
    ("11_exportacao_dominio.py", "Exportação Domínio", "📤"),
    ("12_historico_exportacoes.py", "Histórico de Exportações", "📚"),
    ("13_correcoes.py", "Correções e Aprendizado", "🧠"),
    ("14_configuracao.py", "Configuração", "🔧"),
)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### {APP_ICON} {APP_TITLE}")
        st.caption("A IA sugere. O contador aprova.")
        st.divider()
        for file_name, label, icon in NAVIGATION:
            st.page_link(f"pages/{file_name}", label=label, icon=icon)
    user_input_sidebar()


def render_home() -> None:
    settings = get_settings()
    healthy, message = check_provider_health()

    st.markdown(f"# {APP_ICON} {APP_TITLE}")
    st.markdown(
        "Esteira contábil local: leitura da pasta do cliente, classificação documental, "
        "organização em pastas, extração de dados, sugestão de lançamento por IA, "
        "**validação humana obrigatória** e exportação para o Domínio Contábil."
    )

    if settings.ai_provider == "mock":
        st.warning(
            f"**Provedor de IA em modo MOCK.** {message} "
            "As sugestões são simuladas e não têm valor contábil. "
            "Configure `AI_PROVIDER` e a chave no arquivo `.env` para uso real.",
            icon="🧪",
        )
    elif not healthy:
        st.error(f"**IA indisponível.** {message}", icon="⛔")
    else:
        st.success(message, icon="🤖")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.markdown("#### Fluxo de trabalho")
        st.markdown(
            "1. **Empresas** — cadastre o cliente e as pastas de entrada/destino.\n"
            "2. **Plano de Contas, Históricos, Centros de Custo** — base contábil.\n"
            "3. **Orientações** e **Exemplos de Lançamentos** — memória da IA.\n"
            "4. **Processar Pasta** — classifica, organiza e extrai os documentos.\n"
            "5. **Validação de Lançamentos** — revise, corrija e aprove.\n"
            "6. **Exportação Domínio** — gera o XLSX apenas com aprovados."
        )
    with right:
        st.markdown("#### Regras que a aplicação garante")
        st.markdown(
            "- Arquivos originais são **copiados**, nunca movidos.\n"
            "- Documento não reconhecido vai para **OUTROS**.\n"
            "- Falha técnica vai para **ERROS**, com motivo registrado.\n"
            "- Duplicado vai para **DUPLICADOS** e não gera lançamento.\n"
            "- A IA só pode usar contas **existentes e ativas** no plano.\n"
            "- Só lançamento **aprovado** é exportado."
        )

    st.divider()
    st.markdown("#### Acesso rápido")
    columns = st.columns(4)
    quick = (
        ("pages/08_processar_pasta.py", "Processar Pasta", "⚙️"),
        ("pages/10_validacao_lancamentos.py", "Validar Lançamentos", "✅"),
        ("pages/11_exportacao_dominio.py", "Exportar Domínio", "📤"),
        ("pages/01_dashboard.py", "Dashboard", "📊"),
    )
    for column, (target, label, icon) in zip(columns, quick, strict=True):
        with column:
            st.page_link(target, label=label, icon=icon)


render_sidebar()
render_home()
