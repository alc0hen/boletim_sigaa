from .session import SigaaSession
from .login import SigaaLoginImpl
from .account import Account
from .types import InstitutionType
class Sigaa:
    def __init__(self, url, institution=InstitutionType.IFAL, cookies=None):
        self.url = url
        self.institution = institution
        self.session = SigaaSession(url, cookies=cookies)
        if institution in [InstitutionType.IFSC, InstitutionType.IFAL, InstitutionType.UFAL]:
            self.login_controller = SigaaLoginImpl(self.session)
        else:
            raise NotImplementedError(f"Institution {institution} not implemented yet.")
    async def login(self, username, password):
        """
        Logs in and returns an Account object.
        """
        page = await self.login_controller.login(username, password)
        return Account(self.session, page)
    async def close(self):
        await self.session.close()
