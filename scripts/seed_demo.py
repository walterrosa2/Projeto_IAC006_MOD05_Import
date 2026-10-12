"""Cria uma empresa de demonstração com dados fictícios para validação manual.

Uso:
    $env:PYTHONPATH = "."
    .venv\\Scripts\\python.exe scripts/seed_demo.py

Idempotente: rodar de novo atualiza os cadastros em vez de duplicar.
Nenhum dado real de cliente é usado — CNPJs e nomes são fictícios.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.scanner.file_scanner import ensure_input_folder  # noqa: E402
from db.database import init_db  # noqa: E402
from db.repositories import company_repository, example_repository  # noqa: E402

COMPANY_NAME = "Cliente Demonstracao"
DEMO_ROOT = PROJECT_ROOT / "data" / "clientes"

ACCOUNTS = [
    ("1.1.01.001", "Banco conta movimento", "Ativo circulante", True),
    ("1.1.02.001", "Clientes a receber", "Ativo circulante", True),
    ("2.1.01.001", "Fornecedores a pagar", "Passivo circulante", True),
    ("3.1.01.001", "Serviços de terceiros", "Despesa operacional", True),
    ("3.1.01.002", "Fretes e carretos", "Despesa operacional", True),
    ("3.1.02.001", "Material de consumo", "Despesa operacional", True),
    ("4.1.01.001", "Receita de serviços", "Receita operacional", True),
    ("1.1.03.001", "Impostos a recuperar", "Ativo circulante", True),
    ("3.1.01", "Despesas operacionais", "Sintética", False),
]

HISTORIES = [
    ("101", "Pagamento a fornecedor conforme relatório de contas pagas"),
    ("102", "Pagamento de frete conforme CT-e"),
    ("201", "Receita de serviços conforme relatório de faturamento"),
    ("301", "Transferência bancária"),
]

COST_CENTERS = [
    ("001", "Administrativo"),
    ("002", "Operacional"),
    ("003", "Comercial"),
]

GUIDELINES = [
    {
        "title": "Comprovantes PIX são evidência, não documento base",
        "guideline_text": (
            "Comprovantes PIX só devem gerar lançamento quando não houver relatório de "
            "contas pagas, nota fiscal ou CT-e correspondente ao mesmo pagamento. "
            "Havendo documento fiscal, o comprovante é apenas evidência."
        ),
        "applicable_document_type": "COMPROVANTE_PIX",
        "priority": "Alta",
    },
    {
        "title": "Pagamentos a prestadores pessoa física",
        "guideline_text": (
            "Pagamentos a prestadores pessoa física devem ser classificados como "
            "serviços tomados, exceto quando a descrição indicar adiantamento."
        ),
        "applicable_document_type": None,
        "priority": "Alta",
    },
    {
        "title": "Faturamento com retenção",
        "guideline_text": (
            "Faturamento com retenção deve separar receita bruta, impostos retidos e "
            "valor líquido. Conferir se o lançamento sugerido contempla as retenções."
        ),
        "applicable_document_type": "FATURAMENTO",
        "priority": "Média",
    },
]

EXAMPLES = [
    {
        "title": "Pagamento de prestador por relatório de contas pagas",
        "document_type": "CONTAS_PAGAS",
        "base_document": "Relatório de contas pagas",
        "counterparty": "CONSTRUTORA EXEMPLO LTDA",
        "keywords": "empreiteiro; mão de obra; construção; serviços",
        "debit_account_code": "3.1.01.001",
        "credit_account_code": "1.1.01.001",
        "history_code": "101",
        "history_complement_template": (
            "Pagamento a fornecedor conforme relatório de contas pagas: {fornecedor} - {documento}"
        ),
        "debit_cost_center_code": "002",
        "accounting_explanation": (
            "O relatório de contas pagas possui credor, documento fiscal, data de baixa, "
            "valor bruto, desconto e líquido — é mais rico que o comprovante PIX do mesmo "
            "pagamento, portanto é o documento base do lançamento."
        ),
        "priority": "Alta",
    },
    {
        "title": "Frete pago conforme CT-e",
        "document_type": "CTE",
        "base_document": "Conhecimento de transporte eletrônico",
        "counterparty": "TRANSPORTES EXEMPLO LTDA",
        "keywords": "frete; transporte; carreto",
        "debit_account_code": "3.1.01.002",
        "credit_account_code": "2.1.01.001",
        "history_code": "102",
        "history_complement_template": "Frete conforme CT-e {documento} - {fornecedor}",
        "debit_cost_center_code": "002",
        "accounting_explanation": (
            "O CT-e é o documento fiscal do serviço de transporte e traz emitente, "
            "tomador, valor da prestação e ICMS."
        ),
        "priority": "Alta",
    },
    {
        "title": "Receita de serviços por relatório de faturamento",
        "document_type": "FATURAMENTO",
        "base_document": "Relatório de faturamento",
        "counterparty": None,
        "keywords": "faturamento; receita; nota emitida",
        "debit_account_code": "1.1.02.001",
        "credit_account_code": "4.1.01.001",
        "history_code": "201",
        "history_complement_template": "Receita de serviços conforme faturamento: {cliente} - {documento}",
        "debit_cost_center_code": "003",
        "accounting_explanation": (
            "O faturamento gera receita pelo valor bruto, com as retenções lançadas "
            "separadamente em impostos a recuperar."
        ),
        "priority": "Média",
    },
]


def main() -> None:
    init_db()

    input_folder = DEMO_ROOT / COMPANY_NAME / "DADOS_A_CLASSIFICAR"
    ensure_input_folder(input_folder)

    existing = company_repository.get_company_by_name(COMPANY_NAME)
    payload = {
        "name": COMPANY_NAME,
        "legal_name": "CLIENTE DEMONSTRACAO COMERCIO E SERVICOS LTDA",
        "cnpj": "12.345.678/0001-95",
        "input_folder_path": str(input_folder),
        "destination_folder_path": str(DEMO_ROOT),
        "responsible_accountant": "Contador responsável",
        "notes": "Empresa fictícia criada por scripts/seed_demo.py para validação manual.",
        "branch_code": "1",
        "status": "Ativa",
    }

    if existing:
        company = company_repository.update_company(existing.id, payload)
        print(f"[=] Empresa atualizada: {company.name} (id {company.id})")
    else:
        company = company_repository.create_company(payload)
        print(f"[+] Empresa criada: {company.name} (id {company.id})")

    created, updated = company_repository.bulk_upsert_accounts(
        company.id,
        [
            {
                "account_code": code,
                "description": description,
                "account_type": account_type,
                "accepts_entries": accepts,
                "active": True,
            }
            for code, description, account_type, accepts in ACCOUNTS
        ],
    )
    print(f"[+] Plano de contas: {created} criada(s), {updated} atualizada(s)")

    for code, description in HISTORIES:
        company_repository.upsert_history(
            company.id, {"history_code": code, "description": description, "active": True}
        )
    print(f"[+] Históricos: {len(HISTORIES)}")

    for code, description in COST_CENTERS:
        company_repository.upsert_cost_center(
            company.id,
            {"cost_center_code": code, "description": description, "active": True},
        )
    print(f"[+] Centros de custo: {len(COST_CENTERS)}")

    existing_titles = {g.title for g in company_repository.list_guidelines(company.id)}
    for guideline in GUIDELINES:
        if guideline["title"] in existing_titles:
            continue
        company_repository.create_guideline(
            company.id, {**guideline, "active": True, "created_by": "seed_demo"}
        )
    print(f"[+] Orientações: {len(GUIDELINES)}")

    existing_examples = {e.title for e in example_repository.list_examples(company.id)}
    for example in EXAMPLES:
        if example["title"] in existing_examples:
            continue
        example_repository.create_example(
            company.id,
            {
                "counterparty": None,
                "document_excerpt": None,
                "credit_cost_center_code": None,
                **example,
                "active": True,
                "created_by": "seed_demo",
            },
        )
    print(f"[+] Exemplos de lançamento: {len(EXAMPLES)}")

    print()
    print("Pronto. Coloque documentos em:")
    print(f"  {input_folder}")
    print("e abra a tela 'Processar Pasta'.")


if __name__ == "__main__":
    main()
