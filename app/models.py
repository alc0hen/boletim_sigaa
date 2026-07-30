from .extensions import Base
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, LargeBinary, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
import hmac
import hashlib
import logging
from datetime import datetime
from functools import lru_cache

@lru_cache(maxsize=1)
def get_cipher_suite():
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        from .security import is_production
        if is_production():
            raise ValueError("ENCRYPTION_KEY environment variable is required in production!")
        logging.warning(
            "⚠️ ENCRYPTION_KEY ausente: usando chave de desenvolvimento INSEGURA. "
        )
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
    linked_accounts = relationship('LinkedAccount', back_populates='user', lazy='selectin', cascade='all, delete-orphan')
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


@lru_cache(maxsize=1)
def get_vote_hash_key() -> bytes:
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        from .security import is_production
        if is_production():
            raise ValueError("ENCRYPTION_KEY environment variable is required in production!")
        key = base64.urlsafe_b64encode(b'0' * 32)

    if isinstance(key, str):
        key = key.encode('utf-8')

    salt = b'sigaa-api-vote-hash-salt-v1'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return kdf.derive(key)


def compute_vote_hash(aluno_ref: int, disciplina_id: int, professor_id: int) -> str:
    msg = f"{aluno_ref}:{disciplina_id}:{professor_id}".encode('utf-8')
    return hmac.new(get_vote_hash_key(), msg, hashlib.sha256).hexdigest()


class Disciplina(Base):
    __tablename__ = 'disciplinas'
    id = Column(Integer, primary_key=True)
    institution = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint('institution', 'name', name='uq_disciplina'),)


class Professor(Base):
    __tablename__ = 'professores'
    id = Column(Integer, primary_key=True)
    institution = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint('institution', 'name', name='uq_professor'),)


class Avaliacao(Base):
    __tablename__ = 'avaliacoes'
    id = Column(Integer, primary_key=True)
    disciplina_id = Column(Integer, ForeignKey('disciplinas.id'), nullable=False)
    professor_id = Column(Integer, ForeignKey('professores.id'), nullable=False)
    nota_exigencia = Column(Integer, nullable=False)  # 1 (baixa exigência) .. 5 (altíssima exigência)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index('ix_avaliacao_oferta', 'disciplina_id', 'professor_id'),)


class VotoControle(Base):
    __tablename__ = 'votos_controle'
    id = Column(Integer, primary_key=True)
    hash_voto = Column(String(64), unique=True, nullable=False, index=True)
    voto_computado = Column(Boolean, nullable=False, default=True)
