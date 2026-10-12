"""Testes do validador contábil e do parsing do retorno da IA.

A regra central verificada aqui: a IA não pode inventar contas.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from core.accounting.accounting_validator import validate_ai_payload, validate_manual_entry
from core.accounting.ai_accounting_classifier import parse_ai_json
from core.exceptions import AIResponseError


def valid_payload(**overrides) -> dict:
    payload = {
        "should_generate_entry": True,
        "base_document_reason": "Relatório de contas pagas é o documento base.",
        "entry_date": "2026-01-06",
        "debit_account_code": "3.1.01.001",
        "credit_account_code": "1.1.01.001",
        "amount": 1500.00,
        "history_code": None,
        "history_complement": "Pagamento a FICTICIO conforme NF-2026-0042",
        "debit_cost_center_code": None,
        "credit_cost_center_code": None,
        "confidence": 0.88,
        "justification": "Pagamento de serviços de terceiros.",
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class TestParseAiJson:
    def test_json_puro(self):
        assert parse_ai_json('{"a": 1}') == {"a": 1}

    def test_json_dentro_de_cerca_markdown(self):
        assert parse_ai_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_com_texto_ao_redor(self):
        assert parse_ai_json('Segue a resposta:\n{"a": 1}\nEspero ter ajudado.') == {"a": 1}

    def test_resposta_vazia_levanta_erro(self):
        with pytest.raises(AIResponseError):
            parse_ai_json("")

    def test_resposta_sem_json_levanta_erro(self):
        with pytest.raises(AIResponseError):
            parse_ai_json("Não posso responder isso.")


class TestValidacaoDeContas:
    def test_payload_valido_e_aprovado(self, full_company):
        result = validate_ai_payload(valid_payload(), company_id=full_company.id)

        assert result.is_valid
        assert result.should_generate_entry
        assert result.normalized["debit_account_code"] == "3.1.01.001"

    def test_conta_debito_inexistente_e_bloqueada(self, full_company):
        result = validate_ai_payload(
            valid_payload(debit_account_code="9.9.9.999"), company_id=full_company.id
        )

        assert not result.is_valid
        assert any("débito" in error and "não existe" in error for error in result.errors)

    def test_conta_credito_inexistente_e_bloqueada(self, full_company):
        result = validate_ai_payload(
            valid_payload(credit_account_code="INVENTADA"), company_id=full_company.id
        )

        assert not result.is_valid
        assert any("crédito" in error for error in result.errors)

    def test_conta_sintetica_nao_aceita_lancamento(self, full_company):
        """Conta que não aceita lançamento é tão inválida quanto inexistente."""
        result = validate_ai_payload(
            valid_payload(debit_account_code="3.1.01"), company_id=full_company.id
        )

        assert not result.is_valid

    def test_conta_inativa_e_bloqueada(self, full_company):
        result = validate_ai_payload(
            valid_payload(debit_account_code="9.9.99.999"), company_id=full_company.id
        )

        assert not result.is_valid

    def test_debito_igual_a_credito_e_bloqueado(self, full_company):
        result = validate_ai_payload(
            valid_payload(credit_account_code="3.1.01.001"), company_id=full_company.id
        )

        assert not result.is_valid
        assert any("iguais" in error for error in result.errors)


class TestValidacaoDeValorEData:
    def test_valor_ausente_e_bloqueado(self, full_company):
        result = validate_ai_payload(valid_payload(amount=None), company_id=full_company.id)

        assert not result.is_valid
        assert any("Valor" in error for error in result.errors)

    def test_valor_negativo_e_bloqueado(self, full_company):
        result = validate_ai_payload(valid_payload(amount=-100), company_id=full_company.id)

        assert not result.is_valid

    def test_valor_zero_e_bloqueado(self, full_company):
        result = validate_ai_payload(valid_payload(amount=0), company_id=full_company.id)

        assert not result.is_valid

    def test_data_ausente_e_bloqueada(self, full_company):
        result = validate_ai_payload(valid_payload(entry_date=None), company_id=full_company.id)

        assert not result.is_valid
        assert any("Data" in error for error in result.errors)

    def test_data_em_formato_brasileiro_e_aceita(self, full_company):
        result = validate_ai_payload(
            valid_payload(entry_date="06/01/2026"), company_id=full_company.id
        )

        assert result.is_valid
        assert result.normalized["entry_date"] == date(2026, 1, 6)

    def test_data_futura_gera_aviso_sem_bloquear(self, full_company):
        future = (date.today() + timedelta(days=30)).isoformat()
        result = validate_ai_payload(valid_payload(entry_date=future), company_id=full_company.id)

        assert result.is_valid
        assert any("futura" in warning for warning in result.warnings)

    def test_divergencia_de_valor_com_o_documento_gera_aviso(self, full_company):
        result = validate_ai_payload(
            valid_payload(), company_id=full_company.id, document_amount=1600.00
        )

        assert result.is_valid
        assert any("difere do valor extraído" in warning for warning in result.warnings)


class TestValidacaoDeHistoricoECentroDeCusto:
    def test_historico_inexistente_e_descartado_com_aviso(self, full_company):
        result = validate_ai_payload(
            valid_payload(history_code="999"), company_id=full_company.id
        )

        assert result.is_valid
        assert result.normalized["history_code"] is None
        assert any("histórico" in warning for warning in result.warnings)

    def test_historico_cadastrado_e_mantido(self, full_company):
        result = validate_ai_payload(
            valid_payload(history_code="101"), company_id=full_company.id
        )

        assert result.normalized["history_code"] == "101"

    def test_centro_de_custo_inexistente_e_descartado(self, full_company):
        result = validate_ai_payload(
            valid_payload(debit_cost_center_code="999"), company_id=full_company.id
        )

        assert result.is_valid
        assert result.normalized["debit_cost_center_code"] is None

    def test_centro_de_custo_cadastrado_e_mantido(self, full_company):
        result = validate_ai_payload(
            valid_payload(debit_cost_center_code="001"), company_id=full_company.id
        )

        assert result.normalized["debit_cost_center_code"] == "001"

    def test_complemento_de_historico_vazio_e_bloqueado(self, full_company):
        result = validate_ai_payload(
            valid_payload(history_complement="  "), company_id=full_company.id
        )

        assert not result.is_valid


class TestSchemaEConfianca:
    def test_campo_obrigatorio_ausente_e_bloqueado(self, full_company):
        payload = valid_payload()
        del payload["amount"]

        result = validate_ai_payload(payload, company_id=full_company.id)

        assert not result.is_valid
        assert any("obrigatórios ausentes" in error for error in result.errors)

    def test_resposta_que_nao_e_dicionario_e_bloqueada(self, full_company):
        result = validate_ai_payload(["não é um objeto"], company_id=full_company.id)

        assert not result.is_valid

    def test_ia_indicando_que_nao_ha_lancamento(self, full_company):
        result = validate_ai_payload(
            valid_payload(
                should_generate_entry=False,
                base_document_reason="Existe relatório de contas pagas para o mesmo pagamento.",
            ),
            company_id=full_company.id,
        )

        assert result.should_generate_entry is False
        assert result.normalized["should_generate_entry"] is False
        assert any("não deve gerar lançamento" in warning for warning in result.warnings)

    def test_confianca_baixa_gera_aviso_sem_bloquear(self, full_company):
        result = validate_ai_payload(
            valid_payload(confidence=0.20), company_id=full_company.id, min_confidence=0.60
        )

        assert result.is_valid
        assert any("Confiança da IA" in warning for warning in result.warnings)

    def test_confianca_e_limitada_ao_intervalo_valido(self, full_company):
        result = validate_ai_payload(valid_payload(confidence=5.0), company_id=full_company.id)

        assert result.normalized["confidence"] == 1.0

    def test_avisos_da_ia_sao_preservados(self, full_company):
        result = validate_ai_payload(
            valid_payload(warnings=["Possível duplicidade com comprovante PIX."]),
            company_id=full_company.id,
        )

        assert any("duplicidade" in warning for warning in result.warnings)

    def test_valores_nulos_textuais_sao_normalizados(self, full_company):
        result = validate_ai_payload(
            valid_payload(history_code="null", debit_cost_center_code="None"),
            company_id=full_company.id,
        )

        assert result.normalized["history_code"] is None
        assert result.normalized["debit_cost_center_code"] is None


class TestValidacaoManual:
    def test_edicao_humana_passa_pelas_mesmas_regras_de_conta(self, full_company):
        """O contador também não pode aprovar conta inexistente."""
        result = validate_manual_entry(
            {
                "entry_date": date(2026, 1, 6),
                "debit_account_code": "CONTA_QUE_NAO_EXISTE",
                "credit_account_code": "1.1.01.001",
                "amount": 100.0,
                "history_complement": "teste",
            },
            company_id=full_company.id,
        )

        assert not result.is_valid

    def test_edicao_humana_valida_e_aprovada(self, full_company):
        result = validate_manual_entry(
            {
                "entry_date": date(2026, 1, 6),
                "debit_account_code": "3.1.01.001",
                "credit_account_code": "1.1.01.001",
                "amount": 100.0,
                "history_complement": "Pagamento revisado manualmente",
            },
            company_id=full_company.id,
        )

        assert result.is_valid
