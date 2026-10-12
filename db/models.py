"""Modelos SQLAlchemy — 12 entidades da Arquitetura Técnica seção 5."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.constants import DocumentStatus, EntryStatus


class Base(DeclarativeBase):
    """Base declarativa comum."""


class TimestampMixin:
    """created_at/updated_at preenchidos pelo banco."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Company(Base, TimestampMixin):
    """Empresa/cliente do escritório contábil (PRD seção 11)."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    input_folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    destination_folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    responsible_accountant: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    branch_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Ativa", nullable=False)

    accounts: Mapped[list[ChartOfAccount]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    histories: Mapped[list[StandardHistory]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    cost_centers: Mapped[list[CostCenter]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    guidelines: Mapped[list[CompanyGuideline]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    examples: Mapped[list[AccountingExample]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class ChartOfAccount(Base, TimestampMixin):
    """Plano de contas por empresa (PRD seção 12)."""

    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "account_code", name="uq_account_per_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(60))
    accepts_entries: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship(back_populates="accounts")


class StandardHistory(Base, TimestampMixin):
    """Histórico padrão usado na exportação Domínio (PRD RF03)."""

    __tablename__ = "standard_histories"
    __table_args__ = (
        UniqueConstraint("company_id", "history_code", name="uq_history_per_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    history_code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship(back_populates="histories")


class CostCenter(Base, TimestampMixin):
    """Centro de custo por empresa (PRD RF04)."""

    __tablename__ = "cost_centers"
    __table_args__ = (
        UniqueConstraint("company_id", "cost_center_code", name="uq_cost_center_per_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_center_code: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship(back_populates="cost_centers")


class CompanyGuideline(Base, TimestampMixin):
    """Orientação contábil textual por empresa (PRD seção 13)."""

    __tablename__ = "company_guidelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    guideline_text: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_document_type: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(10), default="Média", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120))

    company: Mapped[Company] = relationship(back_populates="guidelines")


class AccountingExample(Base, TimestampMixin):
    """Exemplo concreto de lançamento — memória operacional da IA (PRD seção 14)."""

    __tablename__ = "accounting_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    base_document: Mapped[str] = mapped_column(String(200), nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    keywords: Mapped[str | None] = mapped_column(Text)
    document_excerpt: Mapped[str | None] = mapped_column(Text)
    debit_account_code: Mapped[str] = mapped_column(String(40), nullable=False)
    credit_account_code: Mapped[str] = mapped_column(String(40), nullable=False)
    history_code: Mapped[str | None] = mapped_column(String(20))
    history_complement_template: Mapped[str] = mapped_column(Text, nullable=False)
    debit_cost_center_code: Mapped[str | None] = mapped_column(String(40))
    credit_cost_center_code: Mapped[str | None] = mapped_column(String(40))
    accounting_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="Média", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120))

    company: Mapped[Company] = relationship(back_populates="examples")


class ProcessedDocument(Base, TimestampMixin):
    """Documento que passou pela esteira (Arquitetura 5.7)."""

    __tablename__ = "processed_documents"
    __table_args__ = (
        Index("ix_doc_company_competence", "company_id", "competence_year", "competence_month"),
        Index("ix_doc_company_hash", "company_id", "file_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    stored_file_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    document_date: Mapped[date | None] = mapped_column(Date)
    competence_year: Mapped[int | None] = mapped_column(Integer)
    competence_month: Mapped[int | None] = mapped_column(Integer)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    document_number: Mapped[str | None] = mapped_column(String(80))
    amount: Mapped[float | None] = mapped_column(Float)
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(
        String(30), default=DocumentStatus.NEW, nullable=False, index=True
    )
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_documents.id", ondelete="SET NULL")
    )
    duplicate_reason: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship()
    extracted: Mapped[ExtractedData | None] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    entries: Mapped[list[AccountingEntry]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ExtractedData(Base):
    """Texto bruto e JSON estruturado extraídos de um documento (Arquitetura 5.8)."""

    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("processed_documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured_json: Mapped[str | None] = mapped_column(Text)
    extractor_name: Mapped[str | None] = mapped_column(String(80))
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    document: Mapped[ProcessedDocument] = relationship(back_populates="extracted")


class AccountingEntry(Base, TimestampMixin):
    """Lançamento contábil sugerido pela IA e revisado pelo contador (Arquitetura 5.9)."""

    __tablename__ = "accounting_entries"
    __table_args__ = (Index("ix_entry_company_status", "company_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("processed_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_date: Mapped[date | None] = mapped_column(Date)
    debit_account_code: Mapped[str | None] = mapped_column(String(40))
    credit_account_code: Mapped[str | None] = mapped_column(String(40))
    amount: Mapped[float | None] = mapped_column(Float)
    history_code: Mapped[str | None] = mapped_column(String(20))
    history_complement: Mapped[str | None] = mapped_column(Text)
    batch_start: Mapped[str | None] = mapped_column(String(10))
    branch_code: Mapped[str | None] = mapped_column(String(20))
    debit_cost_center_code: Mapped[str | None] = mapped_column(String(40))
    credit_cost_center_code: Mapped[str | None] = mapped_column(String(40))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_justification: Mapped[str | None] = mapped_column(Text)
    ai_warnings: Mapped[str | None] = mapped_column(Text)
    base_document_reason: Mapped[str | None] = mapped_column(Text)
    validation_issues: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), default=EntryStatus.PENDING_REVIEW, nullable=False, index=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    export_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("export_batches.id", ondelete="SET NULL")
    )

    document: Mapped[ProcessedDocument] = relationship(back_populates="entries")
    company: Mapped[Company] = relationship()
    corrections: Mapped[list[EntryCorrection]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class EntryCorrection(Base):
    """Correção humana de um lançamento + orientação corretiva (PRD seção 15)."""

    __tablename__ = "entry_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_documents.id", ondelete="SET NULL")
    )
    document_type: Mapped[str | None] = mapped_column(String(40), index=True)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    original_json: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_json: Mapped[str] = mapped_column(Text, nullable=False)
    corrective_guidance: Mapped[str | None] = mapped_column(Text)
    convert_to_example: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    converted_example_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounting_examples.id", ondelete="SET NULL")
    )
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    entry: Mapped[AccountingEntry] = relationship(back_populates="corrections")


class ExportBatch(Base):
    """Lote exportado para o Domínio (Arquitetura 5.11)."""

    __tablename__ = "export_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_year: Mapped[int | None] = mapped_column(Integer)
    period_month: Mapped[int | None] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    exported_by: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="CONCLUIDO", nullable=False)

    company: Mapped[Company] = relationship()
    items: Mapped[list[ExportBatchItem]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class ExportBatchItem(Base):
    """Vínculo lote <-> lançamento exportado (Arquitetura 5.12)."""

    __tablename__ = "export_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    export_batch_id: Mapped[int] = mapped_column(
        ForeignKey("export_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    batch: Mapped[ExportBatch] = relationship(back_populates="items")
