"""Constantes de domínio: tipos documentais, status e mapeamento de pastas."""

from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    """Tipos documentais reconhecidos pela esteira (PRD seção 9)."""

    COMPROVANTE_PIX = "COMPROVANTE_PIX"
    COMPROVANTE_TED = "COMPROVANTE_TED"
    COMPROVANTE_BOLETO = "COMPROVANTE_BOLETO"
    EXTRATO_BANCARIO = "EXTRATO_BANCARIO"
    FATURAMENTO = "FATURAMENTO"
    CONTAS_PAGAS = "CONTAS_PAGAS"
    NOTA_FISCAL = "NOTA_FISCAL"
    CTE = "CTE"
    PLANILHA = "PLANILHA"
    OUTRO = "OUTRO"
    ERROR = "ERROR"
    DUPLICATE = "DUPLICATE"


class DocumentStatus(StrEnum):
    """Estados do documento processado (Arquitetura seção 6.1)."""

    NEW = "NEW"
    CLASSIFIED = "CLASSIFIED"
    COPIED_TO_DESTINATION = "COPIED_TO_DESTINATION"
    EXTRACTED = "EXTRACTED"
    ENTRY_GENERATED = "ENTRY_GENERATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    EXPORTED = "EXPORTED"


class EntryStatus(StrEnum):
    """Estados do lançamento contábil (Arquitetura seção 6.2)."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    CORRECTED_APPROVED = "CORRECTED_APPROVED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    ERROR = "ERROR"
    EXPORTED = "EXPORTED"


#: Únicos status que podem ser exportados para o Domínio (RNF03).
EXPORTABLE_ENTRY_STATUSES: frozenset[str] = frozenset(
    {EntryStatus.APPROVED, EntryStatus.CORRECTED_APPROVED}
)


class ErrorType(StrEnum):
    """Taxonomia de erros técnicos gravados junto ao documento (PRD 8.3)."""

    ARQUIVO_CORROMPIDO = "ARQUIVO_CORROMPIDO"
    PDF_SEM_TEXTO = "PDF_SEM_TEXTO"
    PDF_PROTEGIDO = "PDF_PROTEGIDO"
    EXTRACAO_FALHOU = "EXTRACAO_FALHOU"
    IA_INDISPONIVEL = "IA_INDISPONIVEL"
    IA_RETORNO_INVALIDO = "IA_RETORNO_INVALIDO"
    DADOS_OBRIGATORIOS_AUSENTES = "DADOS_OBRIGATORIOS_AUSENTES"
    CONTA_INEXISTENTE = "CONTA_INEXISTENTE"
    ERRO_INESPERADO = "ERRO_INESPERADO"


#: Tipo documental -> nome da pasta de destino (Arquitetura 8.1).
DOCUMENT_TYPE_TO_FOLDER: dict[str, str] = {
    DocumentType.COMPROVANTE_PIX: "COMPROVANTES",
    DocumentType.COMPROVANTE_TED: "COMPROVANTES",
    DocumentType.COMPROVANTE_BOLETO: "COMPROVANTES",
    DocumentType.EXTRATO_BANCARIO: "EXTRATOS",
    DocumentType.FATURAMENTO: "FATURAMENTO",
    DocumentType.PLANILHA: "PLANILHAS",
    DocumentType.NOTA_FISCAL: "NOTAS_FISCAIS",
    DocumentType.CTE: "CTES",
    DocumentType.CONTAS_PAGAS: "CONTAS_PAGAS",
    DocumentType.OUTRO: "OUTROS",
    DocumentType.ERROR: "ERROS",
    DocumentType.DUPLICATE: "DUPLICADOS",
}

#: Todas as pastas criadas por competência.
ALL_DESTINATION_FOLDERS: tuple[str, ...] = (
    "COMPROVANTES",
    "EXTRATOS",
    "FATURAMENTO",
    "PLANILHAS",
    "NOTAS_FISCAIS",
    "CTES",
    "CONTAS_PAGAS",
    "OUTROS",
    "ERROS",
    "DUPLICADOS",
)

#: Tipos que, por si só, devem gerar lançamento contábil (PRD seção 9).
TYPES_THAT_GENERATE_ENTRY: frozenset[str] = frozenset(
    {
        DocumentType.FATURAMENTO,
        DocumentType.CONTAS_PAGAS,
        DocumentType.NOTA_FISCAL,
        DocumentType.CTE,
    }
)

#: Tipos que geram lançamento só na ausência de documento base melhor (PRD 10.1).
TYPES_CONDITIONAL_ENTRY: frozenset[str] = frozenset(
    {
        DocumentType.COMPROVANTE_PIX,
        DocumentType.COMPROVANTE_TED,
        DocumentType.COMPROVANTE_BOLETO,
        DocumentType.EXTRATO_BANCARIO,
    }
)

#: Hierarquia de documento base (PRD 10.1). Menor número = maior prioridade.
DOCUMENT_BASE_PRIORITY: dict[str, int] = {
    DocumentType.NOTA_FISCAL: 1,
    DocumentType.CTE: 1,
    DocumentType.FATURAMENTO: 1,
    DocumentType.CONTAS_PAGAS: 1,
    DocumentType.EXTRATO_BANCARIO: 2,
    DocumentType.COMPROVANTE_PIX: 3,
    DocumentType.COMPROVANTE_TED: 3,
    DocumentType.COMPROVANTE_BOLETO: 3,
    DocumentType.PLANILHA: 4,
    DocumentType.OUTRO: 9,
}

MONTH_NAMES_PT: dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

#: Extensões que a esteira tenta processar.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".xml", ".xlsx", ".xls", ".csv", ".txt"}
)

#: Colunas do layout de importação do Domínio Contábil (PRD seção 19).
DOMINIO_COLUMNS: tuple[str, ...] = (
    "Data",
    "Cód. Conta Debito",
    "Cód. Conta Credito",
    "Valor",
    "Cód. Histórico",
    "Complemento Histórico",
    "Inicia Lote",
    "Código Matriz/Filial",
    "Centro de Custo Débito",
    "Centro de Custo Crédito",
)

PRIORITIES: tuple[str, ...] = ("Alta", "Média", "Baixa")
