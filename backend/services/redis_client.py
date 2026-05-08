"""
Upstash Redis client (serverless Redis over HTTP-compatible redis-py).
"""

import os
import redis
from flask import current_app

_client = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL") or current_app.config["REDIS_URL"]
        _client = redis.from_url(url, decode_responses=True)
    return _client
