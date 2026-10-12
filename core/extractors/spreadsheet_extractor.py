"""Leitura de planilhas XLSX/XLS/CSV como texto e como dados tabulares."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.documents.metadata_extractor import extract_common_metadata
from core.exceptions import CorruptedFileError, ExtractionError
from core.extractors.base_extractor import BaseExtractor, ExtractionResult

#: Limite de linhas lidas por aba — evita carregar planilhas gigantes no prompt.
MAX_ROWS_PER_SHEET = 500


def _read_csv(path: Path) -> list[list[str]]:
    import csv

    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                except csv.Error:
                    dialect = csv.excel
                    dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
                reader = csv.reader(handle, dialect)
                # strict=False: trunca de propósito no teto de linhas.
                return [row for _, row in zip(range(MAX_ROWS_PER_SHEET), reader, strict=False)]
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise CorruptedFileError(
                f"Não foi possível ler o CSV: {path.name}", detail=str(exc)
            ) from exc
    raise CorruptedFileError(
        f"Codificação do CSV não reconhecida: {path.name}", detail="Tentado UTF-8 e Latin-1."
    )


def _read_excel(path: Path) -> dict[str, list[list[Any]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - dependência declarada
        raise ExtractionError("openpyxl não está instalado.", detail=str(exc)) from exc

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise CorruptedFileError(
            f"Não foi possível abrir a planilha: {path.name}", detail=str(exc)
        ) from exc

    sheets: dict[str, list[list[Any]]] = {}
    try:
        for sheet in workbook.worksheets:
            rows: list[list[Any]] = []
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index >= MAX_ROWS_PER_SHEET:
                    break
                if any(cell is not None and str(cell).strip() for cell in row):
                    rows.append(list(row))
            if rows:
                sheets[sheet.title] = rows
    finally:
        workbook.close()

    if not sheets:
        raise ExtractionError(
            f"Planilha sem conteúdo legível: {path.name}",
            detail="Nenhuma aba com linhas preenchidas.",
        )
    return sheets


def read_spreadsheet(file_path: str | Path) -> dict[str, list[list[Any]]]:
    """Conteúdo da planilha como {aba: linhas}. CSV vira a aba 'CSV'."""
    path = Path(file_path)
    if path.suffix.lower() == ".csv":
        return {"CSV": _read_csv(path)}
    return _read_excel(path)


def extract_spreadsheet_text(file_path: str | Path) -> str:
    """Planilha achatada em texto, para classificação e prompt da IA."""
    sheets = read_spreadsheet(file_path)
    blocks: list[str] = []
    for sheet_name, rows in sheets.items():
        lines = [f"### Aba: {sheet_name}"]
        for row in rows:
            cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if cells:
                lines.append(" | ".join(cells))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


class SpreadsheetExtractor(BaseExtractor):
    """Extrator genérico de planilhas auxiliares."""

    name = "spreadsheet"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        content = text or extract_spreadsheet_text(file_path)
        metadata = extract_common_metadata(content)

        sheet_names: list[str] = []
        row_count = 0
        try:
            sheets = read_spreadsheet(file_path)
            sheet_names = list(sheets)
            row_count = sum(len(rows) for rows in sheets.values())
        except (ExtractionError, CorruptedFileError):
            pass

        return self._result(
            raw_text=content,
            structured={
                "sheet_names": sheet_names,
                "row_count": row_count,
                "detected_cnpjs": metadata["cnpjs"],
            },
            document_date=metadata["document_date"],
            amount=metadata["amount"],
            confidence=0.4 if metadata["document_date"] else 0.2,
        )
