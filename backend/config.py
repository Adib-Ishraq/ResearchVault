"""
Application configuration — loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Supabase
    SUPABASE_URL = os.environ["SUPABASE_URL"]
    SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
    SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    # Redis (Upstash)
    REDIS_URL = os.environ["REDIS_URL"]

    # Brevo HTTP API (email / OTP)
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

    # JWT
    JWT_SECRET = os.environ["JWT_SECRET"]
    JWT_ACCESS_EXPIRES = 15 * 60          # 15 minutes in seconds
    JWT_REFRESH_EXPIRES = 7 * 24 * 3600   # 7 days

    # Server master crypto keys (Base64-encoded)
    SERVER_RSA_MASTER_PUBLIC_KEY = os.environ["SERVER_RSA_MASTER_PUBLIC_KEY"]
    SERVER_RSA_MASTER_PRIVATE_KEY = os.environ["SERVER_RSA_MASTER_PRIVATE_KEY"]
    SERVER_ECC_MASTER_PUBLIC_KEY = os.environ["SERVER_ECC_MASTER_PUBLIC_KEY"]
    SERVER_ECC_MASTER_PRIVATE_KEY = os.environ["SERVER_ECC_MASTER_PRIVATE_KEY"]

    # HMAC secret for record integrity
    HMAC_SECRET = os.environ.get("HMAC_SECRET", "change-me-in-production")

    # Groq AI assistant (free tier via https://console.groq.com — no credit card needed)
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    # CORS
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
