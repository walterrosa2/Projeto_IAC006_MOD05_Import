"""Extrator de CT-e (Conhecimento de Transporte Eletrônico).

Trata tanto o XML oficial quanto o DACTE em PDF.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

from core.documents.metadata_extractor import (
    extract_common_metadata,
    find_labeled_amount,
    normalize,
    parse_date_br,
)
from core.extractors.base_extractor import BaseExtractor, ExtractionResult

_ACCESS_KEY = re.compile(r"\b(\d{44})\b")
_CTE_NUMBER = re.compile(r"(?:N[º°]?\s*CT-?E|NUMERO CT-?E|CT-?E N[º°]?|NUMERO)\s*:?\s*(\d{1,12})")
_SERVICE_LABELS = ("VALOR TOTAL DA PRESTACAO", "VALOR DO SERVICO", "VALOR TOTAL DO SERVICO", "VALOR A RECEBER")
_ICMS_LABELS = ("VALOR DO ICMS", "ICMS", "VL ICMS")
_ISSUER_LABELS = ("EMITENTE", "TRANSPORTADOR", "RAZAO SOCIAL DO EMITENTE")
_TAKER_LABELS = ("TOMADOR", "TOMADOR DO SERVICO")
_SENDER_LABELS = ("REMETENTE",)
_RECIPIENT_LABELS = ("DESTINATARIO",)


def _xml_text(root: ElementTree.Element, path: str) -> str | None:
    """Busca por tag ignorando namespace."""
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag == path and element.text and element.text.strip():
            return element.text.strip()
    return None


def _xml_nested(root: ElementTree.Element, parent_tag: str, child_tag: str) -> str | None:
    """Busca `child_tag` dentro do primeiro `parent_tag` encontrado."""
    for element in root.iter():
        if element.tag.split("}")[-1] != parent_tag:
            continue
        for child in element.iter():
            if child.tag.split("}")[-1] == child_tag and child.text and child.text.strip():
                return child.text.strip()
    return None


class CteExtractor(BaseExtractor):
    """CT-e — número, chave, emissor, tomador, valor do serviço e ICMS."""

    name = "cte"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        if file_path.suffix.lower() == ".xml":
            parsed = self._extract_from_xml(file_path, text)
            if parsed is not None:
                return parsed
        return self._extract_from_text(text)

    # ------------------------------------------------------------------ #

    def _extract_from_xml(self, file_path: Path, text: str) -> ExtractionResult | None:
        try:
            root = ElementTree.fromstring(text) if text else ElementTree.parse(file_path).getroot()
        except ElementTree.ParseError:
            return None

        result = self._result(raw_text=text)

        number = _xml_text(root, "nCT")
        access_key = _xml_text(root, "chCTe")
        if not access_key:
            for element in root.iter():
                key = element.attrib.get("Id", "")
                match = _ACCESS_KEY.search(key)
                if match:
                    access_key = match.group(1)
                    break

        issue_raw = _xml_text(root, "dhEmi") or _xml_text(root, "dEmi")
        issue_date = None
        if issue_raw:
            try:
                from datetime import datetime

                issue_date = datetime.fromisoformat(issue_raw.replace("Z", "+00:00")).date()
            except ValueError:
                issue_date = parse_date_br(issue_raw)

        service_amount = self._to_float(_xml_text(root, "vTPrest") or _xml_text(root, "vRec"))
        icms_amount = self._to_float(_xml_text(root, "vICMS"))

        issuer = _xml_nested(root, "emit", "xNome")
        taker = (
            _xml_nested(root, "toma", "xNome")
            or _xml_nested(root, "toma3", "xNome")
            or _xml_nested(root, "toma4", "xNome")
        )
        sender = _xml_nested(root, "rem", "xNome")
        recipient = _xml_nested(root, "dest", "xNome")
        origin = _xml_text(root, "xMunIni")
        destination = _xml_text(root, "xMunFim")

        result.structured = {
            "cte_number": number,
            "access_key": access_key,
            "issue_datetime": issue_raw,
            "issuer": issuer,
            "taker": taker,
            "sender": sender,
            "recipient": recipient,
            "service_amount": service_amount,
            "icms_amount": icms_amount,
            "origin_city": origin,
            "destination_city": destination,
            "source": "xml",
        }
        result.document_date = issue_date
        result.amount = service_amount
        result.counterparty = issuer
        result.document_number = number or access_key

        if service_amount is None:
            result.add_warning("Valor da prestação não encontrado no XML.")
        filled = sum(1 for value in (number, access_key, issuer, service_amount, issue_date) if value)
        result.confidence = round(filled / 5, 2)
        return result

    # ------------------------------------------------------------------ #

    def _extract_from_text(self, text: str) -> ExtractionResult:
        metadata = extract_common_metadata(text)
        result = self._result(raw_text=text)
        normalized = normalize(text)

        access_key = None
        key_match = _ACCESS_KEY.search(re.sub(r"\s", "", text))
        if key_match:
            access_key = key_match.group(1)

        number = None
        number_match = _CTE_NUMBER.search(normalized)
        if number_match:
            number = number_match.group(1)
        elif access_key:
            # Posições 26-34 da chave de acesso carregam o número do CT-e.
            number = access_key[25:34].lstrip("0") or None

        service_amount = find_labeled_amount(text, _SERVICE_LABELS) or metadata["amount"]
        icms_amount = find_labeled_amount(text, _ICMS_LABELS)

        from core.extractors.pix_extractor import _find_name_after_label

        issuer = _find_name_after_label(text, _ISSUER_LABELS)
        taker = _find_name_after_label(text, _TAKER_LABELS)
        sender = _find_name_after_label(text, _SENDER_LABELS)
        recipient = _find_name_after_label(text, _RECIPIENT_LABELS)

        result.structured = {
            "cte_number": number,
            "access_key": access_key,
            "issue_datetime": metadata["document_date"].isoformat() if metadata["document_date"] else None,
            "issuer": issuer,
            "taker": taker,
            "sender": sender,
            "recipient": recipient,
            "service_amount": service_amount,
            "icms_amount": icms_amount,
            "origin_city": None,
            "destination_city": None,
            "source": "pdf",
        }
        result.document_date = metadata["document_date"]
        result.amount = service_amount
        result.counterparty = issuer
        result.document_number = number or access_key

        if service_amount is None:
            result.add_warning("Valor do serviço não identificado no CT-e.")
        if issuer is None:
            result.add_warning("Emitente não identificado no CT-e.")

        filled = sum(
            1 for value in (number, access_key, issuer, service_amount, metadata["document_date"]) if value
        )
        result.confidence = round(filled / 5, 2)
        return result

    @staticmethod
    def _to_float(raw: str | None) -> float | None:
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            from core.documents.metadata_extractor import parse_amount_br

            return parse_amount_br(raw)
