"""Classificador documental por regras (Tarefa 3.3).

Pontua o texto contra as assinaturas de cada tipo. Abaixo da confiança mínima o
documento vai para OUTRO — nunca é forçado a um tipo (PRD 8.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core.config import get_settings
from core.constants import DocumentType
from core.documents.document_types import SIGNATURES, TypeSignature
from core.documents.metadata_extractor import (
    competence_from_date,
    find_dates,
    normalize,
)

#: Pesos por categoria de pista.
_STRONG_WEIGHT = 0.45
_WEAK_WEIGHT = 0.10
_FILENAME_WEIGHT = 0.25
#: Bônus quando o nome do arquivo é corroborado por pistas no conteúdo — o nome
#: sozinho nunca basta para classificar.
_FILENAME_CORROBORATION_BONUS = 0.25
_MIN_WEAK_HITS_FOR_CORROBORATION = 2
_NEGATIVE_PENALTY = 0.35

#: Teto de confiança. Um classificador por regras não alega certeza absoluta;
#: o limite também mantém qualquer threshold configurável acima dele efetivo.
_MAX_CONFIDENCE = 0.98

#: Termos no nome do arquivo que reforçam um tipo.
_FILENAME_HINTS: dict[str, tuple[str, ...]] = {
    DocumentType.COMPROVANTE_PIX: ("PIX", "COMPROVANTE"),
    DocumentType.COMPROVANTE_TED: ("TED",),
    DocumentType.COMPROVANTE_BOLETO: ("BOLETO", "TITULO"),
    DocumentType.EXTRATO_BANCARIO: ("EXTRATO",),
    DocumentType.CONTAS_PAGAS: ("CONTASPAGAS", "CONTAS PAGAS", "CONTAS_PAGAS", "PAGAMENTOS"),
    DocumentType.FATURAMENTO: ("FATURAMENTO", "FATURA"),
    DocumentType.NOTA_FISCAL: ("NF", "NFE", "NFSE", "NOTAFISCAL", "NOTA_FISCAL", "DANFE"),
    DocumentType.CTE: ("CTE", "CT-E", "DACTE"),
    DocumentType.PLANILHA: ("PLANILHA",),
}


@dataclass(frozen=True)
class ClassificationResult:
    """Saída do classificador documental (Arquitetura 7.2)."""

    document_type: str
    confidence: float
    reason: str
    document_date: date | None = None
    competence_year: int | None = None
    competence_month: int | None = None
    scores: dict[str, float] | None = None

    @property
    def is_unknown(self) -> bool:
        return self.document_type == DocumentType.OUTRO


def _score_signature(
    signature: TypeSignature,
    normalized_text: str,
    normalized_filename: str,
    extension: str,
) -> tuple[float, list[str]]:
    """Pontuação de um tipo e as pistas que a justificam."""
    if signature.extensions and extension not in signature.extensions:
        return 0.0, []

    score = signature.extra_weight
    evidence: list[str] = []

    for term in signature.strong:
        if term in normalized_text:
            score += _STRONG_WEIGHT
            evidence.append(term)

    weak_hits = [term for term in signature.weak if term in normalized_text]
    if weak_hits:
        score += _WEAK_WEIGHT * len(weak_hits)
        evidence.extend(weak_hits[:4])

    for hint in _FILENAME_HINTS.get(signature.document_type, ()):
        if hint in normalized_filename:
            score += _FILENAME_WEIGHT
            evidence.append(f"nome do arquivo contém '{hint}'")
            if len(weak_hits) >= _MIN_WEAK_HITS_FOR_CORROBORATION:
                score += _FILENAME_CORROBORATION_BONUS
            break

    for term in signature.negative:
        if term in normalized_text:
            score -= _NEGATIVE_PENALTY
            evidence.append(f"penalizado por '{term}'")

    return max(score, 0.0), evidence


def classify_document(
    *,
    file_name: str,
    extension: str,
    text: str,
    min_confidence: float | None = None,
) -> ClassificationResult:
    """Classifica um documento a partir do texto extraído.

    Args:
        min_confidence: limite abaixo do qual o resultado vira OUTRO.
            Padrão: `MIN_CLASSIFICATION_CONFIDENCE` do .env (0.70).
    """
    threshold = (
        min_confidence
        if min_confidence is not None
        else get_settings().min_classification_confidence
    )

    normalized_text = normalize(text or "")
    normalized_filename = normalize(file_name)
    extension = extension.lower()

    dates = find_dates(text or "")
    document_date = dates[0] if dates else None
    year, month = competence_from_date(document_date)

    if not normalized_text:
        return ClassificationResult(
            document_type=DocumentType.OUTRO,
            confidence=0.0,
            reason="Documento sem texto legível para classificação.",
            document_date=document_date,
            competence_year=year,
            competence_month=month,
            scores={},
        )

    scores: dict[str, float] = {}
    evidences: dict[str, list[str]] = {}
    for signature in SIGNATURES:
        score, evidence = _score_signature(
            signature, normalized_text, normalized_filename, extension
        )
        if score > 0:
            # Comprovantes compartilham assinaturas; fica o maior score do grupo.
            scores[signature.document_type] = max(scores.get(signature.document_type, 0.0), score)
            evidences[signature.document_type] = evidence

    if not scores:
        return ClassificationResult(
            document_type=DocumentType.OUTRO,
            confidence=0.0,
            reason="Nenhuma assinatura de tipo documental reconhecida no conteúdo.",
            document_date=document_date,
            competence_year=year,
            competence_month=month,
            scores={},
        )

    best_type = max(scores, key=lambda key: scores[key])
    best_score = min(scores[best_type], _MAX_CONFIDENCE)

    if best_score < threshold:
        return ClassificationResult(
            document_type=DocumentType.OUTRO,
            confidence=round(best_score, 2),
            reason=(
                f"Melhor hipótese foi {best_type} com confiança {best_score:.2f}, "
                f"abaixo do mínimo de {threshold:.2f}. Enviado para revisão manual."
            ),
            document_date=document_date,
            competence_year=year,
            competence_month=month,
            scores={k: round(v, 2) for k, v in scores.items()},
        )

    hits = ", ".join(evidences.get(best_type, [])[:5]) or "assinaturas gerais"
    return ClassificationResult(
        document_type=best_type,
        confidence=round(best_score, 2),
        reason=f"Classificado como {best_type} por: {hits}.",
        document_date=document_date,
        competence_year=year,
        competence_month=month,
        scores={k: round(v, 2) for k, v in scores.items()},
    )


def classify_file(file_path: str | Path, text: str) -> ClassificationResult:
    """Atalho de `classify_document` a partir do caminho do arquivo."""
    path = Path(file_path)
    return classify_document(file_name=path.name, extension=path.suffix.lower(), text=text)
