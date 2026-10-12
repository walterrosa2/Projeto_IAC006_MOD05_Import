# Instruções para Agente de Desenvolvimento — Antigravity

Use este documento como contexto principal para implementar o projeto.

## 1. Papel do Agente

Você é o agente de desenvolvimento responsável por construir uma aplicação local para organização documental, classificação contábil com IA, validação humana e exportação para Domínio Contábil.

Siga desenvolvimento orientado por especificação.

Não pule etapas. Não implemente features avançadas antes das bases de cadastro, banco, scanner e validação.

---

## 2. Objetivo da Aplicação

Construir uma aplicação que:

1. leia a pasta `DADOS_A_CLASSIFICAR` de cada cliente;
2. identifique automaticamente documentos;
3. copie documentos para pastas padronizadas;
4. extraia dados principais;
5. use IA para sugerir lançamento contábil;
6. permita revisão e correção pelo contador;
7. registre correções e exemplos;
8. gere XLSX no layout do Domínio Contábil;
9. permita consultar histórico de documentos e lançamentos.

---

## 3. Stack Obrigatória do MVP

```text
Python
Streamlit
SQLite
Pydantic
Biblioteca de leitura PDF
Biblioteca de exportação XLSX
pytest
.env para segredos
```

Não usar banco em nuvem no MVP. Não hardcodar chaves de API.

---

## 4. Regras de Segurança

- Nunca gravar chave de API no código.
- Usar `.env`.
- Não registrar tokens em log.
- Não enviar para IA mais conteúdo do que o necessário.
- Tratar CPF/CNPJ e dados financeiros como sensíveis.
- Criar `.env.example` sem credenciais reais.

---

## 5. Estrutura de Pastas Esperada

```text
classificador-contabil/
  app/
  core/
  db/
  data/
  logs/
  tests/
  docs/
```

Siga a arquitetura descrita no arquivo `02_Arquitetura_Tecnica_IDE.md`.

---

## 6. Ordem de Implementação

Implemente nesta ordem:

1. setup do projeto;
2. banco de dados;
3. cadastro de empresas;
4. plano de contas;
5. históricos;
6. centros de custo;
7. orientações;
8. exemplos de lançamentos;
9. scanner da pasta;
10. hash e duplicidade;
11. organizador de pastas;
12. extração de dados;
13. IA para lançamento;
14. validação humana;
15. exportação Domínio;
16. consultas e histórico.

Não inicie IA antes de existir plano de contas, orientações e exemplos.

---

## 7. Regras Funcionais Críticas

### 7.1 Pasta de entrada

Cada empresa possui:

```text
CLIENTES/{cliente}/DADOS_A_CLASSIFICAR/
```

### 7.2 Pastas de destino

```text
CLIENTES/{cliente}/{ano}/{mes}/COMPROVANTES/
CLIENTES/{cliente}/{ano}/{mes}/EXTRATOS/
CLIENTES/{cliente}/{ano}/{mes}/FATURAMENTO/
CLIENTES/{cliente}/{ano}/{mes}/PLANILHAS/
CLIENTES/{cliente}/{ano}/{mes}/NOTAS_FISCAIS/
CLIENTES/{cliente}/{ano}/{mes}/CTES/
CLIENTES/{cliente}/{ano}/{mes}/CONTAS_PAGAS/
CLIENTES/{cliente}/{ano}/{mes}/OUTROS/
CLIENTES/{cliente}/{ano}/{mes}/ERROS/
CLIENTES/{cliente}/{ano}/{mes}/DUPLICADOS/
```

### 7.3 Não mover no MVP

Copiar os arquivos para a pasta de destino. Preservar arquivo original.

### 7.4 Documento desconhecido

Enviar para `OUTROS`.

### 7.5 Falha técnica

Enviar para `ERROS` e registrar motivo.

### 7.6 Duplicado

Enviar para `DUPLICADOS` e não gerar lançamento.

### 7.7 Exportação

Exportar somente lançamentos aprovados.

---

## 8. Cadastro de Exemplos de Lançamentos

Criar tela específica para exemplos por empresa.

O exemplo deve explicar:

- qual documento é base;
- qual tipo documental;
- qual conta débito;
- qual conta crédito;
- qual histórico;
- quando usar;
- por que usar.

A IA deve receber exemplos relevantes no prompt.

Correções feitas pelo usuário podem virar exemplos, mas apenas após confirmação.

---

## 9. JSON Obrigatório da IA

A IA deve retornar exatamente um JSON validável:

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

Se a IA retornar algo fora do schema, o sistema deve marcar erro controlado.

---

## 10. Prompt Base da IA

Use o seguinte modelo conceitual:

```text
Você é um assistente contábil. Sua tarefa é sugerir um lançamento contábil preliminar para revisão humana.

Empresa:
{company}

Tipo documental:
{document_type}

Dados extraídos:
{extracted_data}

Texto relevante do documento:
{document_text}

Plano de contas ativo:
{chart_of_accounts}

Históricos padrão:
{standard_histories}

Centros de custo:
{cost_centers}

Orientações da empresa:
{company_guidelines}

Exemplos de lançamentos relevantes:
{accounting_examples}

Correções anteriores relevantes:
{correction_memory}

Regras:
- Não invente contas.
- Use apenas contas existentes no plano de contas.
- Informe se o documento não deve gerar lançamento.
- Se houver risco de duplicidade, adicione warning.
- Responda somente JSON válido.
```

---

## 11. Testes Obrigatórios

Criar testes para:

- cálculo de hash;
- duplicidade;
- organização de pasta;
- validação de JSON da IA;
- validação de conta existente;
- exportação XLSX;
- bloqueio de lançamento pendente na exportação.

---

## 12. Critério de Parada por Fase

Ao finalizar cada fase:

1. mostrar arquivos alterados;
2. informar como executar;
3. informar como testar;
4. registrar pendências;
5. não avançar sem confirmação.

---

## 13. Não Fazer

- Não criar integração direta com Domínio no MVP.
- Não criar login complexo no MVP.
- Não usar fine-tuning como primeira solução.
- Não sobrescrever documentos originais.
- Não aceitar lançamento sem conta existente.
- Não exportar lançamento pendente.
- Não ocultar erros da IA.