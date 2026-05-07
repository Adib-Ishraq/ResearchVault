"""
JWT session validation + session hijacking prevention.
Tokens are signed with the server RSA private key (RSA-PSS).
Session metadata (JTI → user_id + ip_hash + ua_hash) is stored in Redis.
"""

import json
import time
import uuid
import base64
from functools import wraps
from flask import request, g, current_app, jsonify

from crypto.hash_engine import sha256
from crypto.rsa_engine import (
    rsa_sign, rsa_verify,
    deserialize_public_key, deserialize_private_key,
    RSAPrivateKey, RSAPublicKey,
)
from services.redis_client import get_redis


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def _sign_jwt(payload: dict, private_key: RSAPrivateKey) -> str:
    header = {"alg": "RS256-PSS", "typ": "JWT"}
    h_enc = _b64url_encode(json.dumps(header, separators=(',', ':')).encode())
    p_enc = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode())
    signing_input = f"{h_enc}.{p_enc}".encode()
    sig = rsa_sign(private_key, signing_input)
    return f"{h_enc}.{p_enc}.{_b64url_encode(sig)}"


def _verify_jwt(token: str, public_key: RSAPublicKey) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    h_enc, p_enc, sig_enc = parts
    signing_input = f"{h_enc}.{p_enc}".encode()
    sig = _b64url_decode(sig_enc)
    if not rsa_verify(public_key, signing_input, sig):
        raise ValueError("JWT signature invalid")
    payload = json.loads(_b64url_decode(p_enc))
    return payload


def _fingerprint(ip: str, user_agent: str) -> str:
    raw = f"{ip}|{user_agent}".encode()
    return sha256(raw).hex()


def issue_access_token(user_id: str, role: str, ip: str, user_agent: str) -> str:
    priv = deserialize_private_key(current_app.config["SERVER_RSA_MASTER_PRIVATE_KEY"])
    jti = str(uuid.uuid4())
    now = int(time.time())
    fp = _fingerprint(ip, user_agent)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "fp": fp,
        "iat": now,
        "exp": now + current_app.config["JWT_ACCESS_EXPIRES"],
        "type": "access",
    }
    token = _sign_jwt(payload, priv)

    # Store in Redis: key=jti, value=json(user_id, fp), TTL=access expiry
    r = get_redis()
    r.setex(
        f"sess:{jti}",
        current_app.config["JWT_ACCESS_EXPIRES"],
        json.dumps({"user_id": user_id, "fp": fp, "role": role}),
    )
    return token


def issue_refresh_token(user_id: str, role: str, ip: str, user_agent: str) -> str:
    priv = deserialize_private_key(current_app.config["SERVER_RSA_MASTER_PRIVATE_KEY"])
    jti = str(uuid.uuid4())
    now = int(time.time())
    fp = _fingerprint(ip, user_agent)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "fp": fp,
        "iat": now,
        "exp": now + current_app.config["JWT_REFRESH_EXPIRES"],
        "type": "refresh",
    }
    token = _sign_jwt(payload, priv)

    r = get_redis()
    r.setex(
        f"refresh:{jti}",
        current_app.config["JWT_REFRESH_EXPIRES"],
        json.dumps({"user_id": user_id, "fp": fp, "role": role}),
    )
    return token


def invalidate_token(jti: str, token_type: str = "access"):
    r = get_redis()
    prefix = "sess" if token_type == "access" else "refresh"
    r.delete(f"{prefix}:{jti}")


def validate_access_token(token: str, ip: str, user_agent: str) -> dict:
    """
    Validate access token: signature, expiry, Redis presence, and fingerprint.
    Returns payload dict on success, raises ValueError on failure.
    """
    pub = deserialize_public_key(current_app.config["SERVER_RSA_MASTER_PUBLIC_KEY"])
    payload = _verify_jwt(token, pub)

    if payload.get("type") != "access":
        raise ValueError("Not an access token")
    if payload["exp"] < int(time.time()):
        raise ValueError("Token expired")

    r = get_redis()
    stored = r.get(f"sess:{payload['jti']}")
    if not stored:
        raise ValueError("Session not found — logged out or expired")

    session_data = json.loads(stored)
    current_fp = _fingerprint(ip, user_agent)
    if session_data["fp"] != current_fp:
        # Possible session hijack — invalidate immediately
        r.delete(f"sess:{payload['jti']}")
        raise ValueError("Session fingerprint mismatch — possible hijack")

    return payload


def require_auth(f):
    """Decorator: validate JWT and set g.user_id + g.role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header[7:]
        try:
            payload = validate_access_token(
                token,
                request.remote_addr or "",
                request.headers.get("User-Agent", ""),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 401

        g.user_id = payload["sub"]
        g.role = payload["role"]
        g.jti = payload["jti"]
        return f(*args, **kwargs)
    return decorated
