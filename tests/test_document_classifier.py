"""Testes do classificador documental e dos extratores por tipo."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.constants import DocumentType
from core.documents.document_classifier import classify_document
from core.documents.document_types import get_extractor, get_label
from core.extractors.contas_pagas_extractor import ContasPagasExtractor
from core.extractors.faturamento_extractor import FaturamentoExtractor
from core.extractors.pix_extractor import PixExtractor

CONTAS_PAGAS_TEXT = """RELATORIO DE CONTAS PAGAS
CREDOR: FORNECEDOR FICTICIO SERVICOS LTDA
DOCUMENTO: NF-2026-0042
DATA DE BAIXA: 06/01/2026
VALOR BRUTO: 1.600,00
DESCONTO: 100,00
VALOR LIQUIDO: 1.500,00
"""

FATURAMENTO_TEXT = """RELATORIO DE FATURAMENTO
Periodo: Janeiro/2026
CLIENTE: CONSTRUTORA OMEGA LTDA
NOTA FISCAL: 1234
Data: 31/01/2026
VALOR BRUTO: 10.000,00
IRRF: 150,00
PCC: 465,00
ISS: 200,00
VALOR LIQUIDO: 9.185,00
"""

EXTRATO_TEXT = """EXTRATO DE CONTA CORRENTE
AGENCIA: 1234 CONTA: 56789-0
SALDO ANTERIOR: 5.000,00
02/01/2026  PAGAMENTO FORNECEDOR           -1.500,00
05/01/2026  RECEBIMENTO CLIENTE             3.000,00
SALDO FINAL: 6.500,00
"""

NOTA_FISCAL_TEXT = """NOTA FISCAL DE SERVICOS ELETRONICA - NFS-E
PRESTADOR DE SERVICOS: ALFA CONSULTORIA LTDA
TOMADOR DE SERVICOS: CLIENTE A LTDA
DISCRIMINACAO DOS SERVICOS: consultoria contábil
Data de emissão: 15/01/2026
VALOR TOTAL: 2.000,00
"""


class TestClassificacaoDocumental:
    def test_comprovante_pix(self, sample_pix_text):
        result = classify_document(
            file_name="comprovante.pdf", extension=".pdf", text=sample_pix_text
        )
        assert result.document_type == DocumentType.COMPROVANTE_PIX
        assert result.confidence >= 0.70

    def test_relatorio_de_contas_pagas(self):
        result = classify_document(
            file_name="contas.pdf", extension=".pdf", text=CONTAS_PAGAS_TEXT
        )
        assert result.document_type == DocumentType.CONTAS_PAGAS

    def test_relatorio_de_faturamento(self):
        result = classify_document(
            file_name="fat.pdf", extension=".pdf", text=FATURAMENTO_TEXT
        )
        assert result.document_type == DocumentType.FATURAMENTO

    def test_extrato_bancario(self):
        result = classify_document(
            file_name="extrato.pdf", extension=".pdf", text=EXTRATO_TEXT
        )
        assert result.document_type == DocumentType.EXTRATO_BANCARIO

    def test_nota_fiscal(self):
        result = classify_document(file_name="nf.pdf", extension=".pdf", text=NOTA_FISCAL_TEXT)
        assert result.document_type == DocumentType.NOTA_FISCAL

    def test_texto_irreconhecivel_vai_para_outro(self):
        result = classify_document(
            file_name="qualquer.pdf",
            extension=".pdf",
            text="Lorem ipsum dolor sit amet, texto sem qualquer relação contábil.",
        )
        assert result.document_type == DocumentType.OUTRO
        assert result.is_unknown

    def test_texto_vazio_vai_para_outro_com_confianca_zero(self):
        result = classify_document(file_name="vazio.pdf", extension=".pdf", text="")
        assert result.document_type == DocumentType.OUTRO
        assert result.confidence == 0.0

    def test_confianca_abaixo_do_limite_vira_outro(self, sample_pix_text):
        """Regra de fallback da Arquitetura 7.3."""
        result = classify_document(
            file_name="comprovante.pdf",
            extension=".pdf",
            text=sample_pix_text,
            min_confidence=0.99,
        )
        assert result.document_type == DocumentType.OUTRO
        assert "abaixo do mínimo" in result.reason

    def test_extrai_competencia_da_data_do_documento(self, sample_pix_text):
        result = classify_document(
            file_name="comprovante.pdf", extension=".pdf", text=sample_pix_text
        )
        assert result.competence_year == 2026
        assert result.competence_month == 1

    def test_nome_do_arquivo_reforca_a_classificacao(self):
        """Texto fraco + nome sugestivo ainda deve classificar."""
        weak = "CREDOR: FORNECEDOR X\nVALOR LIQUIDO: 100,00\nDATA DE BAIXA: 01/02/2026"
        by_name = classify_document(
            file_name="relatorio_contas_pagas_jan.pdf", extension=".pdf", text=weak
        )
        assert by_name.document_type == DocumentType.CONTAS_PAGAS

    def test_rotulo_legivel_por_tipo(self):
        assert get_label(DocumentType.CONTAS_PAGAS) == "Relatório de contas pagas"
        assert get_label(DocumentType.OUTRO) == "Não classificado"


class TestRoteamentoDeExtrator:
    @pytest.mark.parametrize(
        "document_type,expected",
        [
            (DocumentType.COMPROVANTE_PIX, "pix"),
            (DocumentType.COMPROVANTE_TED, "pix"),
            (DocumentType.CONTAS_PAGAS, "contas_pagas"),
            (DocumentType.FATURAMENTO, "faturamento"),
            (DocumentType.CTE, "cte"),
            (DocumentType.EXTRATO_BANCARIO, "extrato"),
            (DocumentType.PLANILHA, "spreadsheet"),
        ],
    )
    def test_tipo_roteia_para_extrator_correto(self, document_type, expected):
        assert get_extractor(document_type).name == expected

    def test_tipo_sem_extrator_dedicado_retorna_none(self):
        assert get_extractor(DocumentType.OUTRO) is None


class TestPixExtractor:
    def test_extrai_campos_principais(self, sample_pix_text):
        result = PixExtractor().extract(Path("comprovante.pdf"), sample_pix_text)

        assert result.amount == 1500.00
        assert result.document_date == date(2026, 1, 6)
        assert "FICTICIO" in (result.counterparty or "")
        assert result.structured["payer_name"] is not None
        assert result.confidence > 0

    def test_texto_incompleto_gera_avisos(self):
        result = PixExtractor().extract(Path("x.pdf"), "COMPROVANTE PIX\nsem mais dados")

        assert result.amount is None
        assert result.warnings


class TestContasPagasExtractor:
    def test_usa_valor_liquido_como_valor_do_lancamento(self):
        result = ContasPagasExtractor().extract(Path("cp.pdf"), CONTAS_PAGAS_TEXT)

        assert result.amount == 1500.00
        assert result.structured["gross_amount"] == 1600.00
        assert result.structured["discount"] == 100.00
        assert result.document_date == date(2026, 1, 6)
        assert "FICTICIO" in (result.counterparty or "")
        assert result.document_number == "NF-2026-0042"


class TestFaturamentoExtractor:
    def test_extrai_retencoes_e_calcula_total(self):
        result = FaturamentoExtractor().extract(Path("fat.pdf"), FATURAMENTO_TEXT)

        taxes = result.structured["withheld_taxes"]
        assert taxes["ir"] == 150.00
        assert taxes["pcc"] == 465.00
        assert taxes["iss"] == 200.00
        assert result.structured["total_withheld"] == 815.00
        assert result.structured["net_amount"] == 9185.00

    def test_valor_do_lancamento_e_o_bruto(self):
        result = FaturamentoExtractor().extract(Path("fat.pdf"), FATURAMENTO_TEXT)
        assert result.amount == 10000.00

    def test_retencao_gera_aviso_de_conferencia(self):
        result = FaturamentoExtractor().extract(Path("fat.pdf"), FATURAMENTO_TEXT)
        assert any("Retenções" in w for w in result.warnings)


class TestExtratoExtractor:
    def test_reconhece_linhas_de_movimento(self):
        from core.extractors.extrato_extractor import ExtratoExtractor

        result = ExtratoExtractor().extract(Path("ext.pdf"), EXTRATO_TEXT)

        assert result.structured["movement_count"] == 2
        assert result.structured["final_balance"] == 6500.00

    def test_extrato_com_varios_movimentos_nao_define_valor_unico(self):
        from core.extractors.extrato_extractor import ExtratoExtractor

        result = ExtratoExtractor().extract(Path("ext.pdf"), EXTRATO_TEXT)

        assert result.amount is None
        assert any("evidência" in w for w in result.warnings)


class TestCteExtractor:
    def test_extrai_dados_do_xml(self, tmp_path):
        from core.extractors.cte_extractor import CteExtractor

        xml = """<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="http://www.portalfiscal.inf.br/cte">
  <CTe><infCte Id="CTe35260112345678000195570010000012341000012345">
    <ide><nCT>1234</nCT><dhEmi>2026-01-10T10:00:00-03:00</dhEmi>
      <xMunIni>São Paulo</xMunIni><xMunFim>Campinas</xMunFim></ide>
    <emit><xNome>TRANSPORTES BETA LTDA</xNome></emit>
    <rem><xNome>CLIENTE A LTDA</xNome></rem>
    <dest><xNome>CONSTRUTORA OMEGA LTDA</xNome></dest>
    <vPrest><vTPrest>850.00</vTPrest></vPrest>
    <imp><ICMS><vICMS>102.00</vICMS></ICMS></imp>
  </infCte></CTe>
</cteProc>"""
        path = tmp_path / "cte.xml"
        path.write_text(xml, encoding="utf-8")

        result = CteExtractor().extract(path, xml)

        assert result.structured["cte_number"] == "1234"
        assert result.structured["issuer"] == "TRANSPORTES BETA LTDA"
        assert result.structured["service_amount"] == 850.00
        assert result.structured["icms_amount"] == 102.00
        assert result.document_date == date(2026, 1, 10)
