"""Contrato comum dos extratores de dados."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class ExtractionResult:
    """Saída padronizada de qualquer extrator.

    `structured` carrega os campos específicos do tipo documental; os campos
    promovidos (`document_date`, `amount`, `counterparty`, `document_number`)
    são os que a esteira persiste em `processed_documents`.
    """

    extractor_name: str
    raw_text: str = ""
    structured: dict[str, Any] = field(default_factory=dict)
    document_date: date | None = None
    amount: float | None = None
    counterparty: str | None = None
    document_number: str | None = None
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def as_structured_payload(self) -> dict[str, Any]:
        """JSON gravado em `extracted_data.structured_json`."""
        return {
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "amount": self.amount,
            "counterparty": self.counterparty,
            "document_number": self.document_number,
            "extractor": self.extractor_name,
            "confidence": self.confidence,
            "warnings": self.warnings,
            **self.structured,
        }


class BaseExtractor(ABC):
    """Extrator de um tipo documental."""

    name: str = "base"

    @abstractmethod
    def extract(self, file_path: Path, text: str) -> ExtractionResult:
        """Extrai os campos do documento.

        Args:
            file_path: caminho do arquivo original (para extratores que releem o binário).
            text: texto já extraído pelo leitor de PDF/planilha.
        """

    def _result(self, **kwargs: Any) -> ExtractionResult:
        return ExtractionResult(extractor_name=self.name, **kwargs)
