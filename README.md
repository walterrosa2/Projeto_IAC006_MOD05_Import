# Classificador Contábil com IA

Aplicação local para escritório contábil: lê a pasta de documentos do cliente,
identifica o tipo de cada documento, organiza os arquivos em estrutura
padronizada, extrai os dados, sugere lançamentos contábeis com IA, submete tudo
à validação do contador e exporta a planilha de importação do **Domínio Contábil**.

> **A IA sugere. O contador aprova.**
> Nenhum lançamento é exportado sem aprovação humana.

---

## Início rápido

```powershell
# Windows / PowerShell — cria venv, instala deps e sobe a aplicação
.\_start.ps1
```

```bat
REM Windows / cmd
_start.bat
```

A aplicação abre em <http://127.0.0.1:8501>.

Na primeira execução o script copia `.env.example` para `.env`. O padrão é
`AI_PROVIDER=mock`, que permite navegar por toda a esteira **sem chave de API** —
as sugestões são simuladas e sinalizadas como tal na interface.

### Configurar IA real

Edite o `.env`:

```ini
AI_PROVIDER=anthropic          # ou openai | gemini
AI_MODEL=claude-sonnet-5
ANTHROPIC_API_KEY=sua-chave-aqui
```

A tela **🔧 Configuração** mostra o diagnóstico do provedor, do banco e dos logs.

---

## Fluxo de trabalho

| # | Tela | O que fazer |
|---|---|---|
| 1 | 🏢 Empresas | Cadastrar o cliente, a pasta `DADOS_A_CLASSIFICAR` e a pasta de destino |
| 2 | 📋 Plano de Contas | Cadastrar ou importar (XLSX/CSV) o plano de contas |
| 3 | 🗒️ Históricos · 🏷️ Centros de Custo | Cadastros de apoio da exportação |
| 4 | 📌 Orientações | Regras contábeis da empresa, em linguagem natural |
| 5 | 💡 Exemplos de Lançamentos | Casos concretos que ensinam a IA |
| 6 | ⚙️ Processar Pasta | Classifica, organiza, extrai e (opcional) gera lançamentos |
| 7 | ✅ Validação de Lançamentos | Revisar, corrigir, aprovar ou rejeitar |
| 8 | 📤 Exportação Domínio | Gerar o XLSX apenas com lançamentos aprovados |
| 9 | 🗂️ Documentos · 📚 Exportações · 🧠 Correções | Consulta e auditoria |

---

## Regras que a aplicação garante

- Arquivos originais são **copiados**, nunca movidos — a pasta de entrada fica intacta.
- Documento não reconhecido com segurança vai para **OUTROS**.
- Falha técnica vai para **ERROS**, com um `.json` ao lado descrevendo o motivo.
- Duplicado vai para **DUPLICADOS** e não gera lançamento.
- Duplicidade é detectada por **hash SHA-256** e por **data + valor + contraparte/documento**.
- Quando vários documentos descrevem o mesmo fato, só o de **maior riqueza contábil**
  gera lançamento; os demais ficam como evidência (nota fiscal / CT-e / faturamento /
  contas pagas → extrato → comprovante PIX).
- A IA só pode usar contas **existentes, ativas e que aceitem lançamento**.
- Lançamento nasce em `PENDING_REVIEW` e **só é exportado depois de aprovado**.
- Toda correção do contador vira memória operacional e pode virar exemplo.

---

## Estrutura de pastas dos clientes

Entrada (o cliente deposita aqui):

```text
CLIENTES/Cliente A/DADOS_A_CLASSIFICAR/
```

Destino (criado automaticamente):

```text
CLIENTES/Cliente A/2026/01 - Janeiro/
  COMPROVANTES/  EXTRATOS/       FATURAMENTO/  PLANILHAS/
  NOTAS_FISCAIS/ CTES/           CONTAS_PAGAS/ OUTROS/
  ERROS/         DUPLICADOS/
```

Documentos sem data identificável vão para `SEM_COMPETENCIA/`, salvo quando uma
competência padrão é escolhida na tela de processamento.

---

## Formatos suportados

`.pdf` · `.xml` · `.xlsx` · `.xls` · `.csv` · `.txt`

### OCR de PDFs digitalizados

PDFs sem camada de texto (digitalizações) são transcritos por **OCR via IA
multimodal** — o mesmo provedor configurado em `AI_PROVIDER`, sem depender de
Tesseract ou de qualquer binário externo.

```ini
OCR_ENABLED=true     # opt-in: cada página vira tokens de imagem
OCR_MAX_PAGES=10     # teto de páginas por documento
```

O OCR só entra **depois** que os leitores normais falham, nunca antes. O
documento transcrito é marcado de ponta a ponta:

- a tela mostra `⚠ Texto obtido por OCR — conferir com o original`;
- o extrator é registrado como `<nome>+ocr`;
- o evento vai para `logs/audit.jsonl` com páginas e tokens consumidos.

Com `OCR_ENABLED=false` (padrão) ou no provedor `mock`, o comportamento
anterior é mantido: o arquivo vai para **ERROS** com a recomendação.

Referência de volume, medida sobre 595 PDFs reais de uma competência:
92% têm camada de texto e dispensam OCR. Os 8% restantes concentram-se em
notas fiscais (14%) e extratos — comprovantes bancários nunca precisaram.

---

## Desenvolvimento

```powershell
.\_start.ps1 -Test     # pytest
.\_start.ps1 -Lint     # ruff
.\_start.ps1 -Port 8600
```

Ou diretamente:

```powershell
$env:PYTHONPATH = "."
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\python.exe -m pytest --cov=core --cov=db --cov-report=term-missing
.venv\Scripts\python.exe -m ruff check .
```

### Arquitetura

```text
app/          Streamlit: main.py + 14 telas em pages/ + ui.py (componentes)
core/
  scanner/    varredura, hash SHA-256, detecção de duplicidade
  documents/  classificador documental, organizador de pastas, parsers BR
  extractors/ PDF, OCR via IA, planilha, PIX, contas pagas, faturamento, CT-e, extrato
  accounting/ seleção de exemplos, memória de correções, prompt, IA, validador
  dominio/    layout, validador de exportação, gerador de XLSX
  pipeline.py orquestra a esteira ponta a ponta
db/           modelos SQLAlchemy (12 tabelas) + repositórios
tests/        231 testes (unitários, integração, layouts reais e smoke das telas)
docs/         PRD, arquitetura, plano de tarefas, walkthrough
```

---

## Segurança e LGPD

- Chaves de API ficam apenas no `.env`, que não é versionado.
- Nenhuma chave, token ou senha chega ao log: todo texto passa por redação antes
  de ser gravado.
- CPF é mascarado em tela e em log (`123.***.***-09`).
- À IA é enviado apenas o texto e os campos necessários do documento.
- Auditoria em `logs/audit.jsonl`: quem fez, o quê, quando, com qual resultado.
- Evidências de prompt e resposta da IA ficam em `logs/ai_evidence/`.
- `data/`, `logs/` e `CLIENTES/` estão no `.gitignore`.

---

## Fora do escopo deste MVP

Integração via API com o Domínio · fine-tuning · login multiusuário ·
conciliação bancária automática · classificação sem revisão humana · BI.
