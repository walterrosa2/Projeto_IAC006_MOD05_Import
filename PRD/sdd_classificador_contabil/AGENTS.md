# AGENTS.md — Regras para Agentes no Repositório

## Missão

Construir uma aplicação local para escritório contábil que organize documentos de clientes, classifique documentos, gere lançamentos contábeis preliminares com IA, permita validação humana e exporte XLSX para Domínio Contábil.

## Processo de Trabalho

Siga sempre:

IDEIA → CONTEXTO → REQUISITOS → ESPECIFICAÇÃO → ARQUITETURA → PLANO → IMPLEMENTAÇÃO → TESTES → DOCUMENTAÇÃO → EVOLUÇÃO

## Regras Antes de Codar

Antes de implementar qualquer tarefa, confirme:

- objetivo da tarefa;
- arquivos impactados;
- entradas;
- saídas;
- dependências;
- critério de aceite;
- testes esperados.

## Padrões

- Python.
- Streamlit no MVP.
- SQLite no MVP.
- Pydantic para validação.
- pytest para testes.
- `.env` para segredos.
- logs sem dados sensíveis.

## Regra Contábil Principal

A IA sugere. O contador aprova.

Nenhum lançamento deve ser exportado sem status aprovado.

## Pastas Especiais

- `OUTROS`: documento lido, mas não classificado com segurança.
- `ERROS`: falha técnica.
- `DUPLICADOS`: arquivo ou fato contábil duplicado.

## Duplicidade

Sempre calcular hash do arquivo. Também comparar dados essenciais quando disponíveis: data, valor, contraparte, número de documento e tipo documental.

## Exemplos e Correções

Exemplos de lançamentos por empresa devem ser usados como contexto para IA. Correções do usuário devem ser armazenadas e podem virar exemplos após confirmação.

## Segurança

Nunca versionar:

- `.env`;
- chaves de API;
- dados reais de clientes;
- documentos sensíveis.

## Definition of Done

Uma entrega só está pronta quando:

- código executa;
- teste mínimo passa;
- erro tratado;
- documentação atualizada;
- status e logs estão claros;
- não há exposição de segredos.