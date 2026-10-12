"""Tela de configuração e diagnóstico do ambiente.

Somente leitura das configurações sensíveis: as chaves ficam no `.env` e nunca
são exibidas nem editadas pela interface.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.ui import error_box, page_header, setup_page, warning_box  # noqa: E402
from core.accounting.ai_accounting_classifier import check_provider_health  # noqa: E402
from core.config import PROJECT_ROOT, get_settings, reload_settings  # noqa: E402
from db.database import get_engine  # noqa: E402
from db.models import Base  # noqa: E402

setup_page("Configuração", icon="🔧")
page_header(
    "🔧 Configuração e Diagnóstico",
    "Valores lidos do arquivo `.env`. Chaves de API nunca são exibidas aqui.",
)

if st.button("Recarregar .env"):
    reload_settings()
    st.success("Configuração recarregada.")
    st.rerun()

settings = get_settings()

# --------------------------------------------------------------------------- #
# IA
# --------------------------------------------------------------------------- #

st.markdown("#### Provedor de IA")

healthy, message = check_provider_health()
if settings.ai_provider == "mock":
    warning_box(f"**Modo MOCK.** {message}")
elif healthy:
    st.success(message, icon="🤖")
else:
    error_box(message)

columns = st.columns(4)
columns[0].metric("Provedor", settings.ai_provider)
columns[1].metric("Modelo", settings.ai_model)
columns[2].metric("Timeout", f"{settings.ai_timeout_seconds}s")
columns[3].metric("Tentativas", settings.ai_max_retries)

st.caption(
    "Chave configurada: "
    + ("✅ sim" if settings.api_key else "❌ não")
    + " (o valor nunca é exibido nem registrado em log)"
)

# --------------------------------------------------------------------------- #
# Regras
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Limites e regras de negócio")

st.dataframe(
    pd.DataFrame(
        [
            {
                "Parâmetro": "Confiança mínima do classificador documental",
                "Valor": f"{settings.min_classification_confidence:.2f}",
                "Efeito": "Abaixo disso o documento vai para OUTROS.",
            },
            {
                "Parâmetro": "Confiança mínima da IA contábil",
                "Valor": f"{settings.min_accounting_confidence:.2f}",
                "Efeito": "Abaixo disso o lançamento recebe aviso na revisão.",
            },
            {
                "Parâmetro": "Exemplos por prompt",
                "Valor": settings.max_examples_in_prompt,
                "Efeito": "Teto de exemplos de lançamento enviados à IA.",
            },
            {
                "Parâmetro": "Correções por prompt",
                "Valor": settings.max_corrections_in_prompt,
                "Efeito": "Teto de correções anteriores enviadas à IA.",
            },
            {
                "Parâmetro": "Contas por prompt",
                "Valor": settings.max_accounts_in_prompt,
                "Efeito": "Teto de contas do plano enviadas à IA.",
            },
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

# --------------------------------------------------------------------------- #
# Ambiente
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Ambiente")

env_file = PROJECT_ROOT / ".env"
engine = get_engine()

try:
    with engine.connect() as connection:
        from sqlalchemy import inspect

        tables = sorted(inspect(connection).get_table_names())
    db_status = f"✅ conectado — {len(tables)} tabela(s)"
except Exception as exc:  # noqa: BLE001
    tables = []
    db_status = f"❌ falha: {exc}"

st.dataframe(
    pd.DataFrame(
        [
            {"Item": "Raiz do projeto", "Valor": str(PROJECT_ROOT)},
            {
                "Item": "Arquivo .env",
                "Valor": f"{'✅ encontrado' if env_file.exists() else '⚠️ ausente (usando defaults)'} — {env_file}",
            },
            {"Item": "Banco de dados", "Valor": f"{db_status} — {settings.database_url}"},
            {"Item": "Pasta de logs", "Valor": str(settings.log_dir)},
            {"Item": "Pasta de exportações", "Valor": str(settings.export_dir)},
            {"Item": "Nível de log", "Valor": settings.log_level},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

expected = set(Base.metadata.tables)
missing = expected - set(tables)
if missing:
    error_box(f"Tabelas ausentes no banco: {', '.join(sorted(missing))}")

if not env_file.exists():
    warning_box(
        "Arquivo `.env` não encontrado. Copie `.env.example` para `.env` e preencha "
        "o provedor de IA e a chave de API."
    )

# --------------------------------------------------------------------------- #
# Logs
# --------------------------------------------------------------------------- #

st.divider()
st.markdown("#### Logs e evidências")

audit_file = settings.log_dir / "audit.jsonl"
app_log = settings.log_dir / "app.log"
evidence_dir = settings.log_dir / "ai_evidence"

columns = st.columns(3)
columns[0].metric(
    "Eventos de auditoria",
    sum(1 for _ in audit_file.open(encoding="utf-8")) if audit_file.exists() else 0,
)
columns[1].metric("Log da aplicação", "✅" if app_log.exists() else "—")
columns[2].metric(
    "Evidências de IA",
    len(list(evidence_dir.glob("*.json"))) if evidence_dir.exists() else 0,
)

if audit_file.exists():
    with st.expander("Últimos 20 eventos de auditoria"):
        import json

        lines = audit_file.read_text(encoding="utf-8").strip().splitlines()[-20:]
        events = []
        for line in reversed(lines):
            try:
                record = json.loads(line)
                payload = record.get("record", {}).get("message", record)
                if isinstance(payload, str):
                    payload = json.loads(payload.replace("'", '"'))
                events.append(
                    {
                        "Quando": payload.get("timestamp", "—"),
                        "Ator": payload.get("actor", "—"),
                        "Ação": payload.get("action", "—"),
                        "Alvo": payload.get("target", "—"),
                        "Resultado": payload.get("outcome", "—"),
                    }
                )
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum evento legível no arquivo.")
