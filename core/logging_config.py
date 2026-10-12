"""Logging com Loguru: stdout para operação + JSONL rotativo para auditoria.

Nenhuma chave de API, senha ou token pode chegar ao disco (RNF05). Todo texto
logado passa por `redact()` antes de ser gravado.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from typing import Any

from loguru import logger

from core.config import get_settings

_configured = False

#: Padrões removidos de qualquer mensagem antes da gravação.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}"), "sk-ant-***REDACTED***"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-***REDACTED***"),
    (re.compile(r"AIza[A-Za-z0-9\-_]{20,}"), "AIza***REDACTED***"),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|password|senha|secret|authorization)\b\s*[:=]\s*\S+"),
        r"\1=***REDACTED***",
    ),
)

#: CPF isolado em texto livre é mascarado (RNF09/LGPD).
_CPF_PATTERN = re.compile(r"\b(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})\b")


def redact(text: str) -> str:
    """Remove segredos e mascara CPF de um texto destinado a log."""
    if not text:
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return _CPF_PATTERN.sub(r"\1.***.***-\2", text)


def _redacting_patcher(record: dict[str, Any]) -> None:
    record["message"] = redact(str(record["message"]))


def setup_logging() -> None:
    """Configura os sinks. Idempotente — chamadas repetidas não duplicam saída."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    logger.remove()
    logger.configure(patcher=_redacting_patcher)

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
        filter=lambda record: "audit" not in record["extra"],
    )

    logger.add(
        settings.log_dir / "app.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: "audit" not in record["extra"],
    )

    logger.add(
        settings.log_dir / "audit.jsonl",
        level="INFO",
        serialize=True,
        rotation="10 MB",
        retention="90 days",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: "audit" in record["extra"],
    )

    _configured = True


def log_audit(
    action: str,
    *,
    actor: str = "agent",
    target: str = "system",
    outcome: str = "success",
    data: dict[str, Any] | None = None,
) -> None:
    """Grava um evento de auditoria em logs/audit.jsonl.

    Args:
        action: verbo do evento, ex. "document_classified", "entry_approved".
        actor: quem executou — "user", "agent" ou "app".
        target: objeto afetado, ex. "documento:42".
        outcome: "success" | "failure" | "blocked".
        data: campos extras já livres de segredos.
    """
    setup_logging()
    event = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "actor": actor,
        "action": action,
        "target": target,
        "outcome": outcome,
        "data": data or {},
    }
    logger.bind(audit=True).info(event)


def get_logger():
    """Logger de aplicação já configurado."""
    setup_logging()
    return logger
