"""Parsers de metadados brasileiros: datas, valores, CNPJ/CPF e competência.

Usado por todos os extratores. Mantido sem dependência de banco para poder ser
testado isoladamente.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from core.constants import MONTH_NAMES_PT

# --------------------------------------------------------------------------- #
# Normalização de texto
# --------------------------------------------------------------------------- #


def strip_accents(text: str) -> str:
    """Remove acentuação — facilita casar rótulos escritos de formas diferentes."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Caixa alta, sem acento e com espaços colapsados."""
    return re.sub(r"\s+", " ", strip_accents(text).upper()).strip()


# --------------------------------------------------------------------------- #
# Datas
# --------------------------------------------------------------------------- #

_MONTH_ABBR_PT = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}

_DATE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{2})\b"), "dmy2"),
)

_TEXTUAL_DATE = re.compile(
    r"\b(\d{1,2})\s+DE\s+([A-Z]{3,9})\s+DE\s+(\d{4})\b"
)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_br(raw: str) -> date | None:
    """Converte uma data isolada em `date`. Aceita dd/mm/aaaa, aaaa-mm-dd e variantes."""
    if not raw:
        return None
    text = raw.strip()
    for pattern, order in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        a, b, c = match.groups()
        if order == "ymd":
            return _safe_date(int(a), int(b), int(c))
        if order == "dmy":
            return _safe_date(int(c), int(b), int(a))
        year = int(c)
        return _safe_date(2000 + year if year < 70 else 1900 + year, int(b), int(a))
    return None


def find_dates(text: str) -> list[date]:
    """Todas as datas plausíveis do texto, em ordem de aparição e sem repetição.

    Filtra anos fora de 2000–2100 para descartar números que não são datas.
    """
    found: list[date] = []
    seen: set[date] = set()

    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            a, b, c = match.groups()
            if order == "ymd":
                parsed = _safe_date(int(a), int(b), int(c))
            elif order == "dmy":
                parsed = _safe_date(int(c), int(b), int(a))
            else:
                year = int(c)
                parsed = _safe_date(2000 + year if year < 70 else 1900 + year, int(b), int(a))
            if parsed and 2000 <= parsed.year <= 2100 and parsed not in seen:
                seen.add(parsed)
                found.append(parsed)

    for match in _TEXTUAL_DATE.finditer(normalize(text)):
        day, month_name, year = match.groups()
        month = _MONTH_ABBR_PT.get(month_name[:3])
        if month:
            parsed = _safe_date(int(year), month, int(day))
            if parsed and parsed not in seen:
                seen.add(parsed)
                found.append(parsed)

    return found


def first_date(text: str) -> date | None:
    """Primeira data encontrada no texto, ou None."""
    dates = find_dates(text)
    return dates[0] if dates else None


# --------------------------------------------------------------------------- #
# Valores monetários
# --------------------------------------------------------------------------- #

_AMOUNT_PATTERN = re.compile(r"(?<![\d,.])(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})(?![\d])")
def parse_amount_br(raw: str | float | int | None) -> float | None:
    """Converte '1.234,56', 'R$ 1.234,56' ou '1234.56' em float.

    Retorna None quando não houver número reconhecível.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text:
        return None

    negative = text.startswith("-") or ("(" in text and ")" in text)
    cleaned = re.sub(r"[^\d,.-]", "", text).lstrip("-")
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        # Formato brasileiro: ponto é milhar, vírgula é decimal.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def find_amounts(text: str) -> list[float]:
    """Todos os valores no formato brasileiro encontrados no texto."""
    values: list[float] = []
    for match in _AMOUNT_PATTERN.finditer(text):
        parsed = parse_amount_br(match.group(1))
        if parsed is not None:
            values.append(parsed)
    return values


def find_labeled_amount(text: str, labels: tuple[str, ...]) -> float | None:
    """Valor que aparece logo após um dos rótulos informados.

    Ex.: find_labeled_amount(txt, ("VALOR LIQUIDO", "LIQUIDO")) em um relatório.
    """
    normalized = normalize(text)
    for label in labels:
        target = normalize(label)
        pattern = re.compile(
            rf"{re.escape(target)}[^\d\-]{{0,20}}(-?\s?R?\$?\s?\d[\d.,]*)"
        )
        match = pattern.search(normalized)
        if match:
            parsed = parse_amount_br(match.group(1))
            if parsed is not None:
                return parsed
    return None


def largest_amount(text: str) -> float | None:
    """Maior valor do texto — heurística para o valor principal do documento."""
    values = [v for v in find_amounts(text) if v > 0]
    return max(values) if values else None


# --------------------------------------------------------------------------- #
# CNPJ / CPF
# --------------------------------------------------------------------------- #

_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def find_cnpjs(text: str) -> list[str]:
    """CNPJs encontrados, formatados como 00.000.000/0000-00."""
    results: list[str] = []
    for match in _CNPJ_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) == 14:
            formatted = (
                f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
            )
            if formatted not in results:
                results.append(formatted)
    return results


def find_cpfs(text: str) -> list[str]:
    """CPFs encontrados, formatados como 000.000.000-00."""
    results: list[str] = []
    cnpj_digits = {re.sub(r"\D", "", c) for c in find_cnpjs(text)}
    for match in _CPF_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) != 11:
            continue
        # Evita casar um pedaço de CNPJ como se fosse CPF.
        if any(digits in cnpj for cnpj in cnpj_digits):
            continue
        formatted = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        if formatted not in results:
            results.append(formatted)
    return results


def mask_cpf(cpf: str | None) -> str | None:
    """Mascara CPF para exibição em tela (LGPD, RNF09): 000.***.***-00."""
    if not cpf:
        return cpf
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11:
        return cpf
    return f"{digits[:3]}.***.***-{digits[9:]}"


def normalize_document_number(raw: str | None) -> str | None:
    """Número de documento sem espaços supérfluos, em caixa alta."""
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", str(raw)).upper()
    return cleaned or None


# --------------------------------------------------------------------------- #
# Competência
# --------------------------------------------------------------------------- #


def competence_from_date(value: date | None) -> tuple[int | None, int | None]:
    """(ano, mês) da competência a partir da data do documento."""
    if value is None:
        return None, None
    return value.year, value.month


def format_competence(year: int | None, month: int | None) -> str:
    """Rótulo legível da competência, ex. '01 - Janeiro/2026'."""
    if not year or not month:
        return "Sem competência"
    return f"{month:02d} - {MONTH_NAMES_PT.get(month, '?')}/{year}"


def month_folder_name(month: int) -> str:
    """Nome da pasta do mês, ex. '01 - Janeiro' (PRD seção 8.2)."""
    return f"{month:02d} - {MONTH_NAMES_PT.get(month, 'Indefinido')}"


# --------------------------------------------------------------------------- #
# Metadados comuns
# --------------------------------------------------------------------------- #


def extract_common_metadata(text: str, *, reference: date | None = None) -> dict:
    """Data, valor e identificadores encontrados em qualquer documento textual.

    `reference` permite preferir a data mais próxima de uma competência já
    conhecida; sem ela, usa a primeira data do texto.
    """
    dates = find_dates(text)
    document_date: date | None = None
    if dates:
        if reference is not None:
            document_date = min(dates, key=lambda d: abs((d - reference).days))
        else:
            document_date = dates[0]

    cnpjs = find_cnpjs(text)
    cpfs = find_cpfs(text)
    year, month = competence_from_date(document_date)

    return {
        "document_date": document_date,
        "amount": largest_amount(text),
        "all_dates": dates,
        "all_amounts": find_amounts(text),
        "cnpjs": cnpjs,
        "cpfs": cpfs,
        "competence_year": year,
        "competence_month": month,
    }
