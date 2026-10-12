# Plano de Execução e Backlog Técnico

**Projeto:** Classificador Contábil Automatizado  
**Versão:** 0.2  
**Objetivo:** orientar implementação incremental na IDE agentic.

---

## 1. Estratégia de Execução

O projeto deve ser construído em incrementos pequenos e testáveis.

Não implementar IA completa antes de existirem:

- cadastro de empresa;
- plano de contas;
- orientações;
- exemplos;
- banco de dados;
- validação de retorno;
- tela de revisão.

A lógica contábil deve ser auditável. A IA sugere, o contador aprova.

---

## 2. Fase 0 — Preparação

### Tarefa 0.1 — Criar repositório

**Entregas:**

- estrutura inicial;
- `.gitignore`;
- `.env.example`;
- `requirements.txt`;
- `README.md`.

**Critério de aceite:**

- projeto abre na IDE;
- ambiente virtual pode ser criado;
- dependências instalam sem erro.

### Tarefa 0.2 — Configurar aplicação Streamlit

**Entregas:**

- `app/main.py`;
- menu lateral;
- páginas vazias.

**Critério de aceite:**

- comando `streamlit run app/main.py` abre a aplicação.

---

## 3. Fase 1 — Banco e Cadastros Base

### Tarefa 1.1 — Criar banco SQLite e modelos

**Arquivos:**

- `db/database.py`
- `db/models.py`

**Entidades:**

- companies;
- chart_of_accounts;
- standard_histories;
- cost_centers;
- company_guidelines;
- accounting_examples;
- processed_documents;
- extracted_data;
- accounting_entries;
- entry_corrections;
- export_batches;
- export_batch_items.

**Critério de aceite:**

- banco criado automaticamente;
- tabelas existem;
- aplicação inicia sem erro.

### Tarefa 1.2 — Tela de empresas

**Arquivos:**

- `app/pages/02_empresas.py`
- `db/repositories/company_repository.py`

**Critério de aceite:**

- cadastrar empresa;
- editar empresa;
- listar empresas;
- informar pasta de entrada e destino.

### Tarefa 1.3 — Plano de contas

**Arquivos:**

- `app/pages/03_plano_contas.py`

**Critério de aceite:**

- cadastrar conta manualmente;
- importar de planilha simples;
- listar por empresa;
- marcar conta ativa/inativa.

### Tarefa 1.4 — Históricos padrão

**Arquivos:**

- `app/pages/04_historicos.py`

**Critério de aceite:**

- cadastrar código e descrição;
- listar por empresa.

### Tarefa 1.5 — Centros de custo

**Arquivos:**

- `app/pages/05_centros_custo.py`

**Critério de aceite:**

- cadastrar centro de custo;
- listar por empresa.

---

## 4. Fase 2 — Orientações e Exemplos de Lançamentos

### Tarefa 2.1 — Orientações por empresa

**Arquivos:**

- `app/pages/06_orientacoes.py`

**Critério de aceite:**

- contador cadastra orientações textuais;
- orientações possuem prioridade e status ativo;
- orientações podem ser filtradas por tipo documental.

### Tarefa 2.2 — Exemplos de lançamentos

**Arquivos:**

- `app/pages/07_exemplos_lancamentos.py`
- `db/repositories/example_repository.py`

**Campos principais:**

- empresa;
- título;
- tipo documental;
- documento base;
- fornecedor/cliente;
- palavras-chave;
- conta débito;
- conta crédito;
- histórico;
- centros de custo;
- explicação contábil.

**Critério de aceite:**

- usuário cadastra exemplo;
- sistema valida se contas existem;
- exemplos ativos são listados para uso pela IA.

### Tarefa 2.3 — Seletor de exemplos relevantes

**Arquivos:**

- `core/accounting/examples_selector.py`

**Critério de aceite:**

- dado um documento extraído, retorna exemplos relevantes da mesma empresa;
- prioriza mesmo tipo documental e contraparte semelhante.

---

## 5. Fase 3 — Scanner e Organização de Pastas

### Tarefa 3.1 — Scanner da pasta

**Arquivos:**

- `core/scanner/file_scanner.py`

**Critério de aceite:**

- lê arquivos da pasta `DADOS_A_CLASSIFICAR`;
- ignora subpastas não configuradas;
- retorna lista de arquivos novos.

### Tarefa 3.2 — Hash e duplicidade

**Arquivos:**

- `core/scanner/file_hash.py`
- `core/scanner/duplicate_detector.py`

**Critério de aceite:**

- calcula SHA-256;
- detecta arquivo já processado;
- marca duplicado sem gerar lançamento.

### Tarefa 3.3 — Classificação documental inicial

**Arquivos:**

- `core/documents/document_classifier.py`
- `core/documents/document_types.py`

**Critério de aceite:**

- classifica por regras simples e texto extraído;
- envia desconhecido para `OUTROS`;
- envia erro para `ERROS`.

### Tarefa 3.4 — Organizador de pastas

**Arquivos:**

- `core/documents/folder_organizer.py`

**Critério de aceite:**

- cria estrutura `cliente/ano/mês/tipo`;
- copia arquivo para pasta adequada;
- renomeia com segurança se já existir arquivo com mesmo nome;
- registra caminho final.

### Tarefa 3.5 — Tela Processar Pasta

**Arquivos:**

- `app/pages/08_processar_pasta.py`

**Critério de aceite:**

- usuário seleciona empresa;
- sistema mostra arquivos encontrados;
- botão processa lote;
- resultado mostra classificados, erros, duplicados e outros.

---

## 6. Fase 4 — Extração de Dados

### Tarefa 4.1 — Extrator base

**Arquivos:**

- `core/extractors/base_extractor.py`
- `core/extractors/pdf_text_extractor.py`

**Critério de aceite:**

- extrai texto de PDF;
- retorna erro controlado se falhar.

### Tarefa 4.2 — Extrator comprovante PIX

**Arquivos:**

- `core/extractors/pix_extractor.py`

**Critério de aceite:**

- extrai data, valor, pagador, favorecido e número do comprovante quando presentes.

### Tarefa 4.3 — Extrator relatório de contas pagas

**Arquivos:**

- `core/extractors/contas_pagas_extractor.py`

**Critério de aceite:**

- extrai credor, documento, data de baixa, valor e líquido.

### Tarefa 4.4 — Extrator faturamento

**Arquivos:**

- `core/extractors/faturamento_extractor.py`

**Critério de aceite:**

- extrai cliente, centro de custo, documento, data, valor bruto, retenções e líquido.

### Tarefa 4.5 — Extrator CT-e

**Arquivos:**

- `core/extractors/cte_extractor.py`

**Critério de aceite:**

- extrai número, chave, emissor, tomador, valor do serviço e ICMS.

### Tarefa 4.6 — Persistência de dados extraídos

**Arquivos:**

- `db/repositories/document_repository.py`

**Critério de aceite:**

- texto bruto e JSON estruturado são salvos por documento.

---

## 7. Fase 5 — IA para Lançamentos Contábeis

### Tarefa 5.1 — Prompt builder

**Arquivos:**

- `core/accounting/prompt_builder.py`

**Critério de aceite:**

- monta prompt com empresa, documento, plano de contas, orientações e exemplos;
- limita contexto excessivo;
- proíbe inventar contas.

### Tarefa 5.2 — Cliente IA

**Arquivos:**

- `core/accounting/ai_accounting_classifier.py`

**Critério de aceite:**

- usa chave via `.env`;
- retorna JSON;
- trata timeout e erro de API;
- nunca registra chave em log.

### Tarefa 5.3 — Validador contábil

**Arquivos:**

- `core/accounting/accounting_validator.py`

**Critério de aceite:**

- valida schema;
- valida conta débito;
- valida conta crédito;
- valida data e valor;
- define status pendente, erro ou pronto para revisão.

### Tarefa 5.4 — Gerador de lançamento

**Arquivos:**

- `core/accounting/entry_generator.py`

**Critério de aceite:**

- gera `accounting_entries`;
- vincula lançamento ao documento;
- status inicial é `PENDING_REVIEW`.

---

## 8. Fase 6 — Validação Humana

### Tarefa 6.1 — Tela de validação

**Arquivos:**

- `app/pages/10_validacao_lancamentos.py`

**Critério de aceite:**

- lista lançamentos pendentes;
- mostra arquivo/documento de origem;
- permite editar data, contas, valor, histórico, centro de custo;
- permite aprovar, rejeitar ou marcar duplicado.

### Tarefa 6.2 — Campo de orientação corretiva

**Critério de aceite:**

- quando usuário altera lançamento, sistema exibe campo orientativo;
- salva correção;
- permite marcar “converter em exemplo”.

### Tarefa 6.3 — Memória de correções

**Arquivos:**

- `core/accounting/correction_memory.py`

**Critério de aceite:**

- correções podem ser consultadas;
- correções relevantes entram no contexto da IA em processamentos futuros.

---

## 9. Fase 7 — Exportação Domínio

### Tarefa 7.1 — Exportador XLSX

**Arquivos:**

- `core/dominio/dominio_exporter.py`

**Critério de aceite:**

- gera XLSX com as colunas do modelo Domínio;
- inclui apenas lançamentos aprovados;
- respeita filtros de empresa e período.

### Tarefa 7.2 — Validador de exportação

**Arquivos:**

- `core/dominio/export_validator.py`

**Critério de aceite:**

- bloqueia exportação se faltar conta, valor, data ou histórico obrigatório.

### Tarefa 7.3 — Tela de exportação

**Arquivos:**

- `app/pages/11_exportacao_dominio.py`

**Critério de aceite:**

- usuário escolhe empresa e competência;
- visualiza prévia;
- gera arquivo;
- lote fica registrado.

---

## 10. Fase 8 — Consultas e Auditoria

### Tarefa 8.1 — Documentos processados

**Arquivos:**

- `app/pages/09_documentos.py`

**Critério de aceite:**

- filtro por empresa, competência, tipo e status;
- mostra caminho do arquivo, erro e lançamento relacionado.

### Tarefa 8.2 — Histórico de exportações

**Arquivos:**

- `app/pages/12_historico_exportacoes.py`

**Critério de aceite:**

- lista lotes;
- permite ver lançamentos incluídos;
- permite baixar novamente o arquivo exportado.

### Tarefa 8.3 — Dashboard

**Arquivos:**

- `app/pages/01_dashboard.py`

**Critério de aceite:**

- mostra contadores de documentos e lançamentos por status.

---

## 11. Backlog Priorizado

| ID | Épico | Tarefa | Prioridade | Dependência | Status |
|---|---|---|---|---|---|
| T0.1 | Setup | Criar repositório e estrutura | Alta | - | A fazer |
| T0.2 | Setup | Configurar Streamlit | Alta | T0.1 | A fazer |
| T1.1 | Banco | Criar modelos SQLite | Alta | T0.1 | A fazer |
| T1.2 | Cadastro | Empresas | Alta | T1.1 | A fazer |
| T1.3 | Cadastro | Plano de contas | Alta | T1.1 | A fazer |
| T1.4 | Cadastro | Históricos | Alta | T1.1 | A fazer |
| T1.5 | Cadastro | Centros de custo | Alta | T1.1 | A fazer |
| T2.1 | Contexto IA | Orientações por empresa | Alta | T1.2 | A fazer |
| T2.2 | Contexto IA | Exemplos de lançamentos | Alta | T1.3 | A fazer |
| T2.3 | Contexto IA | Seletor de exemplos | Média | T2.2 | A fazer |
| T3.1 | Documentos | Scanner de pasta | Alta | T1.2 | A fazer |
| T3.2 | Documentos | Hash e duplicidade | Alta | T3.1 | A fazer |
| T3.3 | Documentos | Classificação documental | Alta | T3.1 | A fazer |
| T3.4 | Documentos | Organizador de pastas | Alta | T3.3 | A fazer |
| T3.5 | Interface | Tela processar pasta | Alta | T3.1-T3.4 | A fazer |
| T4.1 | Extração | Extrator base PDF | Alta | T3.3 | A fazer |
| T4.2 | Extração | Extrator PIX | Alta | T4.1 | A fazer |
| T4.3 | Extração | Extrator contas pagas | Alta | T4.1 | A fazer |
| T4.4 | Extração | Extrator faturamento | Alta | T4.1 | A fazer |
| T4.5 | Extração | Extrator CT-e | Média | T4.1 | A fazer |
| T5.1 | IA | Prompt builder | Alta | T2.1-T2.3-T4 | A fazer |
| T5.2 | IA | Cliente IA | Alta | T5.1 | A fazer |
| T5.3 | IA | Validador contábil | Alta | T1.3-T5.2 | A fazer |
| T5.4 | Contábil | Gerador de lançamento | Alta | T5.3 | A fazer |
| T6.1 | Revisão | Tela validação | Alta | T5.4 | A fazer |
| T6.2 | Revisão | Orientação corretiva | Alta | T6.1 | A fazer |
| T6.3 | Revisão | Memória de correções | Média | T6.2 | A fazer |
| T7.1 | Domínio | Exportador XLSX | Alta | T6.1 | A fazer |
| T7.2 | Domínio | Validador exportação | Alta | T7.1 | A fazer |
| T7.3 | Domínio | Tela exportação | Alta | T7.1 | A fazer |
| T8.1 | Consulta | Documentos processados | Média | T3-T4 | A fazer |
| T8.2 | Consulta | Histórico exportações | Média | T7.3 | A fazer |
| T8.3 | Consulta | Dashboard | Baixa | T8.1 | A fazer |

---

## 12. Definition of Done

Uma tarefa só deve ser considerada concluída quando:

- código implementado;
- erro tratado;
- tela ou função testada;
- dados persistidos corretamente;
- logs não expõem dados sensíveis;
- teste mínimo criado quando aplicável;
- README ou documentação atualizada quando houver comando novo.

---

## 13. Entrega Recomendada ao Agente da IDE

Para cada fase, pedir ao agente:

1. explique o plano antes de codar;
2. liste arquivos que serão criados/alterados;
3. implemente;
4. execute testes;
5. atualize documentação;
6. não avance para próxima fase sem validação.