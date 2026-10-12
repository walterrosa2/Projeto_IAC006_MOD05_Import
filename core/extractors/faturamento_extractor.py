"""Extrator de relatório de faturamento, com retenções (Arquitetura 9.2)."""

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

_CUSTOMER_LABELS = ("CLIENTE", "TOMADOR", "SACADO", "DESTINATARIO", "RAZAO SOCIAL")

#: Rótulos que, em documentos tabulares (NFS-e transcrita por OCR), aparecem
#: sozinhos numa linha com o nome logo abaixo.
_STANDALONE_NAME_LABELS = ("NOME / NOME EMPRESARIAL", "NOME EMPRESARIAL", "NOME/NOME EMPRESARIAL")
_GROSS_LABELS = ("VALOR BRUTO", "VALOR TOTAL", "VALOR DOS SERVICOS", "TOTAL BRUTO", "VALOR NOTA")
_NET_LABELS = ("VALOR LIQUIDO", "LIQUIDO A RECEBER", "TOTAL LIQUIDO")

_TAX_LABELS: dict[str, tuple[str, ...]] = {
    "ir": ("IRRF", "IR RETIDO", "IMPOSTO DE RENDA", "IR"),
    "pcc": ("PCC", "CSRF", "PIS/COFINS/CSLL", "RETENCAO PCC"),
    "iss": ("ISS RETIDO", "ISSQN RETIDO", "ISS"),
    "inss": ("INSS RETIDO", "INSS"),
}

_DOCUMENT_PATTERN = re.compile(
    r"(?:NOTA FISCAL|NF-?E?|NUMERO|N[º°]\s*DOC|DOCUMENTO|TITULO)\s*:?\s*([A-Z0-9][A-Z0-9\-\./]{1,25})"
)
_COST_CENTER_PATTERN = re.compile(r"(?:CENTRO DE CUSTO|C\.?\s?CUSTO|CCUSTO)\s*:?\s*([A-Z0-9\-\.]{1,20})")


class FaturamentoExtractor(BaseExtractor):
    """Relatório de faturamento — cliente, valor bruto, retenções e líquido."""

    name = "faturamento"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        metadata = extract_common_metadata(text)
        result = self._result(raw_text=text)
        normalized = normalize(text)

        customer = self._find_customer(text)
        gross = find_labeled_amount(text, _GROSS_LABELS) or metadata["amount"]
        net = find_labeled_amount(text, _NET_LABELS)

        withheld = {
            key: (find_labeled_amount(text, labels) or 0.0) for key, labels in _TAX_LABELS.items()
        }
        total_withheld = round(sum(withheld.values()), 2)

        # Coerência entre bruto, retenções e líquido: completa o que faltar.
        if net is None and gross is not None and total_withheld:
            net = round(gross - total_withheld, 2)
        if gross is None and net is not None and total_withheld:
            gross = round(net + total_withheld, 2)

        document = None
        doc_match = _DOCUMENT_PATTERN.search(normalized)
        if doc_match:
            document = normalize_document_number(doc_match.group(1))

        cost_center = None
        cc_match = _COST_CENTER_PATTERN.search(normalized)
        if cc_match:
            cost_center = cc_match.group(1)

        result.structured = {
            "customer": customer,
            "document_number": document,
            "title": None,
            "issue_date": metadata["document_date"].isoformat() if metadata["document_date"] else None,
            "gross_amount": gross,
            "withheld_taxes": withheld,
            "total_withheld": total_withheld,
            "net_amount": net,
            "cost_center": cost_center,
            "detected_cnpjs": metadata["cnpjs"],
        }
        # O lançamento de receita parte do valor bruto (PRD seção 13).
        result.document_date = metadata["document_date"]
        result.amount = gross or net
        result.counterparty = customer
        result.document_number = document

        if customer is None:
            result.add_warning("Cliente não identificado no relatório de faturamento.")
        if gross is None:
            result.add_warning("Valor bruto não identificado.")
        if total_withheld:
            result.add_warning(
                f"Retenções detectadas (total {total_withheld:.2f}); "
                "conferir se o lançamento deve separar receita, impostos e líquido."
            )

        filled = sum(1 for value in (customer, gross, metadata["document_date"], document) if value)
        result.confidence = round(filled / 4, 2)
        return result

    @staticmethod
    def _find_customer(text: str) -> str | None:
        lines = text.splitlines()
        normalized_lines = [normalize(line) for line in lines]

        for index, norm_line in enumerate(normalized_lines):
            for label in _CUSTOMER_LABELS:
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

        # Layout tabular (NFS-e por OCR): o rótulo ocupa a linha inteira e o
        # nome vem na linha seguinte. A primeira ocorrência é a do emitente,
        # que é a contraparte de uma nota de serviço tomado.
        for index, norm_line in enumerate(normalized_lines):
            if norm_line not in {normalize(lbl) for lbl in _STANDALONE_NAME_LABELS}:
                continue
            for offset in (1, 2):
                if index + offset < len(lines):
                    candidate = _clean_name(lines[index + offset])
                    if candidate:
                        return candidate
        return None
