from .extensions import db
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
import logging
from functools import lru_cache

@lru_cache(maxsize=1)
def get_cipher_suite():
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        is_prod = os.environ.get('Render') or os.environ.get('FLASK_ENV') == 'production'
        if is_prod:
            raise ValueError("ENCRYPTION_KEY environment variable is required in production!")
        logging.warning("Using an insecure fallback encryption key. Do NOT use this in production!")
        key = base64.urlsafe_b64encode(b'0'*32)

    if isinstance(key, str):
        key = key.encode('utf-8')

    if len(key) == 44:
        try:
            decoded = base64.urlsafe_b64decode(key)
            if len(decoded) == 32:
                return Fernet(key)
        except Exception:
            pass

    salt = b'sigaa-api-static-salt-v1'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(key))
    return Fernet(derived_key)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    profile_pic = db.Column(db.String(1024), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    linked_accounts = db.relationship('LinkedAccount', backref='user', lazy=True)
    def __repr__(self):
        return f'<User {self.email}>'
class LinkedAccount(db.Model):
    __tablename__ = 'linked_accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    institution = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    encrypted_password = db.Column(db.LargeBinary, nullable=False)
    history_json = db.Column(db.Text, nullable=True)
    history_updated_at = db.Column(db.DateTime, nullable=True)
    def set_password(self, password):
        cipher = get_cipher_suite()
        if isinstance(password, str):
            password = password.encode('utf-8')
        self.encrypted_password = cipher.encrypt(password)
    def get_password(self):
        cipher = get_cipher_suite()
        try:
            decrypted = cipher.decrypt(self.encrypted_password)
            return decrypted.decode('utf-8')
        except Exception:
            return None
    def __repr__(self):
        return f'<LinkedAccount {self.institution}:{self.username}>'
