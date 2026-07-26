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


def create_app():
    is_prod = os.environ.get('Render') or os.environ.get('FLASK_ENV') == 'production'
    
    # Configure global logging (centralizado em logger_config.py)
    setup_logging(is_prod)
    
    app = Quart(__name__)
    if is_prod:
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable is required in production!")
        app.secret_key = os.environ.get('SECRET_KEY')
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True
    else:
        app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
        app.config['SESSION_COOKIE_SECURE'] = False
        app.config['REMEMBER_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

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
    async def check_csrf():
        from quart import request, session, abort
        if request.method in ('POST', 'PUT', 'DELETE'):
            form = await request.form
            token = form.get('csrf_token') or request.headers.get('X-CSRFToken')
            if not token or token != session.get('_csrf_token'):
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
        if is_configured():
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
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data: https://lh3.googleusercontent.com; connect-src 'self';"
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # ── Middleware de logging HTTP ────────────────────────────
    http_log = logging.getLogger('app.http')

    @app.before_request
    async def log_request_start():
        from quart import request as req, g
        g._req_start = time.perf_counter()
        http_log.info(format_http_start(
            req.method, req.path, req.remote_addr or '-'
        ))

    @app.after_request
    async def log_request_end(response):
        from quart import request as req, session as sess, g
        elapsed = (time.perf_counter() - getattr(g, '_req_start', time.perf_counter())) * 1000
        user_id = sess.get('user_id')
        http_log.info(format_http_end(
            req.method, req.path, response.status_code, elapsed, user_id
        ))
        return response

    # ── Handler global de exceções não tratadas ───────────────
    @app.errorhandler(Exception)
    async def handle_unhandled_exception(exc):
        from quart import request as req, jsonify
        http_log.error(
            f"❌ Exceção não tratada em {req.method} {req.path}\n"
            + traceback.format_exc()
        )
        return jsonify(error="Erro interno do servidor"), 500

    return app