"""Smoke test das telas Streamlit.

Navega a partir de `main.py`, como o usuário faz pela barra lateral — rodar
cada página como entrypoint isolado quebraria os `st.page_link`, que são
resolvidos em relação ao entrypoint real do app.

Não exercita interação: garante apenas que cada tela abre sem exceção, com
banco vazio e com dados.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
PAGES_DIR = APP_DIR / "pages"

#: Tempo generoso: a primeira execução compila e cria o schema.
TIMEOUT = 60

PAGE_FILES = sorted(p.name for p in PAGES_DIR.glob("*.py") if not p.name.startswith("_"))


def run_page(file_name: str) -> AppTest:
    """Abre o app e navega até a página, como acontece em produção."""
    app = AppTest.from_file(str(APP_DIR / "main.py"), default_timeout=TIMEOUT)
    app.run()
    app.switch_page(f"pages/{file_name}")
    app.run()
    return app


def assert_no_exception(app: AppTest, context: str) -> None:
    if app.exception:
        messages = [f"{e.type}: {e.message}" for e in app.exception]
        pytest.fail(f"{context} levantou exceção: {messages}")


class TestTelasComBancoVazio:
    """Sem empresa cadastrada, nenhuma tela pode quebrar."""

    def test_home_abre(self):
        app = AppTest.from_file(str(APP_DIR / "main.py"), default_timeout=TIMEOUT)
        app.run()
        assert_no_exception(app, "main.py")

    @pytest.mark.parametrize("page", PAGE_FILES)
    def test_pagina_abre_sem_dados(self, page):
        assert_no_exception(run_page(page), page)


class TestTelasComDados:
    """Com empresa, plano de contas, documento e lançamento carregados."""

    @pytest.fixture(autouse=True)
    def _seed(self, full_company):
        from datetime import date

        from core.constants import EntryStatus
        from db.repositories import (
            accounting_entry_repository,
            document_repository,
            example_repository,
        )

        document = document_repository.create_document(
            {
                "company_id": full_company.id,
                "original_file_name": "contas_pagas.pdf",
                "original_file_path": "/x/contas_pagas.pdf",
                "stored_file_path": "/x/out/contas_pagas.pdf",
                "file_hash": "a" * 64,
                "file_extension": ".pdf",
                "document_type": "CONTAS_PAGAS",
                "document_date": date(2026, 1, 6),
                "competence_year": 2026,
                "competence_month": 1,
                "counterparty": "FICTICIO SERVICOS",
                "amount": 1500.0,
                "classification_confidence": 0.9,
                "processing_status": "ENTRY_GENERATED",
            }
        )
        document_repository.save_extracted_data(
            document.id,
            raw_text="RELATORIO DE CONTAS PAGAS...",
            structured={"creditor": "FICTICIO SERVICOS", "net_amount": 1500.0},
            extractor_name="contas_pagas",
        )

        entry = accounting_entry_repository.create_entry(
            {
                "company_id": full_company.id,
                "document_id": document.id,
                "entry_date": date(2026, 1, 6),
                "debit_account_code": "3.1.01.001",
                "credit_account_code": "1.1.01.001",
                "amount": 1500.0,
                "history_complement": "Pagamento a FICTICIO",
                "ai_confidence": 0.85,
                "ai_justification": "Serviços de terceiros.",
                "status": EntryStatus.PENDING_REVIEW,
            }
        )

        accounting_entry_repository.create_correction(
            entry_id=entry.id,
            company_id=full_company.id,
            document_id=document.id,
            document_type="CONTAS_PAGAS",
            counterparty="FICTICIO SERVICOS",
            original={"debit_account_code": "1.1.01.001"},
            corrected={
                "debit_account_code": "3.1.01.001",
                "credit_account_code": "1.1.01.001",
                "history_complement": "Pagamento a FICTICIO",
            },
            corrective_guidance="Usar serviços de terceiros.",
            convert_to_example=True,
            created_by="contador",
        )

        example_repository.create_example(
            full_company.id,
            {
                "title": "Pagamento de prestador",
                "document_type": "CONTAS_PAGAS",
                "base_document": "Relatório de contas pagas",
                "counterparty": "FICTICIO SERVICOS",
                "debit_account_code": "3.1.01.001",
                "credit_account_code": "1.1.01.001",
                "history_complement_template": "Pagamento a {fornecedor}",
                "accounting_explanation": "Contas pagas é o documento base.",
                "priority": "Alta",
                "active": True,
            },
        )

        company_repository_guideline = __import__(
            "db.repositories.company_repository", fromlist=["create_guideline"]
        )
        company_repository_guideline.create_guideline(
            full_company.id,
            {
                "title": "Prestadores PF",
                "guideline_text": "Classificar como serviços tomados.",
                "priority": "Alta",
                "active": True,
            },
        )

    @pytest.mark.parametrize("page", PAGE_FILES)
    def test_pagina_abre_com_dados(self, page):
        assert_no_exception(run_page(page), f"{page} (com dados)")
