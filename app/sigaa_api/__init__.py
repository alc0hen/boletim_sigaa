from flask import Flask
import os
def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'some_secret_key_for_session')
    from . import routes
    app.register_blueprint(routes.bp)
    return app