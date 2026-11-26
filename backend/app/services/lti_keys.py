"""LTI 1.3 RSA keypair + JWKS for the tool."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings

_private_key = None
_kid: str | None = None


def _b64url_uint(val: int) -> str:
    length = (val.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(val.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _ensure_key() -> None:
    global _private_key, _kid
    if _private_key is not None:
        return

    path = Path(settings.LTI_PRIVATE_KEY_PATH)
    if path.exists():
        pem = path.read_bytes()
        _private_key = serialization.load_pem_private_key(pem, password=None)
    else:
        _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            _private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    pub_der = _private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _kid = hashlib.sha256(pub_der).hexdigest()[:16]


def get_private_key_pem() -> str:
    _ensure_key()
    return _private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def get_kid() -> str:
    _ensure_key()
    return _kid or "antiplagiat"


def get_jwks() -> dict[str, Any]:
    _ensure_key()
    public = _private_key.public_key()
    numbers = public.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": get_kid(),
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }
