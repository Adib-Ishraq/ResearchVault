"""
Search module: discover universities, supervisors, and researchers.
Searches on plaintext index columns only; full data decrypted after access check.
"""

from flask import Blueprint, request, jsonify

from services.supabase_client import get_supabase
from middleware.session import require_auth
from crypto.key_manager import decrypt_field

search_bp = Blueprint("search", __name__)


@search_bp.get("/universities")
@require_auth
def list_universities():
    """Return distinct university names for the left-panel filter."""
    db = get_supabase()
    rows = db.table("profiles").select("university_plaintext").execute()
    universities = sorted({
        r["university_plaintext"]
        for r in (rows.data or [])
        if r.get("university_plaintext")
    })
    return jsonify(universities), 200


@search_bp.get("/supervisors")
@require_auth
def search_supervisors():
    """
    GET /api/search/supervisors?university=X&name=Y
    Filters supervisors by university (plaintext index), then decrypts names for display.
    """
    university = request.args.get("university", "").strip()
    name_query = request.args.get("name", "").strip().lower()

    db = get_supabase()

    # Start with supervisors
    query = db.table("users").select(
        "id, username_enc, role, public_key_ecc"
    ).eq("role", "supervisor")

    users_result = query.execute()
    supervisors = users_result.data or []

    # Filter by university via profiles table
    if university:
        profile_rows = db.table("profiles").select("user_id").eq(
            "university_plaintext", university
        ).execute()
        university_user_ids = {r["user_id"] for r in (profile_rows.data or [])}
        supervisors = [s for s in supervisors if s["id"] in university_user_ids]

    # Decrypt and optionally filter by name
    result = []
    profile_ids = [s["id"] for s in supervisors]

    # Batch fetch profiles
    profiles_map = {}
    if profile_ids:
        p_rows = db.table("profiles").select(
            "user_id, university_plaintext, profile_pic_url, research_interest_enc, bio_enc"
        ).in_("user_id", profile_ids).execute()
        for p in (p_rows.data or []):
            profiles_map[p["user_id"]] = p

    for sup in supervisors:
        username = decrypt_field(sup["username_enc"])
        if name_query and name_query not in username.lower():
            continue

        profile = profiles_map.get(sup["id"], {})
        result.append({
            "id": sup["id"],
            "username": username,
            "role": sup["role"],
            "university": profile.get("university_plaintext"),
            "profile_pic_url": profile.get("profile_pic_url"),
            "research_interests": decrypt_field(profile["research_interest_enc"])
                if profile.get("research_interest_enc") else None,
            "bio_snippet": (decrypt_field(profile["bio_enc"])[:200]
                if profile.get("bio_enc") else None),
        })

    return jsonify(result), 200


@search_bp.get("/researchers")
@require_auth
def search_researchers():
    """
    GET /api/search/researchers?university=X&name=Y&role=postgrad
    """
    university = request.args.get("university", "").strip()
    name_query = request.args.get("name", "").strip().lower()
    role_filter = request.args.get("role", "").strip()

    db = get_supabase()

    query = db.table("users").select("id, username_enc, role, public_key_ecc")
    if role_filter in ("postgrad", "undergraduate", "supervisor"):
        query = query.eq("role", role_filter)
    else:
        query = query.in_("role", ["supervisor", "postgrad", "undergraduate"])

    users_result = query.execute()
    researchers = users_result.data or []

    if university:
        profile_rows = db.table("profiles").select("user_id").eq(
            "university_plaintext", university
        ).execute()
        university_user_ids = {r["user_id"] for r in (profile_rows.data or [])}
        researchers = [r for r in researchers if r["id"] in university_user_ids]

    profile_ids = [r["id"] for r in researchers]
    profiles_map = {}
    if profile_ids:
        p_rows = db.table("profiles").select(
            "user_id, university_plaintext, profile_pic_url, research_interest_enc"
        ).in_("user_id", profile_ids).execute()
        for p in (p_rows.data or []):
            profiles_map[p["user_id"]] = p

    result = []
    for res in researchers:
        username = decrypt_field(res["username_enc"])
        if name_query and name_query not in username.lower():
            continue
        profile = profiles_map.get(res["id"], {})
        result.append({
            "id": res["id"],
            "username": username,
            "role": res["role"],
            "university": profile.get("university_plaintext"),
            "profile_pic_url": profile.get("profile_pic_url"),
            "research_interests": decrypt_field(profile["research_interest_enc"])
                if profile.get("research_interest_enc") else None,
        })

    return jsonify(result), 200
