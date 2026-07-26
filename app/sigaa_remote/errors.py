class RemoteError(Exception):
    """Base de todas as falhas do cliente remoto."""


class RemoteUnavailable(RemoteError):
    """A API remota não pôde ser alcançada.

    Timeout, DNS, conexão recusada ou 5xx do próprio servidor da API —
    ou seja, falhas em que tentar de novo pelo scraper interno faz
    sentido.
    """


class RemoteApiError(RemoteError):
    """A API remota respondeu com um erro de negócio."""

    def __init__(self, status_code, code=None, message=None):
        self.status_code = status_code
        self.code = code
        self.message = message or f"Erro {status_code} da API do SIGAA."
        super().__init__(self.message)


class RemoteSessionExpired(RemoteApiError):
    """A sessão remota (ou a sessão SIGAA por trás dela) não existe mais.

    Quem chama deve refazer o login e repetir a operação.
    """


class RemoteQuestionnaireError(RemoteApiError):
    """Questionário obrigatório do SIGAA bloqueando o acesso aos dados."""


class RemoteInvalidCredentials(RemoteApiError):
    """Usuário ou senha do SIGAA incorretos."""
