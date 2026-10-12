"""Testes de hash de arquivo e detecção de duplicidade."""

from __future__ import annotations

import pytest

from core.exceptions import CorruptedFileError
from core.scanner.duplicate_detector import check_by_business_data, check_by_hash
from core.scanner.file_hash import compute_bytes_hash, compute_file_hash


class TestComputeFileHash:
    def test_hash_e_deterministico(self, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("conteúdo do documento", encoding="utf-8")

        assert compute_file_hash(path) == compute_file_hash(path)

    def test_arquivos_iguais_tem_mesmo_hash(self, tmp_path):
        first = tmp_path / "a.txt"
        second = tmp_path / "b.txt"
        first.write_text("mesmo conteúdo", encoding="utf-8")
        second.write_text("mesmo conteúdo", encoding="utf-8")

        assert compute_file_hash(first) == compute_file_hash(second)

    def test_arquivos_diferentes_tem_hashes_diferentes(self, tmp_path):
        first = tmp_path / "a.txt"
        second = tmp_path / "b.txt"
        first.write_text("conteúdo A", encoding="utf-8")
        second.write_text("conteúdo B", encoding="utf-8")

        assert compute_file_hash(first) != compute_file_hash(second)

    def test_hash_tem_64_caracteres_hex(self, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("x", encoding="utf-8")

        digest = compute_file_hash(path)
        assert len(digest) == 64
        assert all(char in "0123456789abcdef" for char in digest)

    def test_arquivo_inexistente_levanta_erro_tratado(self, tmp_path):
        with pytest.raises(CorruptedFileError):
            compute_file_hash(tmp_path / "nao_existe.pdf")

    def test_hash_de_bytes_bate_com_hash_de_arquivo(self, tmp_path):
        payload = b"conteudo binario"
        path = tmp_path / "doc.bin"
        path.write_bytes(payload)

        assert compute_bytes_hash(payload) == compute_file_hash(path)


class TestDuplicateByHash:
    def test_hash_novo_nao_e_duplicado(self, company):
        assert check_by_hash(company.id, "a" * 64).is_duplicate is False

    def test_mesmo_hash_e_detectado_como_duplicado(self, company):
        from db.repositories import document_repository

        original = document_repository.create_document(
            {
                "company_id": company.id,
                "original_file_name": "comprovante.pdf",
                "original_file_path": "/x/comprovante.pdf",
                "file_hash": "b" * 64,
                "file_extension": ".pdf",
                "document_type": "COMPROVANTE_PIX",
                "processing_status": "EXTRACTED",
            }
        )

        check = check_by_hash(company.id, "b" * 64)

        assert check.is_duplicate is True
        assert check.original_document_id == original.id
        assert check.match_type == "HASH"

    def test_hash_de_outra_empresa_nao_conta_como_duplicado(self, company):
        from db.repositories import company_repository, document_repository

        other = company_repository.create_company(
            {
                "name": "Cliente B",
                "legal_name": "CLIENTE B LTDA",
                "cnpj": "11.111.111/0001-11",
                "input_folder_path": "/b/in",
                "destination_folder_path": "/b/out",
            }
        )
        document_repository.create_document(
            {
                "company_id": other.id,
                "original_file_name": "x.pdf",
                "original_file_path": "/b/x.pdf",
                "file_hash": "c" * 64,
                "file_extension": ".pdf",
                "document_type": "COMPROVANTE_PIX",
                "processing_status": "EXTRACTED",
            }
        )

        assert check_by_hash(company.id, "c" * 64).is_duplicate is False


class TestDuplicateByBusinessData:
    def _create(self, company_id, **overrides):
        from datetime import date

        from db.repositories import document_repository

        data = {
            "company_id": company_id,
            "original_file_name": "doc.pdf",
            "original_file_path": "/x/doc.pdf",
            "file_hash": "d" * 64,
            "file_extension": ".pdf",
            "document_type": "CONTAS_PAGAS",
            "document_date": date(2026, 1, 6),
            "amount": 1500.0,
            "counterparty": "FICTICIO SERVICOS",
            "document_number": "NF-2026-0042",
            "processing_status": "EXTRACTED",
        }
        data.update(overrides)
        return document_repository.create_document(data)

    def test_mesmo_fato_contabil_e_duplicado(self, company):
        from datetime import date

        original = self._create(company.id)

        check = check_by_business_data(
            company.id,
            document_date=date(2026, 1, 6),
            amount=1500.0,
            counterparty="FICTICIO SERVICOS",
            document_number="NF-2026-0042",
            document_type="CONTAS_PAGAS",
        )

        assert check.is_duplicate is True
        assert check.original_document_id == original.id
        assert check.match_type == "DADOS_ESSENCIAIS"

    def test_valor_diferente_nao_e_duplicado(self, company):
        from datetime import date

        self._create(company.id)

        check = check_by_business_data(
            company.id,
            document_date=date(2026, 1, 6),
            amount=1600.0,
            counterparty="FICTICIO SERVICOS",
            document_number="NF-2026-0042",
            document_type="CONTAS_PAGAS",
        )

        assert check.is_duplicate is False

    def test_sem_data_ou_valor_nao_conclui_duplicidade(self, company):
        self._create(company.id)

        check = check_by_business_data(
            company.id,
            document_date=None,
            amount=1500.0,
            counterparty="FICTICIO SERVICOS",
            document_number="NF-2026-0042",
            document_type="CONTAS_PAGAS",
        )

        assert check.is_duplicate is False
