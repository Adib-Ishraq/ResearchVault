"""
Custom HMAC-SHA256 implementation (RFC 2104).
Builds on hash_engine.sha256 — no standard library crypto used.
"""

from .hash_engine import sha256

_BLOCK_SIZE = 64  # SHA-256 block size in bytes


def hmac_sha256(key: bytes, message: bytes) -> bytes:
    """Return 32-byte HMAC-SHA256 digest."""
    if isinstance(key, str):
        key = key.encode()
    if isinstance(message, str):
        message = message.encode()

    # If key longer than block size, hash it down
    if len(key) > _BLOCK_SIZE:
        key = sha256(key)

    # Pad key to block size
    key = key.ljust(_BLOCK_SIZE, b'\x00')

    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)

    return sha256(o_key_pad + sha256(i_key_pad + message))


def hmac_sha256_hex(key: bytes, message: bytes) -> str:
    return hmac_sha256(key, message).hex()


def compute_record_hmac(secret_key: bytes, *fields: str) -> str:
    """
    Compute HMAC over concatenated encrypted field values for DB row integrity.
    Fields are joined with a null byte separator to prevent splicing attacks.
    """
    payload = b'\x00'.join(
        (f.encode() if isinstance(f, str) else f) for f in fields
    )
    return hmac_sha256_hex(secret_key, payload)


def verify_record_hmac(secret_key: bytes, expected_hex: str, *fields: str) -> bool:
    computed = compute_record_hmac(secret_key, *fields)
    # Constant-time comparison
    if len(computed) != len(expected_hex):
        return False
    result = 0
    for a, b in zip(computed, expected_hex):
        result |= ord(a) ^ ord(b)
    return result == 0
