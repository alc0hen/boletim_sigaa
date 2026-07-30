from quart import Quart
from .extensions import init_db, create_tables, close_db, google_oauth, generate_csrf_token
import os
import time
import logging
import traceback
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()
from .logger_config import setup_logging, format_http_start, format_http_end
from .security import is_production, load_secret_key


def create_app():

    is_prod = is_production()

    # Configure global logging (centralizado em logger_config.py)
    setup_logging(is_prod)

    app = Quart(__name__)
    
    if not is_prod:
        app.config['TEMPLATES_AUTO_RELOAD'] = True
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        app.debug = True

    app.secret_key = load_secret_key()
    app.config['SESSION_COOKIE_SECURE'] = is_prod
    app.config['REMEMBER_COOKIE_SECURE'] = is_prod
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
    app.config['SESSION_PERMANENT'] = True

    # Database configuration
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['DATABASE_URL'] = database_url

    # Google OAuth configuration
    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', 'placeholder-client-id')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', 'placeholder-client-secret')

    # Initialize extensions
    init_db(database_url, pool_pre_ping=True, pool_recycle=300)
    google_oauth.init_app(app)

    # Make globals available in all templates
    @app.context_processor
    def inject_globals():
        app_version = "Unknown"
        try:
            import json
            version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'versao.json')
            with open(version_path, 'r', encoding='utf-8') as f:
                app_version = json.load(f).get('version', 'Unknown')
        except Exception as e:
            pass
        return dict(csrf_token=generate_csrf_token, app_version=app_version)

    @app.before_request
    async def enforce_session_lifetime():
        from quart import session
        session.permanent = True

    @app.before_request
    async def check_csrf():
        from quart import request, session, abort
        import hmac
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            form = await request.form
            token = form.get('csrf_token') or request.headers.get('X-CSRFToken')
            expected = session.get('_csrf_token')
            if not token or not expected or not hmac.compare_digest(str(token), str(expected)):
                abort(403)

    # Register blueprint
    from . import routes
    app.register_blueprint(routes.bp)

    @app.before_serving
    async def setup():
        from . import models  # noqa: F401 — ensure models are imported
        await create_tables()

        backend_pref = os.environ.get("SIGAA_BACKEND", "auto").strip().lower()
        app.logger.info(f"⚙️ Sistema de API configurado (SIGAA_BACKEND): {backend_pref.upper()}")

        from .sigaa_remote import is_configured, get_client
        if backend_pref == 'local':
            app.logger.info("🏠 Backend local forçado. Ignorando configuração da API Remota e conexões de teste.")
        elif is_configured():
            app.logger.info("📡 API Remota configurada. Testando comunicação...")
            client = get_client()
            if client:
                try:
                    is_healthy = await client.healthy(force=True)
                    if is_healthy:
                        app.logger.info("✅ Comunicação com a API Remota estabelecida com sucesso!")
                    else:
                        app.logger.warning("⚠️ Não foi possível se comunicar com a API Remota (serviço retornou erro ou indisponível).")
                except Exception as e:
                    app.logger.warning(f"⚠️ Erro ao tentar se comunicar com a API Remota: {e}")
        else:
            app.logger.info("⚠️ Nenhuma API Remota configurada. O acesso utilizará o scraper local (se backend for auto ou local).")

    @app.before_request
    async def create_session():
        from quart import g
        from .extensions import db_session
        g.db_session = db_session()

    @app.teardown_request
    async def close_session(exception=None):
        from quart import g
        session = g.pop('db_session', None)
        if session:
            if exception:
                await session.rollback()
            await session.close()

    @app.after_serving
    async def teardown():
        await close_db()

    @app.after_request
    async def set_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'self'"
        )
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=()'
        return response

    # ── Middleware de logging HTTP ────────────────────────────
    http_log = logging.getLogger('app.http')

    # Rotas de submissão de avaliações anônimas: por design, IP e user_id nunca
    # são gravados nos logs do servidor para essas requisições.
    _ANONYMOUS_LOG_PATHS = {'/api/avaliacoes/submeter'}

    @app.before_request
    async def log_request_start():
        from quart import request as req, g
        g._req_start = time.perf_counter()
        is_anonymous_route = req.path in _ANONYMOUS_LOG_PATHS
        http_log.info(format_http_start(
            req.method, req.path, '-' if is_anonymous_route else (req.remote_addr or '-')
        ))

    @app.after_request
    async def log_request_end(response):
        from quart import request as req, session as sess, g
        elapsed = (time.perf_counter() - getattr(g, '_req_start', time.perf_counter())) * 1000
        is_anonymous_route = req.path in _ANONYMOUS_LOG_PATHS
        user_id = None if is_anonymous_route else sess.get('user_id')
        http_log.info(format_http_end(
            req.method, req.path, response.status_code, elapsed, user_id
        ))
        return response

    # ── Handler global de exceções não tratadas ───────────────
    @app.errorhandler(Exception)
    async def handle_unhandled_exception(exc):
        from quart import request as req, jsonify
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc

        http_log.error(
            f"❌ Exceção não tratada em {req.method} {req.path}\n"
            + traceback.format_exc()
        )
        return jsonify(error="Erro interno do servidor"), 500

    return app