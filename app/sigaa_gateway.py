import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from .sigaa_remote import RemoteApiError, RemoteQuestionnaireError, RemoteSessionExpired, RemoteUnavailable, get_client, is_configured
logger = logging.getLogger(__name__)
SIGAA_URL = 'https://sigaa.ifal.edu.br'
INSTITUTION_URLS = {'IFAL': SIGAA_URL, 'UFAL': 'https://sigaa.sig.ufal.br', 'UFPE': 'https://sigaa.ufpe.br'}
REMOTE = 'remote'
LOCAL = 'local'

class SigaaError(Exception):
    pass

class SigaaSessionExpired(SigaaError):
    pass

class SigaaQuestionnaire(SigaaError):
    pass

class SigaaLoginFailed(SigaaError):
    pass

class SigaaInstitutionError(SigaaError):
    pass

def institution_url(institution: str) -> str:
    try:
        return INSTITUTION_URLS[(institution or '').upper()]
    except KeyError:
        raise SigaaInstitutionError(f'Instituição sem URL cadastrada: {institution!r}')

def _canonical_url(url: str):
    parsed = urlparse((url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"

def resolve_sigaa_url(institution: str, submitted_url: str=None) -> str:
    expected = institution_url(institution)
    if not submitted_url:
        return expected
    if _canonical_url(submitted_url) != _canonical_url(expected):
        raise SigaaInstitutionError(f'URL {submitted_url!r} não confere com a cadastrada para {institution!r}.')
    return expected

def _backend_preference() -> str:
    return os.environ.get('SIGAA_BACKEND', 'auto').strip().lower()
_local_enrollment: dict[str, dict] = {}
_LOCAL_ENROLLMENT_TTL = 900

def _prune_local_enrollment():
    cutoff = time.time() - _LOCAL_ENROLLMENT_TTL
    for token in [t for t, s in _local_enrollment.items() if s['updated_at'] < cutoff]:
        _local_enrollment.pop(token, None)

class _RemoteBackend:
    name = REMOTE

    def __init__(self, session_id, url, institution):
        self.session_id = session_id
        self.url = url
        self.institution = institution

    async def open(self):
        return self

    async def close_scope(self):
        pass

    @staticmethod
    def translate(exc):
        return None

    async def get_bonds(self):
        data = await get_client().list_bonds(self.session_id)
        return data.get('bonds', [])

    async def get_courses(self, bond_id):
        data = await get_client().list_courses(self.session_id, bond_id)
        return data.get('courses', [])

    async def get_course_details(self, bond_id, course_id, skip_professor=False):
        return await get_client().course_details(self.session_id, bond_id, course_id)

    async def get_history(self, bond_id, cached_history=None):
        data = await get_client().history(self.session_id, bond_id, cached_history=cached_history)
        return data.get('history', {})

    async def get_institutional_data(self, bond_id):
        return {}

    async def get_enrollment(self, bond_id):
        return await get_client().enrollment_disciplines(self.session_id, bond_id)

    async def submit_enrollment(self, bond_id, selected_class_ids):
        return await get_client().enrollment_selection(self.session_id, bond_id, selected_class_ids)

    async def confirm_enrollment(self, bond_id, password):
        return await get_client().enrollment_confirm(self.session_id, bond_id, password)

    async def logout(self):
        try:
            await get_client().close_session(self.session_id)
        except Exception as e:
            logger.info('Falha ao encerrar sessão remota (ignorada): %s', e)

    def state(self):
        return {'backend': REMOTE, 'session_id': self.session_id}

class _LocalBackend:
    name = LOCAL

    def __init__(self, cookies, url, institution, enrollment_token=None):
        self.cookies = cookies
        self.url = url
        self.institution = institution
        self.enrollment_token = enrollment_token
        self.credentials = None
        self._sigaa = None
        self._account = None
        self._courses = {}

    def _institution_type(self):
        from .sigaa_api.enums import InstitutionType
        try:
            return InstitutionType[(self.institution or 'UFAL').upper()]
        except KeyError:
            return InstitutionType.IFAL

    async def open(self):
        from .sigaa_api.sigaa import Sigaa
        from .sigaa_api.account import Account
        from .sigaa_api.exceptions import SigaaQuestionnaireError
        if self._sigaa is not None and self._account is not None:
            return self
        self._sigaa = Sigaa(self.url, self._institution_type(), cookies=self.cookies)
        try:
            response = await self._sigaa.session.get('/sigaa/portais/discente/discente.jsf')
            if 'login' in str(getattr(response.url, 'path', response.url)):
                raise SigaaSessionExpired('Sessão do SIGAA expirada.')
            self._account = Account(self._sigaa.session, response)
        except SigaaQuestionnaireError as e:
            await self.close_scope()
            raise SigaaQuestionnaire(str(e))
        except SigaaSessionExpired:
            await self.close_scope()
            raise
        except Exception as e:
            await self.close_scope()
            raise SigaaError(str(e))
        return self

    @staticmethod
    def translate(exc):
        from .sigaa_api.exceptions import SigaaException, SigaaInvalidCredentials, SigaaQuestionnaireError, SigaaSessionExpired as ScraperSessionExpired
        if isinstance(exc, SigaaQuestionnaireError):
            return SigaaQuestionnaire(str(exc))
        if isinstance(exc, ScraperSessionExpired):
            return SigaaSessionExpired(str(exc))
        if isinstance(exc, SigaaInvalidCredentials):
            return SigaaLoginFailed(str(exc))
        if isinstance(exc, SigaaException):
            return SigaaError(str(exc))
        return None

    async def close_scope(self):
        if self._sigaa is not None:
            try:
                await self._sigaa.close()
            finally:
                self._sigaa = None
                self._account = None
                self._courses = {}

    def _bond_lists(self):
        return {'active': self._account.active_bonds or [], 'inactive': getattr(self._account, 'inactive_bonds', None) or []}

    def _find_bond(self, bond_id):
        try:
            status, index = bond_id.split(':', 1)
            index = int(index)
        except (ValueError, AttributeError):
            raise SigaaError(f'bond_id inválido: {bond_id!r}')
        bonds = self._bond_lists().get(status)
        if bonds is None or not 0 <= index < len(bonds):
            raise SigaaError(f'Vínculo não encontrado: {bond_id}')
        return bonds[index]

    def _enrollment_state(self):
        _prune_local_enrollment()
        if not self.enrollment_token:
            self.enrollment_token = uuid.uuid4().hex
        return _local_enrollment.setdefault(self.enrollment_token, {'updated_at': time.time()})

    @staticmethod
    def _bond_summary(bond_id, status, bond):
        if hasattr(bond, 'registration'):
            return {'bond_id': bond_id, 'status': status, 'type': 'student', 'registration': bond.registration, 'program': bond.program}
        return {'bond_id': bond_id, 'status': status, 'type': 'teacher'}

    async def get_bonds(self):
        summaries = []
        for status, bonds in self._bond_lists().items():
            for i, bond in enumerate(bonds):
                summaries.append(self._bond_summary(f'{status}:{i}', status, bond))
        return summaries

    async def get_courses(self, bond_id):
        bond = self._find_bond(bond_id)
        if not hasattr(bond, 'get_courses'):
            raise SigaaError('Vínculo docente não possui disciplinas.')
        courses = await bond.get_courses()
        self._courses[bond_id] = courses
        return [{'id': i, 'title': c.title, 'schedule_code': getattr(c, 'schedule_code', ''), 'turma_id': getattr(c, 'turma_key', None)} for i, c in enumerate(courses)]

    async def _course_objects(self, bond_id):
        if bond_id not in self._courses:
            await self.get_courses(bond_id)
        return self._courses[bond_id]

    async def get_course_details(self, bond_id, course_id, skip_professor=False):
        courses = await self._course_objects(bond_id)
        if not 0 <= course_id < len(courses):
            raise SigaaError(f'Disciplina não encontrada: {course_id}')
        course = courses[course_id]
        grades, frequency, professor = await course.get_all_details(skip_professor=skip_professor)
        return {'id': course_id, 'title': course.title, 'schedule_code': getattr(course, 'schedule_code', ''), 'grades': grades, 'frequency': frequency, 'professor': professor, 'review_name': getattr(course, 'canonical_title', course.title), 'code': getattr(course, 'code', None)}

    async def get_history(self, bond_id, cached_history=None):
        bond = self._find_bond(bond_id)
        credentials = self._parallel_credentials()
        return await bond.get_history(cached_history=cached_history, credentials=credentials)

    async def get_institutional_data(self, bond_id):
        bond = self._find_bond(bond_id)
        if hasattr(bond, 'get_institutional_data'):
            return await bond.get_institutional_data()
        return {}

    def _parallel_credentials(self):
        creds = getattr(self, 'credentials', None)
        if not creds:
            return None
        return {'username': creds['username'], 'password': creds['password'], 'url': self.url, 'inst_type': self._institution_type()}

    async def get_enrollment(self, bond_id):
        bond = self._find_bond(bond_id)
        result = await bond.get_enrollment_disciplines()
        state = self._enrollment_state()
        state.update({'view_state': result.get('view_state'), 'action_url': result.get('action_url'), 'updated_at': time.time()})
        return {'levels': result.get('levels'), 'view_state': result.get('view_state')}

    async def submit_enrollment(self, bond_id, selected_class_ids):
        bond = self._find_bond(bond_id)
        state = self._enrollment_state()
        if not state.get('view_state'):
            raise SigaaError('Consulte as turmas antes de submeter a matrícula.')
        page = await bond.submit_enrollment(selected_class_ids, state['view_state'], action_url=state.get('action_url'))
        state.update({'confirm_view_state': page.view_state, 'confirm_body': page.body, 'updated_at': time.time()})
        return {'html': page.body, 'view_state': page.view_state}

    async def confirm_enrollment(self, bond_id, password):
        bond = self._find_bond(bond_id)
        state = self._enrollment_state()
        if not state.get('confirm_view_state'):
            raise SigaaError('Submeta a seleção de turmas antes de confirmar.')
        password_page = await bond.request_confirmation_page(state['confirm_view_state'])
        final_page = await bond.confirm_enrollment(password, password_page.view_state, password_page.body)
        return {'html': final_page.body}

    async def logout(self):
        if self.enrollment_token:
            _local_enrollment.pop(self.enrollment_token, None)

    def state(self):
        state = {'backend': LOCAL, 'cookies': self.cookies}
        if self.enrollment_token:
            state['enrollment_token'] = self.enrollment_token
        return state

class SigaaGateway:

    def __init__(self, backend, url, institution, credentials=None):
        self._backend = backend
        self.url = url
        self.institution = institution
        self.credentials = credentials
        self._scope_depth = 0
        if isinstance(backend, _LocalBackend):
            backend.credentials = credentials

    @property
    def backend_name(self):
        return self._backend.name

    @classmethod
    async def login(cls, url, institution, username, password, credentials=None, keep_session=False):
        institution = (institution or 'UFAL').upper()
        preference = _backend_preference()
        if preference != LOCAL and is_configured():
            try:
                data = await get_client().create_session(url, institution, username, password)
                backend = _RemoteBackend(data['session_id'], url, institution)
                gateway = cls(backend, url, institution, credentials)
                gateway.login_info = {'name': data.get('name'), 'bonds': data.get('bonds', [])}
                return gateway
            except RemoteQuestionnaireError as e:
                raise SigaaQuestionnaire(str(e))
            except RemoteSessionExpired as e:
                raise SigaaLoginFailed(str(e))
            except RemoteUnavailable as e:
                if preference == REMOTE:
                    raise SigaaError(f'API do SIGAA indisponível: {e}')
                logger.warning('API do SIGAA indisponível, usando scraper interno: %s', e)
            except RemoteApiError as e:
                if e.status_code == 401:
                    raise SigaaLoginFailed(str(e))
                raise SigaaError(str(e))
        return await cls._login_local(url, institution, username, password, credentials, keep_session=keep_session)

    @classmethod
    async def _login_local(cls, url, institution, username, password, credentials=None, keep_session=False):
        from .sigaa_api.sigaa import Sigaa
        from .sigaa_api.enums import InstitutionType
        from .sigaa_api.exceptions import SigaaException, SigaaInvalidCredentials, SigaaQuestionnaireError
        try:
            inst_type = InstitutionType[institution]
        except KeyError:
            inst_type = InstitutionType.IFAL
        sigaa = Sigaa(url, inst_type)
        keep = False
        try:
            account = await sigaa.login(username, password)
            client_session = await sigaa.session._get_session()
            cookies = {c.key: c.value for c in client_session.cookie_jar}
            name = await account.get_name()
            bonds = []
            for i, bond in enumerate(account.active_bonds or []):
                bonds.append(_LocalBackend._bond_summary(f'active:{i}', 'active', bond))
            for i, bond in enumerate(getattr(account, 'inactive_bonds', None) or []):
                bonds.append(_LocalBackend._bond_summary(f'inactive:{i}', 'inactive', bond))
            keep = keep_session
        except SigaaQuestionnaireError as e:
            raise SigaaQuestionnaire(str(e))
        except SigaaInvalidCredentials as e:
            raise SigaaLoginFailed(str(e))
        except SigaaException as e:
            raise SigaaError(str(e))
        finally:
            if not keep:
                await sigaa.close()
        backend = _LocalBackend(cookies, url, institution)
        if keep:
            backend._sigaa = sigaa
            backend._account = account
        gateway = cls(backend, url, institution, credentials)
        gateway.login_info = {'name': name, 'bonds': bonds}
        return gateway

    @classmethod
    def from_state(cls, state, credentials=None):
        if not state:
            return None
        url = state.get('url') or SIGAA_URL
        institution = (state.get('institution') or 'UFAL').upper()
        if state.get('backend') == REMOTE and state.get('session_id'):
            backend = _RemoteBackend(state['session_id'], url, institution)
        elif state.get('cookies'):
            backend = _LocalBackend(state['cookies'], url, institution, state.get('enrollment_token'))
        else:
            return None
        return cls(backend, url, institution, credentials)

    def state(self):
        state = {'url': self.url, 'institution': self.institution}
        state.update(self._backend.state())
        return state

    @asynccontextmanager
    async def scope(self):
        await self._enter_scope()
        try:
            yield self
        finally:
            await self._exit_scope()

    async def _enter_scope(self):
        if self._scope_depth == 0:
            await self._backend.open()
        self._scope_depth += 1

    async def _exit_scope(self):
        self._scope_depth -= 1
        if self._scope_depth <= 0:
            self._scope_depth = 0
            await self._backend.close_scope()

    @asynccontextmanager
    async def _auto_scope(self):
        await self._enter_scope()
        try:
            yield
        finally:
            await self._exit_scope()

    async def _invoke(self, method, *args, **kwargs):
        try:
            async with self._auto_scope():
                return await getattr(self._backend, method)(*args, **kwargs)
        except Exception as e:
            translated = self._backend.translate(e)
            if translated is not None:
                raise translated from e
            raise

    async def _call(self, method, *args, **kwargs):
        pref = _backend_preference()
        needs_relogin = False
        if pref == LOCAL and self.backend_name == REMOTE:
            needs_relogin = True
        elif pref == REMOTE and self.backend_name == LOCAL and is_configured():
            needs_relogin = True
        if needs_relogin:
            if not await self._relogin():
                raise SigaaSessionExpired('Sessão do SIGAA expirada devido a mudança de backend.')
        try:
            return await self._invoke(method, *args, **kwargs)
        except (RemoteSessionExpired, SigaaSessionExpired):
            if not await self._relogin():
                raise SigaaSessionExpired('Sessão do SIGAA expirada.')
            return await self._invoke(method, *args, **kwargs)
        except RemoteQuestionnaireError as e:
            raise SigaaQuestionnaire(str(e))
        except RemoteUnavailable as e:
            raise SigaaError(f'API do SIGAA indisponível: {e}')
        except SigaaError:
            raise
        except RemoteApiError as e:
            raise SigaaError(str(e))

    async def _relogin(self):
        if not self.credentials:
            return False
        try:
            fresh = await SigaaGateway.login(self.url, self.institution, self.credentials['username'], self.credentials['password'], credentials=self.credentials)
        except SigaaError as e:
            logger.warning('Re-login automático falhou: %s', e)
            return False
        depth, self._scope_depth = (self._scope_depth, 0)
        try:
            await self._backend.close_scope()
        except Exception:
            logger.debug('Falha ao fechar o backend antigo no re-login.', exc_info=True)
        self._backend = fresh._backend
        if isinstance(self._backend, _LocalBackend):
            self._backend.credentials = self.credentials
        self.login_info = getattr(fresh, 'login_info', None)
        for _ in range(depth):
            await self._enter_scope()
        return True

    async def get_bonds(self):
        return await self._call('get_bonds')

    async def get_courses(self, bond_id):
        return await self._call('get_courses', bond_id)

    async def get_course_details(self, bond_id, course_id, skip_professor=False):
        return await self._call('get_course_details', bond_id, course_id, skip_professor=skip_professor)

    async def get_history(self, bond_id, cached_history=None):
        return await self._call('get_history', bond_id, cached_history=cached_history)

    async def get_institutional_data(self, bond_id):
        return await self._call('get_institutional_data', bond_id)

    async def get_enrollment(self, bond_id):
        return await self._call('get_enrollment', bond_id)

    async def submit_enrollment(self, bond_id, selected_class_ids):
        return await self._call('submit_enrollment', bond_id, selected_class_ids)

    async def confirm_enrollment(self, bond_id, password):
        return await self._call('confirm_enrollment', bond_id, password)

    async def logout(self):
        try:
            await self._backend.logout()
        except Exception as e:
            logger.info('Falha ao encerrar sessão do SIGAA (ignorada): %s', e)

    async def close(self):
        try:
            await self._backend.close_scope()
        except Exception:
            logger.debug('Falha ao fechar o backend do SIGAA.', exc_info=True)