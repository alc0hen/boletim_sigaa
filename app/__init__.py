from flask import Flask
from .extensions import db, csrf, oauth
import os
import logging
from dotenv import load_dotenv
load_dotenv()
def create_app():
    app = Flask(__name__)
    is_prod = os.environ.get('Render') or os.environ.get('FLASK_ENV') == 'production'
    if is_prod:
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable is required in production!")
        app.secret_key = os.environ.get('SECRET_KEY')
        app.config['SESSION_COOKIE_SECURE'] = True
    else:
        app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
        app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
    }
    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', 'placeholder-client-id')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', 'placeholder-client-secret')
    db.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    from . import routes
    app.register_blueprint(routes.bp)
    with app.app_context():
        from . import models
        db.create_all()
    logging.basicConfig(level=logging.INFO)
    return app