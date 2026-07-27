from quart import Blueprint, render_template, request, redirect, url_for, session, Response, flash, jsonify, g

from .sigaa_api.types import InstitutionType
from .sigaa_gateway import (
    SigaaError,
    SigaaGateway,
    SigaaInstitutionError,
    SigaaLoginFailed,
    SigaaQuestionnaire,
    SigaaSessionExpired,
    institution_url,
    resolve_sigaa_url,
)
from .domain.factory import CalculatorFactory
from .demo_data import get_demo_data
from .extensions import db_session, google_oauth, generate_csrf_token
from .security import RateLimiter, is_dev_emulation, sanitize_for_log
from sqlalchemy import select, func, distinct
from .models import User, LinkedAccount, CourseReview, ProfessorReview, get_cipher_suite
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
SUPPORTERS_URL = "https://raw.githubusercontent.com/AlbertCohenhgs/public_lists/refs/heads/main/apoiadores.json"

QUESTIONNAIRE_MESSAGE = (
    "Questionário de Avaliação PENDENTE bloqueia o acesso aos dados. "
    "Acesse o SIGAA para respondê-lo e tente novamente."
)

_login_limiter = RateLimiter(max_attempts=8, window_seconds=300)
_data_limiter = RateLimiter(max_attempts=12, window_seconds=60)


def _client_ip() -> str:
    """IP do cliente, considerando o proxy reverso da hospedagem."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'desconhecido'


def _rate_limited(limiter: RateLimiter, key: str):
    """Retorna os segundos de espera, ou 0 se a requisição é permitida."""
    return limiter.check(key)


_RATING_MIN = 1.0
_RATING_MAX = 5.0
_MAX_REVIEW_NAME = 255
_MAX_REVIEWS_PER_REQUEST = 200


def _parse_rating(value):
    """Valida a nota. Retorna (ok, valor) — valor None significa 'sem nota'."""
    if value is None:
        return True, None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return False, None
    # math.isfinite rejeita NaN e ±Infinity de uma vez.
    import math
    if not math.isfinite(rating):
        return False, None
    if not (_RATING_MIN <= rating <= _RATING_MAX):
        return False, None
    return True, round(rating, 2)


def _parse_review_name(value):
    """Normaliza e valida o nome de disciplina/professor enviado pelo cliente."""
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
                logger.warning(f"Falha ao ler credenciais da conta vinculada: {e}")

    encrypted = session.get('sigaa_temp_password')
    if encrypted and session.get('username'):
        try:
            cipher = get_cipher_suite()
            return {
                'username': session['username'],
                'password': cipher.decrypt(encrypted.encode('utf-8')).decode('utf-8'),
            }
        except Exception as e:
            logger.warning(f"Falha ao decifrar a senha temporária da sessão: {e}")
    return None


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
            listing.append({
                'id': len(listing) + 1,
                'bond_id': bond['bond_id'],
                'course_id': course['id'],
                'title': course.get('title'),
                'program': bond.get('program'),
            })
    return bonds, listing


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
            return await render_template('login.html', error="Informe usuário e senha.")

        retry_after = _rate_limited(_login_limiter, f"login:{_client_ip()}")
        if retry_after:
            logger.warning(f"Rate limit de login atingido para o IP {sanitize_for_log(_client_ip())}")
            return await render_template(
                'login.html',
                error=f"Muitas tentativas de login. Aguarde {int(retry_after) + 1} segundos e tente novamente.",
            ), 429

        try:
            url = resolve_sigaa_url(institution_str, form.get('sigaa_url'))
        except SigaaInstitutionError as e:
            logger.warning(f"Login recusado por instituição/URL inválida: {sanitize_for_log(e)}")
            return await render_template('login.html', error="Instituição inválida. Selecione uma das opções da lista.")

        try:
            gateway = await SigaaGateway.login(
                url, institution_str, username, password,
                credentials={'username': username, 'password': password},
            )
            _login_limiter.reset(f"login:{_client_ip()}")
            _save_gateway(gateway)
            session['username'] = username
            cipher = get_cipher_suite()
            session['sigaa_temp_password'] = cipher.encrypt(password.encode('utf-8')).decode('utf-8')
            try:
                async with db_session() as s:
                    query = select(LinkedAccount).filter_by(
                        username=username, institution=institution_str
                    )
                    session_user_id = session.get('user_id')
                    if session_user_id:
                        query = query.filter_by(user_id=session_user_id)
                    result = await s.execute(query)
                    linked_account = result.scalars().first()
                    if linked_account:
                        session['active_account_id'] = linked_account.id
                    else:
                        # Evita herdar o vínculo ativo de um login anterior.
                        session.pop('active_account_id', None)
            except Exception as e:
                logger.error(f"Error linking session to account: {sanitize_for_log(e)}")
            return redirect(url_for('main.dashboard'))
        except SigaaQuestionnaire:
            logger.warning("Login bloqueado por questionário obrigatório do SIGAA.")
            return await render_template('login.html', error=QUESTIONNAIRE_MESSAGE)
        except SigaaLoginFailed:
            logger.info("Login recusado pelo SIGAA.")
            return await render_template('login.html', error="Falha no login. Verifique suas credenciais.")
        except SigaaError as e:
                                                                   
                                                                         
            logger.error(f"Login indisponível: {e}")
            return await render_template('login.html', error="O SIGAA está indisponível no momento. Tente novamente em alguns minutos.")
        except Exception as e:
            logger.error(f"Login failed: {type(e).__name__}")
            return await render_template('login.html', error="Falha no login. Verifique suas credenciais.")
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

        if not code or not state or not expected_state:
            logger.warning("Callback OAuth rejeitado: code ou state ausente.")
            return redirect(url_for('main.login'))
        if not hmac.compare_digest(str(state), str(expected_state)):
            logger.warning("Callback OAuth rejeitado: state não confere.")
            return redirect(url_for('main.login'))

        redirect_uri = url_for('main.authorize_google', _external=True)
        token_data = await google_oauth.exchange_code(code, redirect_uri)
        user_info = await google_oauth.get_userinfo(token_data['access_token'])
        if not user_info or not user_info.get('sub'):
             return "Falha na autenticação Google (sem info)", 400

        if not user_info.get('email') or not user_info.get('email_verified'):
            logger.warning("Callback OAuth rejeitado: e-mail do Google não verificado.")
            return redirect(url_for('main.login'))
    except Exception as e:
        logger.error(f"Google Auth Error: {sanitize_for_log(e)}")
        return redirect(url_for('main.login'))

    async with db_session() as s:
        result = await s.execute(select(User).filter_by(google_id=user_info['sub']))
        user = result.scalars().first()
        if not user:
            user = User(
                google_id=user_info['sub'],
                email=user_info['email'],
                name=user_info.get('name'),
                profile_pic=user_info.get('picture')
            )
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
            result2 = await s.execute(
                select(LinkedAccount).filter_by(user_id=user.id, institution=temp_inst, username=temp_user)
            )
            existing = result2.scalars().first()
            if not existing:
                try:
                    new_account = LinkedAccount(
                        user_id=user.id,
                        institution=temp_inst,
                        username=temp_user
                    )
                    new_account.set_password(temp_pass)
                    s.add(new_account)
                    await s.commit()
                    await s.refresh(new_account)
                    session['active_account_id'] = new_account.id
                    logger.info(f"Auto-linked SIGAA account {temp_user} ({temp_inst}) to Google user {user.email}")
                except Exception as e:
                    logger.error(f"Error auto-linking account: {sanitize_for_log(e)}")
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
    form = await request.form
    institution_str = form.get('institution')
    username = form.get('username')
    password = form.get('password')
    if not all([institution_str, username, password]):
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error="Preencha todos os campos.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
                                                                  
                            
    try:
        url = resolve_sigaa_url(institution_str)
    except SigaaInstitutionError as e:
        logger.warning(f"Vínculo recusado por instituição inválida: {e}")
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error="Instituição inválida.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))

    try:
        gateway = await SigaaGateway.login(
            url, institution_str, username, password,
            credentials={'username': username, 'password': password},
        )
        async with db_session() as s:
            new_account = LinkedAccount(
                user_id=session['user_id'],
                institution=institution_str,
                username=username
            )
            new_account.set_password(password)
            s.add(new_account)
            await s.commit()
            await s.refresh(new_account)
            session['active_account_id'] = new_account.id
        _save_gateway(gateway)
        session['username'] = username
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.error(f"Link Account Failed: {e}")
        async with db_session() as s:
            user = await s.get(User, session['user_id'])
            return await render_template('profile.html', error="Falha ao vincular: Credenciais inválidas.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))


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
    if 'user_id' in session and not session.get('sigaa_state'):
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
            gateway = await SigaaGateway.login(
                url, acct_institution, acct_username, password,
                credentials={'username': acct_username, 'password': password},
            )
            _save_gateway(gateway)
            session['username'] = acct_username
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f"Auto-login failed for {acct_username}: {e}")
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
    return await render_template('dashboard.html', user=user, linked_accounts=linked_accounts, active_account_id=session.get('active_account_id'))


def _scrub_active_semester_from_cache(cached_data):
    # Logic removed: bond.py already excludes the active semester and active courses correctly.
    # Guessing based on hardcoded statuses was erroneously deleting valid previous semesters (e.g., if a status was "Concluído").
    return cached_data

@bp.route('/api/academic_profile')
async def academic_profile():

    if not session.get('sigaa_state'):
        return jsonify({"error": "Unauthorized", "session_expired": True}), 401

    retry_after = _rate_limited(_data_limiter, f"profile:{_client_ip()}")
    if retry_after:
        return jsonify({
            "error": "Muitas requisições. Aguarde alguns segundos.",
            "retry_after": int(retry_after) + 1,
        }), 429
    force_update = request.args.get('force') == 'true'
    active_account_id = session.get('active_account_id')
    linked_account = None
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
                                                                   
    cache_key = f"{session.get('user_id')}_{session.get('username')}_{session.get('sigaa_inst')}_profile"
    if not force_update:
        cached = await cache_get('profile', cache_key)
        if cached:
            logger.info("Redis cache hit for academic profile")
            return jsonify(_scrub_active_semester_from_cache(cached))
                             
    if linked_account and not force_update and linked_account.history_json and linked_account.history_updated_at:
        if datetime.utcnow() - linked_account.history_updated_at < timedelta(days=3):
            try:
                cipher = get_cipher_suite()
                decrypted_json = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
                cached_data = json.loads(decrypted_json)
                return jsonify(_scrub_active_semester_from_cache(cached_data))
            except Exception as e:
                logger.error(f"Cache decryption failed: {e}")
                pass
    inst_type = _inst_type()

    gateway = await _get_gateway()
    if gateway is None:
        return jsonify({"error": "Unauthorized", "session_expired": True}), 401

    try:
        start_time = time.time()
        async with gateway.scope():
            bonds = _active_student_bonds(await gateway.get_bonds())
            if not bonds:
                return jsonify({"error": "No active bonds"}), 404
            history = await gateway.get_history(bonds[0]['bond_id'])
        _save_gateway(gateway)
        duration = time.time() - start_time
        logger.info(f"Historical data fetch took {duration:.2f}s")

        total_grades = []
        best_grade = 0
        best_subject = "-"
        semesters_data = []
        calculator = CalculatorFactory.get_calculator(inst_type)
        for sem, subjects in history.items():
            sem_grades = []
            for subj in subjects:
                try:
                    res = calculator.calculate(subj.get('grades', []))
                    subj['final_grade'] = res.average
                    subj['status_dict'] = res.to_dict()
                    logger.info(f"Calculator applied for '{subj.get('name')}': {res.average} ({res.status.name})")
                except Exception as e:
                    logger.error(f"Failed to calculate history grades for {subj.get('name')}: {e}")
                
                grade = subj.get('final_grade')
                if grade is not None:
                    sem_grades.append(grade)
                    total_grades.append(grade)
                    if grade > best_grade:
                        best_grade = grade
                        best_subject = subj.get('name')
            sem_avg = sum(sem_grades)/len(sem_grades) if sem_grades else 0
            if sem_grades:
                semesters_data.append({
                    "semester": sem,
                    "average": round(sem_avg, 2),
                    "count": len(sem_grades)
                })
        general_avg = sum(total_grades)/len(total_grades) if total_grades else 0
        final_data = {
            "general_average": round(general_avg, 2),
            "best_subject": best_subject,
            "best_grade": best_grade,
            "semesters": semesters_data,
            "history_raw": history
        }
        if linked_account:
            try:
                cipher = get_cipher_suite()
                json_str = json.dumps(final_data)
                encrypted_data = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')
                linked_account.history_json = encrypted_data
                linked_account.history_updated_at = datetime.utcnow()
                await g.db_session.commit()
            except Exception as e:
                logger.error(f"Cache encryption failed: {e}")

                                                            
        try:
            cache_key = f"{session.get('user_id')}_{session.get('username')}_{session.get('sigaa_inst')}_profile"
            await cache_set('profile', cache_key, final_data)
            logger.info("Redis cache set for academic profile")
        except Exception as e:
            logger.error(f"Redis cache set failed: {e}")

        return jsonify(final_data)
    except SigaaQuestionnaire as e:
        logger.warning(f"Profile error - questionnaire: {e}")
        return jsonify({"error": QUESTIONNAIRE_MESSAGE, "is_questionnaire": True}), 403
    except SigaaSessionExpired:
        _clear_sigaa_session()
        return jsonify({"error": "Session expired", "session_expired": True}), 401
    except Exception as e:
        logger.error(f"Profile error: {e}")
        return jsonify({"error": "Failed to fetch profile"}), 500


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
                msg['data'] = {
                    "grades": raw,
                    "status": res.to_dict()
                }
            await asyncio.sleep(0.1)
            yield json.dumps(msg) + "\n"
        yield json.dumps({"type": "sync_end"}) + "\n"

    return Response(generate(), mimetype='application/x-ndjson')


@bp.route('/api/update_course/<int:course_id>', methods=['POST'])
async def update_course(course_id):
    gateway = await _get_gateway()
    if gateway is None:
        return Response(json.dumps({"error": "Unauthorized", "session_expired": True}), status=401, mimetype='application/json')
    inst_type = _inst_type()

    try:
        async with gateway.scope():
            _, listing = await _enumerate_courses(gateway)
            target = next((item for item in listing if item['id'] == course_id), None)
            if not target:
                return Response(json.dumps({"error": "Course not found"}), status=404, mimetype='application/json')
            details = await gateway.get_course_details(target['bond_id'], target['course_id'])
        _save_gateway(gateway)

        raw_grades = details.get("grades") or []
        freq_data = details.get("frequency")
        calculator = CalculatorFactory.get_calculator(inst_type)
        course_result = calculator.calculate(raw_grades)
        response_data = {
            "id": course_id,
            "data": {
                "grades": raw_grades,
                "status": course_result.to_dict()
            }
        }
        if freq_data:
            response_data['frequency'] = freq_data
        return Response(json.dumps(response_data), mimetype='application/json')
    except SigaaQuestionnaire as e:
        logger.warning(f"Single update error - questionnaire: {e}")
        return Response(json.dumps({"error": QUESTIONNAIRE_MESSAGE, "is_questionnaire": True}), status=403, mimetype='application/json')
    except SigaaSessionExpired:
        _clear_sigaa_session()
        return Response(json.dumps({"error": "Session expired", "session_expired": True}), status=401, mimetype='application/json')
    except Exception as e:
        logger.error(f"Single update error: {e}")
        return Response(json.dumps({"error": "Internal Server Error"}), status=500, mimetype='application/json')


@bp.route('/api/stream_grades')
async def stream_grades():
                                                             
    if not session.get('sigaa_state'):
        return Response(json.dumps({"error": "Unauthorized", "session_expired": True}) + "\n", status=401, mimetype='application/x-ndjson')

    retry_after = _rate_limited(_data_limiter, f"stream:{_client_ip()}")
    if retry_after:
        return Response(
            json.dumps({
                "error": "Muitas requisições. Aguarde alguns segundos.",
                "retry_after": int(retry_after) + 1,
            }) + "\n",
            status=429,
            mimetype='application/x-ndjson',
        )

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
                    logger.warning(f"Failed to load cached history: {e}")
        else:
            logger.warning("active_account_id existe na sessão mas não no banco.")

    gateway = await _get_gateway()
    if gateway is None:
        return Response(json.dumps({"error": "Unauthorized", "session_expired": True}) + "\n", status=401, mimetype='application/x-ndjson')

    async def get_supporters_task():
        try:
            async with aiohttp.ClientSession() as http_client_session:
                async with http_client_session.get(SUPPORTERS_URL, timeout=3) as resp:
                    if resp.status == 200: return await resp.json(content_type=None)
        except: pass
        return []

    async def async_generate():
        if cached_profile:
            yield json.dumps({"type": "profile_data", "data": cached_profile}) + "\n"
            logger.info("SIGAA: Emitted cached history_json for instant UI rendering.")

        try:
            async with gateway.scope():
                bonds = _active_student_bonds(await gateway.get_bonds())

                                                           
                supporters = await get_supporters_task()
                registration = bonds[0].get('registration') if bonds else None
                is_supporter = bool(registration and str(registration) in {str(s) for s in supporters})

                yield json.dumps({"type": "user_info", "name": student_name, "is_supporter": is_supporter}) + "\n"

                if bonds:
                    calculator = CalculatorFactory.get_calculator(inst_type)
                    _, listing = await _enumerate_courses(gateway, bonds)

                    yield json.dumps({"type": "sync_start", "total_courses": len(listing)}) + "\n"

                                             
                    for item in listing:
                        yield json.dumps({"type": "course_start", "id": item['id'], "name": item['title'], "obs": item['program']}) + "\n"

                                                 
                    for bond in bonds:
                        bond_id = bond['bond_id']
                        bond_courses = [item for item in listing if item['bond_id'] == bond_id]
                        for item in bond_courses:
                            course_id = item['id']

                            if course_id in skip_ids:
                                yield json.dumps({"type": "course_skipped", "id": course_id}) + "\n"
                                continue

                            yield json.dumps({"type": "course_loading", "id": course_id, "step": "notas"}) + "\n"

                            try:
                                details = await gateway.get_course_details(bond_id, item['course_id'])
                                raw_grades = details.get("grades") or []
                                freq_data = details.get("frequency")
                                course_result = calculator.calculate(raw_grades)
                                result_data = {
                                    "grades": raw_grades,
                                    "status": course_result.to_dict(),
                                    "professor": details.get("professor")
                                }
                                yield json.dumps({"type": "course_data", "id": course_id, "data": result_data}) + "\n"

                                yield json.dumps({"type": "course_loading", "id": course_id, "step": "frequencia"}) + "\n"
                                if freq_data:
                                    yield json.dumps({"type": "course_frequency", "id": course_id, "data": freq_data}) + "\n"
                            except Exception:
                                empty_result = calculator.calculate([])
                                fallback_data = {
                                    "grades": [],
                                    "status": empty_result.to_dict()
                                }
                                yield json.dumps({"type": "course_data", "id": course_id, "data": fallback_data}) + "\n"

                            yield json.dumps({"type": "course_loading", "id": course_id, "step": "done"}) + "\n"

                        try:
                            c_hist = cached_profile.get('history_raw', {}) if cached_profile else None
                            start_time = time.time()
                            history = await gateway.get_history(bond_id, cached_history=c_hist)
                            duration = time.time() - start_time
                            logger.info(f"Historical data fetch took {duration:.2f}s")
                        except Exception as e:
                            logger.error(f"Error fetching history: {sanitize_for_log(e)}")
                            history = {}

                                                                                
                        for sem, subjects in history.items():
                            unique_subjects = []
                            seen_names = set()
                            for subj in subjects:
                                if subj['name'] in seen_names:
                                    continue
                                seen_names.add(subj['name'])
                                try:
                                    res = calculator.calculate(subj.get('grades', []))
                                    subj['final_grade'] = res.average
                                    subj['status_dict'] = res.to_dict()
                                    logger.info(f"Calculator applied for '{subj.get('name')}': {res.average} ({res.status.name})")
                                except Exception as e:
                                    logger.error(f"Failed to calculate history grades for {subj.get('name')}: {e}")
                                unique_subjects.append(subj)
                            history[sem] = unique_subjects

                        total_grades = []
                        best_grade = 0
                        best_subject = "-"
                        semesters_data = []
                        for sem, subjects in history.items():
                            sem_grades = []
                            for subj in subjects:
                                grade = subj.get('final_grade')
                                if grade is not None:
                                    sem_grades.append(grade)
                                    total_grades.append(grade)
                                    if grade > best_grade:
                                        best_grade = grade
                                        best_subject = subj.get('name')
                            sem_avg = sum(sem_grades)/len(sem_grades) if sem_grades else 0
                            if sem_grades:
                                semesters_data.append({
                                    "semester": sem,
                                    "average": round(sem_avg, 2),
                                    "count": len(sem_grades)
                                })
                        general_avg = sum(total_grades)/len(total_grades) if total_grades else 0
                        profile_data = {
                            "general_average": round(general_avg, 2),
                            "best_subject": best_subject,
                            "best_grade": best_grade,
                            "semesters": semesters_data,
                            "history_raw": history
                        }
                        profile_data = _scrub_active_semester_from_cache(profile_data)
                        if has_linked_account and active_account_id:
                            try:
                                cipher = get_cipher_suite()
                                json_str = json.dumps(profile_data)
                                encrypted_data = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')

                                async with db_session() as s:
                                    db_account = await s.get(LinkedAccount, active_account_id)
                                    if db_account:
                                        db_account.history_json = encrypted_data
                                        db_account.history_updated_at = datetime.utcnow()
                                        await s.commit()
                                        logger.info("Successfully persisted history_json in stream_grades")
                            except Exception as e:
                                logger.error(f"Failed to cache history in stream_grades: {e}")

                        yield json.dumps({"type": "profile_data", "data": profile_data}) + "\n"

                                                                            
                                                                 
                yield json.dumps({"type": "sync_end"}) + "\n"
        except SigaaQuestionnaire as e:
            logger.warning(f"Stream blocked by questionnaire: {e}")
            yield json.dumps({"error": QUESTIONNAIRE_MESSAGE, "is_questionnaire": True}) + "\n"
        except SigaaSessionExpired:
            logger.info("Stream interrompido: sessão do SIGAA expirada.")
            yield json.dumps({"error": "Session expired", "session_expired": True}) + "\n"
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Stream error: {err_msg}")
            if "Session expired" in err_msg:
                yield json.dumps({"error": "Session expired", "session_expired": True}) + "\n"
            else:
                yield json.dumps({"error": "Erro no carregamento dos dados."}) + "\n"

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

                                            
    users_with_accounts = await g.db_session.scalar(
        select(func.count(distinct(LinkedAccount.user_id)))
    )

                                                      
    active_percentage = round((users_with_accounts / total_users * 100) if total_users > 0 else 0, 1)

                                                                                   
    avg_accounts = round((total_linked_accounts / users_with_accounts) if users_with_accounts > 0 else 0, 1)

                          
    result = await g.db_session.execute(
        select(LinkedAccount.institution, func.count(LinkedAccount.id))
        .group_by(LinkedAccount.institution)
    )
    inst_counts = result.all()

    stats = {
        'total_users': total_users,
        'total_linked_accounts': total_linked_accounts,
        'users_with_accounts': users_with_accounts,
        'active_percentage': active_percentage,
        'avg_accounts': avg_accounts,
        'institutions': dict(inst_counts)
    }

                                                                   
    result2 = await g.db_session.execute(select(User).order_by(User.id.desc()))
    all_users = result2.scalars().all()
    user_list = []
    for u in all_users:
        accounts = []
        for acc in u.linked_accounts:
                                                                           
            masked_username = acc.username[:3] + "***" + acc.username[-2:] if len(acc.username) > 5 else "***"
            accounts.append({
                'institution': acc.institution,
                'username_masked': masked_username,
                'history_updated': acc.history_updated_at.strftime('%d/%m/%Y %H:%M') if acc.history_updated_at else 'Nunca'
            })

        user_list.append({
            'id': u.id,
            'name': u.name if u.name else 'Usuário Anônimo',
            'accounts': accounts
        })

    return await render_template('admin.html', user=user, stats=stats, user_list=user_list)

                                                                      
@bp.route('/api/matricula/status')
async def api_matricula_status():
    if not session.get('sigaa_state'):
        return jsonify({"error": "Unauthorized", "session_expired": True}), 401

    is_dev = is_dev_emulation()
    
    if is_dev:
                        
        try:
            from .sigaa_api.enrollment_parser import parse_enrollment_page
            ufal_dir = os.path.join(
                os.path.dirname(__file__), "sigaa_api", "paginas_sigaa", "UFAL"
            )
            with open(os.path.join(ufal_dir, "matricula", "selecao_turmas.html"), "r", encoding="utf-8") as f:
                selecao_body = f.read()
                
            levels = parse_enrollment_page(selecao_body)
                             
            session['mock_view_state'] = 'mock_view_state_123'
            return jsonify({
                "is_dev": True,
                "levels": levels,
                "view_state": 'mock_view_state_123',
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error loading mock matricula: {sanitize_for_log(e)}")
            return jsonify({"error": "Erro na emulação."}), 500
            
    else:
                         
        gateway = await _get_gateway()
        if gateway is None:
            return jsonify({"error": "Unauthorized", "session_expired": True}), 401

        try:
            async with gateway.scope():
                bonds = _active_student_bonds(await gateway.get_bonds())
                if not bonds:
                    return jsonify({"error": "No active bonds"}), 404
                bond_id = bonds[0]['bond_id']
                result = await gateway.get_enrollment(bond_id)
                                                                    
                                                                      
            session['sigaa_enrollment_bond'] = bond_id
            _save_gateway(gateway)
            return jsonify({
                "is_dev": False,
                "levels": result.get("levels"),
                "view_state": result.get("view_state"),
                "status": "success"
            })
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return jsonify({"error": "Session expired", "session_expired": True}), 401
        except SigaaQuestionnaire:
            return jsonify({"error": QUESTIONNAIRE_MESSAGE, "is_questionnaire": True}), 403
        except Exception as e:
            logger.error(f"Error loading live matricula: {sanitize_for_log(e)}")
            return jsonify({"error": "Erro ao acessar o SIGAA. Tente novamente."}), 500


@bp.route('/api/matricula/submit', methods=['POST'])
async def api_matricula_submit():
    if not session.get('sigaa_state'):
        return jsonify({"error": "Unauthorized", "session_expired": True}), 401

    is_dev = is_dev_emulation()
    data = (await request.get_json()) or {}
    selected_class_ids = data.get('selected_class_ids', [])

    if not selected_class_ids:
        return jsonify({"error": "Nenhuma turma selecionada"}), 400

    if is_dev:
                        
        try:
                                     
            tests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
            confirm_path = os.path.join(tests_dir, "confirm_page_debug.html")
            
            with open(confirm_path, "r", encoding="utf-8") as f:
                confirm_body = f.read()
                
            session['mock_confirm_page_body'] = confirm_body
            session['mock_confirm_view_state'] = 'mock_confirm_view_state_456'
            
            return jsonify({
                "is_dev": True,
                "html": confirm_body,
                "view_state": 'mock_confirm_view_state_456',
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error submitting mock matricula: {sanitize_for_log(e)}")
            return jsonify({"error": "Erro na emulação."}), 500
    else:
                         
        gateway = await _get_gateway()
        bond_id = session.get('sigaa_enrollment_bond')
        if gateway is None:
            return jsonify({"error": "Unauthorized", "session_expired": True}), 401
        if not bond_id:
            return jsonify({"error": "Consulte as turmas disponíveis antes de submeter."}), 409

        try:
            res = await gateway.submit_enrollment(bond_id, selected_class_ids)
            _save_gateway(gateway)
            return jsonify({
                "is_dev": False,
                "html": res.get("html"),
                "view_state": res.get("view_state"),
                "status": "success"
            })
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return jsonify({"error": "Session expired", "session_expired": True}), 401
        except Exception as e:
            logger.error(f"Error submitting live matricula: {sanitize_for_log(e)}")
            return jsonify({"error": "Erro ao submeter a matrícula ao SIGAA."}), 500


@bp.route('/api/matricula/confirm', methods=['POST'])
async def api_matricula_confirm():
    if not session.get('sigaa_state'):
        return jsonify({"error": "Unauthorized", "session_expired": True}), 401

    is_dev = is_dev_emulation()
    data = (await request.get_json()) or {}
    password = data.get('password')
    
    if not password and not is_dev:
        return jsonify({"error": "Senha é obrigatória para confirmação"}), 400

    if is_dev:
                        
        if password == "erro":
            return jsonify({
                "status": "error",
                "message": "Senha incorreta ou erro de pré-requisitos no SIGAA."
            }), 400
        else:
            return jsonify({
                "status": "success",
                "message": "Matrícula realizada com sucesso! (Emulado)"
            })
    else:
                         
        gateway = await _get_gateway()
        bond_id = session.get('sigaa_enrollment_bond')
        if gateway is None:
            return jsonify({"error": "Unauthorized", "session_expired": True}), 401
        if not bond_id:
            return jsonify({"error": "Sessão inválida ou expirada"}), 400

        try:
            res = await gateway.confirm_enrollment(bond_id, password)
            _save_gateway(gateway)
            html = res.get("html") or ""
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            
            res_body_lower = html.lower()
            if soup.find('input', type='password') or "senha incorreta" in res_body_lower or "senha de confirmação inválida" in res_body_lower or "inválida" in res_body_lower:
                error_elements = soup.find_all(class_='erros')
                msg = ""
                if error_elements:
                    msg = "; ".join([err.get_text(strip=True) for err in error_elements])
                else:
                    msg = "Senha incorreta ou erro de confirmação no SIGAA."
                return jsonify({"status": "error", "message": msg}), 400
                
            return jsonify({
                "status": "success",
                "message": "Matrícula gravada com sucesso no SIGAA!"
            })
        except SigaaSessionExpired:
            _clear_sigaa_session()
            return jsonify({"error": "Session expired", "session_expired": True}), 401
        except Exception as e:
            logger.error(f"Error finalizing live matricula: {sanitize_for_log(e)}")
            return jsonify({"error": "Erro ao confirmar a matrícula no SIGAA."}), 500

@bp.route('/api/reviews/pending', methods=['GET'])
async def pending_reviews():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return jsonify({"error": "Unauthorized"}), 401

    if not linked_account or not linked_account.history_json:
        return jsonify({"courses": [], "professors": []}), 200

    user_id = linked_account.user_id

    try:
        cipher = get_cipher_suite()
        decrypted = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
        cached_profile = json.loads(decrypted)
        history_raw = cached_profile.get('history_raw', {})
    except Exception as e:
        logger.error(f"Error parsing history for reviews: {sanitize_for_log(e)}")
        return jsonify({"courses": [], "professors": []}), 200

    past_courses = set()
    past_professors = set()

                                                     
    for sem, classes in history_raw.items():
        for cls in classes:
            status = cls.get('status', '')
                                                                                              
            if status not in ['Matriculado', 'Cursando', 'Indefinido']:
                c_name = cls.get('name')
                p_name = cls.get('professor')
                
                if c_name:
                    past_courses.add(c_name)
                if p_name and p_name.strip() and p_name.strip().upper() != "DESCONHECIDO":
                    past_professors.add(p_name.strip().upper())

                                                         
    institution = linked_account.institution

    result_c = await g.db_session.execute(select(CourseReview).filter_by(user_id=user_id, institution=institution))
    existing_c_reviews = result_c.scalars().all()
    reviewed_courses = {r.name for r in existing_c_reviews}
    
    result_p = await g.db_session.execute(select(ProfessorReview).filter_by(user_id=user_id, institution=institution))
    existing_p_reviews = result_p.scalars().all()
    reviewed_professors = {r.name for r in existing_p_reviews}

    pending_courses = list(past_courses - reviewed_courses)
    pending_professors = list(past_professors - reviewed_professors)

    return jsonify({
        "courses": pending_courses,
        "professors": pending_professors
    })

@bp.route('/api/reviews/submit', methods=['POST'])
async def submit_reviews():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return jsonify({"error": "Unauthorized"}), 401

    if not linked_account:
        return jsonify({"error": "No linked account"}), 400

    user_id = linked_account.user_id

    data = await request.get_json()
    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    institution = linked_account.institution
    
                                                                                                        
    courses_data = data.get('courses', [])
    professors_data = data.get('professors', [])

    if not isinstance(courses_data, list) or not isinstance(professors_data, list):
        return jsonify({"error": "Invalid payload"}), 400
    if len(courses_data) + len(professors_data) > _MAX_REVIEWS_PER_REQUEST:
        return jsonify({"error": "Too many reviews in a single request"}), 400

    try:
        for c in courses_data:
            if not isinstance(c, dict):
                continue
            name = _parse_review_name(c.get('name'))
            if not name:
                continue
            ok, rating = _parse_rating(c.get('rating'))
            if not ok:
                return jsonify({"error": "Nota inválida: use um valor entre 1 e 5."}), 400
            declined = bool(c.get('declined', False))

            result = await g.db_session.execute(select(CourseReview).filter_by(user_id=user_id, institution=institution, name=name))
            review = result.scalars().first()
            if not review:
                review = CourseReview(user_id=user_id, institution=institution, name=name)
                g.db_session.add(review)
            review.difficulty_rating = rating
            review.is_declined = declined

        for p in professors_data:
            if not isinstance(p, dict):
                continue
            name = _parse_review_name(p.get('name'))
            if not name:
                continue
            name = name.upper()
            ok, rating = _parse_rating(p.get('rating'))
            if not ok:
                return jsonify({"error": "Nota inválida: use um valor entre 1 e 5."}), 400
            declined = bool(p.get('declined', False))

            result = await g.db_session.execute(select(ProfessorReview).filter_by(user_id=user_id, institution=institution, name=name))
            review = result.scalars().first()
            if not review:
                review = ProfessorReview(user_id=user_id, institution=institution, name=name)
                g.db_session.add(review)
            review.difficulty_rating = rating
            review.is_declined = declined

        await g.db_session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        await g.db_session.rollback()
        logger.error(f"Failed to submit reviews: {e}")
        return jsonify({"error": "Database error"}), 500

@bp.route('/api/reviews/stats', methods=['GET'])
async def get_review_stats():
                                                                
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = await g.db_session.get(LinkedAccount, active_account_id)
    elif user_id:
        result = await g.db_session.execute(select(LinkedAccount).filter_by(user_id=user_id))
        linked_account = result.scalars().first()
    else:
        return jsonify({"error": "Unauthorized"}), 401

    if not linked_account:
        return jsonify({"error": "No linked account"}), 400
        
    course_name = request.args.get('course')
    professor_name = request.args.get('professor')
    institution = linked_account.institution

    stats = {}

    if course_name:
        result = await g.db_session.execute(
            select(CourseReview).filter(
                CourseReview.institution == institution,
                CourseReview.name == course_name,
                CourseReview.is_declined == False,
                CourseReview.difficulty_rating != None
            )
        )
        reviews = result.scalars().all()
        
        if reviews:
            avg = sum(r.difficulty_rating for r in reviews) / len(reviews)
            stats['course'] = {"average": round(avg, 1), "count": len(reviews)}
        else:
            stats['course'] = None

    if professor_name:
        professor_name = professor_name.strip().upper()
        result = await g.db_session.execute(
            select(ProfessorReview).filter(
                ProfessorReview.institution == institution,
                ProfessorReview.name == professor_name,
                ProfessorReview.is_declined == False,
                ProfessorReview.difficulty_rating != None
            )
        )
        reviews = result.scalars().all()
        
        if reviews:
            avg = sum(r.difficulty_rating for r in reviews) / len(reviews)
            stats['professor'] = {"average": round(avg, 1), "count": len(reviews)}
        else:
            stats['professor'] = None

    return jsonify(stats)


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
            
                                                                
        result = await s.execute(select(User).filter_by(email="anonimo@boletimapp.com"))
        anon_user = result.scalars().first()
        if not anon_user:
            anon_user = User(
                google_id="anonymous_virtual_account",
                email="anonimo@boletimapp.com",
                name="Anônimo",
                profile_pic=None
            )
            s.add(anon_user)
            await s.flush()
            
                                              
        result_cr = await s.execute(select(CourseReview).filter_by(user_id=user_id))
        for cr in result_cr.scalars().all():
            cr.user_id = anon_user.id
            
                                                 
        result_pr = await s.execute(select(ProfessorReview).filter_by(user_id=user_id))
        for pr in result_pr.scalars().all():
            pr.user_id = anon_user.id
            
                                                                            
        await s.delete(user)
        await s.commit()
        
    session.clear()
    return redirect(url_for('main.login'))
