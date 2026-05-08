"""
Direct messaging module.
Each message is ECIES-encrypted for both conversation participants — strictly asymmetric.
No symmetric key is used for content encryption.
"""

import os
import json
import base64
from flask import Blueprint, request, jsonify, g, current_app

from services.supabase_client import get_supabase
from middleware.session import require_auth
from crypto.key_manager import (
    wrap_room_key_for_member,
    unwrap_user_private_keys,
    decrypt_field,
)
from crypto.rsa_engine import deserialize_public_key
from crypto.ecc_engine import ecies_encrypt, ecies_decrypt, deserialize_ecc_public_key
from crypto.hmac_engine import compute_record_hmac, verify_record_hmac

messages_bp = Blueprint("messages", __name__)


def _hmac_key() -> bytes:
    return current_app.config["HMAC_SECRET"].encode()


def _ecies_encrypt_for_participants(conv: dict, plaintext: bytes, db) -> str:
    """ECIES-encrypt plaintext for both conversation participants. Returns JSON {uid: b64_ct}."""
    result = {}
    for uid in [conv["participant_a"], conv["participant_b"]]:
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


def _peer_id(conv: dict, my_id: str) -> str:
    return conv["participant_b"] if conv["participant_a"] == my_id else conv["participant_a"]


def _username(user_id: str, db) -> str:
    row = db.table("users").select("username_enc").eq("id", user_id).execute()
    if row.data:
        return decrypt_field(row.data[0]["username_enc"])
    return "Unknown"


# ─── List conversations ───────────────────────────────────────────────────────

@messages_bp.get("/conversations")
@require_auth
def list_conversations():
    db = get_supabase()

    rows = db.table("conversations").select("*").or_(
        f"participant_a.eq.{g.user_id},participant_b.eq.{g.user_id}"
    ).order("created_at", desc=True).execute()

    result = []
    for conv in (rows.data or []):
        peer = _peer_id(conv, g.user_id)
        peer_name = _username(peer, db)

        last = db.table("messages").select("created_at").eq(
            "conversation_id", conv["id"]
        ).order("created_at", desc=True).limit(1).execute()

        result.append({
            "id": conv["id"],
            "peer_id": peer,
            "peer_name": peer_name,
            "created_at": conv["created_at"],
            "last_message_at": last.data[0]["created_at"] if last.data else conv["created_at"],
        })

    result.sort(key=lambda c: c["last_message_at"], reverse=True)
    return jsonify(result), 200


# ─── Start or retrieve a conversation ────────────────────────────────────────

@messages_bp.post("/conversations/<peer_id>")
@require_auth
def get_or_create_conversation(peer_id: str):
    if peer_id == g.user_id:
        return jsonify({"error": "Cannot message yourself"}), 400

    db = get_supabase()

    peer_row = db.table("users").select("id, public_key_rsa").eq("id", peer_id).execute()
    if not peer_row.data:
        return jsonify({"error": "User not found"}), 404

    # Canonical ordering so (A,B) and (B,A) map to the same row
    a, b = sorted([g.user_id, peer_id])

    existing = db.table("conversations").select("id").eq("participant_a", a).eq(
        "participant_b", b
    ).execute()
    if existing.data:
        return jsonify({"id": existing.data[0]["id"]}), 200

    my_row = db.table("users").select("public_key_rsa").eq("id", g.user_id).execute()
    if not my_row.data:
        return jsonify({"error": "Your user record not found"}), 500

    # Store RSA-wrapped keys in the conversations row (schema requirement).
    # Message content itself is ECIES-encrypted per message — not via this key.
    placeholder_key = os.urandom(32)
    rsa_pub_a = deserialize_public_key(
        my_row.data[0]["public_key_rsa"] if a == g.user_id
        else peer_row.data[0]["public_key_rsa"]
    )
    rsa_pub_b = deserialize_public_key(
        peer_row.data[0]["public_key_rsa"] if b == peer_id
        else my_row.data[0]["public_key_rsa"]
    )

    result = db.table("conversations").insert({
        "participant_a": a,
        "participant_b": b,
        "conv_key_enc_a": wrap_room_key_for_member(placeholder_key, rsa_pub_a),
        "conv_key_enc_b": wrap_room_key_for_member(placeholder_key, rsa_pub_b),
    }).execute()

    return jsonify({"id": result.data[0]["id"]}), 201


# ─── Fetch messages ───────────────────────────────────────────────────────────

@messages_bp.get("/conversations/<conv_id>/messages")
@require_auth
def get_messages(conv_id: str):
    db = get_supabase()

    conv = db.table("conversations").select("*").eq("id", conv_id).execute()
    if not conv.data:
        return jsonify({"error": "Conversation not found"}), 404

    conv = conv.data[0]
    if g.user_id not in (conv["participant_a"], conv["participant_b"]):
        return jsonify({"error": "Access denied"}), 403

    user_row = db.table("users").select("private_key_enc").eq("id", g.user_id).execute()
    _, ecc_priv = unwrap_user_private_keys(user_row.data[0]["private_key_enc"])

    msgs = db.table("messages").select("*").eq(
        "conversation_id", conv_id
    ).order("created_at", desc=False).execute()

    result = []
    for msg in (msgs.data or []):
        try:
            content = _ecies_decrypt_for_user(msg["content_enc"], ecc_priv, g.user_id).decode()
            valid_hmac = verify_record_hmac(
                _hmac_key(), msg["hmac"],
                msg["content_enc"], conv_id, msg["sender_id"]
            )
        except Exception:
            content = "[decryption error]"
            valid_hmac = False

        result.append({
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "sender_name": _username(msg["sender_id"], db),
            "content": content,
            "created_at": msg["created_at"],
            "is_mine": msg["sender_id"] == g.user_id,
            "hmac_valid": valid_hmac,
        })

    return jsonify(result), 200


# ─── Send a message ───────────────────────────────────────────────────────────

@messages_bp.post("/conversations/<conv_id>/messages")
@require_auth
def send_message(conv_id: str):
    data = request.get_json(force=True)
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Message content cannot be empty"}), 400

    db = get_supabase()

    conv = db.table("conversations").select("*").eq("id", conv_id).execute()
    if not conv.data:
        return jsonify({"error": "Conversation not found"}), 404

    conv = conv.data[0]
    if g.user_id not in (conv["participant_a"], conv["participant_b"]):
        return jsonify({"error": "Access denied"}), 403

    # ECIES-encrypt for both participants
    content_enc = _ecies_encrypt_for_participants(conv, content.encode(), db)
    hmac_val = compute_record_hmac(_hmac_key(), content_enc, conv_id, g.user_id)

    result = db.table("messages").insert({
        "conversation_id": conv_id,
        "sender_id": g.user_id,
        "content_enc": content_enc,
        "hmac": hmac_val,
    }).execute()

    return jsonify({
        "id": result.data[0]["id"],
        "created_at": result.data[0]["created_at"],
    }), 201
