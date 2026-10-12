# Arquitetura Técnica para IDE Agentic — Classificador Contábil com IA

**Projeto:** Classificador Contábil Automatizado  
**Versão:** 0.2  
**Objetivo:** fornecer contexto técnico suficiente para implementação via IDE agentic Antigravity.

---

## 1. Premissas Técnicas

- Aplicação local no MVP.
- Interface web simples para uso por contador ou assistente.
- Banco local SQLite.
- Backend em Python.
- Exportação XLSX no layout do Domínio Contábil.
- IA usada como classificador e gerador de lançamento sugerido, com retorno JSON validado.
- Toda classificação contábil precisa de revisão humana antes da exportação.
- Não armazenar chaves de API no código.
- Desenvolvimento orientado por especificação e testes incrementais.

---

## 2. Stack Recomendada

### MVP

```text
Linguagem: Python
Interface: Streamlit
Banco: SQLite
ORM: SQLAlchemy ou camada simples de repositórios
Validação: Pydantic
Leitura de PDF: PyMuPDF e/ou pdfplumber
Leitura de planilhas: biblioteca Python para XLSX/CSV
Exportação XLSX: biblioteca Python para XLSX
IA: provedor configurável por variável de ambiente
Configuração: .env
Logs: logging nativo do Python
Testes: pytest
```

### Evolução futura

```text
Backend: FastAPI
Frontend: React ou Next.js
Banco: PostgreSQL
Fila: Celery/RQ
Armazenamento: S3 compatível ou rede interna
Autenticação: usuários e perfis
Deploy: servidor interno ou cloud privada
```

---

## 3. Visão de Componentes

```text
[Pastas dos Clientes]
        |
        v
[File Scanner]
        |
        v
[Document Registry / Hash]
        |
        v
[Document Classifier]
        |
        +--> OUTROS
        +--> ERROS
        +--> DUPLICADOS
        |
        v
[Folder Organizer]
        |
        v
[Data Extractor]
        |
        v
[AI Accounting Classifier]
        |
        v
[Validation UI]
        |
        v
[Approved Entries]
        |
        v
[Dominio XLSX Exporter]
```

---

## 4. Estrutura de Pastas do Projeto

```text
classificador-contabil/
  README.md
  .env.example
  .gitignore
  requirements.txt
  pyproject.toml

  app/
    main.py
    pages/
      01_dashboard.py
      02_empresas.py
      03_plano_contas.py
      04_historicos.py
      05_centros_custo.py
      06_orientacoes.py
      07_exemplos_lancamentos.py
      08_processar_pasta.py
      09_documentos.py
      10_validacao_lancamentos.py
      11_exportacao_dominio.py
      12_historico_exportacoes.py

  core/
    config.py
    logging_config.py
    constants.py
    exceptions.py

    scanner/
      file_scanner.py
      file_hash.py
      duplicate_detector.py

    documents/
      document_classifier.py
      folder_organizer.py
      document_types.py
      metadata_extractor.py

    extractors/
      base_extractor.py
      pdf_text_extractor.py
      pix_extractor.py
      extrato_extractor.py
      faturamento_extractor.py
      contas_pagas_extractor.py
      cte_extractor.py
      spreadsheet_extractor.py

    accounting/
      prompt_builder.py
      ai_accounting_classifier.py
      accounting_validator.py
      entry_generator.py
      correction_memory.py
      examples_selector.py

    dominio/
      dominio_template.py
      dominio_exporter.py
      export_validator.py

  db/
    database.py
    models.py
    repositories/
      company_repository.py
      document_repository.py
      accounting_entry_repository.py
      example_repository.py
      export_repository.py

  data/
    app.db
    samples/
    templates/
      planilhamodeloimportacaolancamentoscontabeis.xlsx

  logs/
    app.log

  tests/
    test_file_hash.py
    test_folder_organizer.py
    test_document_classifier.py
    test_accounting_validator.py
    test_dominio_exporter.py

  docs/
    PRD.md
    ARCHITECTURE.md
    TASK_PLAN.md
    AGENT_INSTRUCTIONS.md
```

---

## 5. Modelo de Dados

### 5.1 companies

```text
id
name
legal_name
cnpj
input_folder_path
destination_folder_path
responsible_accountant
status
created_at
updated_at
```

### 5.2 chart_of_accounts

```text
id
company_id
account_code
description
account_type
accepts_entries
active
created_at
updated_at
```

### 5.3 standard_histories

```text
id
company_id
history_code
description
active
created_at
updated_at
```

### 5.4 cost_centers

```text
id
company_id
cost_center_code
description
active
created_at
updated_at
```

### 5.5 company_guidelines

```text
id
company_id
title
guideline_text
applicable_document_type
priority
active
created_at
created_by
updated_at
```

### 5.6 accounting_examples

```text
id
company_id
title
document_type
base_document
counterparty
keywords
document_excerpt
debit_account_code
credit_account_code
history_code
history_complement_template
debit_cost_center_code
credit_cost_center_code
accounting_explanation
priority
active
created_at
created_by
updated_at
```

### 5.7 processed_documents

```text
id
company_id
original_file_name
original_file_path
stored_file_path
file_hash
file_extension
document_type
document_date
competence_year
competence_month
counterparty
document_number
amount
classification_confidence
processing_status
error_type
error_message
created_at
updated_at
```

### 5.8 extracted_data

```text
id
document_id
raw_text
structured_json
extractor_name
extraction_confidence
created_at
```

### 5.9 accounting_entries

```text
id
company_id
document_id
entry_date
debit_account_code
credit_account_code
amount
history_code
history_complement
batch_start
branch_code
debit_cost_center_code
credit_cost_center_code
ai_confidence
ai_justification
status
created_at
updated_at
approved_by
approved_at
```

### 5.10 entry_corrections

```text
id
entry_id
company_id
document_id
original_json
corrected_json
corrective_guidance
convert_to_example
created_by
created_at
```

### 5.11 export_batches

```text
id
company_id
period_year
period_month
file_path
exported_at
exported_by
status
```

### 5.12 export_batch_items

```text
id
export_batch_id
entry_id
created_at
```

---

## 6. Estados e Status

### 6.1 Status do documento

```text
NEW
CLASSIFIED
COPIED_TO_DESTINATION
EXTRACTED
ENTRY_GENERATED
PENDING_REVIEW
APPROVED
REJECTED
DUPLICATE
UNKNOWN
ERROR
EXPORTED
```

### 6.2 Status do lançamento

```text
PENDING_REVIEW
APPROVED
CORRECTED_APPROVED
REJECTED
DUPLICATE
ERROR
EXPORTED
```

---

## 7. Classificação Documental

### 7.1 Entrada

```json
{
  "file_name": "documento.pdf",
  "extension": ".pdf",
  "text_sample": "RECIBO DE TRANSFERÊNCIA PIX ENVIADO...",
  "company_context": {
    "company_name": "Cliente A",
    "cnpj": "00.000.000/0000-00"
  }
}
```

### 7.2 Saída esperada

```json
{
  "document_type": "COMPROVANTE_PIX",
  "confidence": 0.94,
  "reason": "Documento contém RECIBO DE TRANSFERÊNCIA PIX ENVIADO, valor, pagador e favorecido.",
  "document_date": "2026-01-06",
  "competence_year": 2026,
  "competence_month": 1
}
```

### 7.3 Regras de fallback

- Se confiança < 0.70: classificar como `OUTRO`.
- Se leitura falhou: classificar como `ERROR`.
- Se duplicado: classificar como `DUPLICATE`.
- Se data não for identificada: usar competência selecionada pelo usuário ou marcar como pendente.

---

## 8. Organizador de Pastas

### 8.1 Mapeamento tipo → pasta

```python
DOCUMENT_TYPE_TO_FOLDER = {
    "COMPROVANTE_PIX": "COMPROVANTES",
    "COMPROVANTE_TED": "COMPROVANTES",
    "COMPROVANTE_BOLETO": "COMPROVANTES",
    "EXTRATO_BANCARIO": "EXTRATOS",
    "FATURAMENTO": "FATURAMENTO",
    "PLANILHA": "PLANILHAS",
    "NOTA_FISCAL": "NOTAS_FISCAIS",
    "CTE": "CTES",
    "CONTAS_PAGAS": "CONTAS_PAGAS",
    "OUTRO": "OUTROS",
    "ERROR": "ERROS",
    "DUPLICATE": "DUPLICADOS"
}
```

### 8.2 Caminho de destino

```text
{destination_root}/{company_name}/{year}/{month_number} - {month_name}/{folder_name}/{safe_file_name}
```

### 8.3 Regra de cópia

No MVP, usar cópia, não mover definitivo. O arquivo original permanece em `DADOS_A_CLASSIFICAR`.

---

## 9. Extração de Dados

### 9.1 Campos mínimos comuns

```json
{
  "document_type": "string",
  "document_date": "YYYY-MM-DD",
  "amount": 0.0,
  "counterparty": "string",
  "document_number": "string|null",
  "description": "string",
  "source_file": "string"
}
```

### 9.2 Campos específicos

#### Comprovante PIX

```json
{
  "proof_number": "string",
  "transfer_datetime": "YYYY-MM-DDTHH:MM:SS",
  "payer_name": "string",
  "payer_cnpj_cpf": "string",
  "beneficiary_name": "string",
  "beneficiary_cnpj_cpf": "string",
  "amount": 0.0
}
```

#### Faturamento

```json
{
  "customer": "string",
  "document_number": "string",
  "title": "string",
  "issue_date": "YYYY-MM-DD",
  "gross_amount": 0.0,
  "withheld_taxes": {
    "ir": 0.0,
    "pcc": 0.0,
    "iss": 0.0,
    "inss": 0.0
  },
  "net_amount": 0.0,
  "cost_center": "string|null"
}
```

#### Contas pagas

```json
{
  "creditor": "string",
  "creditor_code": "string|null",
  "document": "string",
  "posting_number": "string",
  "payment_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD|null",
  "gross_amount": 0.0,
  "addition": 0.0,
  "discount": 0.0,
  "net_amount": 0.0
}
```

#### CT-e

```json
{
  "cte_number": "string",
  "access_key": "string",
  "issue_datetime": "YYYY-MM-DDTHH:MM:SS",
  "issuer": "string",
  "taker": "string",
  "sender": "string",
  "recipient": "string",
  "service_amount": 0.0,
  "icms_amount": 0.0,
  "origin_city": "string",
  "destination_city": "string"
}
```

---

## 10. IA para Classificação Contábil

### 10.1 Contexto enviado à IA

O prompt deve conter:

```text
1. Papel: assistente contábil para classificação preliminar.
2. Empresa.
3. Tipo documental.
4. Dados extraídos.
5. Texto relevante do documento.
6. Plano de contas ativo da empresa.
7. Históricos padrão.
8. Centros de custo.
9. Orientações da empresa.
10. Exemplos de lançamentos relevantes.
11. Correções anteriores relevantes.
12. Regras de saída em JSON.
13. Proibição de inventar contas inexistentes.
```

### 10.2 JSON de saída obrigatório

```json
{
  "should_generate_entry": true,
  "base_document_reason": "string",
  "entry_date": "YYYY-MM-DD",
  "debit_account_code": "string",
  "credit_account_code": "string",
  "amount": 0.0,
  "history_code": "string|null",
  "history_complement": "string",
  "debit_cost_center_code": "string|null",
  "credit_cost_center_code": "string|null",
  "confidence": 0.0,
  "justification": "string",
  "warnings": ["string"]
}
```

### 10.3 Validações pós-IA

A aplicação deve rejeitar ou marcar pendente quando:

- JSON inválido;
- conta débito inexistente;
- conta crédito inexistente;
- valor ausente;
- data ausente;
- confiança abaixo do limite;
- IA indicar que não deve gerar lançamento;
- documento possivelmente duplicado;
- histórico obrigatório não preenchido.

---

## 11. Seleção de Exemplos para IA

Módulo: `core/accounting/examples_selector.py`

Critérios:

1. mesma empresa;
2. mesmo tipo documental;
3. fornecedor/cliente semelhante;
4. palavras-chave encontradas no documento;
5. prioridade do exemplo;
6. exemplos ativos;
7. limite de exemplos por prompt, para evitar contexto excessivo.

Saída:

```json
[
  {
    "title": "Pagamento de prestador por contas pagas",
    "document_type": "CONTAS_PAGAS",
    "base_document": "Relatório de contas pagas",
    "expected_debit": "XXXX",
    "expected_credit": "YYYY",
    "history_model": "Pagamento a {fornecedor} conforme {documento}",
    "explanation": "Usar contas pagas como base quando houver credor, documento e líquido."
  }
]
```

---

## 12. Exportador Domínio

### 12.1 Entrada

Lista de lançamentos aprovados.

### 12.2 Saída

Arquivo XLSX com colunas:

```text
Data
Cód. Conta Debito
Cód. Conta Credito
Valor
Cód. Histórico
Complemento Histórico
Inicia Lote
Código Matriz/Filial
Centro de Custo Débito
Centro de Custo Crédito
```

### 12.3 Regras

- Não exportar pendentes.
- Não exportar rejeitados.
- Não exportar duplicados.
- Não exportar erro.
- Registrar lote.
- Atualizar status dos lançamentos para `EXPORTED`.

---

## 13. Segurança e LGPD

- `.env` fora do versionamento.
- Nunca registrar chave de API em log.
- Não enviar documentos desnecessários à IA; enviar apenas texto e campos relevantes quando possível.
- Permitir apagar dados de teste.
- Evitar expor CPF completo em telas quando não necessário.
- Registrar trilha de auditoria das aprovações e correções.

---

## 14. Testes Mínimos

### Unitários

- hash de arquivo;
- detecção de duplicidade;
- criação de caminho destino;
- mapeamento tipo → pasta;
- validação do JSON da IA;
- validação de conta existente;
- exportação XLSX.

### Integração

- processar pasta com documentos variados;
- classificar e copiar para destino;
- gerar lançamento pendente;
- aprovar lançamento;
- exportar Domínio.

### Aceitação

- usuário consegue processar cliente real;
- revisar lançamentos;
- corrigir classificação;
- salvar orientação corretiva;
- gerar planilha importável.

---

## 15. Ordem Recomendada de Implementação

1. Estrutura do projeto.
2. Banco e modelos.
3. Cadastro de empresas.
4. Plano de contas, históricos e centros de custo.
5. Orientações e exemplos.
6. Scanner de pasta.
7. Hash e duplicidade.
8. Organizador de pastas.
9. Extração básica de PDF.
10. Classificador documental.
11. Prompt e retorno JSON da IA.
12. Tela de validação.
13. Exportador Domínio.
14. Consultas.
15. Testes e documentação.