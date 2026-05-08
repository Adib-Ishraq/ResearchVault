"""
Email delivery via Brevo HTTP API for OTP and notification emails.
"""

import os
import random
import string
import requests
from flask import current_app

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _send_via_brevo(to: str, subject: str, html: str) -> bool:
    api_key = os.environ.get("BREVO_API_KEY", "")
    payload = {
        "sender": {"name": "Research Vault", "email": "ikadib10@gmail.com"},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }
    try:
        resp = requests.post(_BREVO_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error("Brevo send failed: %s", e)
        return False


def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str, purpose: str = "login") -> bool:
    subject = "Your Research Vault verification code"
    html = f"""
    <div style="font-family: 'DM Sans', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h2 style="color: #1A1A2E; margin-bottom: 8px;">Research Vault</h2>
      <p style="color: #4A5568; margin-bottom: 24px;">
        Use the code below to complete your {purpose}.
      </p>
      <div style="background: #E8F5F3; border-radius: 8px; padding: 24px; text-align: center;">
        <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #4A9B8E;">{otp}</span>
      </div>
      <p style="color: #718096; font-size: 13px; margin-top: 24px;">
        This code expires in 10 minutes. Do not share it with anyone.
      </p>
    </div>
    """
    return _send_via_brevo(to_email, subject, html)
