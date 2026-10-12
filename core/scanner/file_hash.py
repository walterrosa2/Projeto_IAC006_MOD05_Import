"""Cálculo de hash SHA-256 de arquivos (base da detecção de duplicidade)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.exceptions import CorruptedFileError

#: Lê em blocos para suportar arquivos grandes sem carregar tudo na memória.
CHUNK_SIZE = 1024 * 1024


def compute_file_hash(file_path: str | Path) -> str:
    """SHA-256 hexadecimal do conteúdo do arquivo.

    Raises:
        CorruptedFileError: arquivo inexistente ou ilegível.
    """
    path = Path(file_path)
    if not path.is_file():
        raise CorruptedFileError(
            f"Arquivo não encontrado: {path.name}", detail=str(path)
        )

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)
    except OSError as exc:
        raise CorruptedFileError(
            f"Não foi possível ler o arquivo: {path.name}", detail=str(exc)
        ) from exc

    return digest.hexdigest()


def compute_bytes_hash(payload: bytes) -> str:
    """SHA-256 de um conteúdo já em memória."""
    return hashlib.sha256(payload).hexdigest()
