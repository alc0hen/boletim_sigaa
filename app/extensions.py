"""
Native async extensions for Quart application.

Uses SQLAlchemy 2.0 async engine directly (no Flask-SQLAlchemy),
manual CSRF protection, and manual OAuth2 via httpx.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import secrets
from quart import session, request, abort
from functools import wraps


# ── SQLAlchemy 2.0 Async ──────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


# These are initialized at app startup via init_db()
engine = None
db_session: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str, **engine_kwargs):
    """Initialize the async database engine and session factory.

    Converts standard database URLs to async-compatible driver URLs:
      - postgresql:// → postgresql+asyncpg://
      - sqlite:///    → sqlite+aiosqlite:///
    """
    global engine, db_session

    # Convert sync driver URLs to async driver URLs
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("sqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    engine = create_async_engine(database_url, **engine_kwargs)
    db_session = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables():
    """Create all tables defined in models. Call during app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose of the engine connection pool. Call during app shutdown."""
    if engine:
        await engine.dispose()


# ── CSRF Protection (manual, no Flask-WTF) ────────────────────────
def generate_csrf_token():
    """Generate a CSRF token and store it in the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def csrf_protect(f):
    """Decorator to verify CSRF token on POST/PUT/DELETE requests."""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE'):
            form = await request.form
            token = form.get('csrf_token') or request.headers.get('X-CSRFToken')
            if not token or token != session.get('_csrf_token'):
                abort(403)
        return await f(*args, **kwargs)
    return decorated_function


# ── OAuth2 Google (manual, no Authlib) ────────────────────────────
class GoogleOAuth:
    """Minimal async OAuth2 client for Google login using httpx."""

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self):
        self.client_id = None
        self.client_secret = None

    def init_app(self, app):
        self.client_id = app.config['GOOGLE_CLIENT_ID']
        self.client_secret = app.config['GOOGLE_CLIENT_SECRET']

    def get_authorize_url(self, redirect_uri: str, state: str) -> str:
        """Build the Google OAuth2 authorization URL."""
        import urllib.parse
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{self.AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            })
            resp.raise_for_status()
            return resp.json()

    async def get_userinfo(self, access_token: str) -> dict:
        """Fetch user info from Google using the access token."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.USERINFO_URL, headers={
                "Authorization": f"Bearer {access_token}",
            })
            resp.raise_for_status()
            return resp.json()


google_oauth = GoogleOAuth()
