"""
Users / Profile module: get own profile, get other profiles, update profile.
Publications are included here as nested resources.
"""

import os
import base64
from flask import Blueprint, request, jsonify, g

from services.supabase_client import get_supabase
from middleware.session import require_auth
from middleware.rbac import can_upload, require_role
from crypto.key_manager import encrypt_field, decrypt_field, unwrap_user_private_keys
from crypto.rsa_engine import rsa_sign, rsa_verify, deserialize_public_key
from crypto.hmac_engine import compute_record_hmac, verify_record_hmac
from flask import current_app

users_bp = Blueprint("users", __name__)


def _hmac_key() -> bytes:
    return current_app.config["HMAC_SECRET"].encode()


def _get_verification(pub_id: str, db) -> dict | None:
    """Return verification data for a publication, or None if no record exists."""
    row = db.table("credential_verifications").select(
        "status, verifier_id, verified_at"
    ).eq("publication_id", pub_id).execute()
    if not row.data:
        return None
    v = row.data[0]
    verifier_name = None
    if v.get("verifier_id"):
        vr = db.table("users").select("username_enc").eq("id", v["verifier_id"]).execute()
        if vr.data:
            verifier_name = decrypt_field(vr.data[0]["username_enc"])
    return {
        "status": v["status"],
        "verifier_id": v["verifier_id"],
        "verifier_name": verifier_name,
        "verified_at": v["verified_at"],
    }


def _decrypt_user(row: dict) -> dict:
    """Decrypt a user row's encrypted fields and return a clean dict."""
    return {
        "id": row["id"],
        "role": row["role"],
        "username": decrypt_field(row["username_enc"]),
        "public_key_rsa": row["public_key_rsa"],
        "public_key_ecc": row["public_key_ecc"],
        "two_fa_enabled": row.get("two_fa_enabled", False),
        "is_available": row.get("is_available", True),
        "created_at": row.get("created_at"),
    }


def _decrypt_profile(row: dict) -> dict:
    def safe_dec(val):
        return decrypt_field(val) if val else None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "bio": safe_dec(row.get("bio_enc")),
        "university": safe_dec(row.get("university_enc")) or row.get("university_plaintext"),
        "department": safe_dec(row.get("department_enc")),
        "academic_credentials": safe_dec(row.get("academic_credentials_enc")),
        "work_experience": safe_dec(row.get("work_experience_enc")),
        "google_scholar_url": safe_dec(row.get("google_scholar_url_enc")),
        "research_interests": safe_dec(row.get("research_interest_enc")),
        "profile_pic_url": row.get("profile_pic_url"),
        "updated_at": row.get("updated_at"),
    }


# ─── Own profile ──────────────────────────────────────────────────────────────

@users_bp.get("/me")
@require_auth
def get_me():
    db = get_supabase()
    user_row = db.table("users").select(
        "id, role, username_enc, public_key_rsa, public_key_ecc, two_fa_enabled, is_available, created_at"
    ).eq("id", g.user_id).execute()

    if not user_row.data:
        return jsonify({"error": "User not found"}), 404

    profile_row = db.table("profiles").select("*").eq("user_id", g.user_id).execute()

    user_data = _decrypt_user(user_row.data[0])
    profile_data = _decrypt_profile(profile_row.data[0]) if profile_row.data else {}

    pubs = db.table("publications").select(
        "id, title_enc, abstract_enc, file_url, published_year_enc, created_at"
    ).eq("user_id", g.user_id).execute()

    publications = []
    for pub in (pubs.data or []):
        publications.append({
            "id": pub["id"],
            "title": decrypt_field(pub["title_enc"]),
            "abstract": decrypt_field(pub["abstract_enc"]) if pub.get("abstract_enc") else None,
            "file_url": pub.get("file_url"),
            "published_year": decrypt_field(pub["published_year_enc"]) if pub.get("published_year_enc") else None,
            "created_at": pub["created_at"],
            "verification": _get_verification(pub["id"], db),
        })

    return jsonify({**user_data, "profile": profile_data, "publications": publications}), 200


# ─── Get other user's profile ─────────────────────────────────────────────────

@users_bp.get("/<user_id>")
@require_auth
def get_user(user_id: str):
    db = get_supabase()
    user_row = db.table("users").select(
        "id, role, username_enc, public_key_rsa, public_key_ecc, is_available, created_at"
    ).eq("id", user_id).execute()

    if not user_row.data:
        return jsonify({"error": "User not found"}), 404

    profile_row = db.table("profiles").select("*").eq("user_id", user_id).execute()

    user_data = _decrypt_user(user_row.data[0])
    profile_data = _decrypt_profile(profile_row.data[0]) if profile_row.data else {}

    # Only include publications that are public
    pubs = db.table("publications").select(
        "id, title_enc, abstract_enc, file_url, published_year_enc, created_at"
    ).eq("user_id", user_id).execute()

    publications = []
    for pub in (pubs.data or []):
        publications.append({
            "id": pub["id"],
            "title": decrypt_field(pub["title_enc"]),
            "abstract": decrypt_field(pub["abstract_enc"]) if pub.get("abstract_enc") else None,
            "file_url": pub.get("file_url"),
            "published_year": decrypt_field(pub["published_year_enc"]) if pub.get("published_year_enc") else None,
            "created_at": pub["created_at"],
            "verification": _get_verification(pub["id"], db),
        })

    return jsonify({**user_data, "profile": profile_data, "publications": publications}), 200


# ─── Update own profile ───────────────────────────────────────────────────────

@users_bp.put("/profile")
@require_auth
def update_profile():
    data = request.get_json(force=True)
    db = get_supabase()

    def enc(val):
        return encrypt_field(val) if val else None

    fields_to_update = {}
    plaintext_university = None

    if "bio" in data:
        fields_to_update["bio_enc"] = enc(data["bio"])
    if "university" in data:
        fields_to_update["university_enc"] = enc(data["university"])
        fields_to_update["university_plaintext"] = data["university"]
        plaintext_university = data["university"]
    if "department" in data:
        fields_to_update["department_enc"] = enc(data["department"])
    if "academic_credentials" in data:
        fields_to_update["academic_credentials_enc"] = enc(data["academic_credentials"])
    if "work_experience" in data:
        fields_to_update["work_experience_enc"] = enc(data["work_experience"])
    if "google_scholar_url" in data:
        fields_to_update["google_scholar_url_enc"] = enc(data["google_scholar_url"])
    if "research_interests" in data:
        fields_to_update["research_interest_enc"] = enc(data["research_interests"])

    if fields_to_update:
        enc_vals = [v for v in fields_to_update.values() if v]
        fields_to_update["hmac"] = compute_record_hmac(_hmac_key(), *enc_vals)
        db.table("profiles").update(fields_to_update).eq("user_id", g.user_id).execute()

    # Handle username update on users table
    if "username" in data:
        username_enc = encrypt_field(data["username"])
        db.table("users").update({"username_enc": username_enc}).eq("id", g.user_id).execute()

    return jsonify({"message": "Profile updated"}), 200


# ─── Upload profile picture ───────────────────────────────────────────────────

@users_bp.post("/profile/picture")
@require_auth
def upload_profile_picture():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        return jsonify({"error": "Only JPEG/PNG/WebP allowed"}), 400

    db = get_supabase()
    file_bytes = file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower()
    path = f"avatars/{g.user_id}.{ext}"

    # Upload to Supabase Storage
    storage = db.storage.from_("profile-pictures")
    storage.upload(path, file_bytes, {"content-type": file.content_type, "upsert": "true"})
    public_url = storage.get_public_url(path)

    db.table("profiles").update({"profile_pic_url": public_url}).eq("user_id", g.user_id).execute()
    return jsonify({"profile_pic_url": public_url}), 200


# ─── Publications ─────────────────────────────────────────────────────────────

@users_bp.post("/publications")
@require_auth
@can_upload
def create_publication():
    data = request.get_json(force=True)
    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    db = get_supabase()
    title_enc = encrypt_field(data["title"])
    abstract_enc = encrypt_field(data["abstract"]) if data.get("abstract") else None
    year_enc = encrypt_field(str(data["published_year"])) if data.get("published_year") else None

    hmac_val = compute_record_hmac(_hmac_key(), title_enc, abstract_enc or "", year_enc or "")

    row = {
        "user_id": g.user_id,
        "title_enc": title_enc,
        "abstract_enc": abstract_enc,
        "published_year_enc": year_enc,
        "hmac": hmac_val,
    }
    result = db.table("publications").insert(row).execute()
    pub_id = result.data[0]["id"]

    return jsonify({"message": "Publication created", "id": pub_id}), 201


@users_bp.post("/publications/<pub_id>/file")
@require_auth
def upload_publication_file(pub_id: str):
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF allowed"}), 400

    db = get_supabase()
    # Verify ownership
    pub = db.table("publications").select("id").eq("id", pub_id).eq("user_id", g.user_id).execute()
    if not pub.data:
        return jsonify({"error": "Publication not found or not yours"}), 404

    storage = db.storage.from_("publications")
    path = f"{g.user_id}/{pub_id}.pdf"
    storage.upload(path, file.read(), {"content-type": "application/pdf", "upsert": "true"})
    public_url = storage.get_public_url(path)

    db.table("publications").update({"file_url": public_url}).eq("id", pub_id).execute()
    return jsonify({"file_url": public_url}), 200


@users_bp.get("/<user_id>/publications")
@require_auth
def list_publications(user_id: str):
    db = get_supabase()
    pubs = db.table("publications").select(
        "id, title_enc, abstract_enc, file_url, published_year_enc, created_at"
    ).eq("user_id", user_id).execute()

    result = []
    for pub in (pubs.data or []):
        result.append({
            "id": pub["id"],
            "title": decrypt_field(pub["title_enc"]),
            "abstract": decrypt_field(pub["abstract_enc"]) if pub.get("abstract_enc") else None,
            "file_url": pub.get("file_url"),
            "published_year": decrypt_field(pub["published_year_enc"]) if pub.get("published_year_enc") else None,
            "created_at": pub["created_at"],
        })
    return jsonify(result), 200


# ─── Credential Verification ─────────────────────────────────────────────────

@users_bp.post("/publications/<pub_id>/request-verification")
@require_auth
@require_role(["postgrad", "undergraduate"])
def request_credential_verification(pub_id: str):
    """Researcher requests a supervisor/admin to verify one of their publications."""
    data = request.get_json(force=True) or {}
    verifier_id = data.get("verifier_id", "").strip()
    if not verifier_id:
        return jsonify({"error": "verifier_id required"}), 400

    db = get_supabase()

    # Must own the publication
    pub = db.table("publications").select("id").eq("id", pub_id).eq("user_id", g.user_id).execute()
    if not pub.data:
        return jsonify({"error": "Publication not found or not yours"}), 404

    # Verifier must be supervisor or admin
    verifier = db.table("users").select("id, role").eq("id", verifier_id).execute()
    if not verifier.data or verifier.data[0]["role"] not in ("supervisor", "admin"):
        return jsonify({"error": "Verifier must be a supervisor or admin"}), 400

    # Check existing verification record
    existing = db.table("credential_verifications").select("id, status").eq(
        "publication_id", pub_id
    ).execute()
    if existing.data:
        status = existing.data[0]["status"]
        if status == "verified":
            return jsonify({"error": "Credential already verified"}), 409
        if status == "pending":
            return jsonify({"error": "Verification request already pending"}), 409
        # Rejected — allow re-request by deleting old row
        db.table("credential_verifications").delete().eq("id", existing.data[0]["id"]).execute()

    db.table("credential_verifications").insert({
        "publication_id": pub_id,
        "requester_id": g.user_id,
        "verifier_id": verifier_id,
        "status": "pending",
    }).execute()

    db.table("notifications").insert({
        "recipient_id": verifier_id,
        "type": "credential_verification_request",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()

    return jsonify({"message": "Verification request sent"}), 201


@users_bp.put("/publications/<pub_id>/sign")
@require_auth
def sign_credential(pub_id: str):
    """Verifier signs a pending credential with their RSA private key."""
    db = get_supabase()

    # Caller must be supervisor or admin
    caller = db.table("users").select("role, private_key_enc").eq("id", g.user_id).execute()
    if not caller.data or caller.data[0]["role"] not in ("supervisor", "admin"):
        return jsonify({"error": "Only supervisors and admins can verify credentials"}), 403

    # Find the pending request assigned to this verifier
    verif = db.table("credential_verifications").select("*").eq(
        "publication_id", pub_id
    ).eq("verifier_id", g.user_id).eq("status", "pending").execute()
    if not verif.data:
        return jsonify({"error": "No pending verification request for this publication"}), 404

    verif_row = verif.data[0]

    # Unwrap verifier's RSA private key from server-wrapped store
    rsa_priv, _ = unwrap_user_private_keys(caller.data[0]["private_key_enc"])

    # Sign: binds signature to both the publication ID and this specific verifier
    message = f"credential:{pub_id}:{g.user_id}".encode()
    sig_bytes = rsa_sign(rsa_priv, message)
    sig_b64 = base64.b64encode(sig_bytes).decode()

    from datetime import datetime, timezone
    verified_at = datetime.now(timezone.utc).isoformat()

    db.table("credential_verifications").update({
        "status": "verified",
        "signature_b64": sig_b64,
        "verified_at": verified_at,
    }).eq("id", verif_row["id"]).execute()

    db.table("notifications").insert({
        "recipient_id": verif_row["requester_id"],
        "type": "credential_verified",
        "payload_enc": encrypt_field(pub_id),
    }).execute()

    return jsonify({"message": "Credential signed and verified"}), 200


@users_bp.get("/publications/<pub_id>/verify")
@require_auth
def verify_credential(pub_id: str):
    """Re-verify the RSA-PSS signature on a credential and return the result."""
    db = get_supabase()

    verif = db.table("credential_verifications").select("*").eq(
        "publication_id", pub_id
    ).execute()

    if not verif.data or verif.data[0]["status"] != "verified":
        status = verif.data[0]["status"] if verif.data else "none"
        return jsonify({"is_verified": False, "status": status}), 200

    row = verif.data[0]

    verifier_row = db.table("users").select("public_key_rsa, username_enc").eq(
        "id", row["verifier_id"]
    ).execute()
    if not verifier_row.data:
        return jsonify({"is_verified": False, "status": "verifier_not_found"}), 200

    verifier_pub = deserialize_public_key(verifier_row.data[0]["public_key_rsa"])
    message = f"credential:{pub_id}:{row['verifier_id']}".encode()
    sig_bytes = base64.b64decode(row["signature_b64"])

    try:
        is_valid = rsa_verify(verifier_pub, message, sig_bytes)
    except Exception:
        is_valid = False

    verifier_name = decrypt_field(verifier_row.data[0]["username_enc"])

    return jsonify({
        "is_verified": is_valid,
        "status": "verified" if is_valid else "signature_invalid",
        "verifier_id": row["verifier_id"],
        "verifier_name": verifier_name,
        "verified_at": row["verified_at"],
    }), 200


# ─── Supervisor availability ──────────────────────────────────────────────────

@users_bp.put("/availability")
@require_auth
def set_availability():
    db = get_supabase()
    user = db.table("users").select("role").eq("id", g.user_id).execute()
    if not user.data or user.data[0]["role"] != "supervisor":
        return jsonify({"error": "Only supervisors can set availability"}), 403

    data = request.get_json(force=True)
    is_available = bool(data.get("is_available", True))
    db.table("users").update({"is_available": is_available}).eq("id", g.user_id).execute()
    return jsonify({"is_available": is_available}), 200


