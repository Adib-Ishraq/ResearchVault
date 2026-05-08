"""
Role-Based Access Control decorators.
Must be applied AFTER @require_auth so g.role is set.
"""

from functools import wraps
from flask import g, jsonify


def require_role(allowed_roles: list[str]):
    """Decorator: restrict endpoint to users whose role is in allowed_roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "role"):
                return jsonify({"error": "Not authenticated"}), 401
            if g.role not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─── Named role shortcuts ─────────────────────────────────────────────────────

def admin_only(f):
    return require_role(["admin"])(f)


def supervisor_only(f):
    return require_role(["admin", "supervisor"])(f)


def researcher_and_above(f):
    return require_role(["admin", "supervisor", "postgrad", "undergraduate"])(f)


def can_send_supervision_request(f):
    return require_role(["postgrad", "undergraduate"])(f)


def can_upload(f):
    return require_role(["admin", "supervisor", "postgrad", "undergraduate"])(f)
