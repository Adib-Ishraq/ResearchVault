"""
Appointments module: students book appointments with supervisors.
Title and notes are ECIES-encrypted. Proposed times are plaintext (scheduling metadata).
"""

from flask import Blueprint, request, jsonify, g, current_app

from services.supabase_client import get_supabase
from middleware.session import require_auth
from middleware.rbac import require_role
from crypto.key_manager import encrypt_field, decrypt_field
from crypto.hmac_engine import compute_record_hmac

appointments_bp = Blueprint("appointments", __name__)


def _hmac_key() -> bytes:
    return current_app.config["HMAC_SECRET"].encode()


# ─── Book appointment (student → supervisor) ───────────────────────────────────────────────

@appointments_bp.post("/")
@require_auth
@require_role(["postgrad", "undergraduate"])
def book_appointment():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    note = (data.get("note") or "").strip()
    proposed_times = data.get("proposed_times") or []
    supervisor_id = data.get("supervisor_id", "").strip()

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not proposed_times or not isinstance(proposed_times, list) or len(proposed_times) == 0:
        return jsonify({"error": "At least one proposed time is required"}), 400
    if len(proposed_times) > 3:
        return jsonify({"error": "Maximum 3 proposed times allowed"}), 400
    if not supervisor_id:
        return jsonify({"error": "supervisor_id is required"}), 400

    db = get_supabase()
    sup = db.table("users").select("id, role").eq("id", supervisor_id).execute()
    if not sup.data or sup.data[0]["role"] != "supervisor":
        return jsonify({"error": "Supervisor not found"}), 404

    existing = db.table("appointments").select("id").eq(
        "student_id", g.user_id
    ).eq("supervisor_id", supervisor_id).eq("status", "pending").execute()
    if existing.data:
        return jsonify({"error": "You already have a pending appointment with this supervisor"}), 409

    title_enc = encrypt_field(title)
    note_enc = encrypt_field(note) if note else None
    hmac_val = compute_record_hmac(_hmac_key(), title_enc, note_enc or "", supervisor_id)

    result = db.table("appointments").insert({
        "student_id": g.user_id,
        "supervisor_id": supervisor_id,
        "title_enc": title_enc,
        "note_enc": note_enc,
        "proposed_times": proposed_times,
        "status": "pending",
        "hmac": hmac_val,
    }).execute()

    db.table("notifications").insert({
        "recipient_id": supervisor_id,
        "type": "appointment_request",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()

    return jsonify({"message": "Appointment request sent", "id": result.data[0]["id"]}), 201


# ─── List appointments ─────────────────────────────────────────────────────────────────────

@appointments_bp.get("/")
@require_auth
def list_appointments():
    db = get_supabase()

    if g.role == "supervisor":
        rows = db.table("appointments").select("*").eq(
            "supervisor_id", g.user_id
        ).order("created_at", desc=True).execute()
    else:
        rows = db.table("appointments").select("*").eq(
            "student_id", g.user_id
        ).order("created_at", desc=True).execute()

    result = []
    for r in (rows.data or []):
        other_id = r["student_id"] if g.role == "supervisor" else r["supervisor_id"]
        other = db.table("users").select("username_enc").eq("id", other_id).execute()
        other_name = decrypt_field(other.data[0]["username_enc"]) if other.data else "Unknown"

        result.append({
            "id": r["id"],
            "title": decrypt_field(r["title_enc"]),
            "note": decrypt_field(r["note_enc"]) if r.get("note_enc") else None,
            "supervisor_note": decrypt_field(r["supervisor_note_enc"]) if r.get("supervisor_note_enc") else None,
            "proposed_times": r["proposed_times"],
            "status": r["status"],
            "confirmed_time": r["confirmed_time"],
            "student_id": r["student_id"],
            "supervisor_id": r["supervisor_id"],
            "other_user_name": other_name,
            "created_at": r["created_at"],
        })

    return jsonify(result), 200


# ─── Respond to appointment (supervisor) ─────────────────────────────────────────────────────

@appointments_bp.put("/<appt_id>/respond")
@require_auth
@require_role(["supervisor"])
def respond_to_appointment(appt_id: str):
    data = request.get_json(force=True)
    action = data.get("action")
    confirmed_time = data.get("confirmed_time")
    supervisor_note = (data.get("note") or "").strip()

    if action not in ("approve", "reject"):
        return jsonify({"error": "action must be approve or reject"}), 400
    if action == "approve" and not confirmed_time:
        return jsonify({"error": "confirmed_time is required when approving"}), 400

    db = get_supabase()
    appt = db.table("appointments").select("*").eq(
        "id", appt_id
    ).eq("supervisor_id", g.user_id).execute()
    if not appt.data:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.data[0]["status"] != "pending":
        return jsonify({"error": "Appointment is no longer pending"}), 409

    new_status = "approved" if action == "approve" else "rejected"
    sup_note_enc = encrypt_field(supervisor_note) if supervisor_note else None
    update = {"status": new_status, "supervisor_note_enc": sup_note_enc}
    if action == "approve":
        update["confirmed_time"] = confirmed_time

    db.table("appointments").update(update).eq("id", appt_id).execute()

    db.table("notifications").insert({
        "recipient_id": appt.data[0]["student_id"],
        "type": "appointment_approved" if action == "approve" else "appointment_rejected",
        "payload_enc": encrypt_field(g.user_id),
    }).execute()

    return jsonify({"message": f"Appointment {new_status}"}), 200


# ─── Cancel appointment (student) ──────────────────────────────────────────────────────────────────────

@appointments_bp.put("/<appt_id>/cancel")
@require_auth
def cancel_appointment(appt_id: str):
    db = get_supabase()
    appt = db.table("appointments").select("id, status").eq(
        "id", appt_id
    ).eq("student_id", g.user_id).execute()
    if not appt.data:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.data[0]["status"] not in ("pending", "approved"):
        return jsonify({"error": "Appointment cannot be cancelled"}), 409

    db.table("appointments").update({"status": "cancelled"}).eq("id", appt_id).execute()
    return jsonify({"message": "Appointment cancelled"}), 200
