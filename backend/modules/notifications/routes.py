"""
Notifications module + Supervision requests.
"""

from flask import Blueprint, request, jsonify, g

from services.supabase_client import get_supabase
from middleware.session import require_auth
from middleware.rbac import require_role
from crypto.key_manager import encrypt_field, decrypt_field
from crypto.hmac_engine import compute_record_hmac
from flask import current_app

notifications_bp = Blueprint("notifications", __name__)


def _hmac_key() -> bytes:
    return current_app.config["HMAC_SECRET"].encode()


# ─── Notifications ────────────────────────────────────────────────────────────

@notifications_bp.get("")
@require_auth
def get_notifications():
    db = get_supabase()
    rows = db.table("notifications").select("*").eq(
        "recipient_id", g.user_id
    ).order("created_at", desc=True).limit(50).execute()

    result = []
    for row in (rows.data or []):
        item = {k: v for k, v in row.items() if k != "payload_enc"}
        if row.get("payload_enc"):
            try:
                item["payload"] = decrypt_field(row["payload_enc"])
            except Exception:
                item["payload"] = None
        result.append(item)
    return jsonify(result), 200


@notifications_bp.put("/<notif_id>/read")
@require_auth
def mark_read(notif_id: str):
    db = get_supabase()
    db.table("notifications").update({"is_read": True}).eq(
        "id", notif_id
    ).eq("recipient_id", g.user_id).execute()
    return jsonify({"message": "Marked as read"}), 200


@notifications_bp.put("/read-all")
@require_auth
def mark_all_read():
    db = get_supabase()
    db.table("notifications").update({"is_read": True}).eq(
        "recipient_id", g.user_id
    ).execute()
    return jsonify({"message": "All marked as read"}), 200


# ─── Supervision requests ─────────────────────────────────────────────────────

@notifications_bp.post("/supervision/request/<supervisor_id>")
@require_auth
@require_role(["postgrad", "undergraduate"])
def send_supervision_request(supervisor_id: str):
    db = get_supabase()

    # Check supervisor exists and is actually a supervisor
    sup = db.table("users").select("id, role").eq("id", supervisor_id).execute()
    if not sup.data or sup.data[0]["role"] != "supervisor":
        return jsonify({"error": "Supervisor not found"}), 404

    # Prevent duplicate pending request
    existing = db.table("supervision_requests").select("id").eq(
        "researcher_id", g.user_id
    ).eq("supervisor_id", supervisor_id).eq("status", "pending").execute()
    if existing.data:
        return jsonify({"error": "Supervision request already pending"}), 409

    data = request.get_json(force=True) or {}
    message_enc = encrypt_field(data.get("message", "")) if data.get("message") else None
    hmac_val = compute_record_hmac(_hmac_key(), message_enc or "")

    row = {
        "researcher_id": g.user_id,
        "supervisor_id": supervisor_id,
        "status": "pending",
        "message_enc": message_enc,
        "hmac": hmac_val,
    }
    result = db.table("supervision_requests").insert(row).execute()

    db.table("notifications").insert({
        "recipient_id": supervisor_id,
        "type": "supervision_request",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()

    return jsonify({"message": "Supervision request sent", "id": result.data[0]["id"]}), 201


@notifications_bp.get("/supervision/incoming")
@require_auth
@require_role(["supervisor"])
def incoming_supervision_requests():
    db = get_supabase()
    rows = db.table("supervision_requests").select("*").eq(
        "supervisor_id", g.user_id
    ).eq("status", "pending").execute()

    result = []
    for r in (rows.data or []):
        researcher = db.table("users").select("id, username_enc, role").eq(
            "id", r["researcher_id"]
        ).execute()
        username = decrypt_field(researcher.data[0]["username_enc"]) if researcher.data else "Unknown"
        result.append({
            "id": r["id"],
            "researcher_id": r["researcher_id"],
            "researcher_name": username,
            "message": decrypt_field(r["message_enc"]) if r.get("message_enc") else None,
            "created_at": r["created_at"],
        })
    return jsonify(result), 200


@notifications_bp.put("/supervision/<req_id>/accept")
@require_auth
@require_role(["supervisor"])
def accept_supervision(req_id: str):
    db = get_supabase()
    req = db.table("supervision_requests").select("*").eq(
        "id", req_id
    ).eq("supervisor_id", g.user_id).execute()
    if not req.data:
        return jsonify({"error": "Request not found"}), 404

    db.table("supervision_requests").update({"status": "accepted"}).eq("id", req_id).execute()
    db.table("notifications").insert({
        "recipient_id": req.data[0]["researcher_id"],
        "type": "supervision_accepted",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()
    return jsonify({"message": "Supervision request accepted"}), 200


@notifications_bp.put("/supervision/<req_id>/reject")
@require_auth
@require_role(["supervisor"])
def reject_supervision(req_id: str):
    db = get_supabase()
    req = db.table("supervision_requests").select("*").eq(
        "id", req_id
    ).eq("supervisor_id", g.user_id).execute()
    if not req.data:
        return jsonify({"error": "Request not found"}), 404

    db.table("supervision_requests").update({"status": "rejected"}).eq("id", req_id).execute()
    db.table("notifications").insert({
        "recipient_id": req.data[0]["researcher_id"],
        "type": "supervision_rejected",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()
    return jsonify({"message": "Supervision request rejected"}), 200


@notifications_bp.get("/supervision/my-requests")
@require_auth
def my_supervision_requests():
    """List supervision requests sent by the current user."""
    db = get_supabase()
    rows = db.table("supervision_requests").select("*").eq(
        "researcher_id", g.user_id
    ).execute()

    result = []
    for r in (rows.data or []):
        sup = db.table("users").select("id, username_enc").eq(
            "id", r["supervisor_id"]
        ).execute()
        sup_name = decrypt_field(sup.data[0]["username_enc"]) if sup.data else "Unknown"
        result.append({
            "id": r["id"],
            "supervisor_id": r["supervisor_id"],
            "supervisor_name": sup_name,
            "status": r["status"],
            "created_at": r["created_at"],
        })
    return jsonify(result), 200
