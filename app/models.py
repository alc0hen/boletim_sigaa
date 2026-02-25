from .extensions import db
from cryptography.fernet import Fernet
import os
import base64
def get_cipher_suite():
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        is_prod = os.environ.get('Render') or os.environ.get('FLASK_ENV') == 'production'
        if is_prod:
            raise ValueError("ENCRYPTION_KEY environment variable is required in production!")
        key = base64.urlsafe_b64encode(b'0'*32)
    if isinstance(key, str):
        key = key.encode('utf-8')
    return Fernet(key)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    profile_pic = db.Column(db.String(1024), nullable=True)
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
