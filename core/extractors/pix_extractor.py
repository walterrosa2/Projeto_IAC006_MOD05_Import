"""Extrator de comprovantes PIX/TED/boleto (Arquitetura 9.2).

Comprovantes bancários organizam pagador e favorecido em **seções**
(`TRANSFERIDO POR` … `TRANSFERIDO PARA`, ou `Pagador` … `Favorecido`), com os
dados em linhas rotuladas dentro de cada uma. Procurar um rótulo solto e pegar
a linha seguinte erra o alvo: em `RECIBO DE TRANSFERÊNCIA PIX` o termo "DE"
casaria com o título, e o nome real está quatro linhas abaixo.

Por isso a extração é feita em duas etapas: primeiro delimita as seções,
depois procura os campos rotulados dentro de cada uma.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.documents.metadata_extractor import (
    extract_common_metadata,
    find_labeled_amount,
    normalize,
    normalize_document_number,
    parse_amount_br,
    parse_date_br,
)
from core.extractors.base_extractor import BaseExtractor, ExtractionResult

# --------------------------------------------------------------------------- #
# Seções
# --------------------------------------------------------------------------- #

#: Cabeçalhos que abrem a seção do pagador (quem envia o dinheiro).
_PAYER_SECTION = (
    "TRANSFERIDO POR",
    "DADOS DO PAGADOR",
    "PAGADOR",
    "DEBITADO DE",
    "CONTA DE ORIGEM",
    "ORIGEM",
    "REMETENTE",
    "QUEM PAGOU",
)

#: Cabeçalhos que abrem a seção do favorecido (quem recebe).
_BENEFICIARY_SECTION = (
    "TRANSFERIDO PARA",
    "DADOS DO FAVORECIDO",
    "DADOS DO BENEFICIARIO",
    "FAVORECIDO",
    "BENEFICIARIO",
    "CREDITADO A",
    "RECEBEDOR",
    "DESTINATARIO",
    "QUEM RECEBEU",
    "DESTINO",
)

#: Cabeçalhos de outras seções — encerram a seção anterior.
_OTHER_SECTION = ("TRANSACAO", "DADOS DA TRANSACAO", "INFORMACOES ADICIONAIS", "OBSERVACAO")

#: Rótulos de nome, em ordem de preferência. "SACADO" vem por último: em
#: pagamento de boleto o sacado é o devedor, não o credor.
_NAME_LABELS = (
    "NOME DO BENEFICIARIO",
    "NOME DO FAVORECIDO",
    "NOME DO RECEBEDOR",
    "NOME EMPRESARIAL",
    "RAZAO SOCIAL",
    "NOME",
    "NOME DO SACADO",
)

#: Rótulos de CPF/CNPJ dentro de uma seção.
_DOCUMENT_LABELS = (
    "DOCUMENTO DO BENEFICIARIO",
    "DOCUMENTO DO FAVORECIDO",
    "CPF/CNPJ",
    "CNPJ/CPF",
    "CPF / CNPJ",
    "DOCUMENTO",
    "CNPJ",
    "CPF",
)

#: Linhas estruturais que nunca são nome de pessoa/empresa.
_STRUCTURAL_LINES = re.compile(
    r"^(CONTA|CONTA CORRENTE|CONTA POUPANCA|BANCO|AG|AGENCIA|CONTA-DV|CHAVE PIX|"
    r"TIPO|INSTITUICAO|CODIGO|ISPB)\b",
)

_AMOUNT_LABELS = (
    "VALOR TRANSFERIDO",
    "VALOR DO PAGAMENTO",
    "VALOR PAGO",
    "VALOR DA TRANSFERENCIA",
    "VALOR NOMINAL",
    "VALOR TOTAL",
    "VALOR",
)

_PROOF_LABELS = (
    "NUMERO DO COMPROVANTE",
    "ID DA TRANSACAO",
    "IDENTIFICADOR",
    "AUTENTICACAO",
    "CODIGO DE AUTENTICACAO",
    "NUMERO DO DOCUMENTO",
    "CONTROLE",
    "E2E",
)

#: Data seguida de hora, tolerando "HORA:", "às", vírgula ou hífen entre elas.
_DATETIME_PATTERN = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*(?:,)?\s*(?:HORA\s*:?|[àa]s|-|\s)\s*(\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)

#: Rótulos de data do fato, em ordem de preferência.
_DATE_LABELS = ("DATA DE PAGAMENTO", "DATA DO PAGAMENTO", "TRANSFERIDO EM", "PAGO EM", "SOLICITACAO", "DATA")

MAX_NAME_LENGTH = 120
MIN_NAME_LENGTH = 3


#: Cabeçalhos de tabela que o OCR devolve e que nunca são nome de contraparte.
_TABLE_HEADER_TERMS = (
    "CNPJ / CPF",
    "CPF / CNPJ",
    "INSCRICAO MUNICIPAL",
    "NOME / NOME EMPRESARIAL",
    "RAZAO SOCIAL / NOME",
)


def _clean_name(raw: str) -> str | None:
    """Descarta restos numéricos, estruturais e cabeçalhos de tabela."""
    if not raw:
        return None
    # O OCR transcreve tabelas com ' | '; uma célula de cabeçalho não é um nome.
    if "|" in raw:
        return None
    cleaned = re.sub(r"\s+", " ", raw).strip(" :;-\t")
    if any(term in normalize(cleaned) for term in _TABLE_HEADER_TERMS):
        return None
    cleaned = re.sub(r"^(NOME|RAZAO SOCIAL)\s*:?\s*", "", cleaned, flags=re.IGNORECASE)
    if len(cleaned) < MIN_NAME_LENGTH or len(cleaned) > MAX_NAME_LENGTH:
        return None
    if _STRUCTURAL_LINES.match(normalize(cleaned)):
        return None
    letters = sum(ch.isalpha() for ch in cleaned)
    if letters < MIN_NAME_LENGTH or letters / len(cleaned) < 0.4:
        return None
    return cleaned


@dataclass(frozen=True)
class _Section:
    """Trecho de linhas pertencente ao pagador ou ao favorecido."""

    start: int
    end: int
    lines: list[str]

    def labeled_value(self, labels: tuple[str, ...]) -> str | None:
        """Valor do primeiro rótulo encontrado, na ordem de preferência dada."""
        for label in labels:
            target = normalize(label)
            for line in self.lines:
                normalized = normalize(line)
                if not normalized.startswith(target):
                    continue
                remainder = normalized[len(target) :].lstrip()
                if remainder.startswith(":"):
                    # Corta pela posição do ':' no texto original, preservando a caixa.
                    position = line.find(":")
                    if position != -1:
                        value = line[position + 1 :].strip()
                        if value:
                            return value
        return None


def _find_sections(lines: list[str]) -> tuple[_Section | None, _Section | None]:
    """Delimita as seções de pagador e favorecido.

    Cada seção começa no seu cabeçalho e termina no próximo cabeçalho conhecido.
    """
    normalized = [normalize(line) for line in lines]
    markers: list[tuple[int, str]] = []

    for index, line in enumerate(normalized):
        if not line:
            continue
        for label in _PAYER_SECTION:
            if line == normalize(label) or line.startswith(normalize(label)):
                markers.append((index, "payer"))
                break
        else:
            for label in _BENEFICIARY_SECTION:
                if line == normalize(label) or line.startswith(normalize(label)):
                    markers.append((index, "beneficiary"))
                    break
            else:
                for label in _OTHER_SECTION:
                    if line == normalize(label):
                        markers.append((index, "other"))
                        break

    if not markers:
        return None, None

    payer = beneficiary = None
    for position, (index, kind) in enumerate(markers):
        end = markers[position + 1][0] if position + 1 < len(markers) else len(lines)
        section = _Section(start=index, end=end, lines=lines[index + 1 : end])
        # Fica a primeira ocorrência de cada tipo: comprovantes repetem rótulos
        # em rodapés, e a primeira é a que carrega os dados.
        if kind == "payer" and payer is None:
            payer = section
        elif kind == "beneficiary" and beneficiary is None:
            beneficiary = section

    return payer, beneficiary


def _section_name(section: _Section | None) -> str | None:
    if section is None:
        return None
    value = section.labeled_value(_NAME_LABELS)
    if value:
        return _clean_name(value)
    # Sem rótulo de nome: primeira linha não estrutural da seção.
    for line in section.lines:
        candidate = _clean_name(line)
        if candidate:
            return candidate
    return None


def _section_document(section: _Section | None) -> str | None:
    """CPF/CNPJ da seção, preservando máscaras do próprio comprovante.

    Muitos bancos publicam o documento parcialmente oculto (`92.***.348/0001-**`).
    O valor é devolvido como está — mascarar mais não agrega, e reconstruir
    seria inventar dado.
    """
    if section is None:
        return None
    value = section.labeled_value(_DOCUMENT_LABELS)
    if not value:
        return None
    cleaned = value.strip()
    return cleaned if any(ch.isdigit() for ch in cleaned) else None


def _find_labeled_date(lines: list[str]):
    """Data do fato, preferindo rótulos explícitos de pagamento."""
    for label in _DATE_LABELS:
        target = normalize(label)
        for line in lines:
            normalized = normalize(line)
            if not normalized.startswith(target):
                continue
            parsed = parse_date_br(line)
            if parsed:
                return parsed
    return None


class PixExtractor(BaseExtractor):
    """Comprovante de PIX, TED ou pagamento de boleto."""

    name = "pix"

    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        metadata = extract_common_metadata(text)
        result = self._result(raw_text=text)

        payer_section, beneficiary_section = _find_sections(lines)

        payer = _section_name(payer_section)
        beneficiary = _section_name(beneficiary_section)
        payer_document = _section_document(payer_section)
        beneficiary_document = _section_document(beneficiary_section)

        # Sem seções identificadas, cai para os identificadores soltos do texto.
        if payer_document is None and beneficiary_document is None:
            identifiers = metadata["cnpjs"] + metadata["cpfs"]
            payer_document = identifiers[0] if identifiers else None
            beneficiary_document = identifiers[1] if len(identifiers) > 1 else None

        amount = find_labeled_amount(text, _AMOUNT_LABELS) or metadata["amount"]

        document_date = _find_labeled_date(lines) or metadata["document_date"]
        transfer_datetime: str | None = None
        match = _DATETIME_PATTERN.search(text)
        if match:
            parsed = parse_date_br(match.group(1))
            if parsed:
                document_date = document_date or parsed
                transfer_datetime = f"{parsed.isoformat()}T{match.group(2)}"

        proof_number: str | None = None
        for label in _PROOF_LABELS:
            value = self._value_after_label(lines, label)
            if value:
                proof_number = normalize_document_number(value)
                break

        result.structured = {
            "proof_number": proof_number,
            "transfer_datetime": transfer_datetime,
            "payer_name": payer,
            "payer_cnpj_cpf": payer_document,
            "beneficiary_name": beneficiary,
            "beneficiary_cnpj_cpf": beneficiary_document,
            "amount": amount,
        }
        result.document_date = document_date
        result.amount = amount
        # A contraparte de um pagamento é quem recebe.
        result.counterparty = beneficiary or payer
        result.document_number = proof_number

        if amount is None:
            result.add_warning("Valor não identificado no comprovante.")
        if document_date is None:
            result.add_warning("Data não identificada no comprovante.")
        if beneficiary is None:
            result.add_warning("Favorecido não identificado.")

        filled = sum(1 for value in (amount, document_date, beneficiary, proof_number) if value)
        result.confidence = round(filled / 4, 2)
        return result

    @staticmethod
    def _value_after_label(lines: list[str], label: str) -> str | None:
        """Valor na mesma linha do rótulo ou, se a linha só tiver o rótulo, na seguinte."""
        target = normalize(label)
        for index, line in enumerate(lines):
            normalized = normalize(line)
            if not normalized.startswith(target):
                continue
            position = line.find(":")
            if position != -1:
                value = line[position + 1 :].strip()
                if value:
                    return value
            if index + 1 < len(lines):
                nxt = lines[index + 1].strip()
                if nxt and not nxt.endswith(":"):
                    return nxt
        return None


def _find_name_after_label(text: str, labels: tuple[str, ...]) -> str | None:
    """Nome após um rótulo, na mesma linha ou na seguinte.

    Mantido para os extratores de contas pagas, faturamento e CT-e, cujos
    documentos não usam a estrutura de seções dos comprovantes bancários.
    """
    lines = [line.strip() for line in text.splitlines()]
    normalized_lines = [normalize(line) for line in lines]

    for index, norm_line in enumerate(normalized_lines):
        for label in labels:
            target = normalize(label).rstrip(":")
            if not norm_line.startswith(target) and f" {target}" not in norm_line:
                continue

            position = norm_line.find(target) + len(target)
            remainder = lines[index][position:].lstrip(" :\t-")
            candidate = _clean_name(remainder)
            if candidate:
                return candidate

            if index + 1 < len(lines):
                candidate = _clean_name(lines[index + 1])
                if candidate:
                    return candidate
    return None


__all__ = ["PixExtractor", "_clean_name", "_find_name_after_label", "parse_amount_br"]
