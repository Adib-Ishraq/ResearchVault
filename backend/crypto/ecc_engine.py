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


# ─── Point encoding for EC ElGamal ───────────────────────────────────────────
# Koblitz-style embedding: 30 bytes of plaintext into a P-256 point.
# x = m_int * 256 + attempt, where the low 8 bits are the attempt counter.
# P-256 satisfies p ≡ 3 (mod 4), so square roots are pow(y_sq, (p+1)//4, p).

_CHUNK_BYTES = 30


def _point_from_bytes(data: bytes) -> tuple:
    """Embed up to 30 bytes as a P-256 point using Koblitz-style encoding."""
    m_int = int.from_bytes(data.ljust(_CHUNK_BYTES, b'\x00'), 'big')
    for attempt in range(256):
        x = m_int * 256 + attempt
        if x >= _P:
            continue
        y_sq = (x * x * x + _A * x + _B) % _P
        y = pow(y_sq, (_P + 1) // 4, _P)
        if (y * y) % _P == y_sq:
            return (x, y)
    raise ValueError("Could not encode data as a P-256 point in 256 attempts")


def _bytes_from_point(point: tuple) -> bytes:
    """Recover 30 bytes from a point encoded by _point_from_bytes."""
    x, _ = point
    return (x >> 8).to_bytes(_CHUNK_BYTES, 'big')


def _point_negate(P) -> tuple:
    """Return the additive inverse of P on P-256: (x, -y mod p)."""
    if P is _INF:
        return _INF
    return (P[0], (_P - P[1]) % _P)


# ─── Pure EC ElGamal Encrypt / Decrypt ───────────────────────────────────────
# No symmetric cipher used. Each 30-byte chunk of plaintext is encoded as a
# P-256 point M, then encrypted as (C1, C2) = (r*G, M + r*Q).
# Decryption: M = C2 - priv*C1  (since Q = priv*G → r*Q = priv*r*G = priv*C1).

def ecies_encrypt(recipient_public_key: ECCPublicKey, plaintext: bytes) -> bytes:
    """
    Pure EC ElGamal encryption — no symmetric cipher.
    Splits plaintext into 30-byte chunks; each chunk is encoded as a P-256
    point M and encrypted as (C1=r*G, C2=M+r*Q) with a fresh random r.
    Output: [4B num_chunks] || per-chunk([1B data_len][64B C1][64B C2])
    """
    chunks = [plaintext[i:i + _CHUNK_BYTES] for i in range(0, len(plaintext), _CHUNK_BYTES)]
    result = struct.pack(">I", len(chunks))
    for chunk in chunks:
        M = _point_from_bytes(chunk)
        r = int.from_bytes(os.urandom(32), 'big') % _N
        while r == 0:
            r = int.from_bytes(os.urandom(32), 'big') % _N
        C1 = _scalar_mult(r, _G)
        C2 = _point_add(M, _scalar_mult(r, recipient_public_key.point))
        result += struct.pack(">B", len(chunk))
        result += C1[0].to_bytes(32, 'big') + C1[1].to_bytes(32, 'big')
        result += C2[0].to_bytes(32, 'big') + C2[1].to_bytes(32, 'big')
    return result


def ecies_decrypt(private_key: ECCPrivateKey, blob: bytes) -> bytes:
    """
    Pure EC ElGamal decryption.
    M = C2 - priv*C1 = (M + r*Q) - priv*(r*G) = M + r*priv*G - priv*r*G = M.
    """
    offset = 0
    num_chunks = struct.unpack_from(">I", blob, offset)[0]
    offset += 4
    plaintext = b""
    for _ in range(num_chunks):
        chunk_len = struct.unpack_from(">B", blob, offset)[0]
        offset += 1
        C1 = (
            int.from_bytes(blob[offset:offset + 32], 'big'),
            int.from_bytes(blob[offset + 32:offset + 64], 'big'),
        )
        offset += 64
        C2 = (
            int.from_bytes(blob[offset:offset + 32], 'big'),
            int.from_bytes(blob[offset + 32:offset + 64], 'big'),
        )
        offset += 64
        M = _point_add(C2, _point_negate(_scalar_mult(private_key.scalar, C1)))
        plaintext += _bytes_from_point(M)[:chunk_len]
    return plaintext


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
