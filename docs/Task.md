# Task.md — Estado do backlog

**Projeto:** Classificador Contábil com IA · **Atualizado em:** 2026-09-20

Rastreia o backlog de [TASK_PLAN.md](TASK_PLAN.md). Uma tarefa só é marcada
concluída quando o código executa, o erro está tratado e há teste quando aplicável.

---

## Fase 0 — Preparação

- [x] **T0.1** Estrutura do projeto, `.gitignore`, `.env.example`, `requirements.txt`, `README.md`, `pyproject.toml`
- [x] **T0.2** Streamlit configurado: `app/main.py`, menu lateral, `.streamlit/config.toml`, `_start.ps1` / `_start.bat`

## Fase 1 — Banco e cadastros base

- [x] **T1.1** SQLite + 12 modelos SQLAlchemy, criação automática do schema, FK ativas
- [x] **T1.2** Tela de empresas (criar, editar, excluir, diagnóstico das pastas)
- [x] **T1.3** Plano de contas: cadastro manual + importação XLSX/CSV com mapeamento tolerante de colunas
- [x] **T1.4** Históricos padrão
- [x] **T1.5** Centros de custo

## Fase 2 — Orientações e exemplos

- [x] **T2.1** Orientações por empresa, com prioridade, escopo por tipo documental e status ativo
- [x] **T2.2** Exemplos de lançamentos, com validação das contas contra o plano
- [x] **T2.3** Seletor de exemplos relevantes (tipo, contraparte, palavras-chave, trecho, prioridade)

## Fase 3 — Scanner e organização

- [x] **T3.1** Scanner da pasta `DADOS_A_CLASSIFICAR` (ignora subpastas e temporários)
- [x] **T3.2** Hash SHA-256 + duplicidade em duas camadas (hash e dados essenciais)
- [x] **T3.3** Classificador documental por assinaturas, com fallback para OUTROS
- [x] **T3.4** Organizador de pastas `cliente/ano/mês/tipo`, com cópia e resolução de colisão
- [x] **T3.5** Tela Processar Pasta, com seleção de arquivos, progresso e consolidado

## Fase 4 — Extração de dados

- [x] **T4.1** Extrator base + leitor de PDF (PyMuPDF com pdfplumber de reserva)
- [x] **T4.2** Extrator de comprovante PIX/TED/boleto
- [x] **T4.3** Extrator de relatório de contas pagas
- [x] **T4.4** Extrator de relatório de faturamento, com retenções
- [x] **T4.5** Extrator de CT-e (XML e DACTE em PDF)
- [x] **T4.6** Persistência de texto bruto e JSON estruturado
- [x] *(extra)* Extrator de extrato bancário e de planilhas

## Fase 5 — IA para lançamentos

- [x] **T5.1** Prompt builder com empresa, documento, plano, orientações, exemplos e correções
- [x] **T5.2** Cliente de IA multi-provedor, com timeout, retries, redação e evidência
- [x] **T5.3** Validador contábil (schema, contas, valor, data, histórico, centro de custo, confiança)
- [x] **T5.4** Gerador de lançamento, sempre em `PENDING_REVIEW`
- [x] *(extra)* Hierarquia de documento base aplicada antes de chamar a IA

## Fase 6 — Validação humana

- [x] **T6.1** Tela de validação com documento de origem, dados extraídos e edição completa
- [x] **T6.2** Campo de orientação corretiva + marcação "converter em exemplo"
- [x] **T6.3** Memória de correções alimentando o prompt das próximas sugestões

## Fase 7 — Exportação Domínio

- [x] **T7.1** Exportador XLSX no layout de 10 colunas
- [x] **T7.2** Validador de exportação (bloqueia incompleto e não aprovado)
- [x] **T7.3** Tela de exportação com prévia, download e registro do lote

## Fase 8 — Consultas e auditoria

- [x] **T8.1** Consulta de documentos processados, com detalhe e rastreabilidade
- [x] **T8.2** Histórico de exportações, com relação dos lançamentos e redownload
- [x] **T8.3** Dashboard com indicadores e fila de trabalho
- [x] *(extra)* Tela de Correções e Aprendizado
- [x] *(extra)* Tela de Configuração e diagnóstico

## Qualidade

- [x] 231 testes automatizados, todos passando
- [x] Cobertura de 81% em `core/` + `db/`
- [x] `ruff check` sem apontamentos
- [x] Smoke test das 14 telas, com e sem dados
- [x] Critérios de aceite CA01–CA08 cobertos por teste de integração
- [x] Logging com redação de segredos e trilha de auditoria JSONL
- [x] README, Walkthrough, PRD, arquitetura e plano em `docs/`

---

## Entregue em 2026-09-20 (pós-MVP)

- [x] **OCR de PDFs digitalizados** via IA multimodal (`core/extractors/ocr_extractor.py`),
      opt-in por `OCR_ENABLED`, com teto de páginas, marcação do documento e auditoria
- [x] **Correção do extrator de comprovantes**: passou a delimitar seções
      (`TRANSFERIDO POR`/`PARA`, `Pagador`/`Favorecido`) em vez de rótulos soltos.
      O bug devolvia "CONTA CORRENTE" como favorecido
- [x] **Assinaturas dos layouts reais** de comprovante (BMP/SCMEPP e VORTX):
      102 pagamentos de boleto e 1 TED que caíam em OUTROS agora classificam
- [x] Validado contra **250 comprovantes reais**: 100% classificados, 100% dos
      campos (data, valor, pagador, favorecido) extraídos
- [x] `google-genai` acrescentado ao `requirements.txt` (faltava)

---

## Pendente (fora do MVP)

- [x] ~~OCR para PDFs digitalizados~~ — entregue em 2026-09-20 via IA multimodal
- [ ] Desdobramento automático de faturamento com retenção em múltiplos lançamentos
- [ ] Lançamento linha a linha a partir de extrato bancário
- [ ] Autenticação multiusuário
- [ ] Migração para PostgreSQL
- [ ] Integração via API com o Domínio Contábil
- [ ] CI no GitHub Actions (o projeto ainda não está em repositório git)

---

## Validado nesta entrega

| Verificação | Comando | Resultado |
|---|---|---|
| Testes | `.\_start.ps1 -Test` | 231 passando |
| Lint | `.\_start.ps1 -Lint` | `All checks passed!` |
| Aplicação sobe | `.\_start.ps1` | HTTP 200, `/_stcore/health` → `ok` |
| Telas abrem | `pytest tests/test_app_smoke.py` | 29 execuções sem exceção |
