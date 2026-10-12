"""Redação de segredos antes de qualquer gravação em log (RNF05)."""

from core.logging_config import redact

# Valores fictícios, no formato real de cada provedor.
GEMINI_LEGADA = "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
GEMINI_NOVA = "AQ.Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv_wX-yZ"
ANTHROPIC = "sk-ant-api03-abcdefghijklmnopqrstuv"


def test_chave_gemini_legada_e_removida():
    saida = redact(f"chamando gemini com {GEMINI_LEGADA}")
    assert GEMINI_LEGADA not in saida
    assert "AIza***REDACTED***" in saida


def test_chave_gemini_formato_novo_e_removida():
    saida = redact(f"chamando gemini com {GEMINI_NOVA}")
    assert GEMINI_NOVA not in saida
    assert "AQ.***REDACTED***" in saida


def test_chave_anthropic_e_removida():
    assert ANTHROPIC not in redact(f"key {ANTHROPIC}")


def test_atribuicao_de_chave_e_removida():
    saida = redact(f"GEMINI_API_KEY={GEMINI_NOVA}")
    assert GEMINI_NOVA not in saida


def test_texto_comum_com_aq_nao_e_alterado():
    texto = "Pagamento AQ.123 referente a NF 456"
    assert redact(texto) == texto


def test_cpf_e_mascarado():
    assert redact("CPF 123.456.789-09") == "CPF 123.***.***-09"
