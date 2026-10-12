"""Montagem do prompt enviado à IA contábil (Tarefa 5.1).

Regras invioláveis embutidas no prompt:
  - a IA só pode usar contas existentes e ativas no plano da empresa;
  - deve informar quando o documento NÃO deve gerar lançamento;
  - deve responder exclusivamente um JSON válido no schema acordado.

O contexto é limitado pelos tetos do .env para não estourar tokens nem
enviar mais dados do que o necessário (RNF/LGPD).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.accounting import correction_memory, examples_selector
from core.config import get_settings
from core.constants import TYPES_CONDITIONAL_ENTRY
from core.logging_config import redact
from db.models import Company
from db.repositories import company_repository

#: Teto de caracteres do texto do documento enviado à IA.
MAX_DOCUMENT_TEXT_CHARS = 6000

SYSTEM_INSTRUCTION = (
    "Você é um assistente contábil brasileiro que sugere lançamentos contábeis "
    "PRELIMINARES para revisão humana obrigatória. Você nunca decide sozinho: "
    "um contador aprova ou corrige cada sugestão.\n"
    "Responda SEMPRE e SOMENTE com um único objeto JSON válido, sem texto antes "
    "ou depois, sem cercas de código markdown."
)

JSON_SCHEMA_BLOCK = """{
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
}"""


@dataclass(frozen=True)
class PromptContext:
    """Prompt pronto + o que foi usado para montá-lo (auditoria)."""

    system_instruction: str
    user_prompt: str
    accounts_count: int
    examples_used: list[dict]
    corrections_used: list[dict]
    guidelines_used: list[str]

    @property
    def approximate_tokens(self) -> int:
        """Estimativa grosseira: ~4 caracteres por token."""
        return (len(self.system_instruction) + len(self.user_prompt)) // 4


def _format_accounts(accounts: list, limit: int) -> tuple[str, int]:
    """Plano de contas em linhas `código | descrição`, só contas que aceitam lançamento."""
    usable = [a for a in accounts if a.accepts_entries]
    truncated = usable[:limit]
    lines = [f"{a.account_code} | {a.description}" for a in truncated]
    if len(usable) > limit:
        lines.append(f"... (+{len(usable) - limit} contas não listadas por limite de contexto)")
    return "\n".join(lines) or "(plano de contas vazio)", len(truncated)


def _format_simple_list(items: list, code_attr: str, desc_attr: str) -> str:
    lines = [f"{getattr(i, code_attr)} | {getattr(i, desc_attr)}" for i in items]
    return "\n".join(lines) or "(nenhum cadastrado)"


def _format_guidelines(guidelines: list) -> tuple[str, list[str]]:
    if not guidelines:
        return "(nenhuma orientação cadastrada)", []
    blocks: list[str] = []
    titles: list[str] = []
    for guideline in guidelines:
        scope = guideline.applicable_document_type or "todos os tipos"
        blocks.append(
            f"- [{guideline.priority}] {guideline.title} (aplica-se a: {scope})\n"
            f"  {guideline.guideline_text.strip()}"
        )
        titles.append(guideline.title)
    return "\n".join(blocks), titles


def _json_block(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def build_prompt(
    *,
    company: Company,
    document_type: str,
    extracted_data: dict[str, Any],
    document_text: str,
    counterparty: str | None = None,
    base_document_note: str | None = None,
) -> PromptContext:
    """Monta o prompt completo para um documento.

    Args:
        base_document_note: conclusão da hierarquia de documento base — entra no
            prompt para a IA saber se este arquivo é base ou evidência.
    """
    settings = get_settings()

    accounts = company_repository.list_accounts(company.id, only_active=True)
    histories = company_repository.list_histories(company.id, only_active=True)
    cost_centers = company_repository.list_cost_centers(company.id, only_active=True)
    guidelines = company_repository.list_guidelines(
        company.id, document_type=document_type, only_active=True
    )

    scored_examples = examples_selector.select_relevant_examples(
        company.id,
        document_type=document_type,
        counterparty=counterparty,
        document_text=document_text,
    )
    examples_payload = examples_selector.to_prompt_payload(scored_examples)

    corrections = correction_memory.select_relevant_corrections(
        company.id, document_type=document_type, counterparty=counterparty
    )
    corrections_payload = correction_memory.to_prompt_payload(corrections)

    accounts_block, accounts_count = _format_accounts(accounts, settings.max_accounts_in_prompt)
    guidelines_block, guideline_titles = _format_guidelines(guidelines)

    trimmed_text = (document_text or "").strip()[:MAX_DOCUMENT_TEXT_CHARS]
    if len(document_text or "") > MAX_DOCUMENT_TEXT_CHARS:
        trimmed_text += "\n[... texto truncado por limite de contexto ...]"

    conditional_note = ""
    if document_type in TYPES_CONDITIONAL_ENTRY:
        conditional_note = (
            "\nATENÇÃO: este tipo documental só deve gerar lançamento quando NÃO houver "
            "documento de maior riqueza contábil (nota fiscal, CT-e, relatório de "
            "faturamento ou de contas pagas) para o mesmo fato. Caso contrário, "
            "responda should_generate_entry = false e explique em base_document_reason."
        )

    base_note = f"\nAnálise de documento base já realizada pelo sistema:\n{base_document_note}" if base_document_note else ""

    user_prompt = f"""Sugira o lançamento contábil preliminar para o documento abaixo.

## Empresa
Nome: {company.name}
Razão social: {company.legal_name}
CNPJ: {company.cnpj}

## Tipo documental
{document_type}{conditional_note}{base_note}

## Dados extraídos do documento
{_json_block(extracted_data)}

## Texto relevante do documento
{trimmed_text or "(sem texto extraído)"}

## Plano de contas ativo (código | descrição)
Use EXCLUSIVAMENTE códigos desta lista.
{accounts_block}

## Históricos padrão (código | descrição)
{_format_simple_list(histories, "history_code", "description")}

## Centros de custo (código | descrição)
{_format_simple_list(cost_centers, "cost_center_code", "description")}

## Orientações contábeis desta empresa
{guidelines_block}

## Exemplos de lançamentos desta empresa
{_json_block(examples_payload) if examples_payload else "(nenhum exemplo relevante cadastrado)"}

## Correções anteriores do contador
{_json_block(corrections_payload) if corrections_payload else "(nenhuma correção registrada)"}

## Regras obrigatórias
1. NÃO invente contas. Use apenas códigos presentes no plano de contas acima.
2. Se o documento não deve gerar lançamento, responda should_generate_entry = false
   e explique o motivo em base_document_reason.
3. Se houver risco de duplicidade com outro documento do mesmo fato contábil,
   acrescente um item em warnings.
4. amount deve ser numérico positivo, com ponto decimal.
5. entry_date no formato YYYY-MM-DD.
6. history_code deve existir na lista de históricos padrão, ou ser null.
7. Centros de custo devem existir na lista acima, ou ser null.
8. confidence entre 0.0 e 1.0, refletindo sua certeza real.
9. Siga as orientações da empresa e os exemplos acima quando se aplicarem.
10. Responda SOMENTE o JSON no formato:

{JSON_SCHEMA_BLOCK}
"""

    return PromptContext(
        system_instruction=SYSTEM_INSTRUCTION,
        user_prompt=redact(user_prompt),
        accounts_count=accounts_count,
        examples_used=examples_payload,
        corrections_used=corrections_payload,
        guidelines_used=guideline_titles,
    )
