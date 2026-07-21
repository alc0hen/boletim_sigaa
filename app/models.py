from .extensions import Base
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, LargeBinary, UniqueConstraint
from sqlalchemy.orm import relationship
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


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    profile_pic = Column(String(1024), nullable=True)
    is_admin = Column(Boolean, default=False)
    linked_accounts = relationship('LinkedAccount', back_populates='user', lazy='selectin')
    def __repr__(self):
        return f'<User {self.email}>'


class LinkedAccount(Base):
    __tablename__ = 'linked_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    institution = Column(String(50), nullable=False)
    username = Column(String(255), nullable=False)
    encrypted_password = Column(LargeBinary, nullable=False)
    history_json = Column(Text, nullable=True)
    history_updated_at = Column(DateTime, nullable=True)
    portal_cache_json = Column(Text, nullable=True)
    portal_cache_updated_at = Column(DateTime, nullable=True)
    user = relationship('User', back_populates='linked_accounts')
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


class CourseReview(Base):
    __tablename__ = 'course_reviews'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    institution = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    difficulty_rating = Column(Float, nullable=True) # 1.0 to 5.0
    is_declined = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('user_id', 'institution', 'name', name='uq_course_review'),)


class ProfessorReview(Base):
    __tablename__ = 'professor_reviews'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    institution = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    difficulty_rating = Column(Float, nullable=True) # 1.0 to 5.0
    is_declined = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('user_id', 'institution', 'name', name='uq_professor_review'),)
