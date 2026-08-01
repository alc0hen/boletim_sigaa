import hashlib
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

class RequestSigner:

    def __init__(self, private_key_hex: str):
        self._private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        self.public_key_hex = self._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def headers(self, method: str, path: str, body: bytes=b'') -> dict:
        timestamp = str(int(time.time()))
        body_hash = hashlib.sha256(body or b'').hexdigest()
        message = f'{method.upper()}|{path}|{timestamp}|{body_hash}'.encode('utf-8')
        return {'X-Signature': self._private_key.sign(message).hex(), 'X-Timestamp': timestamp}