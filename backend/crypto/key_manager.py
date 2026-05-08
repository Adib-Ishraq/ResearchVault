"""
Key Manager: handles key generation, wrapping, unwrapping, and rotation.
All private keys are wrapped (encrypted) with the server RSA master key before DB storage.
"""

import os
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from .rsa_engine import (
    RSAPublicKey, RSAPrivateKey,
    generate_rsa_keypair,
    rsa_encrypt, rsa_decrypt,
    rsa_encrypt_large, rsa_decrypt_large,
    serialize_public_key, deserialize_public_key,
    serialize_private_key, deserialize_private_key,
)
from .ecc_engine import (
    ECCPublicKey, ECCPrivateKey,
    generate_ecc_keypair,
    ecies_encrypt, ecies_decrypt,
    serialize_ecc_public_key, deserialize_ecc_public_key,
    serialize_ecc_private_key, deserialize_ecc_private_key,
)

_ROTATION_DAYS = 90  # Key rotation period


class ServerMasterKeys:
    """Holds the server's master RSA + ECC keypairs (loaded from env at startup)."""

    def __init__(
        self,
        rsa_pub: RSAPublicKey,
        rsa_priv: RSAPrivateKey,
        ecc_pub: ECCPublicKey,
        ecc_priv: ECCPrivateKey,
    ):
        self.rsa_pub = rsa_pub
        self.rsa_priv = rsa_priv
        self.ecc_pub = ecc_pub
        self.ecc_priv = ecc_priv

    @classmethod
    def from_env(cls) -> "ServerMasterKeys":
        """Load server master keys from environment variables."""
        rsa_pub_b64 = os.environ["SERVER_RSA_MASTER_PUBLIC_KEY"]
        rsa_priv_b64 = os.environ["SERVER_RSA_MASTER_PRIVATE_KEY"]
        ecc_pub_b64 = os.environ["SERVER_ECC_MASTER_PUBLIC_KEY"]
        ecc_priv_b64 = os.environ["SERVER_ECC_MASTER_PRIVATE_KEY"]

        return cls(
            rsa_pub=deserialize_public_key(rsa_pub_b64),
            rsa_priv=deserialize_private_key(rsa_priv_b64),
            ecc_pub=deserialize_ecc_public_key(ecc_pub_b64),
            ecc_priv=deserialize_ecc_private_key(ecc_priv_b64),
        )

    @classmethod
    def generate_new(cls) -> "ServerMasterKeys":
        """Generate fresh server master keys (for initial setup / tests)."""
        rsa_pub, rsa_priv = generate_rsa_keypair(2048)
        ecc_pub, ecc_priv = generate_ecc_keypair()
        return cls(rsa_pub, rsa_priv, ecc_pub, ecc_priv)

    def export_env_vars(self) -> dict:
        """Export key material as env var values (for initial setup)."""
        return {
            "SERVER_RSA_MASTER_PUBLIC_KEY": serialize_public_key(self.rsa_pub),
            "SERVER_RSA_MASTER_PRIVATE_KEY": serialize_private_key(self.rsa_priv),
            "SERVER_ECC_MASTER_PUBLIC_KEY": serialize_ecc_public_key(self.ecc_pub),
            "SERVER_ECC_MASTER_PRIVATE_KEY": serialize_ecc_private_key(self.ecc_priv),
        }


# Module-level singleton — set by app factory at startup
_master: Optional[ServerMasterKeys] = None


def init_master_keys(master: ServerMasterKeys):
    global _master
    _master = master


def get_master() -> ServerMasterKeys:
    if _master is None:
        raise RuntimeError("Master keys not initialized — call init_master_keys() first")
    return _master


# ─── User key generation ──────────────────────────────────────────────────────

def generate_user_keys() -> dict:
    """
    Generate RSA-2048 + ECC P-256 keypairs for a new user.
    Returns a dict ready for DB insertion:
      - public_key_rsa: Base64 serialized public key (stored plaintext)
      - public_key_ecc: Base64 serialized ECC public key
      - private_key_enc: RSA-OAEP encrypted private keys bundle (Base64)
    """
    rsa_pub, rsa_priv = generate_rsa_keypair(2048)
    ecc_pub, ecc_priv = generate_ecc_keypair()
    master = get_master()

    # Bundle both private keys as JSON, wrap with server RSA master public key.
    # Uses hybrid encryption because the bundle exceeds the RSA-OAEP 190-byte limit.
    bundle = json.dumps({
        "rsa_priv": serialize_private_key(rsa_priv),
        "ecc_priv": serialize_ecc_private_key(ecc_priv),
    }).encode()

    wrapped = rsa_encrypt_large(master.rsa_pub, bundle)
    wrapped_b64 = base64.b64encode(wrapped).decode()

    return {
        "public_key_rsa": serialize_public_key(rsa_pub),
        "public_key_ecc": serialize_ecc_public_key(ecc_pub),
        "private_key_enc": wrapped_b64,
        "rotation_due": (datetime.now(timezone.utc) + timedelta(days=_ROTATION_DAYS)).isoformat(),
    }


def unwrap_user_private_keys(private_key_enc: str) -> tuple[RSAPrivateKey, ECCPrivateKey]:
    """Decrypt and return a user's RSA and ECC private keys."""
    master = get_master()
    wrapped = base64.b64decode(private_key_enc)
    bundle_bytes = rsa_decrypt_large(master.rsa_priv, wrapped)
    bundle = json.loads(bundle_bytes.decode())
    rsa_priv = deserialize_private_key(bundle["rsa_priv"])
    ecc_priv = deserialize_ecc_private_key(bundle["ecc_priv"])
    return rsa_priv, ecc_priv


# ─── Room key management ──────────────────────────────────────────────────────

def generate_room_key() -> bytes:
    """Generate a 32-byte symmetric room key."""
    return os.urandom(32)


def wrap_room_key_for_member(room_key: bytes, member_rsa_pub: RSAPublicKey) -> str:
    """RSA-OAEP encrypt the room key for a specific member. Returns Base64 string."""
    encrypted = rsa_encrypt(member_rsa_pub, room_key)
    return base64.b64encode(encrypted).decode()


def unwrap_room_key(room_key_enc: str, member_rsa_priv: RSAPrivateKey) -> bytes:
    """Decrypt a member's copy of the room key."""
    encrypted = base64.b64decode(room_key_enc)
    return rsa_decrypt(member_rsa_priv, encrypted)


# ─── Data field encryption using ECC (ECIES) ─────────────────────────────────

def encrypt_field(value: str, ecc_pub: Optional[ECCPublicKey] = None) -> str:
    """
    Encrypt a plaintext field value with ECIES using the server ECC master public key
    (or a provided public key). Returns Base64-encoded ciphertext.
    """
    if ecc_pub is None:
        ecc_pub = get_master().ecc_pub
    blob = ecies_encrypt(ecc_pub, value.encode())
    return base64.b64encode(blob).decode()


def decrypt_field(ciphertext_b64: str, ecc_priv: Optional[ECCPrivateKey] = None) -> str:
    """Decrypt a Base64 ECIES-encrypted field. Uses server ECC master private key by default."""
    if ecc_priv is None:
        ecc_priv = get_master().ecc_priv
    blob = base64.b64decode(ciphertext_b64)
    return ecies_decrypt(ecc_priv, blob).decode()


# ─── Key rotation ─────────────────────────────────────────────────────────────

def rotate_user_keys(old_private_key_enc: str) -> dict:
    """
    Rotate a user's keypair:
      1. Decrypt old private keys
      2. Generate new keypairs
      3. Wrap new private keys
      Returns new key fields for DB update.
    """
    # Unwrap current keys (we need the old private keys to re-encrypt existing data if needed)
    _old_rsa_priv, _old_ecc_priv = unwrap_user_private_keys(old_private_key_enc)

    # Generate new keypairs
    new_rsa_pub, new_rsa_priv = generate_rsa_keypair(2048)
    new_ecc_pub, new_ecc_priv = generate_ecc_keypair()
    master = get_master()

    bundle = json.dumps({
        "rsa_priv": serialize_private_key(new_rsa_priv),
        "ecc_priv": serialize_ecc_private_key(new_ecc_priv),
    }).encode()

    wrapped = rsa_encrypt_large(master.rsa_pub, bundle)
    wrapped_b64 = base64.b64encode(wrapped).decode()

    return {
        "public_key_rsa": serialize_public_key(new_rsa_pub),
        "public_key_ecc": serialize_ecc_public_key(new_ecc_pub),
        "private_key_enc": wrapped_b64,
        "rotation_due": (datetime.now(timezone.utc) + timedelta(days=_ROTATION_DAYS)).isoformat(),
    }
