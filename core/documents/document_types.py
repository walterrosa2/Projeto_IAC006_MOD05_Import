"""Assinaturas textuais de cada tipo documental e roteamento para o extrator."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.constants import DocumentType


@dataclass(frozen=True)
class TypeSignature:
    """Pistas que identificam um tipo documental em texto normalizado.

    - `strong`: termo praticamente exclusivo do tipo (peso alto);
    - `weak`: termo de apoio, comum a vários documentos (peso baixo);
    - `negative`: termo que desqualifica o tipo;
    - `extensions`: quando preenchido, restringe o tipo a essas extensões.
    """

    document_type: str
    strong: tuple[str, ...] = ()
    weak: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    label: str = ""
    extra_weight: float = 0.0
    keywords: tuple[str, ...] = field(default=(), repr=False)


#: Pistas estruturais comuns aos comprovantes bancários, independentes do banco.
#: Sozinhas não identificam o tipo — apenas reforçam quando há um termo forte.
_COMPROVANTE_BANCARIO_WEAK: tuple[str, ...] = (
    "TRANSFERIDO POR",
    "TRANSFERIDO PARA",
    "TRANSFERIDO EM",
    "VALOR TRANSFERIDO",
    "NUMERO DO COMPROVANTE",
    "CONTA-DV",
    "DEBITO REALIZADO COM SUCESSO",
)

#: Ordem importa apenas para desempate humano; a pontuação decide.
SIGNATURES: tuple[TypeSignature, ...] = (
    TypeSignature(
        document_type=DocumentType.COMPROVANTE_PIX,
        label="Comprovante PIX",
        strong=(
            "COMPROVANTE DE TRANSFERENCIA PIX",
            "RECIBO DE TRANSFERENCIA PIX",
            "COMPROVANTE PIX",
            "PIX ENVIADO",
            "PIX RECEBIDO",
            "TRANSFERENCIA PIX",
            "CHAVE PIX",
        ),
        weak=("FAVORECIDO", "PAGADOR", "IDENTIFICADOR", "AUTENTICACAO", "E2E"),
        negative=("EXTRATO DE CONTA", "RELATORIO DE CONTAS PAGAS"),
    ),
    TypeSignature(
        document_type=DocumentType.COMPROVANTE_TED,
        label="Comprovante TED/DOC",
        strong=(
            "COMPROVANTE DE TED",
            "TRANSFERENCIA ELETRONICA DISPONIVEL",
            "COMPROVANTE DE DOC",
            "TED ENVIADA",
            "RECIBO DE TRANSFERENCIA TED",
            "TRANSFERENCIA TED",
        ),
        weak=(
            "FAVORECIDO",
            "PAGADOR",
            "BANCO DESTINO",
            "FINALIDADE",
            *_COMPROVANTE_BANCARIO_WEAK,
        ),
        negative=("EXTRATO DE CONTA",),
    ),
    TypeSignature(
        document_type=DocumentType.COMPROVANTE_BOLETO,
        label="Comprovante de boleto",
        strong=(
            "COMPROVANTE DE PAGAMENTO DE BOLETO",
            "PAGAMENTO DE TITULO",
            "LINHA DIGITAVEL",
            "CODIGO DE BARRAS",
            "COMPROVANTE DE PAGAMENTO",
            "PAGAMENTO REALIZADO",
        ),
        weak=(
            "CEDENTE",
            "SACADO",
            "VENCIMENTO",
            "NOSSO NUMERO",
            "VALOR NOMINAL",
            "VALOR DO DESCONTO",
            "VALOR DO JUROS",
            "VALOR PAGO",
            "DATA DE VENCIMENTO",
            "DATA DE PAGAMENTO",
            "NOME DO BENEFICIARIO",
            "NOME DO SACADO",
        ),
        negative=("RELATORIO DE CONTAS PAGAS",),
    ),
    TypeSignature(
        document_type=DocumentType.EXTRATO_BANCARIO,
        label="Extrato bancário",
        strong=(
            "EXTRATO DE CONTA CORRENTE",
            "EXTRATO BANCARIO",
            "EXTRATO CONSOLIDADO",
            "EXTRATO DE CONTA",
            "SALDO ANTERIOR",
        ),
        weak=("SALDO FINAL", "LANCAMENTOS DO PERIODO", "AGENCIA", "CONTA CORRENTE", "D/C"),
        negative=("COMPROVANTE DE TRANSFERENCIA",),
    ),
    TypeSignature(
        document_type=DocumentType.CONTAS_PAGAS,
        label="Relatório de contas pagas",
        strong=(
            "RELATORIO DE CONTAS PAGAS",
            "CONTAS PAGAS",
            "TITULOS PAGOS",
            "RELACAO DE PAGAMENTOS",
            "BAIXAS DO PERIODO",
        ),
        weak=("CREDOR", "VALOR LIQUIDO", "DATA DE BAIXA", "DESCONTO", "ACRESCIMO", "VENCIMENTO"),
    ),
    TypeSignature(
        document_type=DocumentType.FATURAMENTO,
        label="Relatório de faturamento",
        strong=(
            "RELATORIO DE FATURAMENTO",
            "FATURAMENTO DO PERIODO",
            "RELACAO DE FATURAMENTO",
            "DEMONSTRATIVO DE FATURAMENTO",
            "NOTAS EMITIDAS",
        ),
        weak=("CLIENTE", "VALOR BRUTO", "IRRF", "PCC", "ISS", "VALOR LIQUIDO", "RETENCAO"),
    ),
    TypeSignature(
        document_type=DocumentType.NOTA_FISCAL,
        label="Nota fiscal",
        strong=(
            "NOTA FISCAL DE SERVICOS ELETRONICA",
            "NFS-E",
            "NFSE",
            "DANFE",
            "NOTA FISCAL ELETRONICA",
            "DOCUMENTO AUXILIAR DA NOTA FISCAL",
        ),
        weak=("PRESTADOR DE SERVICOS", "TOMADOR DE SERVICOS", "DISCRIMINACAO DOS SERVICOS", "CFOP", "NATUREZA DA OPERACAO"),
        negative=("CONHECIMENTO DE TRANSPORTE",),
    ),
    TypeSignature(
        document_type=DocumentType.CTE,
        label="CT-e",
        strong=(
            "CONHECIMENTO DE TRANSPORTE ELETRONICO",
            "DACTE",
            "CT-E",
            "<CTE",
            "INFCTE",
        ),
        weak=("TOMADOR DO SERVICO", "REMETENTE", "DESTINATARIO", "VALOR TOTAL DA PRESTACAO", "MODAL"),
    ),
    TypeSignature(
        document_type=DocumentType.PLANILHA,
        label="Planilha auxiliar",
        strong=(),
        weak=("### ABA:", "TOTAL", "SOMA"),
        extensions=(".xlsx", ".xls", ".csv"),
        extra_weight=0.35,
    ),
)

#: Tipo documental -> classe do extrator (import tardio evita ciclo).
_EXTRACTOR_MAP: dict[str, str] = {
    DocumentType.COMPROVANTE_PIX: "core.extractors.pix_extractor:PixExtractor",
    DocumentType.COMPROVANTE_TED: "core.extractors.pix_extractor:PixExtractor",
    DocumentType.COMPROVANTE_BOLETO: "core.extractors.pix_extractor:PixExtractor",
    DocumentType.EXTRATO_BANCARIO: "core.extractors.extrato_extractor:ExtratoExtractor",
    DocumentType.CONTAS_PAGAS: "core.extractors.contas_pagas_extractor:ContasPagasExtractor",
    DocumentType.FATURAMENTO: "core.extractors.faturamento_extractor:FaturamentoExtractor",
    DocumentType.NOTA_FISCAL: "core.extractors.faturamento_extractor:FaturamentoExtractor",
    DocumentType.CTE: "core.extractors.cte_extractor:CteExtractor",
    DocumentType.PLANILHA: "core.extractors.spreadsheet_extractor:SpreadsheetExtractor",
}


def get_extractor(document_type: str):
    """Instância do extrator adequado ao tipo. None quando não há extrator dedicado."""
    target = _EXTRACTOR_MAP.get(document_type)
    if target is None:
        return None
    module_name, class_name = target.split(":")
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)()


def get_label(document_type: str) -> str:
    """Rótulo legível do tipo documental, para telas e relatórios."""
    for signature in SIGNATURES:
        if signature.document_type == document_type:
            return signature.label or document_type
    return {
        DocumentType.OUTRO: "Não classificado",
        DocumentType.ERROR: "Erro de processamento",
        DocumentType.DUPLICATE: "Duplicado",
    }.get(document_type, document_type)
