"""
Custom ECC implementation over NIST P-256.
  - Affine point addition and doubling
  - Scalar multiplication (double-and-add)
  - ECDH key exchange
  - ECIES encryption/decryption
No standard library crypto used.
"""

import os
import base64
import json
import struct
from .hash_engine import sha256
from .hmac_engine import hmac_sha256

# ─── NIST P-256 curve parameters ─────────────────────────────────────────────
# y² = x³ + ax + b  (mod p)

_P  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
_B  = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_Gx = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
_Gy = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
_N  = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_G  = (_Gx, _Gy)

# Point at infinity represented as None
_INF = None


# ─── Field arithmetic ─────────────────────────────────────────────────────────

def _mod_inv(a: int, p: int) -> int:
    """Modular inverse using Fermat's little theorem (p is prime)."""
    return pow(a, p - 2, p)


# ─── Point operations (affine coordinates) ────────────────────────────────────

def _point_add(P, Q):
    """Add two points on the P-256 curve."""
    if P is _INF:
        return Q
    if Q is _INF:
        return P
    x1, y1 = P
    x2, y2 = Q

    if x1 == x2:
        if y1 != y2:
            return _INF
        return _point_double(P)

    lam = ((y2 - y1) * _mod_inv(x2 - x1, _P)) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _point_double(P):
    """Double a point on P-256."""
    if P is _INF:
        return _INF
    x1, y1 = P
    if y1 == 0:
        return _INF

    lam = ((3 * x1 * x1 + _A) * _mod_inv(2 * y1, _P)) % _P
    x3 = (lam * lam - 2 * x1) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _scalar_mult(k: int, P) -> tuple:
    """Scalar multiplication using double-and-add."""
    if k == 0 or P is _INF:
        return _INF
    if k < 0:
        k = k % _N
    result = _INF
    addend = P
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_double(addend)
        k >>= 1
    return result


def _is_on_curve(P) -> bool:
    if P is _INF:
        return True
    x, y = P
    return (y * y - x * x * x - _A * x - _B) % _P == 0


# ─── Key types ────────────────────────────────────────────────────────────────

class ECCPublicKey:
    def __init__(self, point: tuple):
        self.point = point  # (x, y)

    def to_dict(self) -> dict:
        return {"x": hex(self.point[0]), "y": hex(self.point[1])}

    @classmethod
    def from_dict(cls, d: dict) -> "ECCPublicKey":
        return cls((int(d["x"], 16), int(d["y"], 16)))


class ECCPrivateKey:
    def __init__(self, scalar: int):
        self.scalar = scalar
        self._pub = None

    def public_key(self) -> ECCPublicKey:
        if self._pub is None:
            self._pub = ECCPublicKey(_scalar_mult(self.scalar, _G))
        return self._pub

    def to_dict(self) -> dict:
        return {"k": hex(self.scalar)}

    @classmethod
    def from_dict(cls, d: dict) -> "ECCPrivateKey":
        return cls(int(d["k"], 16))


def generate_ecc_keypair() -> tuple[ECCPublicKey, ECCPrivateKey]:
    while True:
        raw = int.from_bytes(os.urandom(32), "big") % _N
        if raw > 1:
            priv = ECCPrivateKey(raw)
            pub = priv.public_key()
            return pub, priv


# ─── ECDH ─────────────────────────────────────────────────────────────────────

def ecdh_shared_secret(private_key: ECCPrivateKey, peer_public_key: ECCPublicKey) -> bytes:
    """Compute ECDH shared secret: private_key * peer_public_key → x-coordinate."""
    shared_point = _scalar_mult(private_key.scalar, peer_public_key.point)
    if shared_point is _INF:
        raise ValueError("ECDH produced point at infinity")
    x, _ = shared_point
    return x.to_bytes(32, "big")


# ─── KDF (ANSI X9.63 / SP 800-56A style with SHA-256) ────────────────────────

def _kdf(shared_secret: bytes, info: bytes = b"ECIES", key_len: int = 32) -> bytes:
    """Derive key material from shared secret using SHA-256."""
    result = b""
    counter = 1
    while len(result) < key_len:
        result += sha256(shared_secret + struct.pack(">I", counter) + info)
        counter += 1
    return result[:key_len]


# ─── XOR stream cipher using derived key ─────────────────────────────────────

def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate keystream for XOR cipher: SHA-256-based CTR mode."""
    stream = b""
    block = 0
    while len(stream) < length:
        stream += sha256(key + nonce + struct.pack(">I", block))
        block += 1
    return stream[:length]


# ─── ECIES Encrypt / Decrypt ──────────────────────────────────────────────────

def ecies_encrypt(recipient_public_key: ECCPublicKey, plaintext: bytes) -> bytes:
    """
    ECIES encryption:
      1. Generate ephemeral keypair
      2. ECDH → shared secret
      3. KDF → encryption key + MAC key
      4. XOR-stream encrypt plaintext
      5. HMAC-SHA256 over ciphertext
    Output format: [ephemeral_x(32)] + [ephemeral_y(32)] + [nonce(16)] + [ciphertext] + [mac(32)]
    """
    eph_pub, eph_priv = generate_ecc_keypair()
    shared = ecdh_shared_secret(eph_priv, recipient_public_key)

    enc_key = _kdf(shared, b"ENC", 32)
    mac_key = _kdf(shared, b"MAC", 32)

    nonce = os.urandom(16)
    stream = _keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))

    mac = hmac_sha256(mac_key, nonce + ciphertext)

    eph_x = eph_pub.point[0].to_bytes(32, "big")
    eph_y = eph_pub.point[1].to_bytes(32, "big")
    return eph_x + eph_y + nonce + ciphertext + mac


def ecies_decrypt(private_key: ECCPrivateKey, blob: bytes) -> bytes:
    """Decrypt ECIES blob produced by ecies_encrypt."""
    if len(blob) < 32 + 32 + 16 + 32:
        raise ValueError("ECIES blob too short")

    eph_x = int.from_bytes(blob[0:32], "big")
    eph_y = int.from_bytes(blob[32:64], "big")
    nonce = blob[64:80]
    ciphertext = blob[80:-32]
    mac = blob[-32:]

    eph_pub = ECCPublicKey((eph_x, eph_y))
    shared = ecdh_shared_secret(private_key, eph_pub)

    enc_key = _kdf(shared, b"ENC", 32)
    mac_key = _kdf(shared, b"MAC", 32)

    expected_mac = hmac_sha256(mac_key, nonce + ciphertext)
    if expected_mac != mac:
        raise ValueError("ECIES MAC verification failed — data tampered")

    stream = _keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream))


# ─── Base64 serialization ─────────────────────────────────────────────────────

def serialize_ecc_public_key(pub: ECCPublicKey) -> str:
    return base64.b64encode(json.dumps(pub.to_dict()).encode()).decode()


def deserialize_ecc_public_key(s: str) -> ECCPublicKey:
    return ECCPublicKey.from_dict(json.loads(base64.b64decode(s).decode()))


def serialize_ecc_private_key(priv: ECCPrivateKey) -> str:
    return base64.b64encode(json.dumps(priv.to_dict()).encode()).decode()


def deserialize_ecc_private_key(s: str) -> ECCPrivateKey:
    return ECCPrivateKey.from_dict(json.loads(base64.b64decode(s).decode()))


def ecies_encrypt_b64(recipient_public_key: ECCPublicKey, plaintext: str) -> str:
    """Encrypt a UTF-8 string and return Base64-encoded ciphertext."""
    blob = ecies_encrypt(recipient_public_key, plaintext.encode())
    return base64.b64encode(blob).decode()


def ecies_decrypt_b64(private_key: ECCPrivateKey, ciphertext_b64: str) -> str:
    """Decrypt a Base64-encoded ECIES blob and return UTF-8 string."""
    blob = base64.b64decode(ciphertext_b64)
    return ecies_decrypt(private_key, blob).decode()
