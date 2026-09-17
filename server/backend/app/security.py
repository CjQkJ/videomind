import datetime as dt
import hashlib
import hmac
import secrets
import string
from typing import Any, Dict

import jwt

from app.config import get_settings


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_code(code: str, pepper: str) -> str:
    return hashlib.sha256(f"{pepper}:{code}".encode("utf-8")).hexdigest()


def verify_code(code: str, code_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_code(code, pepper), code_hash)


# ---- password hashing (stdlib pbkdf2, no extra deps) ----

_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """pbkdf2_hmac sha256, returns 'iterations$salt$hash_hex'."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Compare password against a stored hash_str from hash_password."""
    try:
        iters, salt, dk_hex = stored.split("$", 2)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


# ---- JWT ----


def create_access_token(user_id: int, email: str) -> str:
    s = get_settings()
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=s.jwt_expire_hours)
    payload = {"sub": str(user_id), "email": email, "exp": exp}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_api_key() -> str:
    return "vw_" + secrets.token_urlsafe(32)
