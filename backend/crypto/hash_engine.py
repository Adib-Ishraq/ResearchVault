"""
Custom SHA-256 implementation per FIPS 180-4.
No hashlib or any built-in crypto functions used.
Also provides PBKDF2 for password hashing.
"""

import struct
import os


# SHA-256 constants: first 32 bits of fractional parts of cube roots of first 64 primes
_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]

# SHA-256 initial hash values: first 32 bits of fractional parts of square roots of first 8 primes
_H0 = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]

_MASK32 = 0xFFFFFFFF


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & _MASK32


def _sha256_compress(chunk: bytes, h: list) -> list:
    assert len(chunk) == 64
    w = list(struct.unpack(">16I", chunk))
    for i in range(16, 64):
        s0 = _rotr(w[i-15], 7) ^ _rotr(w[i-15], 18) ^ (w[i-15] >> 3)
        s1 = _rotr(w[i-2], 17) ^ _rotr(w[i-2], 19) ^ (w[i-2] >> 10)
        w.append((w[i-16] + s0 + w[i-7] + s1) & _MASK32)

    a, b, c, d, e, f, g, hh = h

    for i in range(64):
        S1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        ch = (e & f) ^ ((~e & _MASK32) & g)
        temp1 = (hh + S1 + ch + _K[i] + w[i]) & _MASK32
        S0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        temp2 = (S0 + maj) & _MASK32

        hh = g
        g = f
        f = e
        e = (d + temp1) & _MASK32
        d = c
        c = b
        b = a
        a = (temp1 + temp2) & _MASK32

    return [
        (h[0] + a) & _MASK32, (h[1] + b) & _MASK32,
        (h[2] + c) & _MASK32, (h[3] + d) & _MASK32,
        (h[4] + e) & _MASK32, (h[5] + f) & _MASK32,
        (h[6] + g) & _MASK32, (h[7] + hh) & _MASK32,
    ]


def sha256(data: bytes) -> bytes:
    """Return 32-byte SHA-256 digest of data."""
    if isinstance(data, str):
        data = data.encode()

    msg = bytearray(data)
    orig_len_bits = len(data) * 8

    # Padding: append 0x80, then zeros, then 64-bit big-endian length
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0x00)
    msg += struct.pack(">Q", orig_len_bits)

    h = list(_H0)
    for i in range(0, len(msg), 64):
        h = _sha256_compress(bytes(msg[i:i+64]), h)

    return struct.pack(">8I", *h)


def sha256_hex(data: bytes) -> str:
    return sha256(data).hex()


# ---------- PBKDF2-SHA256 (RFC 2898) ----------

def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _prf(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256 used as the PBKDF2 PRF — inline to avoid circular import."""
    if len(key) > 64:
        key = sha256(key)
    key = key.ljust(64, b'\x00')
    o_key = bytes(b ^ 0x5C for b in key)
    i_key = bytes(b ^ 0x36 for b in key)
    return sha256(o_key + sha256(i_key + data))


def pbkdf2_sha256(password: bytes, salt: bytes, iterations: int = 100_000, dklen: int = 32) -> bytes:
    """
    PBKDF2 with HMAC-SHA256 PRF.
    Returns dklen bytes of derived key material.
    """
    if isinstance(password, str):
        password = password.encode()
    if isinstance(salt, str):
        salt = salt.encode()

    hlen = 32  # SHA-256 output length
    num_blocks = -(-dklen // hlen)  # ceiling division
    dk = b""

    for block_num in range(1, num_blocks + 1):
        u = _prf(password, salt + struct.pack(">I", block_num))
        t = u
        for _ in range(iterations - 1):
            u = _prf(password, u)
            t = _xor_bytes(t, u)
        dk += t

    return dk[:dklen]


def generate_salt(nbytes: int = 32) -> bytes:
    return os.urandom(nbytes)


def hash_password(password: str) -> tuple[str, str]:
    """Return (hash_hex, salt_hex) using PBKDF2-SHA256."""
    salt = generate_salt(32)
    dk = pbkdf2_sha256(password.encode(), salt)
    return dk.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    dk = pbkdf2_sha256(password.encode(), salt)
    return dk.hex() == hash_hex
