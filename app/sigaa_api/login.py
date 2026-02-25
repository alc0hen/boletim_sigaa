from urllib.parse import urljoin
from .exceptions import SigaaInvalidCredentials
class SigaaLogin:
    def __init__(self, session):
        self.session = session
        self.login_status = False
    async def login(self, username, password):
        raise NotImplementedError
class SigaaLoginImpl(SigaaLogin):
    """Generic Sigaa Login implementation (Works for IFSC, IFAL, etc)"""
    def __init__(self, session):
        super().__init__(session)
    async def get_login_form(self):
        page = await self.session.get('/sigaa/verTelaLogin.do')
        return self._parse_login_form(page)
    def _parse_login_form(self, page):
        form = page.soup.find('form', attrs={'name': 'loginForm'})
        if not form:
            raise ValueError('SIGAA: No login form found.')
        action = form.get('action')
        if not action:
            raise ValueError('SIGAA: No action in login form.')
        full_action_url = urljoin(str(page.url), action)
        post_values = {}
        for input_el in form.find_all('input'):
            name = input_el.get('name')
            value = input_el.get('value')
            if name:
                post_values[name] = value if value is not None else ''
        return full_action_url, post_values
    async def login(self, username, password):
        action_url, post_values = await self.get_login_form()
        post_values['user.login'] = username
        post_values['user.senha'] = password
        page = await self.session.post(action_url, data=post_values)
        if '/sigaa/questionarios.jsf' in str(page.url):
             page = await self.session.get('/sigaa/verPortalDiscente.do')
        if 'Entrar no Sistema' in page.body or 'Usuário e/ou senha inválidos' in page.body:
             if 'Usuário e/ou senha inválidos' in page.body:
                 raise SigaaInvalidCredentials('SIGAA: Invalid credentials.')
             raise ValueError('SIGAA: Invalid response after login attempt (Check credentials or system status).')
        self.login_status = True
        return page
