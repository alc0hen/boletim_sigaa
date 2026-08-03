from quart import Blueprint, render_template, request, redirect, url_for, session, Response, flash, jsonify, g
from .sigaa_api.enums import InstitutionType
from .sigaa_gateway import SigaaError, SigaaGateway, SigaaInstitutionError, SigaaLoginFailed, SigaaQuestionnaire, SigaaSessionExpired, institution_url, resolve_sigaa_url
from .domain.factory import CalculatorFactory
from .demo_data import get_demo_data
from .extensions import db_session, google_oauth, generate_csrf_token
from .security import RateLimiter, is_dev_emulation, sanitize_for_log
from sqlalchemy import select, func, distinct
from sqlalchemy.exc import IntegrityError
from .models import User, LinkedAccount, Disciplina, Professor, Avaliacao, VotoControle, compute_vote_hash, get_cipher_suite
import asyncio
import hmac
from .cache import get as cache_get, set as cache_set
import json
import os
import aiohttp
import logging
import time
import unicodedata
from datetime import datetime, timedelta
bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)
SUPPORTERS_URL = 'https://raw.githubusercontent.com/AlbertCohenhgs/public_lists/refs/heads/main/apoiadores.json'
QUESTIONNAIRE_MESSAGE = 'Questionário de Avaliação PENDENTE bloqueia o acesso aos dados. Acesse o SIGAA para respondê-lo e tente novamente.'
_login_limiter = RateLimiter(max_attempts=8, window_seconds=300)
_data_limiter = RateLimiter(max_attempts=12, window_seconds=60)

def _client_ip() -> str:
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'desconhecido'

async def _rate_limited(limiter: RateLimiter, key: str):
    return await limiter.check(key)
_NOTA_MIN = 1
_NOTA_MAX = 5
_MAX_REVIEW_NAME = 255
_MAX_REVIEWS_PER_REQUEST = 200
_MIN_VOTES_TO_SHOW_COUNT = 20

def _parse_nota(value):
    if value is None:
        return (True, None)
    try:
        nota = int(value)
    except (TypeError, ValueError):
        return (False, None)
    if not _NOTA_MIN <= nota <= _NOTA_MAX:
        return (False, None)
    return (True, nota)

def _parse_review_name(value):
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > _MAX_REVIEW_NAME:
        return None
    return name

def _inst_type(inst_str=None):
    try:
        return InstitutionType[(inst_str or session.get('sigaa_inst') or 'IFAL').upper()]
    except KeyError:
        return InstitutionType.IFAL

async def _load_credentials(db=None):
    active_account_id = session.get('active_account_id')
    if active_account_id:
        db = db or getattr(g, 'db_session', None)
        if db is not None:
            try:
                account = await db.get(LinkedAccount, active_account_id)
                if account:
                    password = account.get_password()
                    if password:
                        return {'username': account.username, 'password': password}
            except Exception as e:
                logger.warning(f'Falha ao ler credenciais da conta vinculada: {e}')
    encrypted = session.get('sigaa_temp_password')
    if encrypted and session.get('username'):
        try:
            cipher = get_cipher_suite()
            return {'username': session['username'], 'password': cipher.decrypt(encrypted.encode('utf-8')).decode('utf-8')}
        except Exception as e:
            logger.warning(f'Falha ao decifrar a senha temporária da sessão: {e}')
    return None

async def _get_single_media(institution, d_name, p_name):
    if not d_name or not p_name:
        return None
    from app.models import MediaExigencia, Disciplina, Professor
    from app.extensions import db_session
    from sqlalchemy import select
    d_name_parsed = _parse_review_name(d_name)
    p_name_parsed = _parse_review_name(p_name)
    if not d_name_parsed or not p_name_parsed:
        return None
    p_name_parsed = p_name_parsed.upper()
    async with db_session() as s:
        result = await s.execute(select(MediaExigencia.media_exigencia).join(Disciplina, MediaExigencia.disciplina_id == Disciplina.id).join(Professor, MediaExigencia.professor_id == Professor.id).filter(Disciplina.institution == institution, Disciplina.name == d_name_parsed, Professor.name == p_name_parsed))
        val = result.scalar()
        return round(float(val), 1) if val is not None else None

async def _inject_exigencia_medias(institution, profile_dict):
    history_raw = profile_dict.get('history_raw', {})
    if not history_raw:
        return profile_dict
    c_names = set()
    p_names = set()
    for classes in history_raw.values():
        for cls in classes:
            c = (cls.get('name') or '').strip()
            p = (cls.get('professor') or '').strip().upper()
            if c and p and (p != 'DESCONHECIDO'):
                c_names.add(c)
                p_names.add(p)
    if not c_names or not p_names:
        return profile_dict
    from app.extensions import db_session
    from app.models import MediaExigencia
    async with db_session() as s:
        result = await s.execute(select(Disciplina.name, Professor.name, MediaExigencia.media_exigencia).select_from(MediaExigencia).join(Disciplina, MediaExigencia.disciplina_id == Disciplina.id).join(Professor, MediaExigencia.professor_id == Professor.id).filter(Disciplina.institution == institution, Disciplina.name.in_(c_names), Professor.name.in_(p_names)))
        medias = {f'{d}|{p}': round(float(a), 1) for d, p, a in result.all() if a is not None}
    for classes in history_raw.values():
        for cls in classes:
            c = (cls.get('name') or '').strip()
            p = (cls.get('professor') or '').strip().upper()
            if c and p:
                avg = medias.get(f'{c}|{p}')
                cls['exigencia_media'] = avg
    return profile_dict

async def _get_gateway(db=None):
    state = session.get('sigaa_state')
    if not state:
        return None
    return SigaaGateway.from_state(state, await _load_credentials(db))

def _save_gateway(gateway):
    session['sigaa_state'] = gateway.state()
    session['sigaa_url'] = gateway.url
    session['sigaa_inst'] = gateway.institution
    login_info = getattr(gateway, 'login_info', None)
    if login_info and login_info.get('name'):
        session['sigaa_name'] = login_info['name']

def _clear_sigaa_session():
    session.pop('sigaa_state', None)

def _active_student_bonds(bonds):
    return [b for b in bonds if b.get('status') == 'active' and b.get('type') == 'student']

async def _enumerate_courses(gateway, bonds=None):
    if bonds is None:
        bonds = _active_student_bonds(await gateway.get_bonds())
    listing = []
    for bond in bonds:
        for course in await gateway.get_courses(bond['bond_id']):
            listing.append({'id': len(listing) + 1, 'bond_id': bond['bond_id'], 'course_id': course['id'], 'title': course.get('title'), 'program': bond.get('program')})
    return (bonds, listing)

@bp.route('/')
async def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        username = form.get('username', '')
        password = form.get('password', '')
        institution_str = form.get('institution', 'IFAL')
        if not username or not password:
            return await render_template('login.html', error='Informe usuário e senha.')
        retry_after = await _rate_limited(_login_limiter, f'login:{_client_ip()}')
        if retry_after:
            logger.warning(f'Rate limit de login atingido para o IP {sanitize_for_log(_client_ip())}')
            return (await render_template('login.html', error=f'Muitas tentativas de login. Aguarde {int(retry_after) + 1} segundos e tente novamente.'), 429)
        try:
            url = resolve_sigaa_url(institution_str, form.get('sigaa_url'))
        except SigaaInstitutionError as e:
            logger.warning(f'Login recusado por instituição/URL inválida: {sanitize_for_log(e)}')
            return await render_template('login.html', error='Instituição inválida. Selecione uma das opções da lista.')
        try:
            gateway = await SigaaGateway.login(url, institution_str, username, password, credentials={'username': username, 'password': password})
            await _login_limiter.reset(f'login:{_client_ip()}')
            _save_gateway(gateway)
            session['username'] = username
            cipher = get_cipher_suite()
            session['sigaa_temp_password'] = cipher.encrypt(password.encode('utf-8')).decode('utf-8')
            try:
                import uuid
                async with db_session() as s:
                    query = select(LinkedAccount).filter_by(username=username, institution=institution_str)
                    result = await s.execute(query)
                    linked_account = result.scalars().first()
                    session_user_id = session.get('user_id')
                    if linked_account:
                        session['user_id'] = linked_account.user_id
                        session['active_account_id'] = linked_account.id
                        session['sigaa_inst'] = institution_str
                        linked_account.set_password(password)
                    else:
                        if not session_user_id:
                            anon_google_id = f'anon_{uuid.uuid4().hex}'
                            anon_email = f'anon_{uuid.uuid4().hex}@anon.sigaa.local'
                            anon_user = User(google_id=anon_google_id, email=anon_email, name='Usuário Anônimo')
                            s.add(anon_user)
                            await s.flush()
                            session_user_id = anon_user.id
                            session['user_id'] = session_user_id
                            logger.info(f'Criado novo usuário anônimo (ID {session_user_id}) para {institution_str}')
                        linked_account = LinkedAccount(user_id=session_user_id, institution=institution_str, username=username)
                        linked_account.set_password(password)
                        s.add(linked_account)
                        await s.flush()
                        session['active_account_id'] = linked_account.id
                        session['sigaa_inst'] = institution_str
                        logger.info(f'Nova LinkedAccount criada para o usuário {username} na instituição {institution_str}.')
                    await s.commit()
            except Exception as e:
                logger.error(f'Error linking session to account: {sanitize_for_log(e)}')
            return redirect(url_for('main.dashboard'))
        except SigaaQuestionnaire:
            logger.warning('Login bloqueado por questionário obrigatório do SIGAA.')
            return await render_template('login.html', error=QUESTIONNAIRE_MESSAGE)
        except SigaaLoginFailed:
            logger.info('Login recusado pelo SIGAA.')
            return await render_template('login.html', error='Falha no login. Verifique suas credenciais.')
        except SigaaError as e:
            logger.error(f'Login indisponível: {e}')
            return await render_template('login.html', error='O SIGAA está indisponível no momento. Tente novamente em alguns minutos.')
        except Exception as e:
            logger.error(f'Login failed: {type(e).__name__}')
            return await render_template('login.html', error='Falha no login. Verifique suas credenciais.')
    return await render_template('login.html')

@bp.route('/login/google')
async def login_google():
    import secrets
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    redirect_uri = url_for('main.authorize_google', _external=True)
    authorize_url = google_oauth.get_authorize_url(redirect_uri, state)
    return redirect(authorize_url)

@bp.route('/login/google/callback')
async def authorize_google():
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        expected_state = session.pop('oauth_state', None)
        if not code or not state or (not expected_state):
            logger.warning('Callback OAuth rejeitado: code ou state ausente.')
            return redirect(url_for('main.login'))
        if not hmac.compare_digest(str(state), str(expected_state)):
            logger.warning('Callback OAuth rejeitado: state não confere.')
            return redirect(url_for('main.login'))
        redirect_uri = url_for('main.authorize_google', _external=True)
        token_data = await google_oauth.exchange_code(code, redirect_uri)
        user_info = await google_oauth.get_userinfo(token_data['access_token'])
        if not user_info or not user_info.get('sub'):
            return ('Falha na autenticação Google (sem info)', 400)
        if not user_info.get('email') or not user_info.get('email_verified'):
            logger.warning('Callback OAuth rejeitado: e-mail do Google não verificado.')
            return redirect(url_for('main.login'))
    except Exception as e:
        logger.error(f'Google Auth Error: {sanitize_for_log(e)}')
        return redirect(url_for('main.login'))
    async with db_session() as s:
        result = await s.execute(select(User).filter_by(google_id=user_info['sub']))
        user = result.scalars().first()
        if not user:
            user = User(google_id=user_info['sub'], email=user_info['email'], name=user_info.get('name'), profile_pic=user_info.get('picture'))
            s.add(user)
        else:
            user.name = user_info.get('name')
            user.profile_pic = user_info.get('picture')
        await s.commit()
        await s.refresh(user)
        session['user_id'] = user.id
        temp_pass_enc = session.get('sigaa_temp_password')
        temp_pass = None
        if temp_pass_enc:
            cipher = get_cipher_suite()
            try:
                temp_pass = cipher.decrypt(temp_pass_enc.encode('utf-8')).decode('utf-8')
            except Exception:
                pass
        temp_user = session.get('username')
        temp_inst = session.get('sigaa_inst')
        if temp_pass and temp_user and temp_inst:
            result2 = await s.execute(select(LinkedAccount).filter_by(user_id=user.id, institution=temp_inst, username=temp_user))
            existing = result2.scalars().first()
            if not existing:
                try:
                    new_account = LinkedAccount(user_id=user.id, institution=temp_inst, username=temp_user)
                    new_account.set_password(temp_pass)
                    s.add(new_account)
                    await s.commit()
                    await s.refresh(new_account)
                    session['active_account_id'] = new_account.id
                    logger.info(f'Auto-linked SIGAA account {temp_user} ({temp_inst}) to Google user {user.email}')
                except Exception as e:
                    logger.error(f'Error auto-linking account: {sanitize_for_log(e)}')
                    await s.rollback()
            else:
                session['active_account_id'] = existing.id
            session.pop('sigaa_temp_password', None)
        if user.linked_accounts and 'active_account_id' not in session:
            session['active_account_id'] = user.linked_accounts[0].id
    return redirect(url_for('main.dashboard'))

@bp.route('/profile')
async def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        user = await s.get(User, session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('main.login'))
        return await render_template('profile.html', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))

@bp.route('/link_account', methods=['POST'])
async def link_account():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        user = await s.get(User, session['user_id'])
        if user and user.email.endswith('@anon.sigaa.local'):
            return await render_template('profile.html', error='Usuários anônimos não podem vincular múltiplas contas. Faça login com o Google para habilitar essa função.', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
    form = await request.form
    institution_str = form.get('institution')
    username = form.get('username')
    password = form.get('password')
    if not all([institution_str, username, password]):
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error='Preencha todos os campos.', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
    try:
        url = resolve_sigaa_url(institution_str)
    except SigaaInstitutionError as e:
        logger.warning(f'Vínculo recusado por instituição inválida: {e}')
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error='Instituição inválida.', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
    try:
        gateway = await SigaaGateway.login(url, institution_str, username, password, credentials={'username': username, 'password': password})
        async with db_session() as s:
            new_account = LinkedAccount(user_id=session['user_id'], institution=institution_str, username=username)
            new_account.set_password(password)
            s.add(new_account)
            await s.commit()
            await s.refresh(new_account)
            session['active_account_id'] = new_account.id
        _save_gateway(gateway)
        session['username'] = username
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.error(f'Link Account Failed: {e}')
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error='Falha ao vincular: Credenciais inválidas.', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))

@bp.route('/unlink_account/<int:id>', methods=['POST'])
async def unlink_account(id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        account = await s.get(LinkedAccount, id)
        if account and account.user_id == session['user_id']:
            await s.delete(account)
            await s.commit()
            if session.get('active_account_id') == id:
                session.pop('active_account_id', None)
                _clear_sigaa_session()
                user = await s.get(User, session['user_id'])
                if user and user.linked_accounts:
                    session['active_account_id'] = user.linked_accounts[0].id
    return redirect(url_for('main.profile'))

@bp.route('/activate_account/<int:id>', methods=['POST'])
async def activate_account(id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        account = await s.get(LinkedAccount, id)
        if account and account.user_id == session['user_id']:
            session['active_account_id'] = account.id
            _clear_sigaa_session()
    return redirect(url_for('main.dashboard'))

@bp.route('/dashboard')
async def dashboard():
    if 'user_id' in session:
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            if user and (not user.has_completed_onboarding):
                res = await s.execute(select(LinkedAccount).where(LinkedAccount.user_id == user.id))
                if res.first():
                    return redirect(url_for('main.onboarding'))
    if 'user_id' in session and (not session.get('sigaa_state')):
        active_id = session.get('active_account_id')
        async with db_session() as s:
            if not active_id:
                user = await s.get(User, session['user_id'])
                if user and user.linked_accounts:
                    active_id = user.linked_accounts[0].id
                    session['active_account_id'] = active_id
                else:
                    return redirect(url_for('main.profile'))
            account = await s.get(LinkedAccount, active_id)
            if not account:
                session.pop('active_account_id', None)
                return redirect(url_for('main.profile'))
            password = account.get_password()
            if not password:
                return redirect(url_for('main.profile'))
            acct_username = account.username
            acct_institution = account.institution
        try:
            url = institution_url(acct_institution)
            gateway = await SigaaGateway.login(url, acct_institution, acct_username, password, credentials={'username': acct_username, 'password': password})
            _save_gateway(gateway)
            session['username'] = acct_username
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f'Auto-login failed for {acct_username}: {e}')
            return redirect(url_for('main.profile'))
    if not session.get('sigaa_state'):
        if 'user_id' in session:
            return redirect(url_for('main.profile'))
        return redirect(url_for('main.login'))
    user = None
    linked_accounts = []
    if 'user_id' in session:
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            if user:
                linked_accounts = user.linked_accounts
    return await render_template('dashboard.html', user=user, linked_accounts=linked_accounts, active_account_id=session.get('active_account_id'), has_completed_onboarding=user.has_completed_onboarding if user else False)

@bp.route('/onboarding')
async def onboarding():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        user = await s.get(User, session['user_id'])
        if not user:
            return redirect(url_for('main.login'))
        if user.has_completed_onboarding and request.args.get('mode') != 'review':
            return redirect(url_for('main.dashboard'))
    return await render_template('onboarding.html', user=user)

@bp.route('/test_onboarding')
async def test_onboarding():
    return await render_template('dashboard.html', user=None, linked_accounts=[], active_account_id=None, has_completed_onboarding=False)

def _scrub_active_semester_from_cache(cached_data):
    return cached_data

@bp.route('/api/academic_profile')
async def academic_profile():
    if not session.get('sigaa_state'):
        return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
    retry_after = await _rate_limited(_data_limiter, f'profile:{_client_ip()}')
    if retry_after:
        return (jsonify({'error': 'Muitas requisições. Aguarde alguns segundos.', 'retry_after': int(retry_after) + 1}), 429)
    force_update = request.args.get('force') == 'true'
    active_account_id = session.get('active_account_id')
    linked_account = None
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    cache_key = f"{session.get('user_id')}_{session.get('username')}_{session.get('sigaa_inst')}_profile"
    if not force_update:
        cached = await cache_get('profile', cache_key)
        if cached:
            logger.info('Redis cache hit for academic profile')
            return jsonify(_scrub_active_semester_from_cache(cached))
    cached_history_raw = None
    if linked_account and linked_account.history_json:
        try:
            cipher = get_cipher_suite()
            decrypted_json = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
            cached_data = json.loads(decrypted_json)
            cached_history_raw = cached_data.get('history_raw')
            if not force_update and linked_account.history_updated_at:
                if datetime.utcnow() - linked_account.history_updated_at < timedelta(days=3):
                    return jsonify(_scrub_active_semester_from_cache(cached_data))
        except Exception as e:
            logger.error(f'Cache decryption failed: {e}')
            pass
    inst_type = _inst_type()
    gateway = await _get_gateway()
    if gateway is None:
        return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
    try:
        start_time = time.time()
        async with gateway.scope():
            all_bonds = await gateway.get_bonds()
            active_bonds = _active_student_bonds(all_bonds)
            student_bonds = [b for b in all_bonds if b.get('type') == 'student']
            bonds_to_use = active_bonds if active_bonds else student_bonds
            if not bonds_to_use:
                return (jsonify({'error': 'No student bonds found'}), 404)
            history = await gateway.get_history(bonds_to_use[0]['bond_id'], cached_history=cached_history_raw)
        _save_gateway(gateway)
        duration = time.time() - start_time
        logger.info(f'Historical data fetch took {duration:.2f}s')
        total_grades = []
        best_grade = 0
        best_subject = '-'
        semesters_data = []
        calculator = CalculatorFactory.get_calculator(inst_type)
        for sem, subjects in history.items():
            sem_grades = []
            for subj in subjects:
                try:
                    if subj.get('final_grade') is None:
                        res = calculator.calculate(subj.get('grades', []))
                        subj['final_grade'] = res.average
                        subj['status_dict'] = res.to_dict()
                    else:
                        subj.pop('status_dict', None)
                    logger.info(f"Final grade for '{subj.get('name')}': {subj.get('final_grade')} ({subj.get('status', '')})")
                except Exception as e:
                    logger.error(f"Failed to calculate history grades for {subj.get('name')}: {e}")
                grade = subj.get('final_grade')
                if grade is not None:
                    sem_grades.append(grade)
                    total_grades.append(grade)
                    if grade > best_grade:
                        best_grade = grade
                        best_subject = subj.get('name')
            sem_avg = sum(sem_grades) / len(sem_grades) if sem_grades else 0
            if sem_grades:
                semesters_data.append({'semester': sem, 'average': round(sem_avg, 2), 'count': len(sem_grades)})
        general_avg = sum(total_grades) / len(total_grades) if total_grades else 0
        final_data = {'general_average': round(general_avg, 2), 'best_subject': best_subject, 'best_grade': best_grade, 'semesters': semesters_data, 'history_raw': history}
        if linked_account:
            try:
                cipher = get_cipher_suite()
                json_str = json.dumps(final_data)
                encrypted_data = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')
                linked_account.history_json = encrypted_data
                linked_account.history_updated_at = datetime.utcnow()
                await g.db_session.commit()
            except Exception as e:
                logger.error(f'Cache encryption failed: {e}')
        try:
            cache_key = f"{session.get('user_id')}_{session.get('username')}_{session.get('sigaa_inst')}_profile"
            await cache_set('profile', cache_key, final_data)
            logger.info('Redis cache set for academic profile')
        except Exception as e:
            logger.error(f'Redis cache set failed: {e}')
        return jsonify(final_data)
    except SigaaQuestionnaire as e:
        logger.warning(f'Profile error - questionnaire: {e}')
        return (jsonify({'error': QUESTIONNAIRE_MESSAGE, 'is_questionnaire': True}), 403)
    except SigaaSessionExpired:
        _clear_sigaa_session()
        return (jsonify({'error': 'Session expired', 'session_expired': True}), 401)
    except Exception as e:
        logger.error(f'Profile error: {e}')
        return (jsonify({'error': 'Failed to fetch profile'}), 500)

@bp.route('/apoio')
async def support():
    return await render_template('support.html')

@bp.route('/privacy')
async def privacy():
    return await render_template('privacy.html')

@bp.route('/demo')
async def demo():
    return await render_template('dashboard.html')

@bp.route('/api/stream_demo')
async def stream_demo():

    async def generate():
        await asyncio.sleep(0.5)
        calculator = CalculatorFactory.get_calculator(InstitutionType.IFAL)
        for msg in get_demo_data():
            if msg['type'] == 'course_data':
                raw = msg['data']
                res = calculator.calculate(raw)
                msg['data'] = {'grades': raw, 'status': res.to_dict()}
            await asyncio.sleep(0.1)
            yield (json.dumps(msg) + '\n')
        yield (json.dumps({'type': 'sync_end'}) + '\n')
    return Response(generate(), mimetype='application/x-ndjson')

@bp.route('/api/update_course/<int:course_id>', methods=['POST'])
async def update_course(course_id):
    gateway = await _get_gateway()
    if gateway is None:
        return Response(json.dumps({'error': 'Unauthorized', 'session_expired': True}), status=401, mimetype='application/json')
    inst_type = _inst_type()
    try:
        async with gateway.scope():
            _, listing = await _enumerate_courses(gateway)
            target = next((item for item in listing if item['id'] == course_id), None)
            if not target:
                return Response(json.dumps({'error': 'Course not found'}), status=404, mimetype='application/json')
            details = await gateway.get_course_details(target['bond_id'], target['course_id'])
        _save_gateway(gateway)
        raw_grades = details.get('grades') or []
        freq_data = details.get('frequency')
        calculator = CalculatorFactory.get_calculator(inst_type)
        course_result = calculator.calculate(raw_grades)
        response_data = {'id': course_id, 'data': {'grades': raw_grades, 'status': course_result.to_dict()}}
        if freq_data:
            response_data['frequency'] = freq_data
        return Response(json.dumps(response_data), mimetype='application/json')
    except SigaaQuestionnaire as e:
        logger.warning(f'Single update error - questionnaire: {e}')
        return Response(json.dumps({'error': QUESTIONNAIRE_MESSAGE, 'is_questionnaire': True}), status=403, mimetype='application/json')
    except SigaaSessionExpired:
        _clear_sigaa_session()
        return Response(json.dumps({'error': 'Session expired', 'session_expired': True}), status=401, mimetype='application/json')
    except Exception as e:
        logger.error(f'Single update error: {e}')
        return Response(json.dumps({'error': 'Internal Server Error'}), status=500, mimetype='application/json')

@bp.route('/api/stream_grades')
async def stream_grades():
    if not session.get('sigaa_state'):
        return Response(json.dumps({'error': 'Unauthorized', 'session_expired': True}) + '\n', status=401, mimetype='application/x-ndjson')
    retry_after = await _rate_limited(_data_limiter, f'stream:{_client_ip()}')
    if retry_after:
        return Response(json.dumps({'error': 'Muitas requisições. Aguarde alguns segundos.', 'retry_after': int(retry_after) + 1}) + '\n', status=429, mimetype='application/x-ndjson')
    skip_ids = [int(x) for x in request.args.get('skip', '').split(',') if x.strip().isdigit()]
    inst_type = _inst_type()
    student_name = session.get('sigaa_name')
    active_account_id = session.get('active_account_id')
    cached_profile = None
    has_linked_account = False
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
        if linked_account:
            has_linked_account = True
            if linked_account.history_json:
                try:
                    cipher = get_cipher_suite()
                    decrypted = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
                    cached_profile = json.loads(decrypted)
                except Exception as e:
                    logger.warning(f'Failed to load cached history: {e}')
        else:
            logger.warning('active_account_id existe na sessão mas não no banco.')
    gateway = await _get_gateway()
    if gateway is None:
        return Response(json.dumps({'error': 'Unauthorized', 'session_expired': True}) + '\n', status=401, mimetype='application/x-ndjson')

    async def get_supporters_task():
        try:
            async with aiohttp.ClientSession() as http_client_session:
                async with http_client_session.get(SUPPORTERS_URL, timeout=3) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
        except:
            pass
        return []
    sigaa_temp_pwd = session.get('sigaa_temp_password')
    sigaa_inst_val = session.get('sigaa_inst', 'IFAL')
    sigaa_username_val = session.get('username')

    async def async_generate():
        if cached_profile:
            injected_profile = await _inject_exigencia_medias(sigaa_inst_val, cached_profile)
            yield (json.dumps({'type': 'profile_data', 'data': injected_profile}) + '\n')
            logger.info('SIGAA: Emitted cached history_json for instant UI rendering.')
        try:
            async with gateway.scope():
                all_bonds = await gateway.get_bonds()
                active_bonds = _active_student_bonds(all_bonds)
                student_bonds = [b for b in all_bonds if b.get('type') == 'student']
                bonds_to_use = active_bonds if active_bonds else student_bonds
                supporters = await get_supporters_task()
                registration = bonds_to_use[0].get('registration') if bonds_to_use else None
                is_supporter = bool(registration and str(registration) in {str(s) for s in supporters})
                yield (json.dumps({'type': 'user_info', 'name': student_name, 'is_supporter': is_supporter}) + '\n')
                if bonds_to_use:
                    calculator = CalculatorFactory.get_calculator(inst_type)
                    _, listing = await _enumerate_courses(gateway, bonds_to_use)
                    yield (json.dumps({'type': 'sync_start', 'total_courses': len(listing)}) + '\n')
                    for item in listing:
                        yield (json.dumps({'type': 'course_start', 'id': item['id'], 'name': item['title'], 'obs': item['program']}) + '\n')
                    for bond in bonds_to_use:
                        bond_id = bond['bond_id']
                        bond_courses = [item for item in listing if item['bond_id'] == bond_id]
                        all_courses = []
                        for item in bond_courses:
                            if item['id'] in skip_ids:
                                yield (json.dumps({'type': 'course_skipped', 'id': item['id']}) + '\n')
                            else:
                                all_courses.append((bond_id, item))
                        raw_password = None
                        if sigaa_temp_pwd:
                            try:
                                cipher = get_cipher_suite()
                                raw_password = cipher.decrypt(sigaa_temp_pwd.encode('utf-8')).decode('utf-8')
                            except:
                                pass
                        elif active_account_id:
                            try:
                                async with db_session() as s:
                                    db_acc = await s.get(LinkedAccount, active_account_id)
                                    if db_acc:
                                        raw_password = db_acc.get_password()
                            except:
                                pass
                        if raw_password and len(all_courses) > 1:
                            import math
                            num_workers = min(10, len(all_courses))
                            chunk_size = math.ceil(len(all_courses) / num_workers)
                            chunks = [all_courses[i:i + chunk_size] for i in range(0, len(all_courses), chunk_size)]
                            queue = asyncio.Queue()
                            inst_str = sigaa_inst_val
                            try:
                                url = resolve_sigaa_url(inst_str)
                            except:
                                url = gateway.url
                            username_val = sigaa_username_val

                            async def worker(chunk):
                                try:
                                    w_gateway = await SigaaGateway.login(url, inst_str, username_val, raw_password, credentials={'username': username_val, 'password': raw_password})
                                    for b_id, item in chunk:
                                        c_id = item['id']
                                        await queue.put({'type': 'course_loading', 'id': c_id, 'step': 'notas'})
                                        try:
                                            details = await w_gateway.get_course_details(b_id, item['course_id'])
                                            raw_grades = details.get('grades') or []
                                            freq_data = details.get('frequency')
                                            course_result = calculator.calculate(raw_grades)
                                            prof = details.get('professor')
                                            exigencia = await _get_single_media(sigaa_inst_val, item['title'], prof)
                                            result_data = {'grades': raw_grades, 'status': course_result.to_dict(), 'professor': prof, 'exigencia_media': exigencia}
                                            await queue.put({'type': 'course_data', 'id': c_id, 'data': result_data})
                                            await queue.put({'type': 'course_loading', 'id': c_id, 'step': 'frequencia'})
                                            if freq_data:
                                                await queue.put({'type': 'course_frequency', 'id': c_id, 'data': freq_data})
                                        except Exception as e:
                                            logger.error(f"SIGAA: Falha ao coletar dados detalhados para a disciplina '{item['title']}' (ID: {c_id}): {e}", exc_info=True)
                                            empty_result = calculator.calculate([])
                                            fallback_data = {'grades': [], 'status': empty_result.to_dict()}
                                            await queue.put({'type': 'course_data', 'id': c_id, 'data': fallback_data})
                                        await queue.put({'type': 'course_loading', 'id': c_id, 'step': 'done'})
                                    await w_gateway.logout()
                                except Exception as e:
                                    logger.error(f'SIGAA: Worker login falhou no stream_grades (isto afetará {len(chunk)} disciplinas): {e}', exc_info=True)
                                    for b_id, item in chunk:
                                        c_id = item['id']
                                        empty_result = calculator.calculate([])
                                        fallback_data = {'grades': [], 'status': empty_result.to_dict()}
                                        await queue.put({'type': 'course_data', 'id': c_id, 'data': fallback_data})
                                        await queue.put({'type': 'course_loading', 'id': c_id, 'step': 'done'})
                            tasks = [asyncio.create_task(worker(chunk)) for chunk in chunks]

                            async def waiter():
                                await asyncio.gather(*tasks)
                                await queue.put(None)
                            asyncio.create_task(waiter())
                            while True:
                                evt = await queue.get()
                                if evt is None:
                                    break
                                yield (json.dumps(evt) + '\n')
                        else:
                            for b_id, item in all_courses:
                                c_id = item['id']
                                yield (json.dumps({'type': 'course_loading', 'id': c_id, 'step': 'notas'}) + '\n')
                                try:
                                    details = await gateway.get_course_details(b_id, item['course_id'])
                                    raw_grades = details.get('grades') or []
                                    freq_data = details.get('frequency')
                                    course_result = calculator.calculate(raw_grades)
                                    prof = details.get('professor')
                                    exigencia = await _get_single_media(sigaa_inst_val, item['title'], prof)
                                    result_data = {'grades': raw_grades, 'status': course_result.to_dict(), 'professor': prof, 'exigencia_media': exigencia}
                                    yield (json.dumps({'type': 'course_data', 'id': c_id, 'data': result_data}) + '\n')
                                    yield (json.dumps({'type': 'course_loading', 'id': c_id, 'step': 'frequencia'}) + '\n')
                                    if freq_data:
                                        yield (json.dumps({'type': 'course_frequency', 'id': c_id, 'data': freq_data}) + '\n')
                                except Exception as e:
                                    logger.error(f"SIGAA: Falha sequencial ao coletar dados para a disciplina '{item['title']}' (ID: {c_id}): {e}", exc_info=True)
                                    empty_result = calculator.calculate([])
                                    fallback_data = {'grades': [], 'status': empty_result.to_dict()}
                                    yield (json.dumps({'type': 'course_data', 'id': c_id, 'data': fallback_data}) + '\n')
                                yield (json.dumps({'type': 'course_loading', 'id': c_id, 'step': 'done'}) + '\n')
                yield (json.dumps({'type': 'sync_end'}) + '\n')
        except SigaaQuestionnaire as e:
            logger.warning(f'Stream blocked by questionnaire: {e}')
            yield (json.dumps({'error': QUESTIONNAIRE_MESSAGE, 'is_questionnaire': True}) + '\n')
        except SigaaSessionExpired:
            logger.info('Stream interrompido: sessão do SIGAA expirada.')
            yield (json.dumps({'error': 'Session expired', 'session_expired': True}) + '\n')
        except Exception as e:
            err_msg = str(e)
            logger.error(f'Stream error: {err_msg}')
            if 'Session expired' in err_msg:
                yield (json.dumps({'error': 'Session expired', 'session_expired': True}) + '\n')
            else:
                yield (json.dumps({'error': 'Erro no carregamento dos dados.'}) + '\n')
    return Response(async_generate(), mimetype='application/x-ndjson')

@bp.route('/logout')
async def logout():
    gateway = await _get_gateway()
    if gateway is not None:
        await gateway.logout()
    session.clear()
    return redirect(url_for('main.login'))

@bp.route('/admin')
async def admin():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    user = await g.db_session.get(User, session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.dashboard'))
    total_users = await g.db_session.scalar(select(func.count()).select_from(User))
    total_linked_accounts = await g.db_session.scalar(select(func.count()).select_from(LinkedAccount))
    users_with_accounts = await g.db_session.scalar(select(func.count(distinct(LinkedAccount.user_id))))
    active_percentage = round(users_with_accounts / total_users * 100 if total_users > 0 else 0, 1)
    avg_accounts = round(total_linked_accounts / users_with_accounts if users_with_accounts > 0 else 0, 1)
    result = await g.db_session.execute(select(LinkedAccount.institution, func.count(LinkedAccount.id)).group_by(LinkedAccount.institution))
    inst_counts = result.all()
    stats = {'total_users': total_users, 'total_linked_accounts': total_linked_accounts, 'users_with_accounts': users_with_accounts, 'active_percentage': active_percentage, 'avg_accounts': avg_accounts, 'institutions': dict(inst_counts)}
    result2 = await g.db_session.execute(select(User).order_by(User.id.desc()))
    all_users = result2.scalars().all()
    user_list = []
    for u in all_users:
        accounts = []
        for acc in u.linked_accounts:
            masked_username = acc.username[:3] + '***' + acc.username[-2:] if len(acc.username) > 5 else '***'
            accounts.append({'institution': acc.institution, 'username_masked': masked_username, 'history_updated': acc.history_updated_at.strftime('%d/%m/%Y %H:%M') if acc.history_updated_at else 'Nunca'})
        user_list.append({'id': u.id, 'name': u.name if u.name else 'Usuário Anônimo', 'accounts': accounts})
    return await render_template('admin.html', user=user, stats=stats, user_list=user_list)

@bp.route('/admin/avaliacoes')
async def admin_avaliacoes():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    user = await g.db_session.get(User, session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.dashboard'))
    stmt = select(Avaliacao, Disciplina, Professor).join(Disciplina, Avaliacao.disciplina_id == Disciplina.id).join(Professor, Avaliacao.professor_id == Professor.id).order_by(Avaliacao.created_at.desc())
    result = await g.db_session.execute(stmt)
    rows = result.all()
    disciplina_medias = {}
    for aval, disc, prof in rows:
        key = (disc.id, prof.id)
        if key not in disciplina_medias:
            disciplina_medias[key] = {'notas': [], 'disc_name': disc.name, 'prof_name': prof.name}
        disciplina_medias[key]['notas'].append(aval.nota_exigencia)
    medias_list = []
    lookup_medias = {}
    for (d_id, p_id), data in disciplina_medias.items():
        notas = data['notas']
        media = round(sum(notas) / len(notas), 1)
        lookup_medias[d_id, p_id] = media
        medias_list.append({'disciplina': data['disc_name'], 'professor': data['prof_name'], 'media': media, 'quantidade': len(notas)})
    medias_list.sort(key=lambda x: (x['disciplina'], x['professor']))
    avaliacoes = []
    for aval, disc, prof in rows:
        avaliacoes.append({'id': aval.id, 'disciplina': disc.name, 'professor': prof.name, 'nota': aval.nota_exigencia, 'media_disciplina': lookup_medias[disc.id, prof.id], 'data': aval.created_at.strftime('%d/%m/%Y %H:%M') if aval.created_at else ''})
    return await render_template('admin_avaliacoes.html', user=user, avaliacoes=avaliacoes, medias_list=medias_list)

@bp.route('/api/matricula/status')
async def api_matricula_status():
    if not session.get('sigaa_state'):
        return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
    is_dev = is_dev_emulation()
    if is_dev:
        try:
            from .sigaa_api.enrollment_parser import parse_enrollment_page
            ufal_dir = os.path.join(os.path.dirname(__file__), 'sigaa_api', 'paginas_sigaa', 'UFAL')
            with open(os.path.join(ufal_dir, 'matricula', 'selecao_turmas.html'), 'r', encoding='utf-8') as f:
                selecao_body = f.read()
            levels = parse_enrollment_page(selecao_body)
            session['mock_view_state'] = 'mock_view_state_123'
            return jsonify({'is_dev': True, 'levels': levels, 'view_state': 'mock_view_state_123', 'status': 'success'})
        except Exception as e:
            logger.error(f'Error loading mock matricula: {sanitize_for_log(e)}')
            return (jsonify({'error': 'Erro na emulação.'}), 500)
    else:
        gateway = await _get_gateway()
        if gateway is None:
            return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
        try:
            async with gateway.scope():
                bonds = _active_student_bonds(await gateway.get_bonds())
                if not bonds:
                    return (jsonify({'error': 'No active bonds'}), 404)
                bond_id = bonds[0]['bond_id']
                result = await gateway.get_enrollment(bond_id)
            session['sigaa_enrollment_bond'] = bond_id
            _save_gateway(gateway)
            return jsonify({'is_dev': False, 'levels': result.get('levels'), 'view_state': result.get('view_state'), 'status': 'success'})
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return (jsonify({'error': 'Session expired', 'session_expired': True}), 401)
        except SigaaQuestionnaire:
            return (jsonify({'error': QUESTIONNAIRE_MESSAGE, 'is_questionnaire': True}), 403)
        except Exception as e:
            logger.error(f'Error loading live matricula: {sanitize_for_log(e)}')
            return (jsonify({'error': 'Erro ao acessar o SIGAA. Tente novamente.'}), 500)

@bp.route('/api/matricula/submit', methods=['POST'])
async def api_matricula_submit():
    if not session.get('sigaa_state'):
        return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
    is_dev = is_dev_emulation()
    data = await request.get_json() or {}
    selected_class_ids = data.get('selected_class_ids', [])
    if not selected_class_ids:
        return (jsonify({'error': 'Nenhuma turma selecionada'}), 400)
    if is_dev:
        try:
            tests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests')
            confirm_path = os.path.join(tests_dir, 'confirm_page_debug.html')
            with open(confirm_path, 'r', encoding='utf-8') as f:
                confirm_body = f.read()
            session['mock_confirm_page_body'] = confirm_body
            session['mock_confirm_view_state'] = 'mock_confirm_view_state_456'
            return jsonify({'is_dev': True, 'html': confirm_body, 'view_state': 'mock_confirm_view_state_456', 'status': 'success'})
        except Exception as e:
            logger.error(f'Error submitting mock matricula: {sanitize_for_log(e)}')
            return (jsonify({'error': 'Erro na emulação.'}), 500)
    else:
        gateway = await _get_gateway()
        bond_id = session.get('sigaa_enrollment_bond')
        if gateway is None:
            return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
        if not bond_id:
            return (jsonify({'error': 'Consulte as turmas disponíveis antes de submeter.'}), 409)
        try:
            res = await gateway.submit_enrollment(bond_id, selected_class_ids)
            _save_gateway(gateway)
            return jsonify({'is_dev': False, 'html': res.get('html'), 'view_state': res.get('view_state'), 'status': 'success'})
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return (jsonify({'error': 'Session expired', 'session_expired': True}), 401)
        except Exception as e:
            logger.error(f'Error submitting live matricula: {sanitize_for_log(e)}')
            return (jsonify({'error': 'Erro ao submeter a matrícula ao SIGAA.'}), 500)

@bp.route('/api/matricula/confirm', methods=['POST'])
async def api_matricula_confirm():
    if not session.get('sigaa_state'):
        return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
    is_dev = is_dev_emulation()
    data = await request.get_json() or {}
    password = data.get('password')
    if not password and (not is_dev):
        return (jsonify({'error': 'Senha é obrigatória para confirmação'}), 400)
    if is_dev:
        if password == 'erro':
            return (jsonify({'status': 'error', 'message': 'Senha incorreta ou erro de pré-requisitos no SIGAA.'}), 400)
        else:
            return jsonify({'status': 'success', 'message': 'Matrícula realizada com sucesso! (Emulado)'})
    else:
        gateway = await _get_gateway()
        bond_id = session.get('sigaa_enrollment_bond')
        if gateway is None:
            return (jsonify({'error': 'Unauthorized', 'session_expired': True}), 401)
        if not bond_id:
            return (jsonify({'error': 'Sessão inválida ou expirada'}), 400)
        try:
            res = await gateway.confirm_enrollment(bond_id, password)
            _save_gateway(gateway)
            html = res.get('html') or ''
            from app.sigaa_api.enrollment_parser import parse_confirmation_result
            ok, msg = parse_confirmation_result(html)
            if not ok:
                return (jsonify({'status': 'error', 'message': msg}), 400)
            return jsonify({'status': 'success', 'message': 'Matrícula gravada com sucesso no SIGAA!'})
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return (jsonify({'error': 'Session expired', 'session_expired': True}), 401)
        except Exception as e:
            logger.error(f'Error finalizing live matricula: {sanitize_for_log(e)}')
            return (jsonify({'error': 'Erro ao confirmar a matrícula no SIGAA.'}), 500)

@bp.route('/api/avaliacoes/pendentes', methods=['GET'])
async def avaliacoes_pendentes():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
        if linked_account:
            user_id = linked_account.user_id
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return (jsonify({'error': 'Unauthorized'}), 401)
    user = await g.db_session.get(User, user_id)
    if not user:
        return (jsonify({'error': 'User not found'}), 404)
    skipped = user.skipped_review_semesters or ''
    skipped_list = [s.strip() for s in skipped.split(',') if s.strip()]
    if not linked_account or not linked_account.history_json:
        return (jsonify({'pendentes': [], 'current_semester': None, 'skipped_semesters': skipped_list}), 200)
    try:
        cipher = get_cipher_suite()
        decrypted = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
        cached_profile = json.loads(decrypted)
        history_raw = cached_profile.get('history_raw', {})
    except Exception as e:
        logger.error(f'Error parsing history for reviews: {sanitize_for_log(e)}')
        return (jsonify({'pendentes': []}), 200)
    pares = set()
    for sem, classes in history_raw.items():
        for cls in classes:
            status = cls.get('status', '')
            if status not in ['Matriculado', 'Cursando', 'Indefinido']:
                c_name = (cls.get('name') or '').strip()
                p_name = (cls.get('professor') or '').strip().upper()
                if c_name and p_name and (p_name != 'DESCONHECIDO'):
                    pares.add((c_name, p_name))
    current_semester = None
    if history_raw:
        current_semester = sorted(history_raw.keys())[-1]
    if not pares:
        return jsonify({'pendentes': [], 'current_semester': current_semester, 'skipped_semesters': skipped_list})
    institution = linked_account.institution
    course_names = {c for c, _ in pares}
    prof_names = {p for _, p in pares}
    result_d = await g.db_session.execute(select(Disciplina).filter(Disciplina.institution == institution, Disciplina.name.in_(course_names)))
    disciplina_by_name = {d.name: d.id for d in result_d.scalars().all()}
    result_p = await g.db_session.execute(select(Professor).filter(Professor.institution == institution, Professor.name.in_(prof_names)))
    professor_by_name = {p.name: p.id for p in result_p.scalars().all()}
    hash_by_pair = {(c_name, p_name): compute_vote_hash(linked_account.id, disciplina_by_name[c_name], professor_by_name[p_name]) for c_name, p_name in pares if c_name in disciplina_by_name and p_name in professor_by_name}
    votados = set()
    if hash_by_pair:
        result_v = await g.db_session.execute(select(VotoControle.hash_voto).filter(VotoControle.hash_voto.in_(hash_by_pair.values())))
        hashes_existentes = set(result_v.scalars().all())
        votados = {pair for pair, h in hash_by_pair.items() if h in hashes_existentes}
    pendentes = [{'disciplina': c, 'professor': p} for c, p in pares if (c, p) not in votados]
    return jsonify({'pendentes': pendentes, 'current_semester': current_semester, 'skipped_semesters': skipped_list})

@bp.route('/api/avaliacoes/skip', methods=['POST'])
async def skip_avaliacoes():
    user_id = session.get('user_id')
    if not user_id:
        return (jsonify({'error': 'Unauthorized'}), 401)
    data = await request.get_json()
    semester = data.get('semester')
    if not semester:
        return (jsonify({'error': 'Semester is required'}), 400)
    async with db_session() as s:
        user = await s.get(User, user_id)
        if not user:
            return (jsonify({'error': 'User not found'}), 404)
        skipped = user.skipped_review_semesters or ''
        skipped_list = [sem.strip() for sem in skipped.split(',') if sem.strip()]
        if semester not in skipped_list:
            skipped_list.append(semester)
            user.skipped_review_semesters = ','.join(skipped_list)
            await s.commit()
    return jsonify({'status': 'success', 'skipped_semesters': skipped_list})

@bp.route('/api/avaliacoes/submeter', methods=['POST'])
async def avaliacoes_submeter():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return (jsonify({'error': 'Unauthorized'}), 401)
    if not linked_account:
        return (jsonify({'error': 'No linked account'}), 400)
    data = await request.get_json()
    if not data:
        return (jsonify({'error': 'Invalid payload'}), 400)
    itens = data.get('itens', [])
    if not isinstance(itens, list):
        return (jsonify({'error': 'Invalid payload'}), 400)
    if len(itens) > _MAX_REVIEWS_PER_REQUEST:
        return (jsonify({'error': 'Too many reviews in a single request'}), 400)
    institution = linked_account.institution
    aluno_ref = linked_account.id
    parsed = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        disciplina_nome = _parse_review_name(item.get('disciplina'))
        professor_nome = _parse_review_name(item.get('professor'))
        if not disciplina_nome or not professor_nome:
            continue
        professor_nome = professor_nome.upper()
        recusado = bool(item.get('recusado', False))
        ok, nota = _parse_nota(item.get('nota') or item.get('nota_exigencia'))
        if not ok:
            return (jsonify({'error': 'Nota inválida: use um valor inteiro entre 1 e 5.'}), 400)
        if not recusado and nota is None:
            continue
        parsed.append((disciplina_nome, professor_nome, recusado, nota))
    if not parsed:
        return jsonify({'status': 'success'})
    try:
        disciplina_names = {d for d, p, r, n in parsed}
        professor_names = {p for d, p, r, n in parsed}
        result_d = await g.db_session.execute(select(Disciplina).filter(Disciplina.institution == institution, Disciplina.name.in_(disciplina_names)))
        disciplina_by_name = {d.name: d for d in result_d.scalars().all()}
        result_p = await g.db_session.execute(select(Professor).filter(Professor.institution == institution, Professor.name.in_(professor_names)))
        professor_by_name = {p.name: p for p in result_p.scalars().all()}
        for name in disciplina_names - disciplina_by_name.keys():
            d = Disciplina(institution=institution, name=name)
            g.db_session.add(d)
            disciplina_by_name[name] = d
        for name in professor_names - professor_by_name.keys():
            p = Professor(institution=institution, name=name)
            g.db_session.add(p)
            professor_by_name[name] = p
        if len(disciplina_by_name) or len(professor_by_name):
            await g.db_session.flush()
        hashes = []
        for disciplina_nome, professor_nome, recusado, nota in parsed:
            d_id = disciplina_by_name[disciplina_nome].id
            p_id = professor_by_name[professor_nome].id
            hashes.append((compute_vote_hash(aluno_ref, d_id, p_id), d_id, p_id, recusado, nota))
        result_v = await g.db_session.execute(select(VotoControle).filter(VotoControle.hash_voto.in_({h for h, *_ in hashes})))
        ja_votados = {v.hash_voto: v for v in result_v.scalars().all()}
        novos = set()
        affected_pairs = set()
        for hash_voto, d_id, p_id, recusado, nota in hashes:
            existing = ja_votados.get(hash_voto)
            if existing and existing.voto_computado:
                continue
            if hash_voto in novos:
                continue
            novos.add(hash_voto)
            if existing and (not existing.voto_computado) and (not recusado):
                existing.voto_computado = True
                g.db_session.add(Avaliacao(disciplina_id=d_id, professor_id=p_id, nota_exigencia=nota))
                affected_pairs.add((d_id, p_id))
            elif not existing:
                if recusado:
                    g.db_session.add(VotoControle(hash_voto=hash_voto, voto_computado=False))
                else:
                    g.db_session.add(Avaliacao(disciplina_id=d_id, professor_id=p_id, nota_exigencia=nota))
                    g.db_session.add(VotoControle(hash_voto=hash_voto, voto_computado=True))
                    affected_pairs.add((d_id, p_id))
        await g.db_session.commit()
        logger.info(f'Submeter commit OK. Affected pairs: {affected_pairs}')
        if affected_pairs:
            from app.models import MediaExigencia
            for d_id, p_id in affected_pairs:
                aggs = await g.db_session.execute(select(func.avg(Avaliacao.nota_exigencia).label('media'), func.count(Avaliacao.id).label('total')).filter_by(disciplina_id=d_id, professor_id=p_id))
                r = aggs.first()
                if r and r.total > 0:
                    media_val = float(r.media)
                    total_val = r.total
                    existing = await g.db_session.execute(select(MediaExigencia).filter_by(disciplina_id=d_id, professor_id=p_id))
                    m_row = existing.scalars().first()
                    if m_row:
                        m_row.media_exigencia = media_val
                        m_row.total_votos = total_val
                    else:
                        g.db_session.add(MediaExigencia(disciplina_id=d_id, professor_id=p_id, media_exigencia=media_val, total_votos=total_val))
            await g.db_session.commit()
        return jsonify({'status': 'success'})
    except IntegrityError:
        await g.db_session.rollback()
        return jsonify({'status': 'success'})
    except Exception as e:
        await g.db_session.rollback()
        logger.error(f'Failed to submit reviews: {e}')
        return (jsonify({'error': 'Database error'}), 500)

@bp.route('/api/avaliacoes/media', methods=['GET'])
async def avaliacoes_media():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return (jsonify({'error': 'Unauthorized'}), 401)
    if not linked_account:
        return (jsonify({'error': 'No linked account'}), 400)
    disciplina_nome = _parse_review_name(request.args.get('disciplina'))
    professor_nome = _parse_review_name(request.args.get('professor'))
    if not disciplina_nome or not professor_nome:
        return jsonify({'average': None, 'count': None})
    professor_nome = professor_nome.upper()
    institution = linked_account.institution
    from app.models import MediaExigencia, VotoControle, compute_vote_hash
    user_voted = False
    result = await g.db_session.execute(select(MediaExigencia.media_exigencia, MediaExigencia.total_votos, Disciplina.id, Professor.id).join(Disciplina, MediaExigencia.disciplina_id == Disciplina.id).join(Professor, MediaExigencia.professor_id == Professor.id).filter(Disciplina.institution == institution, Disciplina.name == disciplina_nome, Professor.name == professor_nome))
    row = result.first()
    if row:
        avg, count, d_id, p_id = row
        v_hash = compute_vote_hash(linked_account.id, d_id, p_id)
        vc = await g.db_session.execute(select(VotoControle.voto_computado).filter_by(hash_voto=v_hash))
        vc_val = vc.scalars().first()
        if vc_val is True:
            user_voted = True
    else:
        avg, count = (None, 0)
        d_res = await g.db_session.execute(select(Disciplina.id).filter_by(institution=institution, name=disciplina_nome))
        d_id = d_res.scalars().first()
        p_res = await g.db_session.execute(select(Professor.id).filter_by(institution=institution, name=professor_nome))
        p_id = p_res.scalars().first()
        if d_id and p_id:
            v_hash = compute_vote_hash(linked_account.id, d_id, p_id)
            vc = await g.db_session.execute(select(VotoControle.voto_computado).filter_by(hash_voto=v_hash))
            if vc.scalars().first() is True:
                user_voted = True
    return jsonify({'average': round(avg, 1) if count >= 1 else None, 'count': count if count >= _MIN_VOTES_TO_SHOW_COUNT else None, 'user_voted': user_voted})

@bp.route('/api/avaliacoes/medias_lote', methods=['POST'])
async def avaliacoes_medias_lote():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return (jsonify({'error': 'Unauthorized'}), 401)
    if not linked_account:
        return (jsonify({'error': 'No linked account'}), 400)
    data = await request.get_json() or {}
    pares = data.get('pares', [])
    if not pares:
        return jsonify({})
    institution = linked_account.institution
    c_names = {p.get('disciplina') for p in pares if p.get('disciplina')}
    p_names_upper = {p.get('professor').upper() for p in pares if p.get('professor')}
    if not c_names or not p_names_upper:
        return jsonify({})
    from app.models import MediaExigencia, VotoControle, compute_vote_hash
    result = await g.db_session.execute(select(Disciplina.name, Professor.name, MediaExigencia.media_exigencia).select_from(MediaExigencia).join(Disciplina, MediaExigencia.disciplina_id == Disciplina.id).join(Professor, MediaExigencia.professor_id == Professor.id).filter(Disciplina.institution == institution, Disciplina.name.in_(c_names), Professor.name.in_(p_names_upper)))
    rows = result.all()
    upper_to_orig_p = {p.get('professor').upper(): p.get('professor') for p in pares if p.get('professor')}
    medias = {f"{p.get('disciplina')}|{p.get('professor')}": None for p in pares if p.get('disciplina') and p.get('professor')}
    for d_name, p_name_upper, avg in rows:
        orig_p_name = upper_to_orig_p.get(p_name_upper)
        if orig_p_name and avg is not None:
            medias[f'{d_name}|{orig_p_name}'] = round(float(avg), 1)
    result_pairs = await g.db_session.execute(select(Disciplina.id, Disciplina.name, Professor.id, Professor.name).join(Professor, Professor.name.in_(p_names_upper)).filter(Disciplina.institution == institution, Disciplina.name.in_(c_names), Professor.institution == institution))
    pairs_rows = result_pairs.all()
    hash_to_orig_key = {}
    for d_id, d_name, p_id, p_name_upper in pairs_rows:
        orig_p_name = upper_to_orig_p.get(p_name_upper)
        if orig_p_name:
            h = compute_vote_hash(linked_account.id, d_id, p_id)
            hash_to_orig_key[h] = f'{d_name}|{orig_p_name}'
    user_voted_dict = {f"{p.get('disciplina')}|{p.get('professor')}": False for p in pares if p.get('disciplina') and p.get('professor')}
    if hash_to_orig_key:
        result_votes = await g.db_session.execute(select(VotoControle.hash_voto).filter(VotoControle.hash_voto.in_(hash_to_orig_key.keys()), VotoControle.voto_computado == True))
        for h in result_votes.scalars().all():
            if h in hash_to_orig_key:
                user_voted_dict[hash_to_orig_key[h]] = True
    return jsonify({'averages': medias, 'user_voted': user_voted_dict})

@bp.route('/delete_account', methods=['POST'])
async def delete_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    async with db_session() as s:
        user = await s.get(User, user_id)
        if not user:
            session.clear()
            return redirect(url_for('main.login'))
        await s.delete(user)
        await s.commit()
    session.clear()
    return redirect(url_for('main.login'))

@bp.route('/api/user/complete_onboarding', methods=['POST'])
async def complete_onboarding():
    user_id = session.get('user_id')
    if not user_id:
        return (jsonify({'error': 'Unauthorized'}), 401)
    async with db_session() as s:
        user = await s.get(User, user_id)
        if user:
            user.has_completed_onboarding = True
            await s.commit()
            return jsonify({'success': True})
    return (jsonify({'error': 'User not found'}), 404)