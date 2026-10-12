"""Organizador de pastas: copia o documento para cliente/ano/mês/tipo.

No MVP o arquivo é **copiado**, nunca movido — a pasta de entrada permanece
intacta (RNF02 / instrução 7.3).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.constants import (
    ALL_DESTINATION_FOLDERS,
    DOCUMENT_TYPE_TO_FOLDER,
    DocumentType,
)
from core.documents.metadata_extractor import month_folder_name
from core.exceptions import ClassificadorError

#: Caracteres proibidos em nomes de arquivo no Windows.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Nomes reservados pelo Windows que não podem ser usados como nome de arquivo.
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

#: Pasta usada quando a competência do documento não pôde ser determinada.
UNDEFINED_COMPETENCE = "SEM_COMPETENCIA"

MAX_NAME_LENGTH = 120


@dataclass(frozen=True)
class OrganizeResult:
    """Resultado da cópia para a pasta de destino."""

    destination_path: Path
    folder_name: str
    renamed: bool
    created_folders: bool


def safe_file_name(name: str) -> str:
    """Nome de arquivo seguro para Windows, preservando a extensão.

    Sanitiza a string inteira antes de separar a extensão: usar `Path().stem`
    direto descartaria tudo antes de uma barra, já que `/` e `\\` são
    separadores — o que também protege contra path traversal no nome.
    """
    sanitized = _UNSAFE_CHARS.sub("_", name)
    stem, dot, extension = sanitized.rpartition(".")
    if not dot:
        stem, suffix = sanitized, ""
    else:
        stem, suffix = stem, f".{extension}"

    stem = stem.strip(" .")
    stem = re.sub(r"\s+", " ", stem)
    if not stem:
        stem = "documento"
    if stem.upper() in _RESERVED_NAMES:
        stem = f"_{stem}"
    if len(stem) > MAX_NAME_LENGTH:
        stem = stem[:MAX_NAME_LENGTH]

    suffix = _UNSAFE_CHARS.sub("", suffix)
    return f"{stem}{suffix}"


def build_destination_path(
    *,
    destination_root: str | Path,
    company_name: str,
    document_type: str,
    competence_year: int | None,
    competence_month: int | None,
    file_name: str,
) -> Path:
    """Monta o caminho de destino (Arquitetura 8.2).

    `{destination_root}/{empresa}/{ano}/{mm - Mês}/{PASTA_TIPO}/{arquivo}`

    Sem competência identificada, ano e mês são substituídos por
    `SEM_COMPETENCIA`, preservando o resto da estrutura.
    """
    folder_name = DOCUMENT_TYPE_TO_FOLDER.get(document_type, "OUTROS")
    safe_company = _UNSAFE_CHARS.sub("_", company_name).strip(" .") or "EMPRESA"

    root = Path(destination_root).expanduser()
    # Se a raiz já é a pasta do cliente, não repete o nome da empresa.
    base = root if root.name.strip().lower() == company_name.strip().lower() else root / safe_company

    if competence_year and competence_month:
        period = base / str(competence_year) / month_folder_name(competence_month)
    else:
        period = base / UNDEFINED_COMPETENCE

    return period / folder_name / safe_file_name(file_name)


def _resolve_collision(destination: Path) -> tuple[Path, bool]:
    """Evita sobrescrever arquivo existente acrescentando um sufixo único."""
    if not destination.exists():
        return destination, False

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    candidate = destination.with_name(f"{destination.stem}__{stamp}{destination.suffix}")
    counter = 1
    while candidate.exists():
        candidate = destination.with_name(
            f"{destination.stem}__{stamp}_{counter}{destination.suffix}"
        )
        counter += 1
    return candidate, True


def organize_document(
    *,
    source_path: str | Path,
    destination_root: str | Path,
    company_name: str,
    document_type: str,
    competence_year: int | None,
    competence_month: int | None,
) -> OrganizeResult:
    """Copia o documento para a pasta correta, criando a estrutura se preciso.

    Raises:
        ClassificadorError: origem inexistente ou falha de cópia.
    """
    source = Path(source_path)
    if not source.is_file():
        raise ClassificadorError(
            f"Arquivo de origem não encontrado: {source.name}", detail=str(source)
        )

    destination = build_destination_path(
        destination_root=destination_root,
        company_name=company_name,
        document_type=document_type,
        competence_year=competence_year,
        competence_month=competence_month,
        file_name=source.name,
    )

    created = not destination.parent.exists()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        final_path, renamed = _resolve_collision(destination)
        shutil.copy2(source, final_path)
    except OSError as exc:
        raise ClassificadorError(
            f"Falha ao copiar {source.name} para a pasta de destino.", detail=str(exc)
        ) from exc

    return OrganizeResult(
        destination_path=final_path,
        folder_name=final_path.parent.name,
        renamed=renamed,
        created_folders=created,
    )


def write_error_marker(
    *,
    destination_path: Path,
    original_file_name: str,
    company_name: str,
    error_type: str,
    error_message: str,
    recommended_action: str = "Revisar manualmente ou reenviar arquivo legível",
) -> Path:
    """Grava o `.json` de erro ao lado do arquivo na pasta ERROS (PRD 8.3)."""
    import json

    marker = destination_path.with_suffix(destination_path.suffix + ".erro.json")
    payload = {
        "arquivo": original_file_name,
        "empresa": company_name,
        "data_processamento": datetime.now().isoformat(timespec="seconds"),
        "erro_tipo": error_type,
        "erro_mensagem": error_message,
        "acao_recomendada": recommended_action,
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def ensure_competence_folders(
    *,
    destination_root: str | Path,
    company_name: str,
    year: int,
    month: int,
) -> list[Path]:
    """Cria previamente todas as pastas de uma competência (PRD 8.2)."""
    created: list[Path] = []
    for folder in ALL_DESTINATION_FOLDERS:
        path = build_destination_path(
            destination_root=destination_root,
            company_name=company_name,
            document_type=next(
                (t for t, f in DOCUMENT_TYPE_TO_FOLDER.items() if f == folder),
                DocumentType.OUTRO,
            ),
            competence_year=year,
            competence_month=month,
            file_name="_",
        ).parent
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created
