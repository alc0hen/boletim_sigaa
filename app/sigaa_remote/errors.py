class RemoteError(Exception):
    pass

class RemoteUnavailable(RemoteError):
    pass

class RemoteApiError(RemoteError):

    def __init__(self, status_code, code=None, message=None):
        self.status_code = status_code
        self.code = code
        self.message = message or f'Erro {status_code} da API do SIGAA.'
        super().__init__(self.message)

class RemoteSessionExpired(RemoteApiError):
    pass

class RemoteQuestionnaireError(RemoteApiError):
    pass

class RemoteInvalidCredentials(RemoteApiError):
    pass