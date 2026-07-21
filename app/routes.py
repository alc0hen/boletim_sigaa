from flask import Blueprint, render_template, request, redirect, url_for, session, Response, stream_with_context, current_app, flash, jsonify
from .sigaa_api.sigaa import Sigaa, InstitutionType
from .domain.factory import CalculatorFactory
from .demo_data import get_demo_data
from .extensions import db, oauth
from .models import User, LinkedAccount, CourseReview, ProfessorReview, get_cipher_suite
from .sigaa_api.exceptions import SigaaQuestionnaireError
import asyncio
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
SIGAA_URL = "https://sigaa.ifal.edu.br"
SUPPORTERS_URL = "https://raw.githubusercontent.com/AlbertCohenhgs/public_lists/refs/heads/main/apoiadores.json"
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def run_async(coro):
    """Run an async coroutine synchronously in a new event loop. Gevent-safe."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    except Exception as e:
        # Ensure the coroutine is closed to avoid "never awaited" warnings
        if hasattr(coro, 'close'):
            coro.close()
        raise e
    finally:
        try:
            loop.close()
        except:
            pass
        asyncio.set_event_loop(None)
@bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        institution_str = request.form.get('institution', 'IFAL')
        if institution_str == 'UFAL':
            inst_type = InstitutionType.UFAL
            url = "https://sigaa.sig.ufal.br"
        elif institution_str == 'UFPE':
            inst_type = InstitutionType.UFPE
            url = "https://sigaa.ufpe.br"
        else:
            inst_type = InstitutionType.IFAL
            url = SIGAA_URL
        async def perform_login():
            sigaa = Sigaa(url, inst_type)
            try:
                account = await sigaa.login(username, password)
                client_session = await sigaa.session._get_session()
                cookies = {}
                for cookie in client_session.cookie_jar:
                    cookies[cookie.key] = cookie.value
                return cookies
            finally:
                await sigaa.close()

        try:
            cookies = run_async(perform_login())
            session['sigaa_cookies'] = cookies
            session['sigaa_url'] = url
            session['sigaa_inst'] = institution_str
            session['username'] = username
            session['sigaa_temp_password'] = password  # Temporarily store password for auto-linking
            try:
                linked_account = LinkedAccount.query.filter_by(
                    username=username,
                    institution=institution_str
                ).first()
                if linked_account:
                    session['active_account_id'] = linked_account.id
            except Exception as e:
                logger.error(f"Error linking session to account: {e}")
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f"Login failed: {type(e).__name__}")
            return render_template('login.html', error="Falha no login. Verifique suas credenciais.")
    return render_template('login.html')
@bp.route('/login/google')
def login_google():
    redirect_uri = url_for('main.authorize_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)
@bp.route('/login/google/callback')
def authorize_google():
    try:
        token = oauth.google.authorize_access_token()
        user_info = oauth.google.userinfo()
        if not user_info:
             return "Falha na autenticação Google (sem info)", 400
    except Exception as e:
        logger.error(f"Google Auth Error: {e}")
        return redirect(url_for('main.login'))
    user = User.query.filter_by(google_id=user_info['sub']).first()
    if not user:
        user = User(
            google_id=user_info['sub'],
            email=user_info['email'],
            name=user_info.get('name'),
            profile_pic=user_info.get('picture')
        )
        db.session.add(user)
    else:
        user.name = user_info.get('name')
        user.profile_pic = user_info.get('picture')
    db.session.commit()
    session['user_id'] = user.id

    # Auto-link direct login session account to the Google user
    temp_pass = session.get('sigaa_temp_password')
    temp_user = session.get('username')
    temp_inst = session.get('sigaa_inst')
    if temp_pass and temp_user and temp_inst:
        existing = LinkedAccount.query.filter_by(
            user_id=user.id,
            institution=temp_inst,
            username=temp_user
        ).first()
        if not existing:
            try:
                new_account = LinkedAccount(
                    user_id=user.id,
                    institution=temp_inst,
                    username=temp_user
                )
                new_account.set_password(temp_pass)
                db.session.add(new_account)
                db.session.commit()
                session['active_account_id'] = new_account.id
                logger.info(f"Auto-linked SIGAA account {temp_user} ({temp_inst}) to Google user {user.email}")
            except Exception as e:
                logger.error(f"Error auto-linking account: {e}")
                db.session.rollback()
        else:
            session['active_account_id'] = existing.id
        session.pop('sigaa_temp_password', None)

    if user.linked_accounts and 'active_account_id' not in session:
        session['active_account_id'] = user.linked_accounts[0].id
    return redirect(url_for('main.dashboard'))
@bp.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('main.login'))
    return render_template('profile.html', user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
@bp.route('/link_account', methods=['POST'])
def link_account():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    institution_str = request.form.get('institution')
    username = request.form.get('username')
    password = request.form.get('password')
    if not all([institution_str, username, password]):
        user = User.query.get(session['user_id'])
        return render_template('profile.html', error="Preencha todos os campos.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
    if institution_str == 'UFAL':
        inst_type = InstitutionType.UFAL
        url = "https://sigaa.sig.ufal.br"
    elif institution_str == 'UFPE':
        inst_type = InstitutionType.UFPE
        url = "https://sigaa.ufpe.br"
    else:
        inst_type = InstitutionType.IFAL
        url = SIGAA_URL
    async def perform_link():
        sigaa = Sigaa(url, inst_type)
        try:
            await sigaa.login(username, password)
            client_session = await sigaa.session._get_session()
            cookies = {}
            for cookie in client_session.cookie_jar:
                cookies[cookie.key] = cookie.value
            return cookies
        finally:
            await sigaa.close()

    try:
        cookies = run_async(perform_link())
        new_account = LinkedAccount(
            user_id=session['user_id'],
            institution=institution_str,
            username=username
        )
        new_account.set_password(password)
        db.session.add(new_account)
        db.session.commit()
        session['active_account_id'] = new_account.id
        session['sigaa_url'] = url
        session['sigaa_inst'] = institution_str
        session['username'] = username
        session['sigaa_cookies'] = cookies
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.error(f"Link Account Failed: {e}")
        user = User.query.get(session['user_id'])
        return render_template('profile.html', error="Falha ao vincular: Credenciais inválidas.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
@bp.route('/unlink_account/<int:id>', methods=['POST'])
def unlink_account(id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    account = LinkedAccount.query.get(id)
    if account and account.user_id == session['user_id']:
        db.session.delete(account)
        db.session.commit()
        if session.get('active_account_id') == id:
            session.pop('active_account_id', None)
            session.pop('sigaa_cookies', None)
            user = User.query.get(session['user_id'])
            if user.linked_accounts:
                session['active_account_id'] = user.linked_accounts[0].id
    return redirect(url_for('main.profile'))
@bp.route('/activate_account/<int:id>', methods=['POST'])
def activate_account(id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    account = LinkedAccount.query.get(id)
    if account and account.user_id == session['user_id']:
        session['active_account_id'] = account.id
        session.pop('sigaa_cookies', None)
    return redirect(url_for('main.dashboard'))
@bp.route('/dashboard')
def dashboard():
    if 'user_id' in session and not session.get('sigaa_cookies'):
        active_id = session.get('active_account_id')
        if not active_id:
            user = User.query.get(session['user_id'])
            if user and user.linked_accounts:
                active_id = user.linked_accounts[0].id
                session['active_account_id'] = active_id
            else:
                return redirect(url_for('main.profile'))
        account = LinkedAccount.query.get(active_id)
        if not account:
            session.pop('active_account_id', None)
            return redirect(url_for('main.profile'))
        password = account.get_password()
        if not password:
            return redirect(url_for('main.profile'))
        if account.institution == 'UFAL':
            inst_type = InstitutionType.UFAL
            url = "https://sigaa.sig.ufal.br"
        elif account.institution == 'UFPE':
            inst_type = InstitutionType.UFPE
            url = "https://sigaa.ufpe.br"
        else:
            inst_type = InstitutionType.IFAL
            url = SIGAA_URL
        async def perform_auto_login():
            sigaa = Sigaa(url, inst_type)
            try:
                await sigaa.login(account.username, password)
                client_session = await sigaa.session._get_session()
                cookies = {}
                for cookie in client_session.cookie_jar:
                    cookies[cookie.key] = cookie.value
                return cookies
            finally:
                await sigaa.close()

        try:
            cookies = run_async(perform_auto_login())
            session['sigaa_cookies'] = cookies
            session['sigaa_url'] = url
            session['sigaa_inst'] = account.institution
            session['username'] = account.username
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f"Auto-login failed for {account.username}: {e}")
            return redirect(url_for('main.profile'))
    cookies = session.get('sigaa_cookies')
    if not cookies:
        if 'user_id' in session:
             return redirect(url_for('main.profile'))
        return redirect(url_for('main.login'))
    user = None
    linked_accounts = []
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            linked_accounts = user.linked_accounts
    return render_template('dashboard.html', user=user, linked_accounts=linked_accounts, active_account_id=session.get('active_account_id'))
@bp.route('/api/academic_profile')
async def academic_profile():
    cookies = session.get('sigaa_cookies')
    
    # Rate limiting / Smart delay against brute-force reloads
    last_req = session.get('last_academic_req', 0)
    now = time.time()
    if now - last_req < 5:
        time.sleep(5 - (now - last_req))
    session['last_academic_req'] = time.time()

    if not cookies:
        return jsonify({"error": "Unauthorized"}), 401
    force_update = request.args.get('force') == 'true'
    active_account_id = session.get('active_account_id')
    linked_account = None
    if active_account_id:
        linked_account = LinkedAccount.query.get(active_account_id)
    # Redis cache fallback
    cache_key = f"{session.get('user_id')}_{session.get('sigaa_inst')}_profile"
    if not force_update:
        cached = cache_get('history', cache_key)
        if cached:
            logger.info("Redis cache hit for academic profile")
            return jsonify(cached)
    # Existing DB cache check
    if linked_account and not force_update and linked_account.history_json and linked_account.history_updated_at:
        if datetime.utcnow() - linked_account.history_updated_at < timedelta(days=3):
            try:
                cipher = get_cipher_suite()
                decrypted_json = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
                cached_data = json.loads(decrypted_json)
                return jsonify(cached_data)
            except Exception as e:
                logger.error(f"Cache decryption failed: {e}")
                pass
    url = session.get('sigaa_url', SIGAA_URL)
    inst_str = session.get('sigaa_inst', 'IFAL')
    try:
        inst_type = InstitutionType[inst_str]
    except KeyError:
        inst_type = InstitutionType.IFAL
    async def fetch_academic_profile():
        sigaa = Sigaa(url, inst_type, cookies=cookies)
        try:
            response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
            if "login" in response.url.path:
                 return {"error": "Session expired", "status": 401}
            from .sigaa_api.account import Account
            account = Account(sigaa.session, response)
            if not account.active_bonds:
                return {"error": "No active bonds", "status": 404}
            bond = account.active_bonds[0]
            history = await bond.get_history()
            return {"history": history, "status": 200}
        finally:
            await sigaa.close()

    try:
        start_time = time.time()
        res = await fetch_academic_profile()
        duration = time.time() - start_time
        logger.info(f"Historical data fetch took {duration:.2f}s")
        if res["status"] != 200:
            return jsonify({"error": res["error"]}), res["status"]
            
        history = res["history"]
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
                db.session.commit()
            except Exception as e:
                logger.error(f"Cache encryption failed: {e}")

        # Redis cache store
        try:
            cache_key = f"{session.get('user_id')}_{session.get('sigaa_inst')}_profile"
            cache_set('history', cache_key, final_data, ttl=30)
            logger.info("Redis cache set for academic profile")
        except Exception as e:
            logger.error(f"Redis cache set failed: {e}")

        return jsonify(final_data)
    except SigaaQuestionnaireError as e:
        logger.warning(f"Profile error - questionnaire: {e}")
        return jsonify({"error": "Questionário de Avaliação PENDENTE bloqueia o acesso aos dados. Acesse o SIGAA para respondê-lo e tente novamente.", "is_questionnaire": True}), 403
    except Exception as e:
        logger.error(f"Profile error: {e}")
        return jsonify({"error": "Failed to fetch profile"}), 500
@bp.route('/apoio')
def support():
    return render_template('support.html')
@bp.route('/privacy')
def privacy():
    return render_template('privacy.html')
@bp.route('/demo')
def demo():
    return render_template('dashboard.html')
@bp.route('/api/stream_demo')
def stream_demo():
    def generate():
        time.sleep(0.5)
        calculator = CalculatorFactory.get_calculator(InstitutionType.IFAL)
        for msg in get_demo_data():
            if msg['type'] == 'course_data':
                raw = msg['data']
                res = calculator.calculate(raw)
                msg['data'] = {
                    "grades": raw,
                    "status": res.to_dict()
                }
            time.sleep(0.1)
            yield json.dumps(msg) + "\n"
        yield json.dumps({"type": "sync_end"}) + "\n"
    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')
@bp.route('/api/update_course/<int:course_id>', methods=['POST'])
def update_course(course_id):
    cookies = session.get('sigaa_cookies')
    if not cookies: return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype='application/json')
    url = session.get('sigaa_url', SIGAA_URL)
    inst_str = session.get('sigaa_inst', 'IFAL')
    try: inst_type = InstitutionType[inst_str]
    except KeyError: inst_type = InstitutionType.IFAL
    async def perform_update():
        sigaa = Sigaa(url, inst_type, cookies=cookies)
        try:
            response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
            if "login" in response.url.path: return {"error": "Session expired", "status": 401}
            from .sigaa_api.account import Account
            account = Account(sigaa.session, response)
            target_course = None
            current_id = 0
            if account.active_bonds:
                for bond in account.active_bonds:
                    courses = await bond.get_courses()
                    if courses:
                        for course in courses:
                            current_id += 1
                            if current_id == course_id:
                                target_course = course
                                break
                    if target_course: break
            if not target_course: return {"error": "Course not found", "status": 404}
            
            raw_grades, freq_data = await target_course.get_grades_and_frequency()
            return {"status": 200, "grades": raw_grades, "frequency": freq_data}
        finally:
            await sigaa.close()

    try:
        res = run_async(perform_update())
        if res.get("status") != 200:
            return Response(json.dumps({"error": res.get("error")}), status=res.get("status", 500), mimetype='application/json')
            
        raw_grades = res["grades"]
        freq_data = res.get("frequency")
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
    except SigaaQuestionnaireError as e:
        logger.warning(f"Single update error - questionnaire: {e}")
        return Response(json.dumps({"error": "Questionário de Avaliação PENDENTE bloqueia o acesso aos dados. Acesse o SIGAA para respondê-lo e tente novamente.", "is_questionnaire": True}), status=403, mimetype='application/json')
    except Exception as e:
        logger.error(f"Single update error: {e}")
        return Response(json.dumps({"error": "Internal Server Error"}), status=500, mimetype='application/json')
@bp.route('/api/stream_grades')
def stream_grades():
    cookies = session.get('sigaa_cookies')
    
    # Rate limiting / Smart delay against brute-force reloads
    last_req = session.get('last_stream_req', 0)
    now = time.time()
    if now - last_req < 5:
        time.sleep(5 - (now - last_req))
    session['last_stream_req'] = time.time()

    username = session.get('username', 'anonymous')
    if not cookies: return Response("Unauthorized", status=401)
    priority_ids = [int(x) for x in request.args.get('priority', '').split(',') if x.strip().isdigit()]
    skip_ids = [int(x) for x in request.args.get('skip', '').split(',') if x.strip().isdigit()]
    # Extract all needed context data BEFORE starting the thread
    url = session.get('sigaa_url', SIGAA_URL)
    inst_str = session.get('sigaa_inst', 'IFAL')
    active_account_id = session.get('active_account_id')

    async def async_generate(url, inst_str, active_account_id, cookies, username, priority_ids, skip_ids):
        try: inst_type = InstitutionType[inst_str]
        except KeyError: inst_type = InstitutionType.IFAL
        sigaa = Sigaa(url, inst_type, cookies=cookies)
        # Optimization: Use DB cache if fresh (< 10 min)
        linked_account = None
        acc_id = active_account_id
        if acc_id:
            linked_account = LinkedAccount.query.get(acc_id)
            if linked_account and linked_account.history_json:
                try:
                    from .models import get_cipher_suite
                    cipher = get_cipher_suite()
                    decrypted = cipher.decrypt(linked_account.history_json.encode('utf-8')).decode('utf-8')
                    cached_profile = json.loads(decrypted)
                    yield json.dumps({"type": "profile_data", "data": cached_profile}) + "\n"
                    logger.info("SIGAA: Emitted cached history_json for instant UI rendering.")
                except Exception as e:
                    logger.error(f"Failed to load cached history: {e}")
        
        try:
            response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
            if "login" in response.url.path:
                yield json.dumps({"error": "Session expired"}) + "\n"
                return
            from .sigaa_api.account import Account
            account = Account(sigaa.session, response)
            
            async def get_supporters_task():
                try:
                    async with aiohttp.ClientSession() as http_client_session:
                        async with http_client_session.get(SUPPORTERS_URL, timeout=3) as resp:
                            if resp.status == 200: return await resp.json(content_type=None)
                except: pass
                return []
            
            name = await account.get_name()
            
            # Check for actual supporters in background
            supporters = await get_supporters_task()
            is_supporter = False
            registration = None
            if account.active_bonds: registration = account.active_bonds[0].registration
            if registration and str(registration) in {str(s) for s in supporters}: is_supporter = True

            yield json.dumps({"type": "user_info", "name": name, "is_supporter": is_supporter}) + "\n"

            if account and account.active_bonds:
                calculator = CalculatorFactory.get_calculator(inst_type)
                
                bonds_to_process = []
                total_current_courses = 0
                for bond in account.active_bonds:
                    courses = await bond.get_courses()
                    bonds_to_process.append({'program': bond.program, 'courses': courses, 'bond_obj': bond})
                    if courses:
                        total_current_courses += len(courses)

                yield json.dumps({"type": "sync_start", "total_courses": total_current_courses}) + "\n"

                # Phase 1: Mapping (Fast)
                for b_item in bonds_to_process:
                    courses = b_item['courses']
                    if not courses: continue
                    
                    course_list_with_ids = []
                    for i, course in enumerate(courses):
                        course_list_with_ids.append({'id': i + 1, 'course': course})
                    b_item['_course_list'] = course_list_with_ids # Save for phase 2
                    
                    for item in course_list_with_ids:
                        course_id = item['id']
                        course = item['course']
                        yield json.dumps({"type": "course_start", "id": course_id, "name": course.title, "obs": b_item['program']}) + "\n"

                # Phase 2: Slow Data Fetching
                for b_item in bonds_to_process:
                    bond_obj = b_item.get('bond_obj')
                    course_list_with_ids = b_item.get('_course_list', [])
                    for item in course_list_with_ids:
                        course_id = item['id']
                        course = item['course']

                        if course_id in skip_ids:
                            yield json.dumps({"type": "course_skipped", "id": course_id}) + "\n"
                            continue

                        yield json.dumps({"type": "course_loading", "id": course_id, "step": "notas"}) + "\n"

                        try:
                            raw_grades, freq_data = await course.get_grades_and_frequency()
                            course_result = calculator.calculate(raw_grades)
                            result_data = {
                                "grades": raw_grades,
                                "status": course_result.to_dict()
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
                        if bond_obj:
                            c_hist = cached_profile.get('history_raw', {}) if cached_profile else None
                            start_time = time.time()
                            history = await bond_obj.get_history(cached_history=c_hist)
                            duration = time.time() - start_time
                            logger.info(f"Historical data fetch took {duration:.2f}s")
                        else:
                            history = {}
                    except Exception as e:
                        logger.error(f"Error fetching history: {e}")
                        history = {}

                    # Calculate precise averages using the domain calculator
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
                    if linked_account:
                        try:
                            from .models import get_cipher_suite
                            cipher = get_cipher_suite()
                            json_str = json.dumps(profile_data)
                            encrypted_data = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')
                            linked_account.history_json = encrypted_data
                            linked_account.history_updated_at = datetime.utcnow()
                            db.session.commit()
                            logger.info("Successfully persisted history_json in stream_grades")
                        except Exception as e:
                            logger.error(f"Failed to cache history in stream_grades: {e}")
                            db.session.rollback()

                    yield json.dumps({"type": "profile_data", "data": profile_data}) + "\n"
                
                # Final sync end
                yield json.dumps({"type": "sync_end"}) + "\n"
        except SigaaQuestionnaireError as e:
            logger.warning(f"Stream blocked by questionnaire: {e}")
            yield json.dumps({"error": "Questionário de Avaliação PENDENTE bloqueia o acesso aos dados. Acesse o SIGAA para respondê-lo e tente novamente.", "is_questionnaire": True}) + "\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield json.dumps({"error": "Erro no carregamento dos dados."}) + "\n"
        finally: await sigaa.close()
    def sync_generate():
        import queue
        import threading
        q = queue.Queue()

        def thread_target(app):
            with app.app_context():
                if sys.platform == 'win32':
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def run_it():
                    try:
                        async for val in async_generate(url, inst_str, active_account_id, cookies, username, priority_ids, skip_ids):
                            q.put(val)
                    except Exception as e:
                        logger.error(f"Async thread error: {e}")
                        q.put(json.dumps({"error": "Internal Stream Error"}) + "\n")
                    finally:
                        q.put(None)
                
                try:
                    loop.run_until_complete(run_it())
                finally:
                    loop.close()

        t = threading.Thread(target=thread_target, args=(current_app._get_current_object(),))
        t.start()

        while True:
            item = q.get()
            if item is None:
                break
            yield item
        t.join()
    return Response(stream_with_context(sync_generate()), mimetype='application/x-ndjson')
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@bp.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.dashboard'))

    total_users = User.query.count()
    total_linked_accounts = LinkedAccount.query.count()

    # Users with at least one linked account
    users_with_accounts = db.session.query(LinkedAccount.user_id).distinct().count()

    # Percentage of active users (users with accounts)
    active_percentage = round((users_with_accounts / total_users * 100) if total_users > 0 else 0, 1)

    # Average accounts per user (only counting users who have at least one account)
    avg_accounts = round((total_linked_accounts / users_with_accounts) if users_with_accounts > 0 else 0, 1)

    # Count by institution
    inst_counts = db.session.query(
        LinkedAccount.institution,
        db.func.count(LinkedAccount.id)
    ).group_by(LinkedAccount.institution).all()

    stats = {
        'total_users': total_users,
        'total_linked_accounts': total_linked_accounts,
        'users_with_accounts': users_with_accounts,
        'active_percentage': active_percentage,
        'avg_accounts': avg_accounts,
        'institutions': dict(inst_counts)
    }

    # Fetch all users for the detailed list, masking sensitive data
    all_users = User.query.order_by(User.id.desc()).all()
    user_list = []
    for u in all_users:
        accounts = []
        for acc in u.linked_accounts:
            # Mask username (e.g., show only first 3 and last 2 characters)
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

    return render_template('admin.html', user=user, stats=stats, user_list=user_list)

# ----------------- MATRICULA ONLINE ROUTE ENDPOINTS -----------------
@bp.route('/api/matricula/status')
def api_matricula_status():
    cookies = session.get('sigaa_cookies')
    if not cookies:
        return jsonify({"error": "Unauthorized"}), 401

    is_dev = os.environ.get('IS_DEV', '0') == '1'
    
    if is_dev:
        # Emulation mode
        try:
            from .sigaa_api.enrollment_parser import parse_enrollment_page
            ufal_dir = os.path.join(
                os.path.dirname(__file__), "sigaa_api", "paginas_sigaa", "UFAL"
            )
            with open(os.path.join(ufal_dir, "matricula", "selecao_turmas.html"), "r", encoding="utf-8") as f:
                selecao_body = f.read()
                
            levels = parse_enrollment_page(selecao_body)
            # Save mock state
            session['mock_view_state'] = 'mock_view_state_123'
            return jsonify({
                "is_dev": True,
                "levels": levels,
                "view_state": 'mock_view_state_123',
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error loading mock matricula: {e}")
            return jsonify({"error": f"Erro na emulação: {str(e)}"}), 500
            
    else:
        # Live SIGAA mode
        url = session.get('sigaa_url', SIGAA_URL)
        inst_str = session.get('sigaa_inst', 'IFAL')
        try:
            inst_type = InstitutionType[inst_str]
        except KeyError:
            inst_type = InstitutionType.IFAL

        async def fetch_enrollment():
            sigaa = Sigaa(url, inst_type, cookies=cookies)
            try:
                response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
                if "login" in response.url.path:
                    return {"error": "Session expired", "status": 401}
                from .sigaa_api.account import Account
                account = Account(sigaa.session, response)
                if not account.active_bonds:
                    return {"error": "No active bonds", "status": 404}
                bond = account.active_bonds[0]
                result = await bond.get_enrollment_disciplines()
                return {"result": result, "status": 200}
            finally:
                await sigaa.close()

        try:
            res = run_async(fetch_enrollment())
            if res["status"] != 200:
                return jsonify({"error": res["error"]}), res["status"]
            
            result = res["result"]
            # Save view state in session for submission
            session['sigaa_view_state'] = result["view_state"]
            return jsonify({
                "is_dev": False,
                "levels": result["levels"],
                "view_state": result["view_state"],
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error loading live matricula: {e}")
            return jsonify({"error": f"Erro ao acessar o SIGAA: {str(e)}"}), 500


@bp.route('/api/matricula/submit', methods=['POST'])
def api_matricula_submit():
    cookies = session.get('sigaa_cookies')
    if not cookies:
        return jsonify({"error": "Unauthorized"}), 401

    is_dev = os.environ.get('IS_DEV', '0') == '1'
    data = request.json or {}
    selected_class_ids = data.get('selected_class_ids', [])
    view_state = data.get('view_state') or session.get('sigaa_view_state') or session.get('mock_view_state')
    
    if not selected_class_ids:
        return jsonify({"error": "Nenhuma turma selecionada"}), 400

    if is_dev:
        # Emulation mode
        try:
            # Load debug confirm_page
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
            logger.error(f"Error submitting mock matricula: {e}")
            return jsonify({"error": f"Erro na emulação: {str(e)}"}), 500
    else:
        # Live SIGAA mode
        url = session.get('sigaa_url', SIGAA_URL)
        inst_str = session.get('sigaa_inst', 'IFAL')
        try:
            inst_type = InstitutionType[inst_str]
        except KeyError:
            inst_type = InstitutionType.IFAL

        async def post_enrollment():
            sigaa = Sigaa(url, inst_type, cookies=cookies)
            try:
                response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
                from .sigaa_api.account import Account
                account = Account(sigaa.session, response)
                bond = account.active_bonds[0]
                confirm_page = await bond.submit_enrollment(selected_class_ids, view_state)
                return {
                    "html": confirm_page.body,
                    "view_state": confirm_page.view_state,
                    "status": 200
                }
            finally:
                await sigaa.close()

        try:
            res = run_async(post_enrollment())
            session['sigaa_confirm_view_state'] = res["view_state"]
            session['sigaa_confirm_page_body'] = res["html"]
            return jsonify({
                "is_dev": False,
                "html": res["html"],
                "view_state": res["view_state"],
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error submitting live matricula: {e}")
            return jsonify({"error": f"Erro ao submeter ao SIGAA: {str(e)}"}), 500


@bp.route('/api/matricula/confirm', methods=['POST'])
def api_matricula_confirm():
    cookies = session.get('sigaa_cookies')
    if not cookies:
        return jsonify({"error": "Unauthorized"}), 401

    is_dev = os.environ.get('IS_DEV', '0') == '1'
    data = request.json or {}
    password = data.get('password')
    
    if not password and not is_dev:
        return jsonify({"error": "Senha é obrigatória para confirmação"}), 400

    if is_dev:
        # Emulation mode
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
        # Live SIGAA mode
        url = session.get('sigaa_url', SIGAA_URL)
        inst_str = session.get('sigaa_inst', 'IFAL')
        try:
            inst_type = InstitutionType[inst_str]
        except KeyError:
            inst_type = InstitutionType.IFAL

        confirm_view_state = session.get('sigaa_confirm_view_state')
        confirm_page_body = session.get('sigaa_confirm_page_body')
        
        if not confirm_view_state or not confirm_page_body:
            return jsonify({"error": "Sessão inválida ou expirada"}), 400

        async def finalize_enrollment():
            sigaa = Sigaa(url, inst_type, cookies=cookies)
            try:
                response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
                from .sigaa_api.account import Account
                account = Account(sigaa.session, response)
                bond = account.active_bonds[0]
                
                # 1. Request password page
                password_page = await bond.request_confirmation_page(confirm_view_state)
                
                # 2. Submit password page
                final_res = await bond.confirm_enrollment(password, password_page.view_state, password_page.body)
                return {
                    "html": final_res.body,
                    "status": 200
                }
            finally:
                await sigaa.close()

        try:
            res = run_async(finalize_enrollment())
            html = res["html"]
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
        except Exception as e:
            logger.error(f"Error finalizing live matricula: {e}")
            return jsonify({"error": f"Erro de confirmação: {str(e)}"}), 500

@bp.route('/api/reviews/pending', methods=['GET'])
def pending_reviews():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = LinkedAccount.query.get(active_account_id)
    elif user_id:
        linked_account = LinkedAccount.query.filter_by(user_id=user_id).first()
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
        logger.error(f"Error parsing history for reviews: {e}")
        return jsonify({"courses": [], "professors": []}), 200

    past_courses = set()
    past_professors = set()

    # Extract all courses and professors from history
    for sem, classes in history_raw.items():
        for cls in classes:
            status = cls.get('status', '')
            # Allow evaluation only if the user has essentially completed or failed the course
            if status not in ['Matriculado', 'Cursando', 'Indefinido']:
                c_name = cls.get('name')
                p_name = cls.get('professor')
                
                if c_name:
                    past_courses.add(c_name)
                if p_name and p_name.strip() and p_name.strip().upper() != "DESCONHECIDO":
                    past_professors.add(p_name.strip().upper())

    # Check which ones are already reviewed (or declined)
    institution = linked_account.institution

    existing_c_reviews = CourseReview.query.filter_by(user_id=user_id, institution=institution).all()
    reviewed_courses = {r.name for r in existing_c_reviews}
    
    existing_p_reviews = ProfessorReview.query.filter_by(user_id=user_id, institution=institution).all()
    reviewed_professors = {r.name for r in existing_p_reviews}

    pending_courses = list(past_courses - reviewed_courses)
    pending_professors = list(past_professors - reviewed_professors)

    return jsonify({
        "courses": pending_courses,
        "professors": pending_professors
    })

@bp.route('/api/reviews/submit', methods=['POST'])
def submit_reviews():
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = LinkedAccount.query.get(active_account_id)
    elif user_id:
        linked_account = LinkedAccount.query.filter_by(user_id=user_id).first()
    else:
        return jsonify({"error": "Unauthorized"}), 401

    if not linked_account:
        return jsonify({"error": "No linked account"}), 400

    user_id = linked_account.user_id

    data = request.json
    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    institution = linked_account.institution
    
    # data format: {"courses": [{"name": "...", "rating": 4.0, "declined": false}], "professors": [...]}
    courses_data = data.get('courses', [])
    professors_data = data.get('professors', [])

    try:
        for c in courses_data:
            name = c.get('name')
            rating = c.get('rating')
            declined = c.get('declined', False)
            if not name: continue
            
            review = CourseReview.query.filter_by(user_id=user_id, institution=institution, name=name).first()
            if not review:
                review = CourseReview(user_id=user_id, institution=institution, name=name)
                db.session.add(review)
            review.difficulty_rating = float(rating) if rating is not None else None
            review.is_declined = declined

        for p in professors_data:
            name = p.get('name')
            if name: name = name.strip().upper()
            rating = p.get('rating')
            declined = p.get('declined', False)
            if not name: continue
            
            review = ProfessorReview.query.filter_by(user_id=user_id, institution=institution, name=name).first()
            if not review:
                review = ProfessorReview(user_id=user_id, institution=institution, name=name)
                db.session.add(review)
            review.difficulty_rating = float(rating) if rating is not None else None
            review.is_declined = declined

        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to submit reviews: {e}")
        return jsonify({"error": "Database error"}), 500

@bp.route('/api/reviews/stats', methods=['GET'])
def get_review_stats():
    # Public endpoint (for logged in users) to get average stats
    active_account_id = session.get('active_account_id')
    user_id = session.get('user_id')
    
    if active_account_id:
        linked_account = LinkedAccount.query.get(active_account_id)
    elif user_id:
        linked_account = LinkedAccount.query.filter_by(user_id=user_id).first()
    else:
        return jsonify({"error": "Unauthorized"}), 401

    if not linked_account:
        return jsonify({"error": "No linked account"}), 400
        
    course_name = request.args.get('course')
    professor_name = request.args.get('professor')
    institution = linked_account.institution

    stats = {}

    if course_name:
        reviews = CourseReview.query.filter(
            CourseReview.institution == institution,
            CourseReview.name == course_name,
            CourseReview.is_declined == False,
            CourseReview.difficulty_rating != None
        ).all()
        
        if reviews:
            avg = sum(r.difficulty_rating for r in reviews) / len(reviews)
            stats['course'] = {"average": round(avg, 1), "count": len(reviews)}
        else:
            stats['course'] = None

    if professor_name:
        professor_name = professor_name.strip().upper()
        reviews = ProfessorReview.query.filter(
            ProfessorReview.institution == institution,
            ProfessorReview.name == professor_name,
            ProfessorReview.is_declined == False,
            ProfessorReview.difficulty_rating != None
        ).all()
        
        if reviews:
            avg = sum(r.difficulty_rating for r in reviews) / len(reviews)
            stats['professor'] = {"average": round(avg, 1), "count": len(reviews)}
        else:
            stats['professor'] = None

    return jsonify(stats)
