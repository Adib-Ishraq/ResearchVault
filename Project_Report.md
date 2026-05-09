# Department of Computer Science and Engineering
**Course:** CSE447: Cryptography and Cryptanalysis
**Semester:** Spring 2026

---

# Project Report

**Title:** Research Vault — A Secure Academic Research Collaboration Platform

**Submitted To:** [Instructor Name]
**Group No:** [e.g., 01]
**Section:** [e.g., 01]
**Submission Date:** [DD Month YYYY]

---

## Group Members

| No. | Full Name | Student ID |
|---|---|---|
| 1 | [Member 1 Full Name] | [Member 1 Student ID] |
| 2 | [Member 2 Full Name] | [Member 2 Student ID] |
| 3 | [Member 3 Full Name] | [Member 3 Student ID] |

---

## Table of Contents

1. [Introduction and System Overview](#1-introduction-and-system-overview)
2. [Login and Registration Module](#2-login-and-registration-module)
3. [User Data Encryption and Decryption](#3-user-data-encryption-and-decryption)
4. [Password Hashing and Salting](#4-password-hashing-and-salting)
5. [Two-Factor Authentication (2FA)](#5-two-factor-authentication-2fa)
6. [Key Management Module](#6-key-management-module)
7. [Post and Profile Management](#7-post-and-profile-management)
8. [Data Storage Security](#8-data-storage-security)
9. [Message Authentication Code (MAC)](#9-message-authentication-code-mac)
10. [Role-Based Access Control (RBAC)](#10-role-based-access-control-rbac)
11. [Secure Session Management](#11-secure-session-management)
12. [GitHub Repository and Project Structure](#12-github-repository-and-project-structure)
13. [Conclusion](#13-conclusion)

---

## 1. Introduction and System Overview

This report documents the design, implementation, and security analysis of the CSE447 Lab Project. The system is a secure web application integrating multiple cryptographic protocols as required by the course specification. All encryption algorithms have been implemented from scratch without relying on built-in framework encryption functions.

### 1.1 Project Overview

Research Vault is a secure web application designed for academic research teams. It allows supervisors to create private research rooms and invite postgraduate or undergraduate students as members. Within each room, members collaborate by posting structured content across three sections — Updates, Data, and Results — while supervisors can post announcements and view analytics dashboards. Every piece of content is encrypted end-to-end using per-member asymmetric encryption, ensuring that even a full database compromise cannot expose plaintext research data. The platform also supports two-factor authentication, encrypted profile management, file attachments (images and PDFs), and role-based access control.

### 1.2 Technology Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.11 |
| Backend framework | Flask (application factory pattern) |
| Frontend framework | React 18 + Vite + React Router v6 |
| Frontend state | Zustand (auth), TanStack React Query (server cache) |
| Database | Supabase (PostgreSQL) |
| Session cache | Redis (Upstash) |
| Email delivery | Brevo HTTP API (via `requests`) |
| AI assistant | Groq API |
| Crypto (all from scratch) | SHA-256, PBKDF2-SHA256, HMAC-SHA256, RSA-2048, ECC P-256 + EC ElGamal |
| External libraries used | `flask`, `flask-cors`, `supabase`, `redis`, `requests`, `python-dotenv`, `gunicorn`, `groq` |

No built-in Python cryptographic functions (`hashlib`, `hmac`, `cryptography`, `Crypto.*`) are used anywhere.

### 1.3 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                          │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              React SPA  (Vite + React Router)           │   │
│   │   Zustand (auth state)    React Query (server cache)    │   │
│   │   Access token in memory  HttpOnly refresh cookie       │   │
│   └───────────────────────────┬─────────────────────────────┘   │
└───────────────────────────────│─────────────────────────────────┘
                                │  HTTPS  REST / JSON
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FLASK API  (Python)                        │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Auth Module  │  │ Rooms Module │  │   Users Module       │ │
│  └───────────────┘  └──────────────┘  └──────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Custom Crypto Layer                     │   │
│  │  SHA-256 · PBKDF2-SHA256 · HMAC-SHA256                  │   │
│  │  RSA-2048 OAEP/PSS (key wrapping, JWT signing)          │   │
│  │  ECC P-256 EC ElGamal (field + post encryption)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌────────────────┐  ┌───────────────┐  ┌────────────────────┐ │
│  │  RBAC / JWT    │  │  Session Mid. │  │  Email Service     │ │
│  │  Middleware    │  │  require_auth │  │  (Brevo HTTP API)  │ │
│  └────────────────┘  └───────────────┘  └────────────────────┘ │
└────┬──────────────────────┬──────────────────────┬─────────────┘
     │                      │                      │
     ▼                      ▼                      ▼
┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐
│    Redis      │   │    Supabase      │   │  External APIs    │
│  OTP codes   │   │  PostgreSQL DB   │   │  Brevo (email)    │
│  JWT JTIs    │   │  + File Storage  │   │  Groq (AI)        │
│  (with TTL)  │   │                  │   └───────────────────┘
└──────────────┘   └──────────────────┘
```

---

## 2. Login and Registration Module

The system provides secure registration and login flows. New users supply credentials which are validated, encrypted, and persisted. During login, stored encrypted data is retrieved and decrypted for verification.

### 2.1 Registration Flow

Registration is a two-step process gated by email OTP verification:

1. User submits: `email`, `password`, `username`, `role` (supervisor / postgrad / undergraduate), and optionally `university` and `contact`.
2. Server validates all fields and checks the password policy (min 8 chars, upper, lower, digit, special character).
3. Email is looked up by `SHA-256(email)` hash to check for duplicates — the raw email is never stored in plaintext at this stage.
4. Password is hashed immediately using PBKDF2-SHA256 with a fresh 32-byte random salt.
5. A 6-digit numeric OTP is generated and all pending registration data (hashed password, salt, user details) is stored in Redis under `reg_pending:{email_hash}` with a 10-minute TTL.
6. The OTP is emailed to the user via the Brevo API.
7. On `/register/verify`, the server retrieves the Redis payload, checks the OTP, and only then performs the full account creation: encrypt all PII fields with the server RSA master key, generate the user's personal RSA-2048 + ECC P-256 keypair, compute a row HMAC, and insert into the database.

### 2.2 Login Flow

1. User submits `email` and `password`.
2. Server computes `SHA-256(email)` and looks up the matching `email_hash` row in the `users` table.
3. The stored salt is retrieved and `PBKDF2-SHA256(input_password, salt)` is recomputed and compared to the stored hash.
4. If `two_fa_enabled = true`: a 6-digit OTP is generated, stored in Redis under `otp:{pre_token}` (10-min TTL), emailed to the user, and a temporary `pre_token` is returned to the client.
5. On `/verify-2fa`, the pre_token is looked up in Redis, the OTP is matched, and only then are JWT access + refresh tokens issued.
6. If 2FA is disabled, tokens are issued immediately after password verification.

### 2.3 Implementation Details

| Requirement | Implementation Details |
|---|---|
| Login Module | Email hash lookup → PBKDF2-SHA256 password verify → optional OTP 2FA step → RSA-PSS signed JWT issued |
| Registration Module | Fields: email, password (min 8 chars, uppercase, lowercase, digit, special char), username, role, university, contact |
| Data Encrypted Before Storage | `username_enc`, `email_enc`, `contact_enc`, `university_enc` — EC ElGamal encrypted with server ECC master public key before DB insert |
| Data Decrypted on Retrieval | Server uses ECC master private key to EC-ElGamal-decrypt fields on profile fetch and `/users/me` endpoint; email also decrypted to send OTP |

---

## 3. User Data Encryption and Decryption

All sensitive user information (e.g., username, email, contact info) is encrypted before storage using asymmetric encryption algorithms implemented from scratch, and decrypted upon retrieval.

### 3.1 Fields Encrypted

| Database Table | Field | Algorithm |
|---|---|---|
| `users` | `username_enc` | ECC P-256 EC ElGamal |
| `users` | `email_enc` | ECC P-256 EC ElGamal |
| `users` | `contact_enc` | ECC P-256 EC ElGamal |
| `users` | `private_key_enc` | RSA-2048 OAEP (chunked) — user's private key bundle wrapped with server RSA master key |
| `profiles` | `university_enc` | ECC P-256 EC ElGamal |
| `research_rooms` | `title_enc` | ECC P-256 EC ElGamal |
| `research_rooms` | `description_enc` | ECC P-256 EC ElGamal |
| `research_rooms` | `room_key_enc` | RSA-2048 OAEP — 32-byte room key wrapped with server RSA master key |
| `room_members` | `room_key_enc` | RSA-2048 OAEP — per-member copy of room key |
| `room_posts` | `content_enc` | ECC P-256 EC ElGamal — one independent ciphertext per room member |
| `room_posts` | `attachments_enc` | ECC P-256 EC ElGamal — per member |
| `notifications` | `payload_enc` | ECC P-256 EC ElGamal |

### 3.2 Encryption Algorithm — RSA-2048 Implementation

Implemented from scratch in `crypto/rsa_engine.py`. No external crypto library used.

- **Key size:** 2048 bits (two 1024-bit primes p, q)
- **Prime generation:** Miller-Rabin primality test with 12 deterministic witnesses + 20 random rounds; candidates forced odd with high-bit set
- **Key generation:** `n = p·q`, `λ(n) = lcm(p−1, q−1)`, public exponent `e = 65537`, `d = e⁻¹ mod λ(n)` via extended Euclidean algorithm
- **Encryption padding:** OAEP (PKCS#1 v2.2) with SHA-256 hash and MGF1 mask generation
- **Signature padding:** PSS (Probabilistic Signature Scheme) with SHA-256 and 32-byte random salt
- **Large data:** Because OAEP with RSA-2048/SHA-256 limits each block to 190 bytes, `rsa_encrypt_large` splits plaintext into 190-byte chunks and RSA-OAEP encrypts each chunk independently. Format: `[4B num_chunks] || ([2B ct_len] + [256B RSA ciphertext]) * n`. This is 100% asymmetric — no symmetric cipher or derived key.
- **Modular exponentiation:** Python's 3-argument `pow(base, exp, mod)` is used as an arithmetic primitive only (not a crypto library)

### 3.3 Encryption Algorithm — ECC P-256 EC ElGamal Implementation

Implemented from scratch in `crypto/ecc_engine.py`. No external crypto library used.

- **Curve:** NIST P-256 — `y² = x³ + ax + b (mod p)` with standardized parameters
- **Field arithmetic:** Modular inverse via Fermat's little theorem: `a⁻¹ = aᵖ⁻² mod p` using Python's `pow`
- **Point operations:** Affine coordinate point addition and doubling; point at infinity as sentinel `None`
- **Scalar multiplication:** Double-and-add algorithm iterating over each bit of the scalar

**Plaintext-to-point encoding (Koblitz-style):**
Since EC ElGamal encrypts curve points (not arbitrary bytes), each 30-byte chunk of plaintext is embedded as a P-256 point:
```
x = m_int * 256 + attempt  (attempt = 0..255)
y = √(x³ + ax + b) mod p  using pow(y_sq, (p+1)//4, p)  — valid since p ≡ 3 (mod 4)
```
The low 8 bits of x store the attempt counter; the upper 240 bits carry the plaintext. Decoding simply extracts `x >> 8`.

**Encryption (EC ElGamal per chunk):**
```
C1 = r·G         (random scalar r, generator G)
C2 = M + r·Q     (M = encoded plaintext point, Q = recipient ECC public key)
```

**Decryption:**
```
M = C2 − priv·C1   (since Q = priv·G → r·Q = priv·r·G = priv·C1)
```

No symmetric cipher, no XOR stream, no keystream — only elliptic curve point arithmetic.

### 3.4 How Both Algorithms Are Used Differently

| Operation | Algorithm | Reason |
|---|---|---|
| Encrypting all PII fields (username, email, contact, university, room title/description, post content, notifications) | **ECC P-256 EC ElGamal** | Per-user/per-member encryption where each recipient has their own ECC keypair; ECC public keys are compact (32 bytes) making multi-recipient maps efficient |
| Storing per-user private key bundles | **RSA-2048 OAEP (chunked)** | Server master RSA key wraps the bundle; a single server key decrypts any user's stored private keys |
| Wrapping per-member room keys | **RSA-2048 OAEP** | 32-byte room key fits in one OAEP block |
| JWT signing and verification | **RSA-2048 PSS** | Asymmetric signature — any server instance can verify with the public key |

Neither algorithm handles all operations. RSA handles key storage/wrapping and authentication tokens; ECC handles all content and field encryption.

---

## 4. Password Hashing and Salting

Passwords are never stored in plaintext. A cryptographic hash function combined with a random salt is applied before storage to prevent dictionary and rainbow-table attacks.

### 4.1 Hashing Algorithm Used

**PBKDF2 with HMAC-SHA256 as the PRF** (Password-Based Key Derivation Function 2, RFC 2898). SHA-256 was chosen as the underlying hash because:
- It is a well-analyzed, FIPS 140-2 approved function
- The project implements it from scratch (FIPS 180-4 specification), so no external crypto dependency is required
- PBKDF2 layered over HMAC-SHA256 adds iteration-based cost that slows brute-force attacks

The implementation produces a 32-byte (256-bit) derived key.

### 4.2 Salt Generation

- A **32-byte (256-bit) cryptographically random salt** is generated using `os.urandom(32)` for each registration and each password reset.
- The salt is stored alongside the password hash as `salt` (hex-encoded) in the `users` table.
- Using a per-user unique salt ensures that identical passwords produce completely different stored hashes, defeating rainbow table attacks.

```python
def generate_salt(nbytes: int = 32) -> bytes:
    return os.urandom(nbytes)

def hash_password(password: str) -> tuple[str, str]:
    salt = generate_salt(32)
    dk = pbkdf2_sha256(password.encode(), salt)
    return dk.hex(), salt.hex()
```

### 4.3 Verification Process

```python
def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    dk = pbkdf2_sha256(password.encode(), salt)
    return dk.hex() == hash_hex
```

1. The stored `salt` (hex) is retrieved from the database for the matching `email_hash` row.
2. `PBKDF2-SHA256(input_password, stored_salt, iterations=1000)` is recomputed.
3. The result is compared byte-for-byte against `password_hash`. No timing side-channel attack is possible because the comparison is on hex strings of equal length.

---

## 5. Two-Factor Authentication (2FA)

The system enforces two-step verification: the user must pass both primary credential validation and a second authentication factor before a session is granted.

### 5.1 2FA Method

The system implements **email-based OTP (One-Time Password)** as the second factor. The same mechanism is also used for registration verification and password reset — ensuring a consistent, thoroughly tested OTP pipeline.

**Flow when 2FA is enabled at login:**
1. User passes password check (first factor).
2. Server generates a 6-digit numeric OTP using `random.choices(string.digits, k=6)`.
3. Server creates a `pre_token = SHA-256(user_id || otp || timestamp)` and stores `{user_id, role, otp}` in Redis under `otp:{pre_token}` with a 10-minute TTL.
4. OTP is emailed to the user's registered (encrypted) email address via Brevo API.
5. Client receives `{requires_2fa: true, pre_token}` and prompts for OTP.
6. On `/verify-2fa`, the server retrieves the Redis entry using `pre_token`, checks the OTP, deletes the key (single-use), and only then issues the JWT access + refresh tokens.

**Flow for enabling 2FA (opt-in):**
1. Authenticated user calls `/auth/2fa/enable` → OTP sent to email.
2. User submits OTP to `/auth/2fa/confirm` → `two_fa_enabled = true` set in DB.

### 5.2 Code Snippet

```python
# Login Step 1 — password verified, 2FA required
if user["two_fa_enabled"]:
    otp = generate_otp()  # 6-digit numeric string
    pre_token = sha256(f"{user['id']}:{otp}:{time.time()}".encode()).hex()
    r.setex(f"otp:{pre_token}", 600, json.dumps({
        "user_id": user["id"],
        "role": user["role"],
        "otp": otp,
    }))
    real_email = decrypt_field(user_full.data[0]["email_enc"])
    send_otp_email(real_email, otp, "login")
    return jsonify({"requires_2fa": True, "pre_token": pre_token}), 200

# Login Step 2 — OTP verification
@auth_bp.post("/verify-2fa")
def verify_2fa():
    pre_token = data.get("pre_token", "")
    otp_input = data.get("otp", "")
    stored = r.get(f"otp:{pre_token}")
    if not stored:
        return jsonify({"error": "OTP expired or invalid"}), 401
    stored_data = json.loads(stored)
    if stored_data["otp"] != otp_input:
        return jsonify({"error": "Incorrect OTP"}), 401
    r.delete(f"otp:{pre_token}")   # single-use: delete immediately
    access = issue_access_token(stored_data["user_id"], stored_data["role"], ip, ua)
    refresh = issue_refresh_token(stored_data["user_id"], stored_data["role"], ip, ua)
    # ... set HttpOnly cookie and return access token
```

---

## 6. Key Management Module

A dedicated Key Management Module handles the full lifecycle of cryptographic keys: secure storage, and rotation.

### 6.1 Key Storage Security

The system uses a two-layer key hierarchy:

**Server master keypairs** (RSA-2048 + ECC P-256): Generated offline using `generate_master_keys.py` and stored only as environment variables (Base64-encoded). They are never written to the database.

**Per-user keypairs**: At registration, each user receives a fresh RSA-2048 keypair and a fresh ECC P-256 keypair. Both private keys are serialized to JSON, then the JSON bundle is encrypted using `rsa_encrypt_large(server_master_rsa_pub, bundle)` — chunked RSA-OAEP, purely asymmetric — and stored in `users.private_key_enc` as a Base64 blob. Private keys at rest are only readable by the server (which holds the master RSA private key in memory via environment variable). Even with full database read access, an attacker cannot recover any user's private keys without also compromising the server environment.

**Room keys**: Each room has a random 32-byte room key stored in two forms:
- `research_rooms.room_key_enc`: RSA-OAEP wrapped with server master RSA public key (used when new members join)
- `room_members.room_key_enc`: RSA-OAEP wrapped with each individual member's RSA public key

### 6.2 Key Rotation Policy

**Rotation schedule:** User keypairs carry a 90-day rotation period (`_ROTATION_DAYS = 90`). At key generation and after each rotation, `rotation_due` is written to the `users` table:
```python
"rotation_due": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
```

**`rotate_user_keys(old_enc)`:** Unwraps the current private key bundle using the server master RSA key, generates a brand-new RSA-2048 + ECC P-256 keypair, wraps the new private keys with `rsa_encrypt_large`, and returns a new `public_key_rsa`, `public_key_ecc`, `private_key_enc`, and `rotation_due` for a DB update.

**Invalidation without breaking existing records:** Because room posts are EC ElGamal encrypted per-member at post time using the member's *current* ECC public key stored in `room_members`, key rotation is forward-secure by design: all new posts automatically use the new public key. Historical posts encrypted to the old ECC key remain readable as long as the old private key is retained in a grace-period archive; once permanently deleted, those posts become inaccessible — a deliberate design trade-off. Password rotation (on reset) generates a new PBKDF2 hash with a fresh salt, which is always independent of encryption keys and causes no disruption to stored records.

---

## 7. Post and Profile Management

Users can create, view, and edit posts, as well as view and update their profiles. All post and profile data is automatically encrypted before storage and decrypted on retrieval.

### 7.1 Post Module

**Create (`POST /<room_id>/post` or `/<room_id>/announce`):**
1. Requester must be a `room_members` entry for this room.
2. Content is EC ElGamal encrypted individually for every current room member: for each member, the server fetches their `public_key_ecc`, runs `ecies_encrypt(member_ecc_pub, content_bytes)`, and stores `{user_id: base64_blob}` as a JSON string in `content_enc`. Each blob is fully independent — no shared key, no symmetric cipher.
3. An HMAC-SHA256 is computed over `content_enc || section || room_id` and stored with the post.
4. Attachments (image URL, PDF URL) are encrypted in the same per-member ECIES scheme into `attachments_enc`.

**Read (`GET /<room_id>/posts`):**
1. Server decrypts the requesting user's private key bundle with `rsa_decrypt_large(server_master_rsa_priv, private_key_enc)` to obtain the user's ECC private key.
2. For each post, extracts `content_enc[user_id]` (Base64) and calls `ecies_decrypt(user_ecc_priv, blob)`.
3. Only this user's ciphertext is decrypted — no other member's data is touched.

**Edit (`PUT /<room_id>/posts/<post_id>`):**
- Only the original author can edit their own post; announcements cannot be edited.
- Updated content is re-encrypted EC ElGamal for all current members (fresh encryption pass).

**Encrypted fields:**

| Field | Algorithm |
|---|---|
| `content_enc` | ECC P-256 EC ElGamal per member |
| `attachments_enc` | ECC P-256 EC ElGamal per member |

### 7.2 Profile Module

Users can view and update their profile, which includes:

| Field | Encrypted? | Algorithm |
|---|---|---|
| `username` | Yes | ECC P-256 EC ElGamal |
| `email` | Yes | ECC P-256 EC ElGamal |
| `contact` | Yes | ECC P-256 EC ElGamal |
| `university` | Yes | ECC P-256 EC ElGamal |
| `role` | No (plaintext enum) | — |

On profile update, the new value is re-encrypted EC ElGamal with the server ECC master public key, a new HMAC is computed over the updated row, and the database is updated.

### 7.3 Screenshots

> *(Insert screenshots of the post creation form, post listing by section, and profile management page here.)*

---

## 8. Data Storage Security

All critical data — user information, posts, and cryptographic keys — is stored in encrypted form to prevent plaintext access even in the event of a database compromise.

### 8.1 Evidence of Encrypted Storage

> *(Insert a screenshot of the Supabase database table view showing the `users` table with `username_enc`, `email_enc`, `private_key_enc` columns containing Base64-encoded ciphertext blobs; and the `room_posts` table showing `content_enc` as a JSON map of user IDs to Base64 EC ElGamal blobs.)*

A representative row in the `users` table:

| Column | Value (truncated) |
|---|---|
| `email_hash` | `a3f2b1c9...` (SHA-256 hex — lookup only, no decryption possible) |
| `email_enc` | `BAAAA...` (Base64 EC ElGamal blob) |
| `username_enc` | `BAAAA...` (Base64 EC ElGamal blob) |
| `password_hash` | `4d1e2f9a...` (PBKDF2 derived key hex) |
| `salt` | `7c3a8b2f...` (32-byte random salt hex) |
| `private_key_enc` | `BAAAA...` (Base64 chunked RSA-OAEP blob) |
| `hmac` | `9e1f4c2a...` (HMAC-SHA256 hex) |

No plaintext PII appears anywhere in the database. Post `content_enc` looks like:
```json
{"user-id-1": "BAAAA...", "user-id-2": "BAAAA..."}
```

---

## 9. Message Authentication Code (MAC)

Message Authentication Codes (MACs) are used to verify the integrity of stored data and detect any unauthorized modifications.

### 9.1 MAC Algorithm Used

**HMAC-SHA256** (RFC 2104), implemented entirely from scratch in `crypto/hmac_engine.py` using the custom SHA-256 implementation.

HMAC was chosen over CBC-MAC because:
- HMAC is provably secure as a PRF when the underlying hash is collision-resistant.
- CBC-MAC requires block-cipher infrastructure; HMAC reuses the already-implemented SHA-256.
- HMAC is length-extension attack resistant due to the nested construction.

**Implementation:**

```python
def hmac_sha256(key: bytes, message: bytes) -> bytes:
    if len(key) > 64:
        key = sha256(key)
    key = key.ljust(64, b'\x00')
    o_key_pad = bytes(b ^ 0x5C for b in key)
    i_key_pad = bytes(b ^ 0x36 for b in key)
    return sha256(o_key_pad + sha256(i_key_pad + message))
```

For database records, multiple encrypted fields are joined with a null-byte separator (preventing field-splicing attacks) before HMAC:

```python
def compute_record_hmac(secret_key: bytes, *fields: str) -> str:
    payload = b'\x00'.join(
        (f.encode() if isinstance(f, str) else f) for f in fields
    )
    return hmac_sha256_hex(secret_key, payload)
```

The HMAC secret key is loaded from the `HMAC_SECRET` environment variable and never stored in the database.

### 9.2 Integrity Verification Flow

HMACs are computed and stored at write time, and verified on critical reads:

| Record type | Fields included in HMAC | When verified |
|---|---|---|
| `users` row | `username_enc`, `email_enc`, `contact_enc`, `private_key_enc` | On profile fetch / login |
| `research_rooms` row | `title_enc`, `description_enc`, `room_code` | On room detail fetch |
| `room_posts` row | `content_enc`, `section`, `room_id` | On post read / analytics report |
| Analytics report (download) | Full canonical JSON of the report | Client-side: report includes its own `report_hmac` |

Verification uses **constant-time comparison** to prevent timing side-channel attacks:

```python
def verify_record_hmac(secret_key: bytes, expected_hex: str, *fields: str) -> bool:
    computed = compute_record_hmac(secret_key, *fields)
    if len(computed) != len(expected_hex):
        return False
    result = 0
    for a, b in zip(computed, expected_hex):
        result |= ord(a) ^ ord(b)
    return result == 0
```

---

## 10. Role-Based Access Control (RBAC)

Role-Based Access Control defines distinct privilege levels, ensuring that sensitive operations are restricted appropriately.

### 10.1 Roles Defined

| Role | Description |
|---|---|
| `supervisor` | Academic supervisor. Can create research rooms, post announcements, view analytics, download activity reports, remove members from rooms. |
| `postgrad` | Postgraduate student. Can join rooms via room code, post to Updates/Data/Results sections, edit own posts, view all sections. Cannot create rooms. |
| `undergraduate` | Undergraduate student. Same permissions as postgrad within a room. Cannot create rooms. |

The role is assigned at registration and stored in `users.role`. Room-level roles (`supervisor`, `member`) are stored separately in `room_members.role` to distinguish the room creator from other members.

Enforcement is via the `@require_role(["supervisor"])` and `@require_auth` decorators applied at the route level in Flask. Room-level role checks are done inline by querying `room_members` within the handler.

### 10.2 Permission Matrix

| Operation / Resource | Supervisor | Postgrad / Undergraduate |
|---|---|---|
| Register / Login | ✔ | ✔ |
| View own profile | ✔ | ✔ |
| Edit own profile | ✔ | ✔ |
| Enable / disable 2FA | ✔ | ✔ |
| Create research room | ✔ | ✘ |
| Join room via code | ✔ | ✔ |
| Post to Updates / Data / Results | ✔ | ✔ |
| Edit own post | ✔ | ✔ |
| Post announcements | ✔ (room supervisor only) | ✘ |
| View analytics dashboard | ✔ (room supervisor only) | ✘ |
| Download activity report | ✔ (room supervisor only) | ✘ |
| Remove a room member | ✔ (room supervisor only) | ✘ |
| View room code | ✔ (room supervisor only) | ✘ |
| Upload images / PDFs to posts | ✔ | ✔ |

---

## 11. Secure Session Management

Authentication tokens and session identifiers are managed securely to prevent session hijacking, fixation, and replay attacks.

### 11.1 Token Signing / Verification

**Token format:** Custom JWT with header `{"alg": "RS256-PSS", "typ": "JWT"}`, Base64URL-encoded.

**Signing:** The server signs the JWT using RSA-PSS with the server master RSA-2048 **private key** on every token issuance. The signing input is `base64url(header) || "." || base64url(payload)`.

**Verification:** On every protected request, the `require_auth` middleware extracts the Bearer token, calls `rsa_verify(server_master_rsa_public_key, signing_input, signature)`, and rejects any token whose PSS signature does not match.

**Access token:** 15-minute TTL, returned in the JSON response body, stored in JavaScript memory (never `localStorage`).

**Refresh token:** 7-day TTL, set as an `HttpOnly; Secure; SameSite=Strict` cookie — inaccessible to JavaScript, preventing XSS-based theft.

**Session fingerprinting (hijack detection):** At issuance, `SHA-256(IP || User-Agent)` is computed and stored in Redis alongside the JWT ID (`jti`). On every request, the fingerprint is recomputed and compared. A mismatch (different IP or browser) immediately deletes the session from Redis and returns 401 — treating the event as a possible session hijack.

**Replay prevention:** Each token contains a UUID `jti`. The `jti` is stored in Redis with the token's TTL. On logout, the `jti` entry is deleted from Redis; any subsequent use of the same token is rejected at the Redis lookup step even if the RSA signature is valid.

**Token rotation:** On refresh, the old refresh `jti` is deleted from Redis and a new access + refresh token pair is issued — preventing refresh token replay.

---

## 12. GitHub Repository and Project Structure

| Field | Details |
|---|---|
| GitHub Repository URL | `https://github.com/Adib-Ishraq/Research-Vault` |

### 12.1 Repository Structure

```
research-vault/
├── backend/
│   ├── app.py                    # Flask application factory
│   ├── config.py                 # Environment variable configuration
│   ├── requirements.txt
│   ├── crypto/
│   │   ├── hash_engine.py        # SHA-256 + PBKDF2-SHA256 (from scratch)
│   │   ├── hmac_engine.py        # HMAC-SHA256 (from scratch)
│   │   ├── rsa_engine.py         # RSA-2048 OAEP/PSS + chunked large encrypt (from scratch)
│   │   ├── ecc_engine.py         # ECC P-256 + EC ElGamal (from scratch)
│   │   └── key_manager.py        # Key lifecycle: generate, wrap, unwrap, rotate
│   ├── middleware/
│   │   ├── session.py            # JWT issue/verify, session fingerprinting
│   │   └── rbac.py               # require_role decorator
│   ├── modules/
│   │   ├── auth/routes.py        # Register (OTP gated), login, 2FA, logout, reset
│   │   ├── rooms/routes.py       # Create, join, post (EC ElGamal), analytics, member remove
│   │   └── users/routes.py       # Profile view/update
│   └── services/
│       ├── supabase_client.py
│       ├── redis_client.py
│       └── email_service.py      # Brevo HTTP API OTP delivery
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── vercel.json               # SPA catch-all rewrite
│   └── src/
│       ├── api/client.js         # Axios instance + token refresh interceptor
│       ├── store/authStore.js    # Zustand auth state
│       ├── components/
│       │   └── Layout.jsx
│       └── pages/
│           ├── Auth/             # Login, Register (with OTP step), 2FA
│           ├── Room/Room.jsx     # Room detail, posts, analytics, member management
│           ├── Dashboard/        # Room list
│           └── Profile/          # Profile view/edit
├── generate_master_keys.py       # One-time server key generation script
└── README.md
```

### 12.2 README Overview

The `README.md` covers:
- **Features** section listing all major capabilities (per-member ECIES encryption, 2FA, RBAC, analytics, etc.)
- **System Architecture** ASCII diagram showing the full component interaction
- **Tech Stack** tables for backend, frontend, and crypto
- **Custom Cryptography** section explaining from-scratch RSA, ECC, and EC ElGamal
- **Project Structure** full directory tree
- **Getting Started** — step-by-step backend setup (Python venv, `.env` configuration, running Flask) and frontend setup (npm install, `.env.local` with `VITE_API_URL`, running Vite)
- **Environment Variables** reference table listing all required keys for both backend and frontend
- **API Reference** tables for all Auth and Rooms endpoints with HTTP methods, paths, and auth requirements
- **Security Model** section explaining each cryptographic guarantee
- **Deployment** guide

---

## 13. Conclusion

Research Vault demonstrates that a fully functional, multi-user secure collaboration platform can be built with all cryptographic algorithms implemented entirely from scratch, using no external crypto library whatsoever. The most demanding challenge was replacing ECIES and hybrid RSA (both of which used symmetric XOR streams internally) with genuinely pure-asymmetric schemes — EC ElGamal for content encryption and chunked RSA-OAEP for key storage — after the course specification explicitly prohibited symmetric encryption. Implementing EC ElGamal required developing Koblitz-style plaintext-to-point encoding, exploiting the P-256 property `p ≡ 3 (mod 4)` for square root computation, and carefully accounting for chunk boundaries and last-chunk padding. A practical deployment challenge was the incompatibility of pure-Python PBKDF2 at 100,000 iterations with a resource-constrained free-tier server, requiring a trade-off between security margin and response latency. Switching from SMTP to an HTTP-based email API (Brevo) resolved outbound port restrictions on the hosting platform. Overall the project provided a deep, hands-on understanding of how classical asymmetric primitives (RSA, ECC, ElGamal) compose into a coherent real-world security architecture alongside session management, key hierarchies, integrity codes, and role-based access control.
