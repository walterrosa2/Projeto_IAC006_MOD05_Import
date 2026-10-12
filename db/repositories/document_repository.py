"""Acesso a dados de documentos processados e dados extraídos."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import func, select

from core.constants import DocumentStatus
from db.database import session_scope
from db.models import ExtractedData, ProcessedDocument


def create_document(data: dict) -> ProcessedDocument:
    with session_scope() as session:
        document = ProcessedDocument(**data)
        session.add(document)
        session.flush()
        return document


def get_document(document_id: int) -> ProcessedDocument | None:
    with session_scope() as session:
        return session.get(ProcessedDocument, document_id)


def update_document(document_id: int, data: dict) -> ProcessedDocument | None:
    with session_scope() as session:
        document = session.get(ProcessedDocument, document_id)
        if document is None:
            return None
        for key, value in data.items():
            setattr(document, key, value)
        session.flush()
        return document


def find_by_hash(company_id: int, file_hash: str) -> ProcessedDocument | None:
    """Primeiro documento não-duplicado com o mesmo hash (CA04)."""
    with session_scope() as session:
        return session.scalar(
            select(ProcessedDocument)
            .where(
                ProcessedDocument.company_id == company_id,
                ProcessedDocument.file_hash == file_hash,
                ProcessedDocument.processing_status != DocumentStatus.DUPLICATE,
            )
            .order_by(ProcessedDocument.id)
        )


def find_by_business_key(
    company_id: int,
    *,
    document_date: date | None,
    amount: float | None,
    counterparty: str | None,
    document_number: str | None,
    document_type: str | None,
    exclude_id: int | None = None,
) -> ProcessedDocument | None:
    """Documento equivalente pelos dados essenciais — duplicidade de fato contábil.

    Exige data e valor; combina com contraparte OU número do documento.
    """
    if document_date is None or amount is None:
        return None
    if not counterparty and not document_number:
        return None

    with session_scope() as session:
        stmt = select(ProcessedDocument).where(
            ProcessedDocument.company_id == company_id,
            ProcessedDocument.document_date == document_date,
            ProcessedDocument.processing_status != DocumentStatus.DUPLICATE,
            func.abs(ProcessedDocument.amount - amount) < 0.01,
        )
        if document_type:
            stmt = stmt.where(ProcessedDocument.document_type == document_type)
        if document_number:
            stmt = stmt.where(ProcessedDocument.document_number == document_number)
        elif counterparty:
            stmt = stmt.where(ProcessedDocument.counterparty == counterparty)
        if exclude_id is not None:
            stmt = stmt.where(ProcessedDocument.id != exclude_id)
        return session.scalar(stmt.order_by(ProcessedDocument.id))


def find_related_documents(
    company_id: int,
    *,
    document_date: date | None,
    amount: float | None,
    exclude_id: int | None = None,
    day_tolerance: int = 3,
) -> list[ProcessedDocument]:
    """Documentos do mesmo valor em datas próximas — candidatos ao mesmo fato contábil.

    Alimenta a hierarquia de documento base (PRD 10).
    """
    if document_date is None or amount is None:
        return []
    from datetime import timedelta

    start = document_date - timedelta(days=day_tolerance)
    end = document_date + timedelta(days=day_tolerance)

    with session_scope() as session:
        stmt = select(ProcessedDocument).where(
            ProcessedDocument.company_id == company_id,
            ProcessedDocument.document_date >= start,
            ProcessedDocument.document_date <= end,
            func.abs(ProcessedDocument.amount - amount) < 0.01,
            ProcessedDocument.processing_status.notin_(
                [DocumentStatus.DUPLICATE, DocumentStatus.ERROR]
            ),
        )
        if exclude_id is not None:
            stmt = stmt.where(ProcessedDocument.id != exclude_id)
        return list(session.scalars(stmt.order_by(ProcessedDocument.id)))


def search_documents(
    *,
    company_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    document_type: str | None = None,
    status: str | None = None,
    file_name: str | None = None,
    limit: int = 500,
) -> list[ProcessedDocument]:
    """Consulta da tela Documentos Processados (RF17)."""
    with session_scope() as session:
        stmt = select(ProcessedDocument)
        if company_id:
            stmt = stmt.where(ProcessedDocument.company_id == company_id)
        if year:
            stmt = stmt.where(ProcessedDocument.competence_year == year)
        if month:
            stmt = stmt.where(ProcessedDocument.competence_month == month)
        if document_type:
            stmt = stmt.where(ProcessedDocument.document_type == document_type)
        if status:
            stmt = stmt.where(ProcessedDocument.processing_status == status)
        if file_name:
            stmt = stmt.where(ProcessedDocument.original_file_name.ilike(f"%{file_name}%"))
        return list(session.scalars(stmt.order_by(ProcessedDocument.id.desc()).limit(limit)))


def count_documents_by_status(company_id: int | None = None) -> dict[str, int]:
    """Contadores do dashboard."""
    with session_scope() as session:
        stmt = select(ProcessedDocument.processing_status, func.count(ProcessedDocument.id))
        if company_id:
            stmt = stmt.where(ProcessedDocument.company_id == company_id)
        return dict(session.execute(stmt.group_by(ProcessedDocument.processing_status)).all())


# --------------------------------------------------------------------------- #
# Dados extraídos
# --------------------------------------------------------------------------- #


def save_extracted_data(
    document_id: int,
    *,
    raw_text: str | None,
    structured: dict[str, Any] | None,
    extractor_name: str | None,
    confidence: float | None = None,
) -> ExtractedData:
    """Grava (ou substitui) o resultado da extração de um documento."""
    payload = json.dumps(structured, ensure_ascii=False, default=str) if structured else None
    with session_scope() as session:
        record = session.scalar(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )
        if record is None:
            record = ExtractedData(document_id=document_id)
            session.add(record)
        record.raw_text = raw_text
        record.structured_json = payload
        record.extractor_name = extractor_name
        record.extraction_confidence = confidence
        session.flush()
        return record


def get_extracted_data(document_id: int) -> ExtractedData | None:
    with session_scope() as session:
        return session.scalar(
            select(ExtractedData).where(ExtractedData.document_id == document_id)
        )


def get_structured_data(document_id: int) -> dict[str, Any]:
    """JSON estruturado já desserializado ({} quando não houver)."""
    record = get_extracted_data(document_id)
    if record is None or not record.structured_json:
        return {}
    try:
        return json.loads(record.structured_json)
    except json.JSONDecodeError:
        return {}
