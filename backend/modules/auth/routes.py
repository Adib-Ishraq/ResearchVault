"""
Auth module: register, login (step 1 + 2FA), logout, refresh, reset password.
"""

import json
import re
import time
from flask import Blueprint, request, jsonify, make_response, current_app, g

from services.supabase_client import get_supabase
from services.redis_client import get_redis
from services.email_service import generate_otp, send_otp_email
from crypto.hash_engine import sha256, hash_password, verify_password
from crypto.key_manager import (
    generate_user_keys, encrypt_field, decrypt_field,
)
from crypto.hmac_engine import compute_record_hmac, verify_record_hmac
from middleware.session import (
    issue_access_token, issue_refresh_token,
    invalidate_token, validate_access_token, require_auth,
)

auth_bp = Blueprint("auth", __name__)

_OTP_TTL = 600  # 10 minutes


def _validate_password(password: str):
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>?/\\|`~]", password):
        return "Password must contain at least one special character"
    return None


def _email_hash(email: str) -> str:
    return sha256(email.strip().lower().encode()).hex()


def _hmac_key(app=None) -> bytes:
    cfg = app.config if app else current_app.config
    return cfg["HMAC_SECRET"].encode()


# ─── Register ────────────────────────────────────────────────────────────────

@auth_bp.post("/register")
def register():
    data = request.get_json(force=True)
    required = ["email", "password", "username", "role"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    role = data["role"]
    if role not in ("supervisor", "postgrad", "undergraduate"):
        return jsonify({"error": "Invalid role"}), 400

    pw_error = _validate_password(data["password"])
    if pw_error:
        return jsonify({"error": pw_error}), 400

    email = data["email"].strip().lower()
    db = get_supabase()

    # Check duplicate
    e_hash = _email_hash(email)
    existing = db.table("users").select("id").eq("email_hash", e_hash).execute()
    if existing.data:
        return jsonify({"error": "Email already registered"}), 409

    # Hash password
    pw_hash, salt = hash_password(data["password"])

    # Encrypt PII fields with server ECC master public key
    username_enc = encrypt_field(data["username"])
    email_enc = encrypt_field(email)
    contact_enc = encrypt_field(data.get("contact", "")) if data.get("contact") else None

    # Generate user cryptographic keypair
    user_keys = generate_user_keys()

    # Compute HMAC over all encrypted fields
    hmac_val = compute_record_hmac(
        _hmac_key(),
        username_enc, email_enc, contact_enc or "", user_keys["private_key_enc"]
    )

    user_row = {
        "role": role,
        "username_enc": username_enc,
        "email_enc": email_enc,
        "email_hash": e_hash,
        "contact_enc": contact_enc,
        "password_hash": pw_hash,
        "salt": salt,
        "public_key_rsa": user_keys["public_key_rsa"],
        "public_key_ecc": user_keys["public_key_ecc"],
        "private_key_enc": user_keys["private_key_enc"],
        "two_fa_enabled": False,
        "hmac": hmac_val,
    }

    result = db.table("users").insert(user_row).execute()
    if not result.data:
        return jsonify({"error": "Registration failed"}), 500

    user_id = result.data[0]["id"]

    # Create empty profile row
    profile_row = {
        "user_id": user_id,
        "university_plaintext": data.get("university", ""),
        "university_enc": encrypt_field(data.get("university", "")) if data.get("university") else None,
        "hmac": "",
    }
    db.table("profiles").insert(profile_row).execute()

    return jsonify({"message": "Registered successfully", "user_id": user_id}), 201


# ─── Login Step 1: Credential check ─────────────────────────────────────────

@auth_bp.post("/login")
def login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    db = get_supabase()
    e_hash = _email_hash(email)
    result = db.table("users").select(
        "id, role, password_hash, salt, two_fa_enabled"
    ).eq("email_hash", e_hash).execute()

    if not result.data:
        return jsonify({"error": "Invalid credentials"}), 401

    user = result.data[0]
    if not verify_password(password, user["password_hash"], user["salt"]):
        return jsonify({"error": "Invalid credentials"}), 401

    r = get_redis()

    if user["two_fa_enabled"]:
        # Issue a temporary pre-auth token, send OTP
        otp = generate_otp()
        pre_token = sha256(f"{user['id']}:{otp}:{time.time()}".encode()).hex()
        r.setex(f"otp:{pre_token}", _OTP_TTL, json.dumps({
            "user_id": user["id"],
            "role": user["role"],
            "otp": otp,
        }))

        # Fetch decrypted email to send OTP
        user_full = db.table("users").select("email_enc").eq("id", user["id"]).execute()
        real_email = decrypt_field(user_full.data[0]["email_enc"])
        send_otp_email(real_email, otp, "login")

        return jsonify({"requires_2fa": True, "pre_token": pre_token}), 200

    # No 2FA — issue tokens directly
    ip = request.remote_addr or ""
    ua = request.headers.get("User-Agent", "")
    access = issue_access_token(user["id"], user["role"], ip, ua)
    refresh = issue_refresh_token(user["id"], user["role"], ip, ua)

    resp = make_response(jsonify({"access_token": access, "role": user["role"]}))
    resp.set_cookie(
        "refresh_token", refresh,
        httponly=True, secure=True, samesite="Strict",
        max_age=current_app.config["JWT_REFRESH_EXPIRES"],
    )
    return resp, 200


# ─── Login Step 2: 2FA OTP verification ──────────────────────────────────────

@auth_bp.post("/verify-2fa")
def verify_2fa():
    data = request.get_json(force=True)
    pre_token = data.get("pre_token", "")
    otp_input = data.get("otp", "")

    r = get_redis()
    stored = r.get(f"otp:{pre_token}")
    if not stored:
        return jsonify({"error": "OTP expired or invalid"}), 401

    stored_data = json.loads(stored)
    if stored_data["otp"] != otp_input:
        return jsonify({"error": "Incorrect OTP"}), 401

    r.delete(f"otp:{pre_token}")

    ip = request.remote_addr or ""
    ua = request.headers.get("User-Agent", "")
    access = issue_access_token(stored_data["user_id"], stored_data["role"], ip, ua)
    refresh = issue_refresh_token(stored_data["user_id"], stored_data["role"], ip, ua)

    resp = make_response(jsonify({"access_token": access, "role": stored_data["role"]}))
    resp.set_cookie(
        "refresh_token", refresh,
        httponly=True, secure=True, samesite="Strict",
        max_age=current_app.config["JWT_REFRESH_EXPIRES"],
    )
    return resp, 200


# ─── Logout ───────────────────────────────────────────────────────────────────

@auth_bp.post("/logout")
@require_auth
def logout():
    invalidate_token(g.jti, "access")
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            from crypto.rsa_engine import deserialize_public_key
            import base64, json as _json
            parts = refresh_token.split('.')
            payload = _json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
            invalidate_token(payload["jti"], "refresh")
        except Exception:
            pass

    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie("refresh_token")
    return resp, 200


# ─── Refresh token rotation ───────────────────────────────────────────────────

@auth_bp.post("/refresh")
def refresh():
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "No refresh token"}), 401

    from crypto.rsa_engine import deserialize_public_key
    import base64 as _b64, json as _json

    try:
        pub = deserialize_public_key(current_app.config["SERVER_RSA_MASTER_PUBLIC_KEY"])
        parts = refresh_token.split('.')
        if len(parts) != 3:
            raise ValueError("Bad format")
        padding = 4 - len(parts[1]) % 4
        raw = _b64.urlsafe_b64decode(parts[1] + ('=' * padding if padding != 4 else ''))
        payload = _json.loads(raw)

        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        if payload["exp"] < int(time.time()):
            raise ValueError("Refresh token expired")

        r = get_redis()
        stored = r.get(f"refresh:{payload['jti']}")
        if not stored:
            raise ValueError("Refresh session not found")

        ip = request.remote_addr or ""
        ua = request.headers.get("User-Agent", "")

        # Rotate: invalidate old, issue new pair
        r.delete(f"refresh:{payload['jti']}")
        new_access = issue_access_token(payload["sub"], payload["role"], ip, ua)
        new_refresh = issue_refresh_token(payload["sub"], payload["role"], ip, ua)

        resp = make_response(jsonify({"access_token": new_access}))
        resp.set_cookie(
            "refresh_token", new_refresh,
            httponly=True, secure=True, samesite="Strict",
            max_age=current_app.config["JWT_REFRESH_EXPIRES"],
        )
        return resp, 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 401


# ─── Password reset ───────────────────────────────────────────────────────────

@auth_bp.post("/reset-password")
def reset_password_request():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400

    db = get_supabase()
    e_hash = _email_hash(email)
    result = db.table("users").select("id, email_enc").eq("email_hash", e_hash).execute()
    if not result.data:
        # Don't reveal whether email exists
        return jsonify({"message": "If that email exists, an OTP was sent"}), 200

    user = result.data[0]
    otp = generate_otp()
    r = get_redis()
    r.setex(f"reset:{e_hash}", _OTP_TTL, json.dumps({"user_id": user["id"], "otp": otp}))

    real_email = decrypt_field(user["email_enc"])
    send_otp_email(real_email, otp, "password reset")

    return jsonify({"message": "If that email exists, an OTP was sent"}), 200


@auth_bp.post("/reset-password/confirm")
def reset_password_confirm():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    otp_input = data.get("otp", "")
    new_password = data.get("new_password", "")

    if not all([email, otp_input, new_password]):
        return jsonify({"error": "Email, OTP, and new_password required"}), 400

    pw_error = _validate_password(new_password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    e_hash = _email_hash(email)
    r = get_redis()
    stored = r.get(f"reset:{e_hash}")
    if not stored:
        return jsonify({"error": "OTP expired or invalid"}), 401

    stored_data = json.loads(stored)
    if stored_data["otp"] != otp_input:
        return jsonify({"error": "Incorrect OTP"}), 401

    r.delete(f"reset:{e_hash}")

    pw_hash, salt = hash_password(new_password)
    db = get_supabase()
    db.table("users").update({"password_hash": pw_hash, "salt": salt}).eq(
        "id", stored_data["user_id"]
    ).execute()

    return jsonify({"message": "Password reset successfully"}), 200


# ─── Enable/disable 2FA ───────────────────────────────────────────────────────

@auth_bp.post("/2fa/enable")
@require_auth
def enable_2fa():
    db = get_supabase()
    user = db.table("users").select("email_enc").eq("id", g.user_id).execute().data[0]
    real_email = decrypt_field(user["email_enc"])

    otp = generate_otp()
    r = get_redis()
    r.setex(f"2fa_enable:{g.user_id}", _OTP_TTL, otp)
    send_otp_email(real_email, otp, "2FA activation")
    return jsonify({"message": "OTP sent to your email"}), 200


@auth_bp.post("/2fa/confirm")
@require_auth
def confirm_2fa():
    data = request.get_json(force=True)
    otp_input = data.get("otp", "")
    r = get_redis()
    stored_otp = r.get(f"2fa_enable:{g.user_id}")
    if not stored_otp or stored_otp != otp_input:
        return jsonify({"error": "Invalid or expired OTP"}), 401

    r.delete(f"2fa_enable:{g.user_id}")
    db = get_supabase()
    db.table("users").update({"two_fa_enabled": True}).eq("id", g.user_id).execute()
    return jsonify({"message": "2FA enabled"}), 200


@auth_bp.post("/2fa/disable")
@require_auth
def disable_2fa_request():
    db = get_supabase()
    user = db.table("users").select("email_enc, two_fa_enabled").eq("id", g.user_id).execute().data[0]
    if not user.get("two_fa_enabled"):
        return jsonify({"error": "2FA is not currently enabled"}), 400
    real_email = decrypt_field(user["email_enc"])

    otp = generate_otp()
    r = get_redis()
    r.setex(f"2fa_disable:{g.user_id}", _OTP_TTL, otp)
    send_otp_email(real_email, otp, "2FA deactivation")
    return jsonify({"message": "OTP sent to your email"}), 200


@auth_bp.post("/2fa/disable/confirm")
@require_auth
def disable_2fa_confirm():
    data = request.get_json(force=True)
    otp_input = data.get("otp", "")
    r = get_redis()
    stored_otp = r.get(f"2fa_disable:{g.user_id}")
    if not stored_otp or stored_otp != otp_input:
        return jsonify({"error": "Invalid or expired OTP"}), 401

    r.delete(f"2fa_disable:{g.user_id}")
    db = get_supabase()
    db.table("users").update({"two_fa_enabled": False}).eq("id", g.user_id).execute()
    return jsonify({"message": "2FA disabled"}), 200
