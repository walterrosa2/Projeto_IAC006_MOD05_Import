"""Extrator de extrato bancário.

O extrato é documento de conciliação/evidência (PRD seção 10): reúne muitos
lançamentos, então extraímos o período e as linhas de movimento, sem forçar um
valor único de lançamento.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.documents.metadata_extractor import (
    find_amounts,
    find_dates,
    find_labeled_amount,
    normalize,
    parse_amount_br,
    parse_date_br,
)
from core.extractors.base_extractor import BaseExtractor, ExtractionResult

_BALANCE_LABELS = ("SALDO FINAL", "SALDO ATUAL", "SALDO EM CONTA", "SALDO")
_ACCOUNT_PATTERN = re.compile(r"(?:CONTA|C/C|CONTA CORRENTE)\s*:?\s*([\d\.\-]{4,20})")
_AGENCY_PATTERN = re.compile(r"(?:AGENCIA|AG\.?)\s*:?\s*([\d\.\-]{2,10})")
_MOVEMENT_LINE = re.compile(
    r"^\s*(\d{2}/\d{2}(?:/\d{2,4})?)\s+(.{3,80}?)\s+(-?\s?R?\$?\s?[\d.]{1,12},\d{2})\s*$"
)

#: Teto de linhas de movimento preservadas — mantém o JSON e o prompt enxutos.
MAX_MOVEMENTS = 200


class ExtratoExtractor(BaseExtractor):
    """Extrato bancário — período, saldo e linhas de movimento."""

    name = "extrato"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        result = self._result(raw_text=text)
        normalized = normalize(text)

        dates = find_dates(text)
        period_start = min(dates) if dates else None
        period_end = max(dates) if dates else None

        movements = self._parse_movements(text, fallback_year=period_end.year if period_end else None)
        balance = find_labeled_amount(text, _BALANCE_LABELS)

        account = None
        account_match = _ACCOUNT_PATTERN.search(normalized)
        if account_match:
            account = account_match.group(1)

        agency = None
        agency_match = _AGENCY_PATTERN.search(normalized)
        if agency_match:
            agency = agency_match.group(1)

        total_credits = round(sum(m["amount"] for m in movements if m["amount"] > 0), 2)
        total_debits = round(sum(m["amount"] for m in movements if m["amount"] < 0), 2)

        result.structured = {
            "account": account,
            "agency": agency,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "final_balance": balance,
            "movement_count": len(movements),
            "total_credits": total_credits,
            "total_debits": total_debits,
            "movements": movements[:MAX_MOVEMENTS],
        }
        result.document_date = period_end
        # Um extrato não tem "um" valor; só preenchemos quando há movimento único.
        result.amount = movements[0]["amount"] if len(movements) == 1 else None
        result.counterparty = None
        result.document_number = account

        if not movements:
            result.add_warning("Nenhuma linha de movimento reconhecida no extrato.")
        if len(movements) > 1:
            result.add_warning(
                f"Extrato com {len(movements)} movimentos: use como evidência/conciliação, "
                "não como documento base de um único lançamento."
            )

        filled = sum(1 for value in (period_start, period_end, account, movements) if value)
        result.confidence = round(filled / 4, 2)
        return result

    @staticmethod
    def _parse_movements(text: str, *, fallback_year: int | None) -> list[dict]:
        """Linhas no formato `data  descrição  valor`."""
        movements: list[dict] = []
        for line in text.splitlines():
            match = _MOVEMENT_LINE.match(line)
            if not match:
                continue
            raw_date, description, raw_amount = match.groups()
            if len(raw_date) == 5 and fallback_year:
                raw_date = f"{raw_date}/{fallback_year}"
            parsed_date = parse_date_br(raw_date)
            amount = parse_amount_br(raw_amount)
            if parsed_date is None or amount is None:
                continue
            movements.append(
                {
                    "date": parsed_date.isoformat(),
                    "description": re.sub(r"\s+", " ", description).strip(),
                    "amount": amount,
                }
            )

        if not movements:
            # Formato não tabular: registra ao menos os valores encontrados.
            amounts = find_amounts(text)
            if len(amounts) == 1:
                dates = find_dates(text)
                movements.append(
                    {
                        "date": dates[0].isoformat() if dates else None,
                        "description": "Movimento único identificado",
                        "amount": amounts[0],
                    }
                )
        return movements
