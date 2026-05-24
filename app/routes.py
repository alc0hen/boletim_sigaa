from flask import Blueprint, render_template, request, redirect, url_for, session, Response, stream_with_context, current_app, flash, jsonify
from .sigaa_api.sigaa import Sigaa, InstitutionType
from .domain.factory import CalculatorFactory
from .demo_data import get_demo_data
from .extensions import db, oauth
from .models import User, LinkedAccount, get_cipher_suite
from .sigaa_api.exceptions import SigaaQuestionnaireError
import asyncio
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
def academic_profile():
    cookies = session.get('sigaa_cookies')
    if not cookies:
        return jsonify({"error": "Unauthorized"}), 401
    force_update = request.args.get('force') == 'true'
    active_account_id = session.get('active_account_id')
    linked_account = None
    if active_account_id:
        linked_account = LinkedAccount.query.get(active_account_id)
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
        res = run_async(fetch_academic_profile())
        if res["status"] != 200:
            return jsonify({"error": res["error"]}), res["status"]
            
        history = res["history"]
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
        
        cache = None
        if linked_account and linked_account.portal_cache_json:
            try:
                cache = json.loads(linked_account.portal_cache_json)
                cache['timestamp'] = linked_account.portal_cache_updated_at.timestamp() if linked_account.portal_cache_updated_at else 0
            except: pass

        now = time.time()
        use_cache = False
        if cache and (now - cache.get('timestamp', 0) < 600): # 10 minutes
            use_cache = True
            logger.info(f"Using DB portal cache for {username}")
        else:
            logger.info(f"Cache miss for {username}. Reason: {'Old/Missing' if cache else 'No cache'}")

        try:
            account = None
            if not use_cache:
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
            
            # Start fetching name and supporters
            name = cache.get('name') if use_cache else await account.get_name()
            
            # Yield user_info ASAP
            is_supporter_cached = cache.get('is_supporter', False) if use_cache else False
            yield json.dumps({"type": "user_info", "name": name, "is_supporter": is_supporter_cached}) + "\n"

            # Check for actual supporters in background if not using cache or to refresh
            supporters = await get_supporters_task()
            is_supporter = False
            if not use_cache:
                registration = None
                if account.active_bonds: registration = account.active_bonds[0].registration
                if registration and str(registration) in {str(s) for s in supporters}: is_supporter = True
                # If cached value was wrong, we could send an update, but usually it's fine
            else:
                is_supporter = is_supporter_cached

            if use_cache or (account and account.active_bonds):
                calculator = CalculatorFactory.get_calculator(inst_type)
                
                # Reconstruct bonds from cache or use account
                bonds_to_process = []
                if use_cache:
                    from .sigaa_api.bond import StudentBond
                    from .sigaa_api.course import Course
                    for b_data in cache.get('bonds', []):
                        # Create the actual bond object
                        bond_obj = StudentBond(
                            sigaa.session, 
                            b_data.get('registration'), 
                            b_data['program'], 
                            b_data.get('switch_url')
                        )
                        c_list = []
                        for c_data in b_data.get('courses', []):
                            c_list.append(Course(sigaa.session, c_data['title'], c_data['form_data'], c_data.get('schedule_code', '')))
                        bonds_to_process.append({'program': b_data['program'], 'courses': c_list, 'bond_obj': bond_obj})
                else:
                    for bond in account.active_bonds:
                        courses = await bond.get_courses()
                        bonds_to_process.append({'program': bond.program, 'courses': courses, 'bond_obj': bond})

                # Global cache update data
                new_cache_bonds = []
                
                # Phase 1: Mapping & Cache Save (Fast)
                for b_item in bonds_to_process:
                    courses = b_item['courses']
                    if not courses: continue
                    
                    course_list_with_ids = []
                    for i, course in enumerate(courses):
                        course_list_with_ids.append({'id': i + 1, 'course': course})
                    b_item['_course_list'] = course_list_with_ids # Save for phase 2
                    
                    # Cache current bond structure
                    current_bond_cache = {
                        'program': b_item['program'], 
                        'registration': b_item['bond_obj'].registration if 'bond_obj' in b_item else None,
                        'switch_url': b_item['bond_obj'].switch_url if 'bond_obj' in b_item else None,
                        'courses': []
                    }
                    for item in course_list_with_ids:
                        course_id = item['id']
                        course = item['course']
                        yield json.dumps({"type": "course_start", "id": course_id, "name": course.title, "obs": b_item['program']}) + "\n"
                        current_bond_cache['courses'].append({
                            'title': course.title,
                            'form_data': course.form_data,
                            'schedule_code': course.schedule_code
                        })
                    new_cache_bonds.append(current_bond_cache)

                # Save cache BEFORE slow fetching
                if not use_cache and linked_account:
                    try:
                        linked_account.portal_cache_json = json.dumps({
                            'name': name,
                            'is_supporter': is_supporter,
                            'bonds': new_cache_bonds
                        })
                        linked_account.portal_cache_updated_at = datetime.now()
                        db.session.commit()
                        logger.info(f"Portal cache persistent for {username}")
                    except Exception as e:
                        logger.error(f"Cache persistence failed: {e}")
                        db.session.rollback()

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
                            history = await bond_obj.get_history()
                        else:
                            history = {}
                    except Exception as e:
                        logger.error(f"Error fetching history: {e}")
                        history = {}

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
