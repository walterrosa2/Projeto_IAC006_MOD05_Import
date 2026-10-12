# Handoff — Classificador Contábil com IA

Histórico de sessões entre agentes. Entradas mais recentes no topo.

---

## 2026-10-12 12:50 - Claude Code (Opus 5.5) - Distribuição aos alunos + manual

- **Feito:**
  - Repositório publicado em https://github.com/walterrosa2/Projeto_IAC006_MOD05_Import
    (sem `.env`, banco, exportações ou documentos de cliente).
  - Dados com aparência real anonimizados nos testes e docs (nomes, CNPJs, contas,
    código de barras, chave PIX).
  - `_start.bat`/`_start.ps1`: detectam `py`/`python`, exigem 3.11+, modo `setup`;
    `.gitattributes` força CRLF em `.bat`.
  - `.env.example` já vem com `gemini` / `gemini-3.6-flash`; aluno só cola a chave.
  - `AGENTS.md` ganhou a seção "Preparação do Ambiente (alunos — Windows)".
  - Menu lateral único em todas as telas (antes havia dois menus na inicial e as
    demais dependiam do menu automático do Streamlit).
  - Manual do aluno (Word, 20 p.) em `docs/manual/Manual_Aluno_Antigravity.docx`
    (fora do git), com capturas reais de GitHub, python.org, git-scm e da app.
- **Não feito:** prints do Antigravity, dos instaladores (Python/Git), da extração do
  ZIP e do Google AI Studio — computer use não estava disponível na sessão (extensão
  VS Code). Ficaram 15 marcadores amarelos "[INSERIR PRINT]" no manual. Os nomes de
  botões do Antigravity e do AI Studio no manual precisam ser conferidos contra a tela.
- **Próximo passo:** percorrer o manual numa máquina limpa, capturar os prints
  marcados e ajustar rótulos que divergirem.
- **Como validar:** baixar o ZIP do GitHub em `C:\Projetos`, `cmd /c .\_start.bat setup`,
  `cmd /c .\_start.bat` e abrir http://127.0.0.1:8501 (validado nesta sessão, 231 testes ok).

---

## 2026-09-20 11:50 - Claude Code (Opus 5) - OCR e correção dos extratores

- **Feito:**
  - **IA real ligada.** A chave no `.env` era do Gemini, mas `AI_PROVIDER` seguia
    `mock` e `AI_MODEL` apontava para um modelo Anthropic. Ajustado para
    `gemini` / `gemini-3.6-flash` (o `gemini-2.0-flash` foi descontinuado; a
    própria API indicou o substituto). Faltava o pacote `google-genai` no
    `requirements.txt` — instalado e declarado.
  - **OCR implementado** em `core/extractors/ocr_extractor.py`, via IA
    multimodal em vez de Tesseract (sem binário externo). Opt-in por
    `OCR_ENABLED`, teto `OCR_MAX_PAGES`, suporte a gemini/anthropic/openai.
    Só roda depois que PyMuPDF e pdfplumber falham. O documento transcrito é
    marcado na tela, no nome do extrator (`<nome>+ocr`) e na auditoria.
  - **Bug real corrigido no extrator de comprovantes.** Ele procurava rótulos
    soltos ("DE:", "PARA:") e pegava a linha seguinte; nos comprovantes reais
    isso devolvia "CONTA CORRENTE" como favorecido e o título do documento como
    pagador. Reescrito para delimitar **seções** (`TRANSFERIDO POR`/`PARA`,
    `Pagador`/`Favorecido`) e buscar campos rotulados dentro delas.
  - **Assinaturas dos layouts reais** acrescentadas: 102 pagamentos de boleto
    (layout VORTX) e 1 TED caíam em OUTROS por ficarem abaixo do corte de 0,70.
  - 27 testes novos com os dois layouts reais (dados alterados); total 231.

- **Validado de fato:**
  - Chamada real ao Gemini: JSON no schema, contas do plano, confiança 0,98.
  - **250 comprovantes reais**: 100% classificados (147 PIX, 102 boleto, 1 TED),
    100% com data, valor, pagador e favorecido extraídos. Antes: 1 sem extrator
    e nomes errados em todos.
  - OCR ponta a ponta numa NFS-e digitalizada: antes ia para ERROS, agora é
    classificada como NOTA_FISCAL (0,98), vai para NOTAS_FISCAIS, com
    contraparte SOLIDES TECNOLOGIA S/A e o aviso de OCR.
  - 231 testes passando, `ruff check` limpo, app no ar (HTTP 200).

- **Diagnóstico da pasta real (595 PDFs de 01/2026):** 92% têm camada de texto.
  Precisam de OCR: notas fiscais 45/331 (14%), extratos 3/7. Comprovantes: 0.

- **Não feito / limitações conhecidas:**
  - `NOTA_FISCAL` ainda usa o extrator de faturamento. Funciona para o texto ir
    à IA, mas uma nota de **serviço tomado** é despesa, não receita — um
    extrator dedicado de NFS-e traria campos melhores.
  - OCR não foi medido em lote grande: custo e tempo por documento (~12 s por
    chamada de IA) só foram observados em amostras.
  - Extratos bancários digitalizados (3 arquivos) não foram testados com OCR.
  - Projeto segue **sem git**; nenhum CI criado.

- **Ponto de atenção:** `OCR_ENABLED=true` está ligado no `.env` local. Cada
  página digitalizada vira tokens de imagem. Em lote de 48 documentos/mês o
  custo é baixo, mas convém acompanhar na primeira competência real.

- **Próximo passo:** processar uma competência inteira pela tela Processar
  Pasta e conferir tempo, custo e qualidade das sugestões. Se o volume incomodar,
  paralelizar as chamadas de IA (hoje são sequenciais).

- **Como validar:**
  ```powershell
  .\_start.ps1 -Test    # 231 testes
  .\_start.ps1 -Lint    # ruff
  .\_start.ps1          # http://127.0.0.1:8501
  ```

---

## 2026-09-19 17:50 - Claude Code (Opus 5) - Construção do MVP a partir do SDD

- **Feito:** MVP completo implementado do zero a partir da documentação SDD em
  `PRD/sdd_classificador_contabil/`. Todas as 9 fases e as 33 tarefas do
  `03_Plano_Execucao_Backlog.md` concluídas:
  - 12 tabelas SQLAlchemy + 5 repositórios (`db/`);
  - esteira completa em `core/` — scanner, hash SHA-256, duplicidade em duas
    camadas, classificador documental por regras, organizador de pastas,
    7 extratores, camada de IA e exportador Domínio;
  - 14 telas Streamlit em `app/pages/`;
  - 204 testes automatizados passando, 81% de cobertura em `core/` + `db/`;
  - `ruff check` limpo;
  - documentação: `README.md`, `docs/Walkthrough.md`, `docs/Task.md`,
    `AGENTS.md` na raiz e os 4 documentos SDD copiados para `docs/`;
  - `_start.ps1` / `_start.bat` com `PYTHONPATH` configurado;
  - `scripts/seed_demo.py` cria uma empresa fictícia com plano de contas,
    históricos, centros de custo, 3 orientações e 3 exemplos.
- **Validado de fato:** aplicação sobe (`/_stcore/health` → `ok`, HTTP 200);
  smoke test abre as 14 telas com e sem dados; execução end-to-end real
  (5 arquivos → 3 classificados, 1 OUTROS, 1 ERROS → 2 lançamentos aprovados →
  XLSX gerado no layout Domínio). A hierarquia de documento base foi confirmada
  na prática: o comprovante PIX não gerou lançamento porque existia o relatório
  de contas pagas do mesmo pagamento.
- **Não feito (fora do escopo do MVP, registrado em `docs/Task.md`):** OCR para
  PDFs digitalizados; desdobramento automático de faturamento com retenção em
  múltiplos lançamentos; lançamento linha a linha a partir de extrato bancário;
  autenticação multiusuário; PostgreSQL; integração via API com o Domínio.
  O projeto **ainda não é um repositório git**, então nenhum workflow de CI foi
  criado — `git init` é pré-requisito.
- **Ponto de atenção:** `AI_PROVIDER=mock` é o padrão no `.env`. As sugestões
  são simuladas e marcadas como sem valor contábil na interface. Para uso real,
  definir `AI_PROVIDER=anthropic` (ou `openai`/`gemini`) e a chave no `.env`.
  Nenhuma validação foi feita contra um provedor real — apenas contra o mock.
- **Próximo passo:** testar com documentos reais do escritório e ajustar as
  assinaturas textuais em `core/documents/document_types.py` conforme os
  layouts que aparecerem. Depois, configurar o provedor de IA real e comparar
  as sugestões com o que o contador faria, alimentando a tela de Exemplos.
- **Como validar:**
  ```powershell
  .\_start.ps1 -Test    # 204 testes
  .\_start.ps1 -Lint    # ruff
  .\_start.ps1          # http://127.0.0.1:8501
  ```
  Roteiro de validação manual de 10 minutos na seção 5.2 de `docs/Walkthrough.md`.
