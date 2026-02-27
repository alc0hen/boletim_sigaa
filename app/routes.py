from flask import Blueprint, render_template, request, redirect, url_for, session, Response, stream_with_context, current_app, flash, jsonify
from .sigaa_api.sigaa import Sigaa, InstitutionType
from .domain.factory import CalculatorFactory
from .demo_data import get_demo_data
from .extensions import db, oauth
from .models import User, LinkedAccount, get_cipher_suite
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
@bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))
@bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        institution_str = request.form.get('institution', 'IFAL')
        if institution_str == 'UFAL':
            inst_type = InstitutionType.UFAL
            url = "https://sigaa.sig.ufal.br"
        else:
            inst_type = InstitutionType.IFAL
            url = SIGAA_URL
        sigaa = Sigaa(url, inst_type)
        try:
            account = await sigaa.login(username, password)
            client_session = await sigaa.session._get_session()
            cookies = {}
            for cookie in client_session.cookie_jar:
                cookies[cookie.key] = cookie.value
            session['sigaa_cookies'] = cookies
            session['sigaa_url'] = url
            session['sigaa_inst'] = institution_str
            session['username'] = username
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
        finally:
            await sigaa.close()
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
async def link_account():
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
    else:
        inst_type = InstitutionType.IFAL
        url = SIGAA_URL
    sigaa = Sigaa(url, inst_type)
    try:
        await sigaa.login(username, password)
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
        client_session = await sigaa.session._get_session()
        cookies = {}
        for cookie in client_session.cookie_jar:
            cookies[cookie.key] = cookie.value
        session['sigaa_cookies'] = cookies
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.error(f"Link Account Failed: {e}")
        user = User.query.get(session['user_id'])
        return render_template('profile.html', error="Falha ao vincular: Credenciais inválidas.", user=user, linked_accounts=user.linked_accounts, active_account_id=session.get('active_account_id'))
    finally:
        await sigaa.close()
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
async def dashboard():
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
        else:
            inst_type = InstitutionType.IFAL
            url = SIGAA_URL
        sigaa = Sigaa(url, inst_type)
        try:
            await sigaa.login(account.username, password)
            client_session = await sigaa.session._get_session()
            cookies = {}
            for cookie in client_session.cookie_jar:
                cookies[cookie.key] = cookie.value
            session['sigaa_cookies'] = cookies
            session['sigaa_url'] = url
            session['sigaa_inst'] = account.institution
            session['username'] = account.username
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f"Auto-login failed for {account.username}: {e}")
            return redirect(url_for('main.profile'))
        finally:
            await sigaa.close()
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
    sigaa = Sigaa(url, inst_type, cookies=cookies)
    try:
        response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
        if "login" in response.url.path:
             return jsonify({"error": "Session expired"}), 401
        from .sigaa_api.account import Account
        account = Account(sigaa.session, response)
        if not account.active_bonds:
            return jsonify({"error": "No active bonds"}), 404
        bond = account.active_bonds[0]
        history = await bond.get_history()
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
    except Exception as e:
        logger.error(f"Profile error: {e}")
        return jsonify({"error": "Failed to fetch profile"}), 500
    finally:
        await sigaa.close()
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
    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')
@bp.route('/api/update_course/<int:course_id>', methods=['POST'])
async def update_course(course_id):
    cookies = session.get('sigaa_cookies')
    if not cookies: return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype='application/json')
    url = session.get('sigaa_url', SIGAA_URL)
    inst_str = session.get('sigaa_inst', 'IFAL')
    try: inst_type = InstitutionType[inst_str]
    except KeyError: inst_type = InstitutionType.IFAL
    sigaa = Sigaa(url, inst_type, cookies=cookies)
    try:
        response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
        if "login" in response.url.path: return Response(json.dumps({"error": "Session expired"}), status=401, mimetype='application/json')
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
        if not target_course: return Response(json.dumps({"error": "Course not found"}), status=404, mimetype='application/json')
        raw_grades = []
        try:
            raw_grades = await target_course.get_grades()
        except Exception as e:
            logger.error(f"Error fetching grades: {e}")
            return Response(json.dumps({"error": "Failed to fetch grades"}), status=500, mimetype='application/json')
        calculator = CalculatorFactory.get_calculator(inst_type)
        course_result = calculator.calculate(raw_grades)
        response_data = {
            "id": course_id,
            "data": {
                "grades": raw_grades,
                "status": course_result.to_dict()
            }
        }
        freq_data = None
        try:
            freq_data = await target_course.get_frequency()
            if freq_data:
                response_data['frequency'] = freq_data
        except Exception: pass
        return Response(json.dumps(response_data), mimetype='application/json')
    except Exception as e:
        logger.error(f"Single update error: {e}")
        return Response(json.dumps({"error": "Internal Server Error"}), status=500, mimetype='application/json')
    finally: await sigaa.close()
@bp.route('/api/stream_grades')
def stream_grades():
    cookies = session.get('sigaa_cookies')
    if not cookies: return Response("Unauthorized", status=401)
    priority_str = request.args.get('priority', '')
    priority_ids = []
    if priority_str:
        try: priority_ids = [int(x) for x in priority_str.split(',')]
        except ValueError: pass
    async def async_generate():
        url = session.get('sigaa_url', SIGAA_URL)
        inst_str = session.get('sigaa_inst', 'IFAL')
        try: inst_type = InstitutionType[inst_str]
        except KeyError: inst_type = InstitutionType.IFAL
        sigaa = Sigaa(url, inst_type, cookies=cookies)
        try:
            response = await sigaa.session.get("/sigaa/portais/discente/discente.jsf")
            if "login" in response.url.path:
                 yield json.dumps({"error": "Session expired"}) + "\n"
                 return
            from .sigaa_api.account import Account
            account = Account(sigaa.session, response)
            name = await account.get_name()
            is_supporter = False
            registration = None
            if account.active_bonds: registration = account.active_bonds[0].registration
            supporters = []
            try:
                async with aiohttp.ClientSession() as session_http:
                    async with session_http.get(SUPPORTERS_URL) as resp:
                        if resp.status == 200: supporters = await resp.json(content_type=None)
            except Exception:
                try:
                    with open('app/apoio/apoiadores.json', 'r') as f: supporters = json.load(f)
                except Exception: pass
            if registration and str(registration) in {str(s) for s in supporters}: is_supporter = True
            yield json.dumps({"type": "user_info", "name": name, "is_supporter": is_supporter}) + "\n"
            if account.active_bonds:
                calculator = CalculatorFactory.get_calculator(inst_type)
                for bond in account.active_bonds:
                    courses = await bond.get_courses()
                    if not courses:
                        continue
                    course_list_with_ids = []
                    for i, course in enumerate(courses):
                        course_list_with_ids.append({'id': i + 1, 'course': course})
                    if priority_ids:
                        prioritized = [c for c in course_list_with_ids if c['id'] in priority_ids]
                        others = [c for c in course_list_with_ids if c['id'] not in priority_ids]
                        course_list_with_ids = prioritized + others
                    for item in course_list_with_ids:
                        course_id = item['id']
                        course = item['course']
                        yield json.dumps({"type": "course_start", "id": course_id, "name": course.title, "obs": bond.program}) + "\n"

                    try:
                        history = await bond.get_history()
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

                    current_sem = None
                    if history:
                        sorted_sems = sorted(history.keys())
                        current_sem = sorted_sems[-1]

                    current_subjects = history.get(current_sem, []) if current_sem else []

                    # Fast Path: match current subjects with course list
                    def normalize_name(s):
                        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

                    current_subjects_map = {normalize_name(s['name']): s for s in current_subjects}

                    for item in course_list_with_ids:
                        course_id = item['id']
                        course = item['course']
                        norm_title = normalize_name(course.title)

                        if norm_title in current_subjects_map:
                            subject = current_subjects_map[norm_title]
                            raw_grades = subject['grades']
                            # Use existing calculator instance
                            course_result = calculator.calculate(raw_grades)

                            result_data = {
                                "grades": raw_grades,
                                "status": course_result.to_dict()
                            }
                            yield json.dumps({"type": "course_data", "id": course_id, "data": result_data}) + "\n"

                    # Parallel fetching with semaphore limit 1 to avoid race conditions on SIGAA session state
                    # SIGAA uses server-side JSF state (ViewState) which can be invalidated by concurrent POST requests
                    semaphore = asyncio.Semaphore(1)

                    async def fetch_parallel(item):
                        async with semaphore:
                            output = []
                            course_id = item['id']
                            course = item['course']

                            # Always fetch grades from individual page
                            try:
                                raw_grades = await course.get_grades()
                                course_result = calculator.calculate(raw_grades)
                                result_data = {
                                    "grades": raw_grades,
                                    "status": course_result.to_dict()
                                }
                                output.append(json.dumps({"type": "course_data", "id": course_id, "data": result_data}) + "\n")
                            except Exception:
                                pass

                            # If supporter, fetch frequency
                            if is_supporter:
                                try:
                                    freq_data = await course.get_frequency()
                                    if freq_data:
                                        output.append(json.dumps({"type": "course_frequency", "id": course_id, "data": freq_data}) + "\n")
                                except Exception:
                                    pass

                            return output

                    tasks = [fetch_parallel(item) for item in course_list_with_ids]
                    for future in asyncio.as_completed(tasks):
                        results = await future
                        for res in results:
                            yield res
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield json.dumps({"error": "Erro no carregamento dos dados."}) + "\n"
        finally: await sigaa.close()
    def sync_generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = async_generate()
        try:
            while True:
                data = loop.run_until_complete(gen.__anext__())
                yield data
        except StopAsyncIteration: pass
        except Exception: yield json.dumps({"error": "Internal Server Error"}) + "\n"
        finally: loop.close()
    return Response(stream_with_context(sync_generate()), mimetype='application/x-ndjson')
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))
