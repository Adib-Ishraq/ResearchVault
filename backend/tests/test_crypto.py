"""
Unit tests for the custom crypto module.
Run with: python -m pytest tests/test_crypto.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from crypto.hash_engine import sha256, sha256_hex, pbkdf2_sha256, hash_password, verify_password
from crypto.hmac_engine import hmac_sha256, compute_record_hmac, verify_record_hmac
from crypto.rsa_engine import (
    generate_rsa_keypair, rsa_encrypt, rsa_decrypt, rsa_sign, rsa_verify,
    serialize_public_key, deserialize_public_key,
    serialize_private_key, deserialize_private_key,
)
from crypto.ecc_engine import (
    generate_ecc_keypair, ecdh_shared_secret, ecies_encrypt, ecies_decrypt,
    serialize_ecc_public_key, deserialize_ecc_public_key,
    serialize_ecc_private_key, deserialize_ecc_private_key,
)


# ─── SHA-256 tests ────────────────────────────────────────────────────────────

class TestSHA256:
    def test_empty_string(self):
        result = sha256_hex(b"")
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_abc(self):
        # Verified against Python hashlib
        result = sha256_hex(b"abc")
        assert result == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    def test_known_vector(self):
        # "The quick brown fox jumps over the lazy dog"
        msg = b"The quick brown fox jumps over the lazy dog"
        result = sha256_hex(msg)
        assert result == "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592"

    def test_long_message(self):
        # Should handle messages that require multiple blocks
        msg = b"a" * 1000
        result = sha256(msg)
        assert len(result) == 32

    def test_deterministic(self):
        data = b"test data"
        assert sha256(data) == sha256(data)


# ─── PBKDF2 tests ─────────────────────────────────────────────────────────────

class TestPBKDF2:
    def test_hash_and_verify(self):
        password = "correct-horse-battery-staple"
        h, salt = hash_password(password)
        assert verify_password(password, h, salt)
        assert not verify_password("wrong-password", h, salt)

    def test_different_salts_produce_different_hashes(self):
        h1, s1 = hash_password("password123")
        h2, s2 = hash_password("password123")
        assert h1 != h2 or s1 != s2  # At minimum, salts differ

    def test_output_length(self):
        result = pbkdf2_sha256(b"password", b"salt", iterations=1000, dklen=32)
        assert len(result) == 32


# ─── HMAC tests ───────────────────────────────────────────────────────────────

class TestHMAC:
    def test_known_vector(self):
        # RFC 4231 test vector (key=20 bytes of 0x0b, data="Hi There")
        key = bytes([0x0b] * 20)
        data = b"Hi There"
        result = hmac_sha256(key, data).hex()
        assert result == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"

    def test_empty_message(self):
        key = b"key"
        result = hmac_sha256(key, b"")
        assert len(result) == 32

    def test_long_key(self):
        key = b"k" * 100  # Longer than block size — should be hashed first
        result = hmac_sha256(key, b"message")
        assert len(result) == 32

    def test_record_hmac_integrity(self):
        key = b"secret-key"
        fields = ("encrypted_username", "encrypted_email", "encrypted_contact")
        hmac1 = compute_record_hmac(key, *fields)
        assert verify_record_hmac(key, hmac1, *fields)
        assert not verify_record_hmac(key, hmac1, "tampered", "encrypted_email", "encrypted_contact")


# ─── RSA tests ────────────────────────────────────────────────────────────────

class TestRSA:
    @pytest.fixture(scope="class")
    def keypair(self):
        return generate_rsa_keypair(1024)  # 1024-bit for test speed

    def test_encrypt_decrypt(self, keypair):
        pub, priv = keypair
        plaintext = b"Hello, Research Vault!"
        ct = rsa_encrypt(pub, plaintext)
        assert rsa_decrypt(priv, ct) == plaintext

    def test_encrypt_decrypt_empty(self, keypair):
        pub, priv = keypair
        plaintext = b""
        ct = rsa_encrypt(pub, plaintext)
        assert rsa_decrypt(priv, ct) == plaintext

    def test_encrypt_decrypt_max_size(self, keypair):
        pub, priv = keypair
        # OAEP max for 1024-bit key: 1024//8 - 2*32 - 2 = 62 bytes
        plaintext = b"x" * 62
        ct = rsa_encrypt(pub, plaintext)
        assert rsa_decrypt(priv, ct) == plaintext

    def test_sign_verify(self, keypair):
        pub, priv = keypair
        message = b"Post authenticity: Dr. Smith, 2025"
        sig = rsa_sign(priv, message)
        assert rsa_verify(pub, message, sig)
        assert not rsa_verify(pub, b"tampered message", sig)

    def test_wrong_key_decrypt_fails(self, keypair):
        pub, _ = keypair
        _, other_priv = generate_rsa_keypair(1024)
        ct = rsa_encrypt(pub, b"secret")
        with pytest.raises(Exception):
            rsa_decrypt(other_priv, ct)

    def test_serialization_roundtrip(self, keypair):
        pub, priv = keypair
        pub2 = deserialize_public_key(serialize_public_key(pub))
        priv2 = deserialize_private_key(serialize_private_key(priv))
        assert pub2.n == pub.n
        assert pub2.e == pub.e
        assert priv2.d == priv.d

        # Functional after round-trip
        ct = rsa_encrypt(pub2, b"roundtrip test")
        assert rsa_decrypt(priv2, ct) == b"roundtrip test"


# ─── ECC tests ────────────────────────────────────────────────────────────────

class TestECC:
    @pytest.fixture(scope="class")
    def keypair(self):
        return generate_ecc_keypair()

    def test_ecdh_symmetric(self):
        pub_a, priv_a = generate_ecc_keypair()
        pub_b, priv_b = generate_ecc_keypair()
        secret_a = ecdh_shared_secret(priv_a, pub_b)
        secret_b = ecdh_shared_secret(priv_b, pub_a)
        assert secret_a == secret_b

    def test_ecies_encrypt_decrypt(self, keypair):
        pub, priv = keypair
        plaintext = b"Confidential research data"
        ct = ecies_encrypt(pub, plaintext)
        pt = ecies_decrypt(priv, ct)
        assert pt == plaintext

    def test_ecies_wrong_key_fails(self, keypair):
        pub, _ = keypair
        _, other_priv = generate_ecc_keypair()
        ct = ecies_encrypt(pub, b"secret")
        with pytest.raises(ValueError, match="MAC verification failed"):
            ecies_decrypt(other_priv, ct)

    def test_ecies_tamper_detected(self, keypair):
        pub, priv = keypair
        ct = bytearray(ecies_encrypt(pub, b"secret data"))
        ct[100] ^= 0xFF  # Tamper with ciphertext
        with pytest.raises(ValueError, match="MAC verification failed"):
            ecies_decrypt(priv, bytes(ct))

    def test_ecc_serialization_roundtrip(self, keypair):
        pub, priv = keypair
        pub2 = deserialize_ecc_public_key(serialize_ecc_public_key(pub))
        priv2 = deserialize_ecc_private_key(serialize_ecc_private_key(priv))
        assert pub2.point == pub.point
        assert priv2.scalar == priv.scalar

        # Functional after round-trip
        ct = ecies_encrypt(pub2, b"roundtrip")
        assert ecies_decrypt(priv2, ct) == b"roundtrip"

    def test_different_plaintexts_different_ciphertexts(self, keypair):
        pub, _ = keypair
        ct1 = ecies_encrypt(pub, b"message one")
        ct2 = ecies_encrypt(pub, b"message one")
        # ECIES uses random ephemeral keys — ciphertexts differ even for same input
        assert ct1 != ct2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
