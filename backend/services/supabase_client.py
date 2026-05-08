"""
Supabase client using the service role key (full DB access, bypasses RLS).
"""

import os
from supabase import create_client, Client
from flask import current_app

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL") or current_app.config["SUPABASE_URL"]
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or current_app.config["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client
