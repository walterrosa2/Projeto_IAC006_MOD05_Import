"""Engine, sessões e criação automática do schema SQLite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import PROJECT_ROOT, get_settings
from db.models import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _resolve_sqlite_url(url: str) -> str:
    """Converte caminho relativo do SQLite em absoluto, ancorado na raiz do projeto."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw_path = url[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path}"


def get_engine() -> Engine:
    """Engine singleton. Ativa foreign keys no SQLite."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = _resolve_sqlite_url(settings.database_url)
        _engine = create_engine(url, echo=False, future=True)

        if url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _record):  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Fábrica de sessões singleton."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def init_db() -> None:
    """Cria as tabelas que ainda não existem. Seguro para chamar a cada boot."""
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional: commit no sucesso, rollback em qualquer exceção."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Descarta engine e fábrica — usado por testes que trocam o DATABASE_URL."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
