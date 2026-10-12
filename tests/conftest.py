"""Fixtures compartilhadas: banco temporário e dados de uma empresa completa."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Cada teste roda contra um SQLite próprio, em modo MOCK de IA."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("MIN_CLASSIFICATION_CONFIDENCE", "0.70")

    from core.config import get_settings
    from db.database import init_db, reset_engine

    get_settings.cache_clear()
    reset_engine()
    init_db()

    yield

    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def company(tmp_path):
    """Empresa com pastas de entrada e destino reais em tmp_path."""
    from db.repositories import company_repository

    input_folder = tmp_path / "CLIENTES" / "Cliente A" / "DADOS_A_CLASSIFICAR"
    destination = tmp_path / "CLIENTES"
    input_folder.mkdir(parents=True, exist_ok=True)

    return company_repository.create_company(
        {
            "name": "Cliente A",
            "legal_name": "CLIENTE A LTDA",
            "cnpj": "12.345.678/0001-95",
            "input_folder_path": str(input_folder),
            "destination_folder_path": str(destination),
            "branch_code": "1",
            "status": "Ativa",
        }
    )


@pytest.fixture
def chart_of_accounts(company):
    """Plano de contas mínimo: uma conta de despesa, uma de banco e uma sintética."""
    from db.repositories import company_repository

    rows = [
        {
            "account_code": "3.1.01.001",
            "description": "Serviços de terceiros",
            "accepts_entries": True,
            "active": True,
        },
        {
            "account_code": "1.1.01.001",
            "description": "Banco conta movimento",
            "accepts_entries": True,
            "active": True,
        },
        {
            "account_code": "3.1.01",
            "description": "Despesas operacionais (sintética)",
            "accepts_entries": False,
            "active": True,
        },
        {
            "account_code": "9.9.99.999",
            "description": "Conta desativada",
            "accepts_entries": True,
            "active": False,
        },
    ]
    company_repository.bulk_upsert_accounts(company.id, rows)
    return rows


@pytest.fixture
def full_company(company, chart_of_accounts):
    """Empresa com plano de contas, histórico e centro de custo."""
    from db.repositories import company_repository

    company_repository.upsert_history(
        company.id,
        {"history_code": "101", "description": "Pagamento a fornecedor", "active": True},
    )
    company_repository.upsert_cost_center(
        company.id,
        {"cost_center_code": "001", "description": "Administrativo", "active": True},
    )
    return company


@pytest.fixture
def sample_pix_text() -> str:
    return """BANCO EXEMPLO S.A.
COMPROVANTE DE TRANSFERENCIA PIX

Data da transferência: 06/01/2026 14:35
Valor: R$ 1.500,00

PAGADOR
CLIENTE A LTDA
CNPJ: 12.345.678/0001-95

FAVORECIDO
FORNECEDOR FICTICIO SERVICOS LTDA
CNPJ: 98.765.432/0001-10

ID: E123456782026010614350001
"""


@pytest.fixture
def sample_contas_pagas_text() -> str:
    return """RELATORIO DE CONTAS PAGAS
Empresa: CLIENTE A LTDA
Periodo: 01/01/2026 a 31/01/2026

CREDOR: FORNECEDOR FICTICIO SERVICOS LTDA
DOCUMENTO: NF-2026-0042
VENCIMENTO: 05/01/2026
DATA DE BAIXA: 06/01/2026
VALOR BRUTO: 1.600,00
DESCONTO: 100,00
VALOR LIQUIDO: 1.500,00
"""


@pytest.fixture
def make_file(tmp_path):
    """Cria um arquivo de texto na pasta de entrada e devolve o Path."""

    def _make(name: str, content: str, *, folder: Path | None = None) -> Path:
        target = (folder or tmp_path) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    return _make
