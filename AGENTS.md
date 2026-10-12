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
## Preparação do Ambiente (alunos — Windows)

Quando o usuário pedir para **analisar, instalar, preparar o ambiente ou iniciar**
a aplicação, ele **não é programador**. Siga exatamente este roteiro, explicando
cada passo em português simples, sem alterar código do projeto:

1. **Não modifique arquivos `.py`, testes ou scripts.** A tarefa é só preparar e executar.
2. Confirme que a pasta aberta é a raiz do projeto (contém `README.md`, `_start.bat`,
   `requirements.txt`). Se estiver dentro de uma pasta-pai (ex.: ZIP extraído com pasta
   duplicada), avise o usuário qual pasta abrir.
3. Verifique o Python com `py --version` (alternativa: `python --version`).
   Precisa ser 3.11 ou superior (recomendado 3.13). Se faltar, instale com
   `winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements`
   e peça para o usuário **fechar e reabrir o Antigravity** antes de continuar.
4. Prepare o ambiente executando no terminal: `cmd /c .\_start.bat setup`
   (cria `.venv`, instala `requirements.txt` e cria o `.env` a partir do `.env.example`).
   Não use `pip install` global e não use `_start.ps1` (a política de execução do
   Windows pode bloquear scripts `.ps1`).
5. **Nunca leia, exiba ou peça a chave de API no chat.** Oriente o usuário a abrir o
   arquivo `.env` e colar a chave dele em `GEMINI_API_KEY=`, salvando com Ctrl+S.
6. Para iniciar a aplicação, execute `cmd /c .\_start.bat` e mantenha o terminal aberto
   (o serviço roda enquanto o terminal estiver aberto). O endereço é
   <http://127.0.0.1:8501>.
7. Em caso de erro, mostre a mensagem, explique a causa provável em uma frase e proponha
   a correção. Erros comuns: Python ausente; porta 8501 ocupada (feche o terminal anterior);
   falha no pip (apague a pasta `.venv` e rode `cmd /c .\_start.bat setup` de novo).

