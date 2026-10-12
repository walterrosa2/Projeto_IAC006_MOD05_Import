"""Varredura da pasta DADOS_A_CLASSIFICAR de uma empresa."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.constants import SUPPORTED_EXTENSIONS

#: Nome padronizado da pasta de entrada (PRD seção 8.1).
INPUT_FOLDER_NAME = "DADOS_A_CLASSIFICAR"

#: Arquivos de sistema/temporários ignorados na varredura.
_IGNORED_PREFIXES = ("~$", ".~", "._")
_IGNORED_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}


@dataclass(frozen=True)
class ScannedFile:
    """Um arquivo encontrado na pasta de entrada, antes de qualquer processamento."""

    path: Path
    name: str
    extension: str
    size_bytes: int
    modified_at: datetime
    supported: bool

    @property
    def size_kb(self) -> float:
        return round(self.size_bytes / 1024, 1)


def _is_ignored(path: Path) -> bool:
    name = path.name
    if name.lower() in _IGNORED_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in _IGNORED_PREFIXES)


def resolve_input_folder(company_input_path: str | Path) -> Path:
    """Resolve a pasta de entrada.

    Aceita tanto o caminho já apontando para `DADOS_A_CLASSIFICAR` quanto a pasta
    do cliente — nesse caso desce para a subpasta padrão.
    """
    path = Path(company_input_path).expanduser()
    if path.name.upper() == INPUT_FOLDER_NAME:
        return path
    candidate = path / INPUT_FOLDER_NAME
    return candidate if candidate.is_dir() else path


def scan_folder(
    company_input_path: str | Path,
    *,
    recursive: bool = False,
    include_unsupported: bool = True,
) -> list[ScannedFile]:
    """Lista os arquivos da pasta de entrada.

    Args:
        recursive: por padrão ignora subpastas (Tarefa 3.1).
        include_unsupported: mantém na lista arquivos de extensão não suportada,
            marcados com `supported=False`, para que apareçam na tela e possam ir
            para ERROS em vez de sumirem silenciosamente.

    Returns:
        Lista ordenada por nome. Vazia se a pasta não existir.
    """
    folder = resolve_input_folder(company_input_path)
    if not folder.is_dir():
        return []

    iterator = folder.rglob("*") if recursive else folder.glob("*")
    results: list[ScannedFile] = []

    for path in iterator:
        if not path.is_file() or _is_ignored(path):
            continue
        extension = path.suffix.lower()
        supported = extension in SUPPORTED_EXTENSIONS
        if not supported and not include_unsupported:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        results.append(
            ScannedFile(
                path=path,
                name=path.name,
                extension=extension,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                supported=supported,
            )
        )

    return sorted(results, key=lambda f: f.name.lower())


def ensure_input_folder(company_input_path: str | Path) -> Path:
    """Cria a pasta de entrada se ainda não existir e devolve o caminho."""
    folder = resolve_input_folder(company_input_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder
