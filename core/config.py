"""Configuração central da aplicação, carregada de .env (nunca hardcoded)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env", override=True)


def _to_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _to_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _to_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "sim", "yes", "on"}


class Settings(BaseModel):
    """Configuração imutável da aplicação."""

    ai_provider: str = Field(default="mock")
    ai_model: str = Field(default="claude-sonnet-5")
    ai_timeout_seconds: int = Field(default=60)
    ai_max_retries: int = Field(default=3)

    ocr_enabled: bool = Field(default=False)
    ocr_max_pages: int = Field(default=10)

    min_classification_confidence: float = Field(default=0.70)
    min_accounting_confidence: float = Field(default=0.60)
    max_examples_in_prompt: int = Field(default=5)
    max_corrections_in_prompt: int = Field(default=5)
    max_accounts_in_prompt: int = Field(default=400)

    database_url: str = Field(default="sqlite:///data/app.db")
    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=PROJECT_ROOT / "logs")
    export_dir: Path = Field(default=PROJECT_ROOT / "data" / "exports")

    @property
    def api_key(self) -> str | None:
        """Chave do provedor ativo. Lida sob demanda para nunca ficar em repr/log."""
        mapping = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        env_name = mapping.get(self.ai_provider)
        if not env_name:
            return None
        value = os.getenv(env_name, "").strip()
        return value or None

    @property
    def ai_is_configured(self) -> bool:
        """True quando a IA pode ser chamada (mock sempre pode)."""
        if self.ai_provider == "mock":
            return True
        return self.api_key is not None


def _resolve_path(raw: str, default: Path) -> Path:
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings em cache. Use reload_settings() após alterar o .env."""
    settings = Settings(
        ai_provider=os.getenv("AI_PROVIDER", "mock").strip().lower(),
        ai_model=os.getenv("AI_MODEL", "claude-sonnet-5").strip(),
        ai_timeout_seconds=_to_int("AI_TIMEOUT_SECONDS", 60),
        ai_max_retries=_to_int("AI_MAX_RETRIES", 3),
        ocr_enabled=_to_bool("OCR_ENABLED", False),
        ocr_max_pages=_to_int("OCR_MAX_PAGES", 10),
        min_classification_confidence=_to_float("MIN_CLASSIFICATION_CONFIDENCE", 0.70),
        min_accounting_confidence=_to_float("MIN_ACCOUNTING_CONFIDENCE", 0.60),
        max_examples_in_prompt=_to_int("MAX_EXAMPLES_IN_PROMPT", 5),
        max_corrections_in_prompt=_to_int("MAX_CORRECTIONS_IN_PROMPT", 5),
        max_accounts_in_prompt=_to_int("MAX_ACCOUNTS_IN_PROMPT", 400),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/app.db").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        log_dir=_resolve_path(os.getenv("LOG_DIR", ""), PROJECT_ROOT / "logs"),
        export_dir=_resolve_path(os.getenv("EXPORT_DIR", ""), PROJECT_ROOT / "data" / "exports"),
    )
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    return settings


def reload_settings() -> Settings:
    """Recarrega .env e limpa o cache (usado pela tela de configuração)."""
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    get_settings.cache_clear()
    return get_settings()
