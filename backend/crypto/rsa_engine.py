"""
Custom RSA-2048 implementation.
  - Miller-Rabin primality test
  - Extended Euclidean / modular inverse
  - OAEP padding for encryption/decryption
  - PSS padding for sign/verify
No standard library crypto (no cryptography, no rsa, no Crypto.*) used.
"""

import os
import struct
from .hash_engine import sha256
from .hmac_engine import hmac_sha256


# ─── Modular arithmetic helpers ───────────────────────────────────────────────

def _bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _int_to_bytes(n: int, length: int) -> bytes:
    return n.to_bytes(length, "big")


def _random_int(nbits: int) -> int:
    nbytes = (nbits + 7) // 8
    raw = int.from_bytes(os.urandom(nbytes), "big")
    # Mask to exact bit count
    raw &= (1 << nbits) - 1
    return raw


def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return (gcd, x, y) such that a*x + b*y == gcd."""
    if b == 0:
        return a, 1, 0
    g, x, y = _extended_gcd(b, a % b)
    return g, y, x - (a // b) * y


def _mod_inverse(a: int, m: int) -> int:
    g, x, _ = _extended_gcd(a % m, m)
    if g != 1:
        raise ValueError("Modular inverse does not exist")
    return x % m


def _lcm(a: int, b: int) -> int:
    g, _, _ = _extended_gcd(a, b)
    return abs(a * b) // g


def _pow_mod(base: int, exp: int, mod: int) -> int:
    return pow(base, exp, mod)  # Python built-in pow with 3 args is not crypto — it's arithmetic


# ─── Miller-Rabin primality test ──────────────────────────────────────────────

_MR_WITNESSES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]


def _is_prime(n: int, rounds: int = 20) -> bool:
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False

    # Write n-1 as 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2

    witnesses = _MR_WITNESSES + [
        _bytes_to_int(os.urandom(8)) % (n - 4) + 2 for _ in range(rounds)
    ]

    for a in witnesses:
        if a >= n:
            continue
        x = _pow_mod(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = _pow_mod(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _generate_prime(nbits: int) -> int:
    while True:
        candidate = _random_int(nbits)
        candidate |= (1 << (nbits - 1))  # ensure high bit set
        candidate |= 1  # ensure odd
        if _is_prime(candidate):
            return candidate


# ─── MGF1 (Mask Generation Function) using SHA-256 ──────────────────────────

def _mgf1(seed: bytes, length: int) -> bytes:
    """MGF1 with SHA-256 hash function."""
    result = b""
    counter = 0
    while len(result) < length:
        c = struct.pack(">I", counter)
        result += sha256(seed + c)
        counter += 1
    return result[:length]


# ─── OAEP padding ─────────────────────────────────────────────────────────────

_HASH_LEN = 32   # SHA-256 output length
_LABEL = b""     # Empty label per PKCS#1 v2.2


def _oaep_pad(message: bytes, modulus_bytes: int) -> bytes:
    """Apply OAEP padding. modulus_bytes = n bit length // 8."""
    max_msg = modulus_bytes - 2 * _HASH_LEN - 2
    if len(message) > max_msg:
        raise ValueError(f"Message too long for OAEP: max {max_msg} bytes")

    l_hash = sha256(_LABEL)
    ps = b'\x00' * (modulus_bytes - len(message) - 2 * _HASH_LEN - 2)
    db = l_hash + ps + b'\x01' + message

    seed = os.urandom(_HASH_LEN)
    db_mask = _mgf1(seed, len(db))
    masked_db = bytes(a ^ b for a, b in zip(db, db_mask))

    seed_mask = _mgf1(masked_db, _HASH_LEN)
    masked_seed = bytes(a ^ b for a, b in zip(seed, seed_mask))

    return b'\x00' + masked_seed + masked_db


def _oaep_unpad(em: bytes) -> bytes:
    """Remove OAEP padding and return original message."""
    if len(em) < 2 * _HASH_LEN + 2:
        raise ValueError("OAEP unpad: ciphertext too short")
    if em[0] != 0:
        raise ValueError("OAEP unpad: leading byte not zero")

    masked_seed = em[1:1 + _HASH_LEN]
    masked_db = em[1 + _HASH_LEN:]

    seed_mask = _mgf1(masked_db, _HASH_LEN)
    seed = bytes(a ^ b for a, b in zip(masked_seed, seed_mask))

    db_mask = _mgf1(seed, len(masked_db))
    db = bytes(a ^ b for a, b in zip(masked_db, db_mask))

    l_hash = sha256(_LABEL)
    if db[:_HASH_LEN] != l_hash:
        raise ValueError("OAEP unpad: label hash mismatch")

    # Find separator 0x01
    i = _HASH_LEN
    while i < len(db) and db[i] == 0:
        i += 1
    if i >= len(db) or db[i] != 1:
        raise ValueError("OAEP unpad: separator byte not found")

    return db[i + 1:]


# ─── PSS padding for signatures ──────────────────────────────────────────────

_SALT_LEN = 32


def _pss_pad(msg_hash: bytes, em_bits: int) -> bytes:
    """Apply PSS padding to a message hash."""
    em_len = (em_bits + 7) // 8
    salt = os.urandom(_SALT_LEN)

    m_prime = b'\x00' * 8 + msg_hash + salt
    h = sha256(m_prime)

    ps = b'\x00' * (em_len - _SALT_LEN - _HASH_LEN - 2)
    db = ps + b'\x01' + salt

    db_mask = _mgf1(h, len(db))
    masked_db = bytes(a ^ b for a, b in zip(db, db_mask))

    # Zero out top bits
    top_bits = 8 * em_len - em_bits
    masked_db = bytes([masked_db[0] & (0xFF >> top_bits)]) + masked_db[1:]

    return masked_db + h + b'\xbc'


def _pss_verify(msg_hash: bytes, em: bytes, em_bits: int) -> bool:
    """Verify PSS padding."""
    em_len = (em_bits + 7) // 8
    if len(em) != em_len:
        return False
    if em[-1] != 0xBC:
        return False

    masked_db = em[:em_len - _HASH_LEN - 1]
    h = em[em_len - _HASH_LEN - 1:-1]

    top_bits = 8 * em_len - em_bits
    if masked_db[0] & (0xFF << (8 - top_bits)) & 0xFF:
        return False

    db_mask = _mgf1(h, len(masked_db))
    db = bytes(a ^ b for a, b in zip(masked_db, db_mask))

    db = bytes([db[0] & (0xFF >> top_bits)]) + db[1:]

    ps_len = em_len - _SALT_LEN - _HASH_LEN - 2
    if db[:ps_len] != b'\x00' * ps_len:
        return False
    if db[ps_len] != 1:
        return False

    salt = db[ps_len + 1:]
    m_prime = b'\x00' * 8 + msg_hash + salt
    h2 = sha256(m_prime)
    return h == h2


# ─── Key generation ───────────────────────────────────────────────────────────

class RSAPublicKey:
    def __init__(self, n: int, e: int):
        self.n = n
        self.e = e
        self.n_bytes = (n.bit_length() + 7) // 8

    def to_dict(self) -> dict:
        return {"n": hex(self.n), "e": self.e}

    @classmethod
    def from_dict(cls, d: dict) -> "RSAPublicKey":
        return cls(int(d["n"], 16), d["e"])


class RSAPrivateKey:
    def __init__(self, n: int, e: int, d: int, p: int, q: int):
        self.n = n
        self.e = e
        self.d = d
        self.p = p
        self.q = q
        self.n_bytes = (n.bit_length() + 7) // 8

    def public_key(self) -> RSAPublicKey:
        return RSAPublicKey(self.n, self.e)

    def to_dict(self) -> dict:
        return {
            "n": hex(self.n), "e": self.e,
            "d": hex(self.d), "p": hex(self.p), "q": hex(self.q),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RSAPrivateKey":
        return cls(
            int(d["n"], 16), d["e"],
            int(d["d"], 16), int(d["p"], 16), int(d["q"], 16),
        )


def generate_rsa_keypair(bits: int = 2048) -> tuple[RSAPublicKey, RSAPrivateKey]:
    e = 65537
    while True:
        p = _generate_prime(bits // 2)
        q = _generate_prime(bits // 2)
        if p == q:
            continue
        n = p * q
        lam = _lcm(p - 1, q - 1)
        if _extended_gcd(e, lam)[0] != 1:
            continue
        d = _mod_inverse(e, lam)
        pub = RSAPublicKey(n, e)
        priv = RSAPrivateKey(n, e, d, p, q)
        return pub, priv


# ─── Encrypt / Decrypt (OAEP) ─────────────────────────────────────────────────

def rsa_encrypt(public_key: RSAPublicKey, plaintext: bytes) -> bytes:
    """Encrypt plaintext with RSA-OAEP. Returns raw ciphertext bytes."""
    em = _oaep_pad(plaintext, public_key.n_bytes)
    m = _bytes_to_int(em)
    c = _pow_mod(m, public_key.e, public_key.n)
    return _int_to_bytes(c, public_key.n_bytes)


def rsa_decrypt(private_key: RSAPrivateKey, ciphertext: bytes) -> bytes:
    """Decrypt RSA-OAEP ciphertext."""
    c = _bytes_to_int(ciphertext)
    m = _pow_mod(c, private_key.d, private_key.n)
    em = _int_to_bytes(m, private_key.n_bytes)
    return _oaep_unpad(em)


# ─── Hybrid Encrypt / Decrypt (RSA-OAEP + CTR-HMAC) ─────────────────────────
# Used when plaintext exceeds OAEP limit (190 bytes for RSA-2048 with SHA-256).
# Format: [rsa_wrapped_key(256)] + [nonce(16)] + [ciphertext(n)] + [mac(32)]

def _ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    stream = b""
    block = 0
    while len(stream) < length:
        stream += sha256(key + nonce + struct.pack(">I", block))
        block += 1
    return stream[:length]


def rsa_hybrid_encrypt(public_key: RSAPublicKey, plaintext: bytes) -> bytes:
    """Encrypt arbitrarily large plaintext: RSA-OAEP wraps a 32-byte CEK,
    then CTR-mode + HMAC-SHA256 encrypts the plaintext."""
    cek = os.urandom(32)
    mac_key = sha256(cek + b"MAC")
    wrapped_cek = rsa_encrypt(public_key, cek)

    nonce = os.urandom(16)
    stream = _ctr_keystream(cek, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    mac = hmac_sha256(mac_key, nonce + ciphertext)

    return wrapped_cek + nonce + ciphertext + mac


def rsa_hybrid_decrypt(private_key: RSAPrivateKey, blob: bytes) -> bytes:
    """Decrypt blob produced by rsa_hybrid_encrypt."""
    key_len = private_key.n_bytes
    if len(blob) < key_len + 16 + 32:
        raise ValueError("Hybrid blob too short")

    wrapped_cek = blob[:key_len]
    nonce = blob[key_len:key_len + 16]
    ciphertext = blob[key_len + 16:-32]
    mac = blob[-32:]

    cek = rsa_decrypt(private_key, wrapped_cek)
    mac_key = sha256(cek + b"MAC")

    expected_mac = hmac_sha256(mac_key, nonce + ciphertext)
    if expected_mac != mac:
        raise ValueError("Hybrid decrypt: MAC verification failed")

    stream = _ctr_keystream(cek, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream))


# ─── Sign / Verify (PSS) ──────────────────────────────────────────────────────

def rsa_sign(private_key: RSAPrivateKey, message: bytes) -> bytes:
    """Sign message with RSA-PSS. Returns raw signature bytes."""
    msg_hash = sha256(message)
    em_bits = private_key.n.bit_length() - 1
    em = _pss_pad(msg_hash, em_bits)
    m = _bytes_to_int(em)
    s = _pow_mod(m, private_key.d, private_key.n)
    return _int_to_bytes(s, private_key.n_bytes)


def rsa_verify(public_key: RSAPublicKey, message: bytes, signature: bytes) -> bool:
    """Verify RSA-PSS signature."""
    try:
        s = _bytes_to_int(signature)
        m = _pow_mod(s, public_key.e, public_key.n)
        em_bits = public_key.n.bit_length() - 1
        em_len = (em_bits + 7) // 8
        em = _int_to_bytes(m, em_len)
        msg_hash = sha256(message)
        return _pss_verify(msg_hash, em, em_bits)
    except Exception:
        return False


# ─── Convenience: Base64 serialization ───────────────────────────────────────

import base64, json


def serialize_public_key(pub: RSAPublicKey) -> str:
    return base64.b64encode(json.dumps(pub.to_dict()).encode()).decode()


def deserialize_public_key(s: str) -> RSAPublicKey:
    return RSAPublicKey.from_dict(json.loads(base64.b64decode(s).decode()))


def serialize_private_key(priv: RSAPrivateKey) -> str:
    return base64.b64encode(json.dumps(priv.to_dict()).encode()).decode()


def deserialize_private_key(s: str) -> RSAPrivateKey:
    return RSAPrivateKey.from_dict(json.loads(base64.b64decode(s).decode()))
