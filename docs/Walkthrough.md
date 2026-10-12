# Walkthrough — Classificador Contábil com IA

**Versão:** 0.1.0 (MVP) · **Data:** 2026-09-19
**Escrito para:** quem for manter ou auditar este código.

Este documento diz **o que foi construído**, **onde está no código** e **como validar**.

---

## 1. Visão geral

A aplicação implementa a esteira descrita no PRD:

```text
pasta do cliente → hash → duplicidade → texto → classificação documental
  → organização em pastas → extração de dados → hierarquia de documento base
  → IA (sugestão) → validação automática → revisão humana → exportação Domínio
```

Cada etapa é um módulo isolado e testável. O orquestrador é
[core/pipeline.py](../core/pipeline.py).

---

## 2. Mapa do código por requisito

| Requisito | Onde está | Como validar |
|---|---|---|
| RF01 Cadastro de empresa | [app/pages/02_empresas.py](../app/pages/02_empresas.py), [company_repository.py](../db/repositories/company_repository.py) | Tela Empresas → cadastrar e editar |
| RF02 Plano de contas | [03_plano_contas.py](../app/pages/03_plano_contas.py) | Importar XLSX/CSV; colunas são reconhecidas sem distinção de acento/caixa |
| RF03 Históricos | [04_historicos.py](../app/pages/04_historicos.py) | Tela Históricos |
| RF04 Centros de custo | [05_centros_custo.py](../app/pages/05_centros_custo.py) | Tela Centros de Custo |
| RF05 Orientações | [06_orientacoes.py](../app/pages/06_orientacoes.py) | Entram no prompt via `prompt_builder` |
| RF06 Exemplos | [07_exemplos_lancamentos.py](../app/pages/07_exemplos_lancamentos.py) | Contas são validadas contra o plano no submit |
| RF07 Scanner | [core/scanner/file_scanner.py](../core/scanner/file_scanner.py) | `pytest -k TestScanner` |
| RF08 Duplicidade | [file_hash.py](../core/scanner/file_hash.py), [duplicate_detector.py](../core/scanner/duplicate_detector.py) | `pytest tests/test_file_hash.py` |
| RF09 Classificação | [document_classifier.py](../core/documents/document_classifier.py), [document_types.py](../core/documents/document_types.py) | `pytest tests/test_document_classifier.py` |
| RF10 Organização | [folder_organizer.py](../core/documents/folder_organizer.py) | `pytest tests/test_folder_organizer.py` |
| RF11 OUTROS/ERROS/DUPLICADOS | [core/pipeline.py](../core/pipeline.py) | `pytest -k "CA02 or CA03 or CA04"` |
| RF12 Extração | [core/extractors/](../core/extractors/) | `pytest -k Extractor` |
| RF13 IA | [prompt_builder.py](../core/accounting/prompt_builder.py), [ai_accounting_classifier.py](../core/accounting/ai_accounting_classifier.py) | Tela Processar Pasta → "Gerar lançamentos com IA" |
| RF14 Validação do retorno | [accounting_validator.py](../core/accounting/accounting_validator.py) | `pytest tests/test_accounting_validator.py` |
| RF15 Tela de validação | [10_validacao_lancamentos.py](../app/pages/10_validacao_lancamentos.py) | Aprovar / rejeitar / marcar duplicado |
| RF16 Correções | [correction_memory.py](../core/accounting/correction_memory.py), [13_correcoes.py](../app/pages/13_correcoes.py) | Alterar um lançamento e aprovar |
| RF17 Consulta documentos | [09_documentos.py](../app/pages/09_documentos.py) | Filtros por competência, tipo, status |
| RF18 Consulta lançamentos | [accounting_entry_repository.py](../db/repositories/accounting_entry_repository.py) | Filtros da tela de validação |
| RF19 Exportação | [dominio_exporter.py](../core/dominio/dominio_exporter.py) | `pytest tests/test_dominio_exporter.py` |
| RF20 Histórico de lotes | [12_historico_exportacoes.py](../app/pages/12_historico_exportacoes.py) | Tela Histórico de Exportações |

---

## 3. Decisões de implementação que valem explicação

### 3.1 Classificação documental por regras, não por IA

O PRD permite IA na classificação documental, mas o classificador implementado é
**determinístico, por assinaturas textuais** ([document_types.py](../core/documents/document_types.py)).
Motivos: é auditável (o campo `classification_reason` diz exatamente quais termos
decidiram), é gratuito e instantâneo, e a IA fica reservada para a decisão que
realmente exige julgamento — a classificação contábil.

Pontuação: termo forte 0,45 · termo fraco 0,10 · nome do arquivo 0,25
(+0,25 de bônus só quando o conteúdo corrobora — o nome sozinho nunca classifica)
· penalidade de termo negativo 0,35. Teto de 0,98, pois um classificador por
regras não deve alegar certeza absoluta. Abaixo de `MIN_CLASSIFICATION_CONFIDENCE`
(0,70 por padrão) o documento vai para **OUTROS**.

### 3.2 Hierarquia de documento base

Implementada em `decide_base_document`
([duplicate_detector.py](../core/scanner/duplicate_detector.py)) e chamada **antes**
de gastar uma chamada de IA. Documentos com o mesmo valor em datas próximas
(±3 dias) são considerados o mesmo fato contábil; apenas o de maior riqueza
gera lançamento. Empate de prioridade é resolvido pelo menor `id`, para que o
resultado seja determinístico.

Validado em `TestHierarquiaDeDocumentoBase`: um comprovante PIX não gera
lançamento quando existe o relatório de contas pagas do mesmo pagamento.

### 3.3 Duplicidade em duas camadas

1. **Hash SHA-256** — o mesmo arquivo reenviado.
2. **Dados essenciais** — data + valor + (documento OU contraparte), para o mesmo
   fato chegando em arquivo diferente.

A busca por hash ignora documentos já marcados como `DUPLICATE`, senão o segundo
duplicado apontaria para o primeiro duplicado em vez do original.

### 3.4 A IA não pode inventar contas

Três camadas de proteção:

1. O prompt recebe **apenas** contas ativas que aceitam lançamento, e a regra
   "NÃO invente contas" é explícita.
2. `validate_ai_payload` rejeita conta inexistente, inativa ou sintética.
3. `validate_export_batch` revalida na exportação — protege contra contas
   desativadas depois da aprovação.

A mesma validação se aplica à edição humana (`validate_manual_entry`): o
contador também não aprova conta inexistente.

### 3.5 Sugestão inválida não é descartada em silêncio

Quando a IA devolve algo que não passa na validação, o lançamento é criado com
status `ERROR` e o motivo em `validation_issues`. Ele aparece na tela de
validação para o contador corrigir — some-lo seria esconder o erro da IA
(proibido pela instrução 13 do documento do agente).

### 3.6 Provedor de IA plugável, com MOCK padrão

[ai_accounting_classifier.py](../core/accounting/ai_accounting_classifier.py)
suporta `mock | anthropic | openai | gemini`. O padrão é `mock`, para que a
esteira inteira possa ser percorrida e testada sem chave de API. O MOCK não
inventa contas — usa as duas primeiras do plano, devolve confiança 0,35 e um
aviso explícito de que não tem valor contábil.

Retries com backoff exponencial cobrem falha de rede **e** resposta fora do
schema. Erro de configuração (chave ausente) não é repetido.

---

## 4. Modelo de dados

12 tabelas em [db/models.py](../db/models.py), conforme a seção 5 da arquitetura.
Dois campos foram acrescentados ao especificado:

- `companies.branch_code` — alimenta a coluna "Código Matriz/Filial" da exportação.
- `processed_documents.duplicate_of_id` / `duplicate_reason` — rastreiam a
  origem da duplicidade e o vínculo evidência → documento base.
- `accounting_entries.validation_issues` / `ai_warnings` — o que a validação e a
  IA sinalizaram, exibido na revisão.

`ON DELETE CASCADE` está ativo (PRAGMA `foreign_keys=ON` em
[db/database.py](../db/database.py)): excluir uma empresa remove seus dados.

---

## 5. Como validar a entrega

### 5.1 Testes automatizados

```powershell
.\_start.ps1 -Test
```

204 testes: unitários (hash, parsers, organizador, classificador, extratores,
validador, exportador), integração ponta a ponta (CA01–CA08 do PRD) e smoke de
todas as 14 telas, com e sem dados.

```powershell
.venv\Scripts\python.exe -m pytest --cov=core --cov=db --cov-report=term-missing
```

Cobertura atual: **81%** em `core/` + `db/`. O que está descoberto é sobretudo
o caminho de leitura real de PDF (`pdf_text_extractor`, 27%) e os SDKs dos
provedores de IA, que exigiriam arquivos binários e chamadas de rede.

### 5.2 Validação manual (roteiro de 10 minutos)

1. `.\_start.ps1` → a home indica "Provedor de IA em modo MOCK".
2. **Empresas** → cadastrar "Cliente A", marcar "criar a pasta de entrada".
3. **Plano de Contas** → cadastrar ao menos duas contas que aceitem lançamento.
4. **Históricos** → cadastrar um código (ex.: `101`).
5. Copiar alguns PDFs para a pasta `DADOS_A_CLASSIFICAR` do cliente.
6. **Processar Pasta** → marcar os arquivos, processar, conferir os contadores
   (classificados / outros / duplicados / erros) e a estrutura criada em disco.
7. Reprocessar a mesma pasta → tudo deve cair em **DUPLICADOS**.
8. Marcar "Gerar lançamentos com IA" ou usar o botão ao pé da tela.
9. **Validação de Lançamentos** → alterar o histórico de um lançamento, escrever
   uma orientação corretiva, marcar "converter em exemplo" e aprovar.
10. **Exportação Domínio** → conferir a prévia e gerar o XLSX.
11. **Histórico de Exportações** → o lote aparece e o arquivo pode ser rebaixado.
12. **Correções e Aprendizado** → converter a correção em exemplo.
13. **Configuração** → conferir banco, logs e contagem de eventos de auditoria.

### 5.3 Evidências geradas

| Arquivo | Conteúdo |
|---|---|
| `logs/app.log` | Log operacional, com rotação de 10 MB e retenção de 30 dias |
| `logs/audit.jsonl` | Trilha de auditoria: timestamp, ator, ação, alvo, resultado |
| `logs/ai_evidence/*.json` | Prompt e resposta brutos de cada chamada de IA |
| `data/app.db` | Banco SQLite |
| `data/exports/*.xlsx` | Planilhas geradas |

---

## 6. Limitações conhecidas

| Limitação | Impacto | Contorno |
|---|---|---|
| Sem OCR | PDF digitalizado vai para ERROS | Aplicar OCR externo e reenviar |
| Extratores por heurística de rótulo | Layout muito fora do padrão extrai menos campos | O texto completo vai para a IA de qualquer forma; a extração é apoio |
| Extrato bancário não gera lançamento por linha | Extrato entra como evidência/conciliação | Lançar pelo documento base |
| Sem login | Trilha de auditoria usa o nome digitado na barra lateral | Adequado a uso local; previsto no PRD |
| Faturamento com retenção gera um lançamento | Separação receita/imposto/líquido não é automática | A IA avisa; o contador desdobra na revisão |
| SQLite local | Um usuário por vez | Migração para PostgreSQL prevista na evolução |

---

## 7. Próximos passos sugeridos

1. Testar com documentos reais do escritório e ajustar as assinaturas em
   [document_types.py](../core/documents/document_types.py).
2. Configurar provedor de IA real e comparar as sugestões com o que o contador
   faria, alimentando a tela de Exemplos.
3. Avaliar OCR (Tesseract) para PDFs digitalizados.
4. Desdobramento automático de faturamento com retenção em múltiplos lançamentos.
