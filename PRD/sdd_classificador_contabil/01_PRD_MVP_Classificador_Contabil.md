# PRD — Plataforma de Classificação Documental e Lançamentos Contábeis com IA

**Projeto:** Classificador Contábil Automatizado para Escritório Contábil  
**Versão:** 0.2 — Refinamento funcional  
**Data:** 2026-09-19  
**Responsável pelo negócio:** Contador responsável / escritório contábil  
**Ambiente previsto:** Aplicação local, desenvolvida via IDE agentic Antigravity, com arquitetura preparada para evolução.

---

## 1. Visão do Produto

Criar uma aplicação que leia automaticamente uma pasta de documentos recebidos dos clientes, identifique o tipo de cada documento, organize os arquivos em uma estrutura padronizada, extraia dados relevantes, use IA para sugerir lançamentos contábeis conforme plano de contas, regras e exemplos por empresa, permita validação humana e gere a planilha de importação para o Domínio Contábil.

A aplicação não deve apenas extrair dados. Ela deve atuar como uma esteira contábil:

**Entrada de documentos → Classificação documental → Organização em pastas → Extração → Classificação contábil por IA → Revisão do contador → Exportação Domínio → Consulta e auditoria.**

---

## 2. Problema

Clientes do Simples Nacional enviam documentos de forma desorganizada. O contador perde muito tempo em quatro etapas:

1. entender o que é cada documento;
2. separar documentos por tipo e competência;
3. identificar o lançamento contábil correto;
4. montar arquivo de importação para o sistema Domínio Contábil.

Além disso, documentos diferentes podem representar o mesmo fato contábil. Exemplo: comprovante PIX, extrato bancário e relatório de contas pagas podem se referir ao mesmo pagamento. A aplicação precisa reduzir retrabalho e evitar lançamentos duplicados.

---

## 3. Objetivos

### 3.1 Objetivo principal

Automatizar a organização documental e a geração preliminar de lançamentos contábeis, mantendo revisão e aprovação humana antes da exportação.

### 3.2 Objetivos específicos

- Ler automaticamente a pasta `DADOS_A_CLASSIFICAR` de cada cliente.
- Detectar tipo documental: comprovante, extrato, faturamento, planilha, nota fiscal, CT-e, relatório de contas pagas, documento desconhecido ou erro.
- Classificar e copiar documentos para pastas padronizadas por cliente, ano, mês e tipo.
- Extrair dados principais dos documentos.
- Usar IA para sugerir lançamento contábil com base em:
  - conteúdo do documento;
  - plano de contas da empresa;
  - históricos padrão;
  - centros de custo;
  - orientações contábeis por empresa;
  - exemplos de lançamentos cadastrados;
  - histórico de correções anteriores.
- Permitir validação, correção, rejeição e marcação de duplicidade.
- Armazenar histórico de documentos, lançamentos, correções e exportações.
- Gerar planilha final no layout de importação do Domínio Contábil.

---

## 4. Usuários

### 4.1 Contador responsável

Usuário principal. Configura empresas, orientações, exemplos, plano de contas, valida lançamentos e exporta para o Domínio.

### 4.2 Assistente contábil

Pode inserir documentos, revisar pendências e consultar histórico.

### 4.3 Administrador do escritório

Pode administrar cadastros, permissões e parâmetros globais.

---

## 5. Escopo do MVP

O MVP deve entregar uma aplicação local com interface web simples que permita:

1. cadastrar empresas/clientes;
2. configurar pasta de entrada e destino por empresa;
3. cadastrar/importar plano de contas por empresa;
4. cadastrar históricos padrão;
5. cadastrar centros de custo;
6. cadastrar orientações contábeis por empresa;
7. cadastrar exemplos de lançamentos por empresa;
8. ler documentos da pasta `DADOS_A_CLASSIFICAR`;
9. identificar tipo documental;
10. copiar o arquivo para a pasta correta;
11. extrair dados mínimos;
12. gerar lançamento sugerido com IA;
13. validar lançamentos em tela;
14. registrar correções como memória operacional;
15. consultar documentos e lançamentos processados;
16. exportar lançamentos aprovados no layout do Domínio.

---

## 6. Fora de Escopo do MVP

Não faz parte da primeira versão:

- integração direta via API com o Domínio;
- treinamento real/fine-tuning do modelo de IA;
- automação de login em portais fiscais;
- assinatura digital;
- conferência fiscal completa;
- conciliação bancária avançada;
- classificação 100% autônoma sem revisão humana;
- multiempresa em nuvem com controle avançado de usuários;
- BI avançado.

---

## 7. Fluxo Operacional

### 7.1 Fluxo de entrada documental

1. Usuário seleciona empresa.
2. Sistema localiza a pasta de entrada da empresa.
3. Usuário coloca documentos em:

```text
CLIENTES/
  Cliente A/
    DADOS_A_CLASSIFICAR/
      documento_1.pdf
      documento_2.xlsx
      documento_3.xml
```

4. Sistema varre a pasta manualmente por botão ou automaticamente por rotina local.
5. Sistema calcula hash do arquivo para evitar duplicidade.
6. Sistema identifica extensão e tenta extrair conteúdo.
7. Sistema chama classificador documental.
8. Sistema define competência do documento a partir da data identificada.
9. Sistema copia o arquivo para a pasta de destino adequada.
10. Sistema registra o processamento no banco.

---

## 8. Estrutura de Pastas

### 8.1 Estrutura de entrada

```text
CLIENTES/
  Cliente A/
    DADOS_A_CLASSIFICAR/
```

### 8.2 Estrutura de destino

```text
CLIENTES/
  Cliente A/
    2026/
      01 - Janeiro/
        COMPROVANTES/
        EXTRATOS/
        FATURAMENTO/
        PLANILHAS/
        NOTAS_FISCAIS/
        CTES/
        CONTAS_PAGAS/
        OUTROS/
        ERROS/
        DUPLICADOS/
```

### 8.3 Lógica das pastas especiais

#### OUTROS

Usar quando o arquivo foi lido, mas o tipo documental não foi reconhecido com segurança.

Critérios de envio para `OUTROS`:

- tipo documental desconhecido;
- confiança do classificador abaixo do limite mínimo;
- documento é válido, mas ainda não existe categoria mapeada;
- documento não deve gerar lançamento no MVP, mas deve ser preservado.

#### ERROS

Usar quando houve falha técnica ou impossibilidade de leitura.

Critérios de envio para `ERROS`:

- arquivo corrompido;
- PDF protegido ou sem texto legível;
- erro ao abrir arquivo;
- falha na extração;
- falha na chamada de IA;
- retorno de IA inválido;
- ausência de data ou valor quando obrigatório para o tipo documental;
- exceção inesperada.

A aplicação deve gravar um arquivo `.json` ou registro de erro com:

```json
{
  "arquivo": "nome_original.pdf",
  "empresa": "Cliente A",
  "data_processamento": "2026-09-19T10:30:00",
  "erro_tipo": "EXTRACAO_FALHOU",
  "erro_mensagem": "Não foi possível extrair texto do PDF",
  "acao_recomendada": "Revisar manualmente ou reenviar arquivo legível"
}
```

#### DUPLICADOS

Usar quando o hash do arquivo ou a combinação de dados essenciais indicar duplicidade.

Critérios de duplicidade:

- mesmo hash SHA-256;
- mesmo CNPJ/CPF, valor, data, documento e tipo;
- mesmo comprovante bancário;
- mesmo número de nota ou CT-e.

Na primeira versão, o sistema deve copiar o arquivo para `DUPLICADOS` e não gerar lançamento automaticamente.

---

## 9. Tipos Documentais Iniciais

| Código | Tipo | Deve gerar lançamento? | Observação |
|---|---|---:|---|
| COMPROVANTE_PIX | Comprovante de PIX/TED/boleto | Condicional | Pode ser evidência. Gerar apenas se não houver documento base melhor. |
| EXTRATO_BANCARIO | Extrato bancário | Condicional | Usado para conciliação e evidência. |
| FATURAMENTO | Relatório de faturamento | Sim | Pode gerar receitas e retenções. |
| CONTAS_PAGAS | Relatório de contas pagas | Sim | Documento preferencial para pagamentos. |
| NOTA_FISCAL | Nota fiscal de serviço/produto | Sim | Se extraível e vinculada à competência. |
| CTE | Conhecimento de transporte eletrônico | Sim | Frete/transporte. |
| PLANILHA | Planilhas auxiliares | Depende | Pode ser entrada ou base de importação. |
| OUTRO | Documento reconhecido como válido, mas sem categoria | Não | Vai para revisão. |
| ERRO | Documento com erro técnico | Não | Vai para pasta ERROS. |

---

## 10. Hierarquia de Documento Base para Lançamento

A aplicação deve evitar que o mesmo fato contábil gere múltiplos lançamentos.

### 10.1 Regra geral

Quando houver mais de um documento relacionado ao mesmo fato, priorizar o documento com maior riqueza contábil.

Ordem sugerida:

1. nota fiscal, CT-e, relatório de faturamento ou relatório de contas pagas;
2. extrato bancário;
3. comprovante PIX/TED/boleto.

### 10.2 Exemplos

- Se existe relatório de contas pagas com o credor e valor, e também existe comprovante PIX do mesmo pagamento, o relatório de contas pagas deve ser o documento base. O comprovante PIX deve ser vinculado como evidência.
- Se só existe comprovante PIX e não existe documento fiscal ou contas pagas correspondente, o sistema pode sugerir lançamento pendente de revisão.
- Se extrato bancário e comprovante têm mesma data, favorecido e valor, gerar apenas um lançamento ou vincular como evidência.

---

## 11. Cadastro de Empresas

Campos mínimos:

| Campo | Obrigatório | Descrição |
|---|---:|---|
| nome_empresa | Sim | Nome interno da empresa |
| razao_social | Sim | Razão social |
| cnpj | Sim | CNPJ |
| pasta_entrada | Sim | Caminho da pasta DADOS_A_CLASSIFICAR |
| pasta_destino | Sim | Caminho da pasta CLIENTES |
| status | Sim | Ativa/Inativa |
| contador_responsavel | Não | Nome do responsável |
| observacoes | Não | Observações gerais |

---

## 12. Plano de Contas por Empresa

A aplicação deve permitir cadastro/importação do plano de contas da empresa.

Campos mínimos:

| Campo | Obrigatório |
|---|---:|
| empresa_id | Sim |
| codigo_conta | Sim |
| descricao | Sim |
| tipo | Não |
| aceita_lancamento | Sim |
| ativo | Sim |

A IA só pode sugerir contas existentes e ativas no plano de contas da empresa.

---

## 13. Orientações Contábeis por Empresa

Tela para o contador informar regras textuais específicas da empresa.

Exemplo:

```text
Para esta empresa, pagamentos a prestadores pessoa física devem ser classificados como serviços tomados, exceto quando houver descrição de adiantamento.
Comprovantes PIX só devem gerar lançamento se não houver relatório de contas pagas correspondente.
Faturamento com retenção deve separar receita bruta, impostos retidos e valor líquido.
```

Campos mínimos:

| Campo | Obrigatório |
|---|---:|
| empresa_id | Sim |
| titulo | Sim |
| orientacao | Sim |
| tipo_documento_aplicavel | Não |
| prioridade | Sim |
| ativo | Sim |
| data_criacao | Sim |
| usuario_criacao | Não |

---

## 14. Cadastro de Exemplos de Lançamentos por Empresa

Além das orientações textuais, a aplicação deve permitir cadastrar exemplos concretos de lançamentos para a mesma empresa.

Objetivo: explicar para a IA quais documentos são base para determinado lançamento contábil e como o contador espera que casos semelhantes sejam classificados.

### 14.1 Campos da tela

| Campo | Obrigatório | Descrição |
|---|---:|---|
| empresa_id | Sim | Empresa do exemplo |
| titulo_exemplo | Sim | Nome curto do exemplo |
| tipo_documento | Sim | Ex.: CONTAS_PAGAS, COMPROVANTE_PIX, FATURAMENTO, CTE |
| documento_base | Sim | Indica qual documento deve fundamentar o lançamento |
| fornecedor_cliente | Não | Nome da contraparte |
| palavras_chave | Não | Termos relevantes para localizar exemplos |
| trecho_documento_exemplo | Não | Texto representativo do documento |
| conta_debito | Sim | Conta débito esperada |
| conta_credito | Sim | Conta crédito esperada |
| codigo_historico | Não | Código de histórico esperado |
| complemento_historico_modelo | Sim | Modelo de histórico |
| centro_custo_debito | Não | Centro de custo esperado |
| centro_custo_credito | Não | Centro de custo esperado |
| explicacao_contabil | Sim | Justificativa contábil em linguagem natural |
| prioridade | Sim | Alta/Média/Baixa |
| ativo | Sim | Se deve ser usado pela IA |

### 14.2 Exemplo de cadastro

```text
Título: Pagamento de prestador por relatório de contas pagas
Tipo documental: CONTAS_PAGAS
Documento base: Relatório de contas pagas
Fornecedor/cliente: FORNECEDOR FICTICIO SERVICOS LTDA
Regra: quando o relatório de contas pagas trouxer credor, documento fiscal e valor líquido, este relatório é a base do lançamento; comprovante PIX relacionado deve ser apenas evidência.
Débito: Serviços de terceiros / empreiteiros
Crédito: Banco conta movimento
Histórico: Pagamento a fornecedor conforme relatório de contas pagas: {fornecedor} - {documento}
Justificativa: relatório de contas pagas possui credor, documento, data, valor bruto, desconto e líquido.
```

### 14.3 Uso dos exemplos pela IA

Antes de chamar a IA, a aplicação deve selecionar os exemplos mais relevantes por:

- empresa;
- tipo documental;
- fornecedor/cliente;
- palavras-chave;
- valor aproximado, quando aplicável;
- documento base;
- status ativo.

Os exemplos selecionados devem ser enviados ao prompt como referência. Isso não é treinamento real do modelo; é memória operacional auditável e controlada pelo escritório.

---

## 15. Correções do Usuário e Memória Operacional

Quando o usuário alterar um lançamento sugerido, a aplicação deve abrir campo:

```text
Orientação para evitar este erro no futuro
```

A correção deve gerar um registro com:

| Campo | Descrição |
|---|---|
| empresa_id | Empresa |
| documento_id | Documento processado |
| lancamento_id | Lançamento corrigido |
| classificacao_original | Contas e histórico sugeridos pela IA |
| classificacao_corrigida | Contas e histórico aprovados pelo usuário |
| orientacao_corretiva | Texto informado pelo usuário |
| usuario | Quem corrigiu |
| data_correcao | Data/hora |
| converter_em_exemplo | Sim/Não |

Se `converter_em_exemplo` for marcado, a aplicação deve sugerir criar um novo registro na tela de exemplos de lançamentos.

---

## 16. Requisitos Funcionais

### RF01 — Cadastro de empresa

A aplicação deve permitir cadastrar empresas/clientes com dados básicos, pasta de entrada e pasta destino.

### RF02 — Cadastro/importação de plano de contas

A aplicação deve permitir cadastrar ou importar o plano de contas de cada empresa.

### RF03 — Cadastro de históricos padrão

A aplicação deve permitir cadastrar códigos de histórico usados na exportação Domínio.

### RF04 — Cadastro de centros de custo

A aplicação deve permitir cadastrar centros de custo por empresa.

### RF05 — Cadastro de orientações contábeis

A aplicação deve permitir manter orientações textuais por empresa.

### RF06 — Cadastro de exemplos de lançamentos

A aplicação deve permitir cadastrar exemplos concretos de documento base e lançamento esperado por empresa.

### RF07 — Leitura da pasta DADOS_A_CLASSIFICAR

A aplicação deve varrer a pasta de entrada e identificar novos arquivos.

### RF08 — Detecção de duplicidade

A aplicação deve calcular hash do arquivo e verificar duplicidade por hash e por dados essenciais.

### RF09 — Classificação documental

A aplicação deve identificar tipo documental e nível de confiança.

### RF10 — Organização automática em pastas

A aplicação deve copiar o arquivo para a pasta adequada, criando ano/mês/tipo quando necessário.

### RF11 — Tratamento de OUTROS, ERROS e DUPLICADOS

A aplicação deve direcionar documentos não reconhecidos, arquivos com falha e duplicados para as respectivas pastas.

### RF12 — Extração de dados

A aplicação deve extrair data, valor, contraparte, documento, centro de custo e campos relevantes conforme tipo documental.

### RF13 — Geração de proposta de lançamento

A aplicação deve usar IA para sugerir lançamento contábil estruturado.

### RF14 — Validação do retorno da IA

A aplicação deve validar se a IA retornou JSON com campos obrigatórios e contas existentes.

### RF15 — Tela de validação

A aplicação deve permitir revisar, editar, aprovar, rejeitar ou marcar duplicidade.

### RF16 — Registro de correções

A aplicação deve registrar alterações feitas pelo usuário e campo orientativo para evitar erro futuro.

### RF17 — Consulta de documentos processados

A aplicação deve permitir busca por empresa, período, tipo, status e nome do arquivo.

### RF18 — Consulta de lançamentos

A aplicação deve permitir busca por empresa, período, status, conta, valor e documento.

### RF19 — Exportação para Domínio

A aplicação deve gerar planilha no layout do Domínio apenas com lançamentos aprovados.

### RF20 — Histórico de exportações

A aplicação deve registrar lote exportado, data, usuário e lançamentos incluídos.

---

## 17. Requisitos Não Funcionais

| Código | Requisito |
|---|---|
| RNF01 | A aplicação deve preservar rastreabilidade entre arquivo original, documento classificado, lançamento e exportação. |
| RNF02 | A aplicação deve copiar os arquivos classificados, preservando a pasta de entrada. |
| RNF03 | O sistema não deve exportar lançamentos pendentes, rejeitados, duplicados ou com erro. |
| RNF04 | Chaves de API devem ficar em variáveis de ambiente ou arquivo `.env` não versionado. |
| RNF05 | Logs não devem expor senhas, tokens ou dados desnecessários. |
| RNF06 | A aplicação deve registrar erros técnicos com mensagem legível ao usuário. |
| RNF07 | A interface deve ser simples para usuário com conhecimento básico em tecnologia. |
| RNF08 | A estrutura deve permitir evolução futura para multiusuário e banco de dados servidor. |
| RNF09 | A aplicação deve considerar LGPD, pois processa CPF, CNPJ, dados financeiros e documentos fiscais. |
| RNF10 | O retorno da IA deve ser estruturado e validado antes de persistência. |

---

## 18. Telas Necessárias

### 18.1 Dashboard

Indicadores:

- documentos pendentes;
- documentos classificados;
- documentos com erro;
- lançamentos pendentes;
- lançamentos aprovados;
- exportações realizadas.

### 18.2 Empresas

Cadastro e edição de empresas.

### 18.3 Plano de Contas

Importação/cadastro do plano de contas por empresa.

### 18.4 Históricos

Cadastro de históricos padrão.

### 18.5 Centros de Custo

Cadastro de centros de custo por empresa.

### 18.6 Orientações da Empresa

Tela textual de regras e orientações contábeis.

### 18.7 Exemplos de Lançamentos

Tela para cadastrar exemplos de documento base e lançamento esperado.

### 18.8 Processar Pasta

Tela para selecionar empresa, varrer pasta, visualizar arquivos encontrados e iniciar processamento.

### 18.9 Documentos Processados

Consulta dos documentos processados, com status, tipo, pasta destino e erro quando houver.

### 18.10 Validação de Lançamentos

Tela principal de revisão, com edição de débito, crédito, histórico, complemento e centro de custo.

### 18.11 Correções e Aprendizado

Consulta das orientações corretivas e opção de converter correção em exemplo.

### 18.12 Exportação Domínio

Filtro por empresa/período e geração da planilha.

### 18.13 Histórico de Exportações

Consulta de lotes exportados.

---

## 19. Layout de Exportação Domínio

A aplicação deve gerar planilha com as colunas do modelo de importação fornecido:

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

Regras:

- exportar apenas lançamentos aprovados;
- respeitar formatação de data esperada pelo Domínio;
- valor deve ser numérico;
- contas devem vir do plano de contas cadastrado;
- histórico deve vir do cadastro ou da sugestão aprovada;
- campos de centro de custo devem ser preenchidos apenas quando aplicável.

---

## 20. Critérios de Aceite do MVP

### CA01 — Processamento de pasta

Dado que uma empresa possui pasta de entrada configurada, quando o usuário clicar em processar, então a aplicação deve listar arquivos novos, classificar cada arquivo e copiar para a pasta correta.

### CA02 — Tratamento de erro

Dado que um arquivo não pode ser lido, quando o sistema processar a pasta, então o arquivo deve ser enviado para `ERROS` e o motivo deve ser registrado.

### CA03 — Documento desconhecido

Dado que o sistema não reconhece o tipo de um documento, quando o processamento concluir, então o arquivo deve ser enviado para `OUTROS` e não deve gerar lançamento automático.

### CA04 — Duplicidade

Dado que um arquivo já processado aparece novamente, quando o sistema calcular o hash, então deve marcar como duplicado e não gerar novo lançamento.

### CA05 — Classificação contábil com exemplos

Dado que existe exemplo cadastrado para a empresa e tipo documental, quando a IA classificar documento semelhante, então o exemplo deve ser incluído no contexto enviado à IA.

### CA06 — Validação humana

Dado que a IA gerou um lançamento, quando o usuário alterar conta ou histórico, então a aplicação deve salvar a alteração e permitir orientação corretiva.

### CA07 — Exportação

Dado que existem lançamentos aprovados para empresa e período, quando o usuário exportar, então a aplicação deve gerar XLSX no layout Domínio apenas com lançamentos aprovados.

### CA08 — Consulta

Dado que documentos e lançamentos já foram processados, quando o usuário consultar por empresa e mês, então deve visualizar histórico, status, arquivo original, lançamento e lote de exportação quando houver.

---

## 21. Riscos Principais

| Risco | Impacto | Mitigação |
|---|---|---|
| IA sugerir conta incorreta | Alto | Validação humana obrigatória e exemplos por empresa |
| Lançamento duplicado | Alto | Hash, comparação de valor/data/contraparte e hierarquia de documento base |
| Documento ilegível | Médio | Pasta ERROS e revisão manual |
| Plano de contas incompleto | Alto | Bloquear aprovação/exportação quando conta não existir |
| Orientações ambíguas | Médio | Tela de exemplos concretos e revisão |
| Exposição de dados sensíveis | Alto | `.env`, logs controlados e uso local no MVP |

---

## 22. Próxima Etapa

Depois de validar este PRD, o desenvolvimento deve seguir a arquitetura técnica e o plano de execução em fases.