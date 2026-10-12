"""Testes do OCR e dos layouts reais de comprovante bancário.

Os textos abaixo reproduzem os dois layouts encontrados nos documentos do
escritório (250 comprovantes de 01/2026), com nomes e números alterados.
Servem de regressão para o bug em que o extrator pegava a linha errada e
devolvia "CONTA CORRENTE" como favorecido.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.constants import DocumentType
from core.documents.document_classifier import classify_document
from core.documents.document_types import get_extractor
from core.extractors.pix_extractor import PixExtractor

# Layout A — comprovante PIX com seções TRANSFERIDO POR / TRANSFERIDO PARA.
LAYOUT_PIX_SECOES = """.
RECIBO DE TRANSFERÊNCIA PIX ENVIADO
NÚMERO DO COMPROVANTE:
00000000-AAAA-4BBB-8CCC-000000000001
TRANSFERIDO EM:
06/01/2026 HORA: 13:24:32
TRANSFERIDO POR
CONTA CORRENTE:
BANCO: 274 - BMP SCMEPP LTDA
AG: 0001
CONTA-DV DÉBITO: 00012345-6
NOME: CONSTRUTORA EXEMPLO LTDA
CPF/CNPJ: 44.***.666/0001-**
TRANSFERIDO PARA
CONTA CORRENTE:
BANCO: 000 - COOPERATIVA DE CREDITO EXEMPLO
AG: 0109
CONTA-DV CRÉDITO: 9999-1
CHAVE PIX: 77888999000100
NOME: FORNECEDOR FICTICIO SERVICOS LTDA.
CPF/CNPJ: **.***.999/***1-00
VALOR TRANSFERIDO:
R$ 16.599,84
DÉBITO REALIZADO COM SUCESSO
"""

# Layout A, variante TED.
LAYOUT_TED_SECOES = LAYOUT_PIX_SECOES.replace(
    "RECIBO DE TRANSFERÊNCIA PIX ENVIADO", "RECIBO DE TRANSFERÊNCIA TED ENVIADA"
).replace("CHAVE PIX: 77888999000100\n", "")

# Layout B — pagamento de boleto, seções Pagador / Favorecido / Transação.
LAYOUT_BOLETO = """Número do comprovante: 00000000-dddd-4eee-8fff-000000000002
Comprovante de pagamento
Solicitação: 15/01/2026
Pagamento realizado
R$ 56.649,78
Pagador
Conta Corrente: 310 - VORTX DTVM LTDA.
Agência: 0001
Conta: 000123-4
Nome: CONSTRUTORA EXEMPLO LTDA
Favorecido
Nome do beneficiário: SIDERURGICA MODELO SA
Documento do beneficiário: 11.222.333/0001-81
Nome do sacado: CONSTRUTORA EXEMPLO LTDA
Documento do sacado: 44.555.666/0001-02
Transação
Código de barras: 00190000090000000000000000000000100000005664978
Data de vencimento: 16/01/2026
Data de pagamento: 15/01/2026, às 13:28
Valor Nominal: R$ 56.649,78
Valor do desconto: R$ 0,00
Valor do juros: R$ 0,00
Valor pago: R$ 56.649,78
"""


class TestLayoutPixComSecoes:
    """Regressão do bug: 'DE' casava com o título e 'PARA' com 'CONTA CORRENTE:'."""

    @pytest.fixture
    def resultado(self):
        return PixExtractor().extract(Path("comprovante.pdf"), LAYOUT_PIX_SECOES)

    def test_favorecido_e_o_nome_da_secao_transferido_para(self, resultado):
        assert resultado.structured["beneficiary_name"] == "FORNECEDOR FICTICIO SERVICOS LTDA."

    def test_pagador_e_o_nome_da_secao_transferido_por(self, resultado):
        assert resultado.structured["payer_name"] == "CONSTRUTORA EXEMPLO LTDA"

    def test_nao_confunde_titulo_do_documento_com_pagador(self, resultado):
        """O título contém ' DE ' — não pode virar o nome do pagador."""
        assert "TRANSFER" not in (resultado.structured["payer_name"] or "").upper()

    def test_nao_confunde_rotulo_estrutural_com_favorecido(self, resultado):
        assert resultado.structured["beneficiary_name"] != "CONTA CORRENTE"

    def test_contraparte_e_quem_recebe(self, resultado):
        assert resultado.counterparty == "FORNECEDOR FICTICIO SERVICOS LTDA."

    def test_valor(self, resultado):
        assert resultado.amount == 16599.84

    def test_data(self, resultado):
        assert resultado.document_date == date(2026, 1, 6)

    def test_data_hora_com_rotulo_hora(self, resultado):
        assert resultado.structured["transfer_datetime"] == "2026-01-06T13:24:32"

    def test_numero_do_comprovante(self, resultado):
        assert resultado.structured["proof_number"] == "00000000-AAAA-4BBB-8CCC-000000000001"

    def test_documento_mascarado_e_preservado_como_veio(self, resultado):
        """O banco já publica o CNPJ parcialmente oculto; não se reconstrói dado."""
        assert resultado.structured["payer_cnpj_cpf"] == "44.***.666/0001-**"

    def test_sem_avisos_quando_tudo_foi_extraido(self, resultado):
        assert resultado.warnings == []
        assert resultado.confidence == 1.0

    def test_classificacao(self):
        result = classify_document(
            file_name="comprovante.pdf", extension=".pdf", text=LAYOUT_PIX_SECOES
        )
        assert result.document_type == DocumentType.COMPROVANTE_PIX
        assert result.confidence >= 0.70


class TestLayoutTed:
    def test_classificado_como_ted(self):
        """Mesmo sem 'TED' no nome do arquivo, o conteúdo basta."""
        result = classify_document(
            file_name="ship america fundacoes.pdf", extension=".pdf", text=LAYOUT_TED_SECOES
        )
        assert result.document_type == DocumentType.COMPROVANTE_TED
        assert result.confidence >= 0.70

    def test_extrai_favorecido(self):
        result = PixExtractor().extract(Path("ted.pdf"), LAYOUT_TED_SECOES)
        assert result.structured["beneficiary_name"] == "FORNECEDOR FICTICIO SERVICOS LTDA."


class TestLayoutBoleto:
    @pytest.fixture
    def resultado(self):
        return PixExtractor().extract(Path("pagamento.pdf"), LAYOUT_BOLETO)

    def test_classificado_como_boleto(self):
        result = classify_document(
            file_name="pagamento_siderurgica_modelo.pdf", extension=".pdf", text=LAYOUT_BOLETO
        )
        assert result.document_type == DocumentType.COMPROVANTE_BOLETO
        assert result.confidence >= 0.70

    def test_beneficiario_tem_precedencia_sobre_sacado(self, resultado):
        """No boleto o sacado é o devedor; o credor é o beneficiário."""
        assert resultado.structured["beneficiary_name"] == "SIDERURGICA MODELO SA"

    def test_pagador(self, resultado):
        assert resultado.structured["payer_name"] == "CONSTRUTORA EXEMPLO LTDA"

    def test_documento_do_beneficiario(self, resultado):
        assert resultado.structured["beneficiary_cnpj_cpf"] == "11.222.333/0001-81"

    def test_valor_pago(self, resultado):
        assert resultado.amount == 56649.78

    def test_data_de_pagamento_e_preferida_ao_vencimento(self, resultado):
        assert resultado.document_date == date(2026, 1, 15)

    def test_data_hora_com_as(self, resultado):
        assert resultado.structured["transfer_datetime"] == "2026-01-15T13:28"

    def test_roteamento_para_o_extrator_de_comprovante(self):
        assert get_extractor(DocumentType.COMPROVANTE_BOLETO).name == "pix"


class TestOcrConfiguracao:
    """O OCR é opt-in e nunca roda no provedor mock."""

    def test_indisponivel_quando_desligado(self, monkeypatch):
        from core.config import get_settings
        from core.extractors.ocr_extractor import ocr_is_available

        monkeypatch.setenv("OCR_ENABLED", "false")
        get_settings.cache_clear()

        available, reason = ocr_is_available()
        assert available is False
        assert "desativado" in reason.lower()

    def test_indisponivel_no_provedor_mock(self, monkeypatch):
        from core.config import get_settings
        from core.extractors.ocr_extractor import ocr_is_available

        monkeypatch.setenv("OCR_ENABLED", "true")
        monkeypatch.setenv("AI_PROVIDER", "mock")
        get_settings.cache_clear()

        available, reason = ocr_is_available()
        assert available is False
        assert "mock" in reason.lower()

    def test_indisponivel_sem_chave(self, monkeypatch):
        from core.config import get_settings
        from core.extractors.ocr_extractor import ocr_is_available

        monkeypatch.setenv("OCR_ENABLED", "true")
        monkeypatch.setenv("AI_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "")
        get_settings.cache_clear()

        available, reason = ocr_is_available()
        assert available is False
        assert "chave" in reason.lower()

    def test_ocr_nao_e_tentado_quando_indisponivel(self, tmp_path, monkeypatch):
        """PDF sem texto e OCR desligado: mantém o erro original, não trava."""
        import pymupdf

        from core.config import get_settings
        from core.exceptions import PdfWithoutTextError
        from core.extractors.pdf_text_extractor import extract_pdf_text

        monkeypatch.setenv("OCR_ENABLED", "false")
        get_settings.cache_clear()

        # PDF válido, com uma página em branco.
        path = tmp_path / "escaneado.pdf"
        document = pymupdf.open()
        document.new_page()
        document.save(path)
        document.close()

        with pytest.raises(PdfWithoutTextError):
            extract_pdf_text(path, allow_ocr=True)

    def test_marcador_de_ocr_e_reconhecido(self):
        from core.extractors.pdf_text_extractor import OCR_MARKER, text_came_from_ocr

        assert text_came_from_ocr(f"{OCR_MARKER}\nNOTA FISCAL...") is True
        assert text_came_from_ocr("NOTA FISCAL...") is False
        assert text_came_from_ocr("") is False
