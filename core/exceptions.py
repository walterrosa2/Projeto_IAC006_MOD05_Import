"""Exceções de domínio da esteira contábil."""

from __future__ import annotations

from core.constants import ErrorType


class ClassificadorError(Exception):
    """Base de todas as exceções da aplicação."""

    error_type: str = ErrorType.ERRO_INESPERADO

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict[str, str | None]:
        return {
            "erro_tipo": self.error_type,
            "erro_mensagem": self.message,
            "detalhe": self.detail,
        }


class ExtractionError(ClassificadorError):
    """Falha ao ler ou extrair conteúdo de um arquivo."""

    error_type = ErrorType.EXTRACAO_FALHOU


class PdfWithoutTextError(ExtractionError):
    """PDF aberto com sucesso, mas sem camada de texto (provável digitalização)."""

    error_type = ErrorType.PDF_SEM_TEXTO


class PdfProtectedError(ExtractionError):
    """PDF protegido por senha."""

    error_type = ErrorType.PDF_PROTEGIDO


class CorruptedFileError(ExtractionError):
    """Arquivo ilegível ou corrompido."""

    error_type = ErrorType.ARQUIVO_CORROMPIDO


class AIProviderError(ClassificadorError):
    """Falha de comunicação com o provedor de IA (timeout, rede, HTTP)."""

    error_type = ErrorType.IA_INDISPONIVEL


class AIResponseError(ClassificadorError):
    """A IA respondeu, mas fora do schema JSON esperado."""

    error_type = ErrorType.IA_RETORNO_INVALIDO


class ValidationError(ClassificadorError):
    """Dados obrigatórios ausentes ou inválidos."""

    error_type = ErrorType.DADOS_OBRIGATORIOS_AUSENTES


class AccountNotFoundError(ValidationError):
    """Conta contábil sugerida não existe ou está inativa no plano da empresa."""

    error_type = ErrorType.CONTA_INEXISTENTE


class ExportBlockedError(ClassificadorError):
    """Exportação bloqueada por regra de negócio (RNF03)."""

    error_type = ErrorType.DADOS_OBRIGATORIOS_AUSENTES
