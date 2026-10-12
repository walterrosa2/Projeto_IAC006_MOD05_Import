"""Testes do organizador de pastas e dos parsers de metadados."""

from __future__ import annotations

from datetime import date

import pytest

from core.constants import DocumentType
from core.documents.folder_organizer import (
    UNDEFINED_COMPETENCE,
    build_destination_path,
    organize_document,
    safe_file_name,
    write_error_marker,
)
from core.documents.metadata_extractor import (
    find_amounts,
    find_cnpjs,
    find_cpfs,
    find_dates,
    mask_cpf,
    month_folder_name,
    parse_amount_br,
    parse_date_br,
)
from core.exceptions import ClassificadorError


class TestSafeFileName:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("nota fiscal.pdf", "nota fiscal.pdf"),
            ("nota:fiscal?.pdf", "nota_fiscal_.pdf"),
            ('doc"com/barras\\.pdf', "doc_com_barras_.pdf"),
            ("  espaços  .pdf", "espaços.pdf"),
        ],
    )
    def test_remove_caracteres_invalidos(self, raw, expected):
        assert safe_file_name(raw) == expected

    def test_nome_reservado_do_windows_recebe_prefixo(self):
        assert safe_file_name("CON.pdf") == "_CON.pdf"

    def test_nome_vazio_vira_documento(self):
        assert safe_file_name("...pdf").startswith("documento") or safe_file_name("   .pdf") == "documento.pdf"

    def test_nome_muito_longo_e_truncado(self):
        result = safe_file_name("a" * 300 + ".pdf")
        assert len(result) <= 124
        assert result.endswith(".pdf")


class TestBuildDestinationPath:
    def test_estrutura_cliente_ano_mes_tipo(self, tmp_path):
        path = build_destination_path(
            destination_root=tmp_path,
            company_name="Cliente A",
            document_type=DocumentType.COMPROVANTE_PIX,
            competence_year=2026,
            competence_month=1,
            file_name="comprovante.pdf",
        )

        assert path.parts[-4:] == ("2026", "01 - Janeiro", "COMPROVANTES", "comprovante.pdf")
        assert "Cliente A" in str(path)

    @pytest.mark.parametrize(
        "document_type,folder",
        [
            (DocumentType.COMPROVANTE_PIX, "COMPROVANTES"),
            (DocumentType.COMPROVANTE_TED, "COMPROVANTES"),
            (DocumentType.EXTRATO_BANCARIO, "EXTRATOS"),
            (DocumentType.FATURAMENTO, "FATURAMENTO"),
            (DocumentType.CONTAS_PAGAS, "CONTAS_PAGAS"),
            (DocumentType.NOTA_FISCAL, "NOTAS_FISCAIS"),
            (DocumentType.CTE, "CTES"),
            (DocumentType.PLANILHA, "PLANILHAS"),
            (DocumentType.OUTRO, "OUTROS"),
            (DocumentType.ERROR, "ERROS"),
            (DocumentType.DUPLICATE, "DUPLICADOS"),
        ],
    )
    def test_mapeamento_tipo_para_pasta(self, tmp_path, document_type, folder):
        path = build_destination_path(
            destination_root=tmp_path,
            company_name="Cliente A",
            document_type=document_type,
            competence_year=2026,
            competence_month=3,
            file_name="x.pdf",
        )
        assert path.parent.name == folder

    def test_sem_competencia_usa_pasta_dedicada(self, tmp_path):
        path = build_destination_path(
            destination_root=tmp_path,
            company_name="Cliente A",
            document_type=DocumentType.OUTRO,
            competence_year=None,
            competence_month=None,
            file_name="x.pdf",
        )
        assert UNDEFINED_COMPETENCE in path.parts

    def test_nao_repete_nome_da_empresa_quando_raiz_ja_e_a_pasta(self, tmp_path):
        root = tmp_path / "Cliente A"
        path = build_destination_path(
            destination_root=root,
            company_name="Cliente A",
            document_type=DocumentType.OUTRO,
            competence_year=2026,
            competence_month=1,
            file_name="x.pdf",
        )
        assert str(path).count("Cliente A") == 1

    def test_nome_de_mes_em_portugues(self):
        assert month_folder_name(1) == "01 - Janeiro"
        assert month_folder_name(12) == "12 - Dezembro"


class TestOrganizeDocument:
    def test_copia_preservando_o_original(self, tmp_path):
        source = tmp_path / "entrada" / "comprovante.pdf"
        source.parent.mkdir(parents=True)
        source.write_text("conteúdo", encoding="utf-8")

        result = organize_document(
            source_path=source,
            destination_root=tmp_path / "saida",
            company_name="Cliente A",
            document_type=DocumentType.COMPROVANTE_PIX,
            competence_year=2026,
            competence_month=1,
        )

        assert source.exists(), "o arquivo original não pode ser movido (RNF02)"
        assert result.destination_path.exists()
        assert result.destination_path.read_text(encoding="utf-8") == "conteúdo"

    def test_cria_estrutura_de_pastas_inexistente(self, tmp_path):
        source = tmp_path / "doc.pdf"
        source.write_text("x", encoding="utf-8")

        result = organize_document(
            source_path=source,
            destination_root=tmp_path / "novo",
            company_name="Cliente A",
            document_type=DocumentType.CTE,
            competence_year=2026,
            competence_month=7,
        )

        assert result.destination_path.parent.is_dir()
        assert result.destination_path.parent.name == "CTES"

    def test_colisao_de_nome_gera_arquivo_novo_sem_sobrescrever(self, tmp_path):
        source = tmp_path / "doc.pdf"
        source.write_text("primeiro", encoding="utf-8")

        first = organize_document(
            source_path=source,
            destination_root=tmp_path / "out",
            company_name="Cliente A",
            document_type=DocumentType.OUTRO,
            competence_year=2026,
            competence_month=1,
        )

        source.write_text("segundo", encoding="utf-8")
        second = organize_document(
            source_path=source,
            destination_root=tmp_path / "out",
            company_name="Cliente A",
            document_type=DocumentType.OUTRO,
            competence_year=2026,
            competence_month=1,
        )

        assert second.renamed is True
        assert first.destination_path != second.destination_path
        assert first.destination_path.read_text(encoding="utf-8") == "primeiro"
        assert second.destination_path.read_text(encoding="utf-8") == "segundo"

    def test_origem_inexistente_levanta_erro_tratado(self, tmp_path):
        with pytest.raises(ClassificadorError):
            organize_document(
                source_path=tmp_path / "nao_existe.pdf",
                destination_root=tmp_path,
                company_name="Cliente A",
                document_type=DocumentType.OUTRO,
                competence_year=None,
                competence_month=None,
            )


class TestErrorMarker:
    def test_grava_json_com_motivo_do_erro(self, tmp_path):
        import json

        destination = tmp_path / "ERROS" / "doc.pdf"
        destination.parent.mkdir(parents=True)
        destination.write_text("x", encoding="utf-8")

        marker = write_error_marker(
            destination_path=destination,
            original_file_name="doc.pdf",
            company_name="Cliente A",
            error_type="EXTRACAO_FALHOU",
            error_message="Não foi possível extrair texto do PDF",
        )

        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["arquivo"] == "doc.pdf"
        assert payload["empresa"] == "Cliente A"
        assert payload["erro_tipo"] == "EXTRACAO_FALHOU"
        assert "acao_recomendada" in payload


class TestMetadataParsers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("R$ 1.234,56", 1234.56),
            ("1.234,56", 1234.56),
            ("1234,56", 1234.56),
            ("1234.56", 1234.56),
            ("0,01", 0.01),
            ("1.000.000,00", 1000000.00),
            ("-500,00", -500.00),
            ("", None),
            ("abc", None),
        ],
    )
    def test_parse_amount_br(self, raw, expected):
        assert parse_amount_br(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("06/01/2026", date(2026, 1, 6)),
            ("2026-01-06", date(2026, 1, 6)),
            ("06-01-2026", date(2026, 1, 6)),
            ("06.01.2026", date(2026, 1, 6)),
            ("32/01/2026", None),
            ("sem data", None),
        ],
    )
    def test_parse_date_br(self, raw, expected):
        assert parse_date_br(raw) == expected

    def test_find_dates_ignora_anos_improvaveis(self):
        dates = find_dates("pago em 06/01/2026, nascido em 15/03/1850")
        assert date(2026, 1, 6) in dates
        assert all(d.year >= 2000 for d in dates)

    def test_find_amounts_encontra_valores_brasileiros(self):
        assert find_amounts("Bruto 1.600,00 Desconto 100,00 Líquido 1.500,00") == [
            1600.0,
            100.0,
            1500.0,
        ]

    def test_find_cnpjs_normaliza_formatacao(self):
        assert find_cnpjs("CNPJ 12345678000195") == ["12.345.678/0001-95"]
        assert find_cnpjs("CNPJ: 12.345.678/0001-95") == ["12.345.678/0001-95"]

    def test_find_cpfs_nao_confunde_pedaco_de_cnpj(self):
        texto = "CNPJ 12.345.678/0001-95 e CPF 123.456.789-09"
        assert "123.456.789-09" in find_cpfs(texto)

    def test_mask_cpf_oculta_digitos_do_meio(self):
        assert mask_cpf("123.456.789-09") == "123.***.***-09"
        assert mask_cpf(None) is None
