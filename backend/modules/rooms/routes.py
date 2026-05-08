"""
Research Rooms module: create, join, post, read posts.
Room posts are ECIES-encrypted per member — strictly asymmetric, no symmetric content key.
"""

import os
import uuid
import json
import base64
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g, current_app

from services.supabase_client import get_supabase
from middleware.session import require_auth
from middleware.rbac import require_role
from crypto.key_manager import (
    encrypt_field, decrypt_field,
    generate_room_key, wrap_room_key_for_member, unwrap_room_key,
    unwrap_user_private_keys,
)
from crypto.rsa_engine import deserialize_public_key
from crypto.ecc_engine import ecies_encrypt, ecies_decrypt, deserialize_ecc_public_key
from crypto.hmac_engine import compute_record_hmac

rooms_bp = Blueprint("rooms", __name__)


def _hmac_key() -> bytes:
    return current_app.config["HMAC_SECRET"].encode()


def _random_room_code() -> str:
    return base64.urlsafe_b64encode(os.urandom(6)).decode().replace("=", "")


def _ecies_encrypt_for_members(db, room_id: str, plaintext: bytes) -> str:
    """ECIES-encrypt plaintext for every current room member. Returns JSON {user_id: b64_ciphertext}."""
    members = db.table("room_members").select("user_id").eq("room_id", room_id).execute()
    result = {}
    for m in (members.data or []):
        uid = m["user_id"]
        user = db.table("users").select("public_key_ecc").eq("id", uid).execute()
        if user.data:
            ecc_pub = deserialize_ecc_public_key(user.data[0]["public_key_ecc"])
            result[uid] = base64.b64encode(ecies_encrypt(ecc_pub, plaintext)).decode()
    return json.dumps(result)


def _ecies_decrypt_for_user(content_enc: str, ecc_priv, user_id: str) -> bytes:
    """Decrypt this user's ECIES copy from a JSON content_enc map."""
    mapping = json.loads(content_enc)
    if user_id not in mapping:
        raise ValueError("No content available for this user")
    return ecies_decrypt(ecc_priv, base64.b64decode(mapping[user_id]))


# ─── Create room ──────────────────────────────────────────────────────────────

@rooms_bp.post("/create")
@require_auth
@require_role(["supervisor"])
def create_room():
    data = request.get_json(force=True)
    if not data.get("title"):
        return jsonify({"error": "Room title is required"}), 400

    db = get_supabase()

    # Fetch supervisor's RSA public key and private_key_enc
    user_row = db.table("users").select(
        "public_key_rsa, private_key_enc"
    ).eq("id", g.user_id).execute()
    if not user_row.data:
        return jsonify({"error": "User not found"}), 404

    user = user_row.data[0]
    sup_rsa_pub = deserialize_public_key(user["public_key_rsa"])

    # Generate room symmetric key
    room_key = generate_room_key()

    # Wrap room key for the supervisor (they are the first member)
    sup_room_key_enc = wrap_room_key_for_member(room_key, sup_rsa_pub)

    # Also wrap with server master RSA pub for the room row (central storage)
    from crypto.key_manager import get_master
    master_room_key_enc = wrap_room_key_for_member(room_key, get_master().rsa_pub)

    title_enc = encrypt_field(data["title"])
    desc_enc = encrypt_field(data.get("description", "")) if data.get("description") else None
    room_code = _random_room_code()

    hmac_val = compute_record_hmac(_hmac_key(), title_enc, desc_enc or "", room_code)

    room_row = {
        "supervisor_id": g.user_id,
        "title_enc": title_enc,
        "description_enc": desc_enc,
        "room_code": room_code,
        "room_key_enc": master_room_key_enc,
        "hmac": hmac_val,
    }
    result = db.table("research_rooms").insert(room_row).execute()
    room_id = result.data[0]["id"]

    # Add supervisor as member with their copy of the room key
    db.table("room_members").insert({
        "room_id": room_id,
        "user_id": g.user_id,
        "role": "supervisor",
        "room_key_enc": sup_room_key_enc,
    }).execute()

    return jsonify({"message": "Room created", "room_id": room_id, "room_code": room_code}), 201


# ─── Join room ────────────────────────────────────────────────────────────────

@rooms_bp.post("/join")
@require_auth
def join_room():
    data = request.get_json(force=True)
    room_code = data.get("room_code", "").strip()
    if not room_code:
        return jsonify({"error": "room_code required"}), 400

    db = get_supabase()
    room = db.table("research_rooms").select("id, room_key_enc").eq(
        "room_code", room_code
    ).execute()
    if not room.data:
        return jsonify({"error": "Invalid room code"}), 404

    room_id = room.data[0]["id"]

    # Check not already a member
    existing = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if existing.data:
        return jsonify({"error": "Already a member of this room"}), 409

    # Decrypt room key using server master private key
    from crypto.key_manager import get_master
    master_room_key_enc = room.data[0]["room_key_enc"]
    room_key = unwrap_room_key(master_room_key_enc, get_master().rsa_priv)

    # Wrap room key for this new member
    user_row = db.table("users").select("public_key_rsa").eq("id", g.user_id).execute()
    if not user_row.data:
        return jsonify({"error": "User not found"}), 404

    member_rsa_pub = deserialize_public_key(user_row.data[0]["public_key_rsa"])
    member_room_key_enc = wrap_room_key_for_member(room_key, member_rsa_pub)

    db.table("room_members").insert({
        "room_id": room_id,
        "user_id": g.user_id,
        "role": "member",
        "room_key_enc": member_room_key_enc,
    }).execute()

    # Notify room supervisor
    room_full = db.table("research_rooms").select("supervisor_id").eq("id", room_id).execute()
    if room_full.data:
        db.table("notifications").insert({
            "recipient_id": room_full.data[0]["supervisor_id"],
            "type": "room_invite",
            "payload_enc": encrypt_field(room_id),
        }).execute()

    return jsonify({"message": "Joined room", "room_id": room_id}), 200


# ─── Get room detail ──────────────────────────────────────────────────────────

@rooms_bp.get("/<room_id>")
@require_auth
def get_room(room_id: str):
    db = get_supabase()

    # Must be a member
    membership = db.table("room_members").select("role").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    room = db.table("research_rooms").select("*").eq("id", room_id).execute()
    if not room.data:
        return jsonify({"error": "Room not found"}), 404

    r = room.data[0]
    members = db.table("room_members").select(
        "user_id, role, joined_at"
    ).eq("room_id", room_id).execute()

    member_list = []
    for m in (members.data or []):
        u = db.table("users").select("username_enc, role").eq("id", m["user_id"]).execute()
        member_list.append({
            "user_id": m["user_id"],
            "username": decrypt_field(u.data[0]["username_enc"]) if u.data else "Unknown",
            "room_role": m["role"],
            "joined_at": m["joined_at"],
        })

    return jsonify({
        "id": r["id"],
        "title": decrypt_field(r["title_enc"]),
        "description": decrypt_field(r["description_enc"]) if r.get("description_enc") else None,
        "room_code": r["room_code"],
        "supervisor_id": r["supervisor_id"],
        "created_at": r["created_at"],
        "members": member_list,
        "my_role": membership.data[0]["role"],
    }), 200


# ─── List my rooms ────────────────────────────────────────────────────────────

@rooms_bp.get("")
@require_auth
def list_my_rooms():
    db = get_supabase()
    memberships = db.table("room_members").select("room_id, role").eq(
        "user_id", g.user_id
    ).execute()

    result = []
    for m in (memberships.data or []):
        room = db.table("research_rooms").select(
            "id, title_enc, room_code, supervisor_id, created_at"
        ).eq("id", m["room_id"]).execute()
        if room.data:
            r = room.data[0]
            result.append({
                "id": r["id"],
                "title": decrypt_field(r["title_enc"]),
                "room_code": r["room_code"],
                "supervisor_id": r["supervisor_id"],
                "my_role": m["role"],
                "created_at": r["created_at"],
            })
    return jsonify(result), 200


# ─── Post to a room section ───────────────────────────────────────────────────

@rooms_bp.post("/<room_id>/post")
@require_auth
def post_to_room(room_id: str):
    data = request.get_json(force=True)
    section = data.get("section", "")
    content = data.get("content", "")

    if section not in ("updates", "data", "results"):
        return jsonify({"error": "section must be updates, data, or results"}), 400
    if not content:
        return jsonify({"error": "Content is required"}), 400

    db = get_supabase()

    # Must be a member
    membership = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    content_enc = _ecies_encrypt_for_members(db, room_id, content.encode())

    image_url = data.get("image_url", "")
    pdf_url = data.get("pdf_url", "")
    atts = {}
    if image_url:
        atts["image_url"] = image_url
    if pdf_url:
        atts["pdf_url"] = pdf_url
    attachments_enc = _ecies_encrypt_for_members(db, room_id, json.dumps(atts).encode()) if atts else None

    hmac_val = compute_record_hmac(_hmac_key(), content_enc, section, room_id)

    row = {
        "room_id": room_id,
        "author_id": g.user_id,
        "section": section,
        "content_enc": content_enc,
        "attachments_enc": attachments_enc,
        "hmac": hmac_val,
    }
    result = db.table("room_posts").insert(row).execute()
    return jsonify({"message": "Post created", "id": result.data[0]["id"]}), 201


# ─── Fetch posts from a room section ─────────────────────────────────────────

@rooms_bp.get("/<room_id>/posts")
@require_auth
def get_room_posts(room_id: str):
    section = request.args.get("section", "")
    if section and section not in ("updates", "data", "results", "announcements"):
        return jsonify({"error": "Invalid section"}), 400

    db = get_supabase()

    # Must be a member
    membership = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    # Unwrap this user's ECC private key for ECIES decryption
    user_row = db.table("users").select("private_key_enc").eq("id", g.user_id).execute()
    _, ecc_priv = unwrap_user_private_keys(user_row.data[0]["private_key_enc"])

    query = db.table("room_posts").select("*").eq("room_id", room_id)
    if section:
        query = query.eq("section", section)
    posts_result = query.order("created_at", desc=False).execute()

    result = []
    for post in (posts_result.data or []):
        try:
            content = _ecies_decrypt_for_user(post["content_enc"], ecc_priv, g.user_id).decode()
        except Exception:
            content = "[decryption error]"

        image_url = None
        pdf_url = None
        if post.get("attachments_enc"):
            try:
                atts = json.loads(_ecies_decrypt_for_user(post["attachments_enc"], ecc_priv, g.user_id).decode())
                image_url = atts.get("image_url")
                pdf_url = atts.get("pdf_url")
            except Exception:
                pass

        author = db.table("users").select("username_enc").eq("id", post["author_id"]).execute()
        author_name = decrypt_field(author.data[0]["username_enc"]) if author.data else "Unknown"

        result.append({
            "id": post["id"],
            "section": post["section"],
            "content": content,
            "image_url": image_url,
            "pdf_url": pdf_url,
            "author_id": post["author_id"],
            "author_name": author_name,
            "created_at": post["created_at"],
        })

    return jsonify(result), 200


# ─── Edit a post ─────────────────────────────────────────────────────────────

@rooms_bp.put("/<room_id>/posts/<post_id>")
@require_auth
def edit_room_post(room_id: str, post_id: str):
    data = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Content cannot be empty"}), 400

    db = get_supabase()

    membership = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    post = db.table("room_posts").select("author_id, section").eq(
        "id", post_id
    ).eq("room_id", room_id).execute()
    if not post.data:
        return jsonify({"error": "Post not found"}), 404
    if post.data[0]["author_id"] != g.user_id:
        return jsonify({"error": "You can only edit your own posts"}), 403
    if post.data[0]["section"] == "announcements":
        return jsonify({"error": "Announcements cannot be edited"}), 400

    section = post.data[0]["section"]
    content_enc = _ecies_encrypt_for_members(db, room_id, content.encode())
    hmac_val = compute_record_hmac(_hmac_key(), content_enc, section, room_id)

    db.table("room_posts").update({
        "content_enc": content_enc,
        "hmac": hmac_val,
    }).eq("id", post_id).execute()

    return jsonify({"message": "Post updated"}), 200


# ─── Post announcement (supervisor only, notifies all members) ───────────────

@rooms_bp.post("/<room_id>/announce")
@require_auth
def post_announcement(room_id: str):
    data = request.get_json(force=True)
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content is required"}), 400

    db = get_supabase()

    membership = db.table("room_members").select("role").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403
    if membership.data[0]["role"] != "supervisor":
        return jsonify({"error": "Only supervisors can post announcements"}), 403

    content_enc = _ecies_encrypt_for_members(db, room_id, content.encode())
    hmac_val = compute_record_hmac(_hmac_key(), content_enc, "announcements", room_id)

    result = db.table("room_posts").insert({
        "room_id": room_id,
        "author_id": g.user_id,
        "section": "announcements",
        "content_enc": content_enc,
        "hmac": hmac_val,
    }).execute()

    # Notify every other room member
    members = db.table("room_members").select("user_id").eq(
        "room_id", room_id
    ).neq("user_id", g.user_id).execute()
    for m in (members.data or []):
        db.table("notifications").insert({
            "recipient_id": m["user_id"],
            "type": "room_announcement",
            "payload_enc": encrypt_field(room_id),
        }).execute()

    return jsonify({"message": "Announcement posted", "id": result.data[0]["id"]}), 201


# ─── Room analytics (supervisor only) ────────────────────────────────────────

@rooms_bp.get("/<room_id>/analytics")
@require_auth
def get_room_analytics(room_id: str):
    """
    Aggregate post metadata for supervisor analytics.
    Never decrypts post content — operates on counts and timestamps only.
    """
    db = get_supabase()

    membership = db.table("room_members").select("role").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403
    if membership.data[0]["role"] != "supervisor":
        return jsonify({"error": "Analytics available to supervisors only"}), 403

    # Fetch all post metadata (no content decryption)
    posts_result = db.table("room_posts").select(
        "id, author_id, section, created_at"
    ).eq("room_id", room_id).execute()
    all_posts = posts_result.data or []

    # Per-member contribution counts
    member_counts: dict = {}
    for p in all_posts:
        aid = p["author_id"]
        member_counts[aid] = member_counts.get(aid, 0) + 1

    members_result = db.table("room_members").select("user_id").eq("room_id", room_id).execute()
    member_contributions = []
    for m in (members_result.data or []):
        uid = m["user_id"]
        u = db.table("users").select("username_enc").eq("id", uid).execute()
        username = decrypt_field(u.data[0]["username_enc"]) if u.data else "Unknown"
        member_contributions.append({
            "user_id": uid,
            "username": username,
            "post_count": member_counts.get(uid, 0),
        })
    member_contributions.sort(key=lambda x: x["post_count"], reverse=True)

    # Per-section breakdown
    section_counts = {"updates": 0, "data": 0, "results": 0}
    for p in all_posts:
        section_counts[p["section"]] = section_counts.get(p["section"], 0) + 1

    # Activity timeline — posts per day for the last 30 days
    now = datetime.now(timezone.utc)
    day_counts: dict = {}
    for p in all_posts:
        day = p["created_at"][:10]  # "YYYY-MM-DD"
        day_counts[day] = day_counts.get(day, 0) + 1

    timeline = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append({"date": d, "count": day_counts.get(d, 0)})

    report = {
        "room_id": room_id,
        "total_posts": len(all_posts),
        "member_contributions": member_contributions,
        "section_counts": section_counts,
        "timeline": timeline,
        "generated_at": now.isoformat(),
    }

    # HMAC over canonical JSON for download integrity verification
    report_hmac = compute_record_hmac(
        _hmac_key(), json.dumps(report, sort_keys=True)
    )
    report["report_hmac"] = report_hmac

    return jsonify(report), 200


# ─── Upload image to a room section ──────────────────────────────────────────

ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}

@rooms_bp.post("/<room_id>/upload-image")
@require_auth
def upload_room_image(room_id: str):
    db = get_supabase()

    membership = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    f = request.files["image"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_IMAGE_EXTS:
        return jsonify({"error": "File must be jpg, png, gif, or webp"}), 400

    path = f"rooms/{room_id}/{uuid.uuid4().hex}.{ext}"
    file_data = f.read()
    content_type = f.content_type or f"image/{ext}"

    try:
        # Ensure bucket exists (creates it on first use)
        existing = [b.name for b in db.storage.list_buckets()]
        if "publications" not in existing:
            db.storage.create_bucket("publications", options={"public": True})

        bucket = db.storage.from_("publications")
        bucket.upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        image_url = bucket.get_public_url(path)
        if not isinstance(image_url, str):
            image_url = str(image_url)
        return jsonify({"image_url": image_url}), 200
    except Exception as e:
        current_app.logger.error("Image upload failed: %s", e)
        return jsonify({"error": str(e)}), 500


# ─── Upload PDF to the updates section ───────────────────────────────────────

@rooms_bp.post("/<room_id>/upload-pdf")
@require_auth
def upload_room_pdf(room_id: str):
    db = get_supabase()

    membership = db.table("room_members").select("id").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403

    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    f = request.files["pdf"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext != "pdf":
        return jsonify({"error": "File must be a PDF"}), 400

    path = f"rooms/{room_id}/pdfs/{uuid.uuid4().hex}.pdf"
    file_data = f.read()

    try:
        existing = [b.name for b in db.storage.list_buckets()]
        if "publications" not in existing:
            db.storage.create_bucket("publications", options={"public": True})

        bucket = db.storage.from_("publications")
        bucket.upload(
            path=path,
            file=file_data,
            file_options={"content-type": "application/pdf", "upsert": "false"},
        )
        pdf_url = bucket.get_public_url(path)
        if not isinstance(pdf_url, str):
            pdf_url = str(pdf_url)
        return jsonify({"pdf_url": pdf_url}), 200
    except Exception as e:
        current_app.logger.error("PDF upload failed: %s", e)
        return jsonify({"error": str(e)}), 500


# ─── Analytics: full post content for PDF report (supervisor only) ────────────

@rooms_bp.get("/<room_id>/analytics/posts")
@require_auth
def get_analytics_posts(room_id: str):
    db = get_supabase()

    membership = db.table("room_members").select("role").eq(
        "room_id", room_id
    ).eq("user_id", g.user_id).execute()
    if not membership.data:
        return jsonify({"error": "Not a room member"}), 403
    if membership.data[0]["role"] != "supervisor":
        return jsonify({"error": "Supervisor access only"}), 403

    user_row = db.table("users").select("private_key_enc").eq("id", g.user_id).execute()
    _, ecc_priv = unwrap_user_private_keys(user_row.data[0]["private_key_enc"])

    posts_result = db.table("room_posts").select("*").eq(
        "room_id", room_id
    ).order("created_at", desc=False).execute()

    result = []
    for post in (posts_result.data or []):
        try:
            content = _ecies_decrypt_for_user(post["content_enc"], ecc_priv, g.user_id).decode()
        except Exception:
            content = "[encrypted]"
        author = db.table("users").select("username_enc").eq("id", post["author_id"]).execute()
        author_name = decrypt_field(author.data[0]["username_enc"]) if author.data else "Unknown"
        result.append({
            "section": post["section"],
            "author_name": author_name,
            "content": content,
            "created_at": post["created_at"],
        })

    room_row = db.table("research_rooms").select("title_enc").eq("id", room_id).execute()
    room_title = decrypt_field(room_row.data[0]["title_enc"]) if room_row.data else "Research Room"

    return jsonify({
        "room_title": room_title,
        "posts": result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }), 200
