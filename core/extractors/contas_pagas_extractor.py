"""Extrator de relatório de contas pagas (Arquitetura 9.2).

É o documento preferencial para lançamentos de pagamento (PRD seção 10).
"""

from __future__ import annotations

import re
from pathlib import Path

from core.documents.metadata_extractor import (
    extract_common_metadata,
    find_labeled_amount,
    normalize,
    normalize_document_number,
)
from core.extractors.base_extractor import BaseExtractor, ExtractionResult
from core.extractors.pix_extractor import _clean_name

_CREDITOR_LABELS = ("CREDOR", "FORNECEDOR", "BENEFICIARIO", "NOME DO CREDOR")
_GROSS_LABELS = ("VALOR BRUTO", "VALOR ORIGINAL", "VALOR TITULO", "VALOR DO TITULO")
_NET_LABELS = ("VALOR LIQUIDO", "LIQUIDO", "VALOR PAGO", "TOTAL PAGO")
_DISCOUNT_LABELS = ("DESCONTO", "DESCONTOS")
_ADDITION_LABELS = ("ACRESCIMO", "ACRESCIMOS", "JUROS", "MULTA")
_PAYMENT_DATE_LABELS = ("DATA DE BAIXA", "DATA BAIXA", "DATA PAGAMENTO", "DATA DO PAGAMENTO", "PAGO EM")
_DUE_DATE_LABELS = ("VENCIMENTO", "DATA DE VENCIMENTO", "VENCTO")

_DOCUMENT_PATTERN = re.compile(
    r"(?:DOCUMENTO|DOC\.?|NF|NOTA FISCAL|TITULO)\s*:?\s*([A-Z0-9][A-Z0-9\-\./]{2,30})"
)
_POSTING_PATTERN = re.compile(r"(?:LANCAMENTO|N[º°]?\s*LANCAMENTO|BAIXA)\s*:?\s*(\d{1,10})")


def _find_labeled_date(text: str, labels: tuple[str, ...]):
    """Data que aparece logo após um dos rótulos."""
    from core.documents.metadata_extractor import parse_date_br

    normalized = normalize(text)
    for label in labels:
        target = normalize(label)
        match = re.search(rf"{re.escape(target)}[^\d]{{0,15}}(\d{{2}}[/\-.]\d{{2}}[/\-.]\d{{2,4}})", normalized)
        if match:
            parsed = parse_date_br(match.group(1))
            if parsed:
                return parsed
    return None


class ContasPagasExtractor(BaseExtractor):
    """Relatório de contas pagas — credor, documento, data de baixa e líquido."""

    name = "contas_pagas"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        metadata = extract_common_metadata(text)
        result = self._result(raw_text=text)

        creditor = self._find_creditor(text)
        gross = find_labeled_amount(text, _GROSS_LABELS)
        net = find_labeled_amount(text, _NET_LABELS)
        discount = find_labeled_amount(text, _DISCOUNT_LABELS) or 0.0
        addition = find_labeled_amount(text, _ADDITION_LABELS) or 0.0

        payment_date = _find_labeled_date(text, _PAYMENT_DATE_LABELS) or metadata["document_date"]
        due_date = _find_labeled_date(text, _DUE_DATE_LABELS)

        normalized = normalize(text)
        document = None
        doc_match = _DOCUMENT_PATTERN.search(normalized)
        if doc_match:
            document = normalize_document_number(doc_match.group(1))

        posting = None
        posting_match = _POSTING_PATTERN.search(normalized)
        if posting_match:
            posting = posting_match.group(1)

        # O valor do lançamento é o efetivamente pago; cai para o bruto e, por fim,
        # para o maior valor do texto.
        amount = net or gross or metadata["amount"]

        result.structured = {
            "creditor": creditor,
            "creditor_code": None,
            "document": document,
            "posting_number": posting,
            "payment_date": payment_date.isoformat() if payment_date else None,
            "due_date": due_date.isoformat() if due_date else None,
            "gross_amount": gross,
            "addition": addition,
            "discount": discount,
            "net_amount": net,
            "detected_cnpjs": metadata["cnpjs"],
        }
        result.document_date = payment_date
        result.amount = amount
        result.counterparty = creditor
        result.document_number = document

        if creditor is None:
            result.add_warning("Credor não identificado no relatório.")
        if amount is None:
            result.add_warning("Valor pago não identificado.")
        if payment_date is None:
            result.add_warning("Data de baixa não identificada.")

        filled = sum(1 for value in (creditor, amount, payment_date, document) if value)
        result.confidence = round(filled / 4, 2)
        return result

    @staticmethod
    def _find_creditor(text: str) -> str | None:
        lines = text.splitlines()
        normalized_lines = [normalize(line) for line in lines]
        for index, norm_line in enumerate(normalized_lines):
            for label in _CREDITOR_LABELS:
                target = normalize(label)
                if target not in norm_line:
                    continue
                position = norm_line.find(target) + len(target)
                candidate = _clean_name(lines[index][position:].lstrip(" :\t-"))
                if candidate:
                    return candidate
                if index + 1 < len(lines):
                    candidate = _clean_name(lines[index + 1])
                    if candidate:
                        return candidate
        return None
