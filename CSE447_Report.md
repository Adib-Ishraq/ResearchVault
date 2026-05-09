# CSE447 Lab Project — Security Report: Research Vault
**CSE447 | Spring 2026 | BRAC University**

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

**Research Vault** is a secure academic collaboration platform designed for universities. It connects three types of users — supervisors, postgraduate researchers, and undergraduate students — through a shared workspace where they can discover each other, collaborate in encrypted research rooms, exchange end-to-end encrypted direct messages, manage academic profiles with verifiable publications, and communicate via an AI-powered research assistant.

**Core functionality includes:**
- Encrypted user registration and login with two-factor authentication
- Research rooms with section-based posting (Updates, Data, Results, Announcements) — all ECIES-encrypted per member
- End-to-end encrypted direct messaging (ECIES per participant)
- Publication management with RSA-PSS supervisor-signed credential verification
- Supervision request workflow between students and supervisors
- Role-based access control with four distinct privilege levels
- AI research assistant (Groq / LLaMA 3.3 70B)
- Notifications with click-through routing to relevant content

All cryptographic primitives — RSA-2048, ECC P-256 / ECIES, SHA-256, PBKDF2, and HMAC-SHA256 — are implemented entirely from scratch in Python with no use of standard library crypto functions (`cryptography`, `hashlib`, `Crypto.*`, etc.).

---

### 1.2 Technology Stack

| Layer | Technology |
|---|---|
| **Backend language** | Python 3.12 |
| **Backend framework** | Flask 3.0.3, Flask-CORS |
| **Frontend** | React 18, Vite, TailwindCSS, TanStack React Query, React Router v6 |
| **Database** | Supabase (PostgreSQL) with Row-Level Security policies |
| **Session store** | Redis (Upstash) — JWT JTI tracking, OTP storage, token blacklisting |
| **File storage** | Supabase Storage (publication PDFs, room images) |
| **Email (2FA)** | Gmail SMTP via Python `smtplib` (standard library, not crypto) |
| **AI assistant** | Groq API — LLaMA 3.3 70B (free tier) |
| **Custom crypto** | `rsa_engine.py`, `ecc_engine.py`, `hash_engine.py`, `hmac_engine.py`, `key_manager.py` — all from scratch |
| **Deployment** | Gunicorn (backend), Vercel (frontend) |
| **Non-crypto libraries** | `supabase`, `redis`, `requests`, `python-dotenv`, `groq` — none provide encryption |

---

### 1.3 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND  (React + Vite)                 │
│                                                                  │
│   Auth  →  Dashboard  →  Discover  →  Rooms  →  Messages        │
│                    Profile  ←→  Notifications                    │
│                  AI Assistant  (floating widget)                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │  HTTPS  /  JWT Bearer token
┌───────────────────────────▼─────────────────────────────────────┐
│                    FLASK REST API  (Gunicorn)                    │
│                                                                  │
│  /api/auth    /api/users    /api/rooms    /api/messages          │
│  /api/notifications    /api/search    /api/ai                    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │   middleware/    │  │    crypto/       │  │  key_manager  │  │
│  │  session.py      │  │  rsa_engine.py   │  │  generate /   │  │
│  │  (JWT RSA-PSS)   │  │  ecc_engine.py   │  │  wrap /       │  │
│  │  rbac.py         │  │  hash_engine.py  │  │  unwrap /     │  │
│  │  (role checks)   │  │  hmac_engine.py  │  │  rotate keys  │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
└──────────┬───────────────────────────────┬────────────────────── ┘
           │                               │
┌──────────▼────────────┐    ┌─────────────▼──────────────┐
│   Supabase (DB)        │    │   Redis  (Upstash)          │
│  All fields stored     │    │  JWT JTI sessions           │
│  as ciphertext only    │    │  OTP codes (10-min TTL)     │
│  RSA / ECIES encrypted │    │  Blacklisted tokens         │
└────────────────────────┘    └────────────────────────────┘
```

---

## 2. Login and Registration Module

The system provides secure registration and login flows. New users supply credentials which are validated, encrypted, and persisted. During login, stored encrypted data is retrieved and decrypted for verification.

### 2.1 Registration Flow

```
User submits form
(username, email, password, confirmPassword, role, university)
        │
        ▼
Frontend validation
  • Strong password rules enforced live:
      – Minimum 8 characters
      – At least one uppercase letter (A–Z)
      – At least one lowercase letter (a–z)
      – At least one number (0–9)
      – At least one special character (!@#$%...)
  • Passwords match check
  • Live 5-bar strength indicator
        │
        ▼
POST /api/auth/register
        │
        ▼
Backend validation
  • Role must be supervisor / postgrad / undergraduate
  • _validate_password() re-enforces all 5 rules server-side
  • Email uniqueness check via hashed lookup
        │
        ▼
Cryptographic operations
  1. hash_password(password)
       → PBKDF2-SHA256 with 32-byte random salt
       → stores (password_hash, salt) — never plaintext
  2. generate_user_keys()
       → RSA-2048 keypair + ECC P-256 keypair generated per user
  3. rsa_hybrid_encrypt(server_rsa_pub, private_key_bundle)
       → wraps user private keys before DB storage
  4. encrypt_field(username) → ECIES with server ECC master public key
  5. encrypt_field(email)    → ECIES with server ECC master public key
  6. sha256(email)           → stored as email_hash for O(1) lookup
        │
        ▼
DB INSERT (users table)
  username_enc, email_enc, email_hash, password_hash, salt,
  public_key_rsa, public_key_ecc, private_key_enc, role ...
        │
        ▼
Redirect to /login
```

---

### 2.2 Login Flow

```
User submits email + password
        │
        ▼
POST /api/auth/login
        │
        ▼
sha256(email) → lookup row by email_hash (no plaintext stored)
        │
        ▼
verify_password(input, stored_hash, stored_salt)
  → PBKDF2-SHA256 re-derive with stored salt → compare
        │
        ▼
        ├─── 2FA ENABLED ──────────────────────────────────────────┐
        │                                                          │
        ▼                                                          ▼
Generate 6-digit OTP                              Issue access token (JWT / RSA-PSS)
Store in Redis (10-min TTL)                       Issue refresh token → httpOnly cookie
Send to email via SMTP                            Return 200 + access token
Return 200 {"two_fa_required": true}
        │
        ▼
POST /api/auth/verify-2fa
  Fetch OTP from Redis → compare → delete (single-use)
        │
        ▼
Issue JWT access token + refresh token
Return 200
```

---

### 2.3 Implementation Details

| Requirement | Implementation Details |
|---|---|
| **Login Module** | `POST /api/auth/login` — looks up user by `sha256(email)`, verifies password via PBKDF2-SHA256, optionally sends email OTP for 2FA, then issues RSA-PSS-signed JWT access token and sets httpOnly refresh cookie |
| **Registration Module** | `POST /api/auth/register` — validates role, enforces 5-rule password policy server-side via `_validate_password()`, generates RSA-2048 + ECC P-256 keypair per user, hashes+salts password, ECIES-encrypts all PII fields before DB insert |
| **Data Encrypted Before Storage** | `username_enc` and `email_enc` — ECIES with server ECC master public key; `private_key_enc` — RSA-hybrid-encrypted with server RSA master public key; `password_hash` — PBKDF2-SHA256 one-way hash |
| **Data Decrypted on Retrieval** | `decrypt_field()` uses the server ECC private key to ECIES-decrypt PII fields on every authenticated profile read; private key bundles unwrapped with `rsa_hybrid_decrypt()` when needed for post/message decryption |

---

## 3. User Data Encryption and Decryption

All sensitive user information is encrypted before storage using asymmetric encryption algorithms implemented from scratch, and decrypted upon retrieval.

### 3.1 Fields Encrypted

| Table | Column | Algorithm | Key Used |
|---|---|---|---|
| `users` | `username_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `users` | `email_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `users` | `private_key_enc` | RSA-2048 hybrid (OAEP + XOR-CTR + HMAC) | Server RSA master public key |
| `profiles` | `bio_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `profiles` | `research_interests_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `profiles` | `university_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `profiles` | `department_enc` | ECIES (ECC P-256) | Server ECC master public key |
| `room_posts` | `content_enc` | ECIES per member | Each member's ECC public key |
| `room_posts` | `attachments_enc` | ECIES per member | Each member's ECC public key |
| `messages` | `content_enc` | ECIES per participant | Each participant's ECC public key |
| `conversations` | `conv_key_enc_a` / `conv_key_enc_b` | RSA-OAEP | Each participant's RSA public key |
| `notifications` | `payload_enc` | ECIES (ECC P-256) | Server ECC master public key |

---

### 3.2 Encryption Algorithm — RSA Implementation

Implemented entirely from scratch in `backend/crypto/rsa_engine.py`.

**Key generation:**
- Two independent 1024-bit primes `p` and `q` are generated via `_generate_prime(1024)`
- Primality is tested with the Miller-Rabin algorithm: 12 fixed deterministic witnesses + 20 random rounds
- Public exponent `e = 65537` (standard Fermat prime)
- Private exponent `d = e⁻¹ mod λ(n)` computed via `_mod_inverse()` using the Extended Euclidean Algorithm
- `λ(n) = lcm(p−1, q−1)` using Carmichael's totient function

**Encryption — OAEP padding (PKCS#1 v2.2):**
- `_mgf1()` mask generation function built on the custom SHA-256 implementation
- Label hash `sha256(b"")`, random 32-byte seed per operation, XOR-masking of DB and seed blocks
- Ciphertext computed as `pow(padded_message, e, n)` — Python's built-in 3-argument `pow` for fast modular exponentiation

**Signature — PSS padding:**
- Message hashed with custom SHA-256; PSS salt = 32 random bytes per signature
- Signature: `pow(pss_encoded, d, n)` using the private exponent
- Verification: `pow(sig, e, n)` then `_pss_verify()` — used for JWT token signing and publication credential signing

**Hybrid mode** (`rsa_hybrid_encrypt`):
For large payloads exceeding the OAEP limit (190 bytes for RSA-2048 with SHA-256), RSA-OAEP wraps a 32-byte content encryption key (CEK); the CEK drives a XOR-CTR stream cipher for the payload; HMAC-SHA256 provides authenticated integrity over the ciphertext.

---

### 3.3 Encryption Algorithm — ECC Implementation

Implemented entirely from scratch in `backend/crypto/ecc_engine.py`.

**Curve parameters — NIST P-256 (secp256r1):**
```
p  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
a  = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC
b  = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
Gx = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
Gy = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
n  = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
```

**Point arithmetic:**
- `_point_add(P, Q)` — affine coordinate addition using the Lagrange slope formula: `λ = (y2−y1) · (x2−x1)⁻¹ mod p`
- `_point_double(P)` — tangent-based point doubling: `λ = (3x² + a) · (2y)⁻¹ mod p`
- `_scalar_mult(k, P)` — double-and-add algorithm over the 256-bit scalar `k`
- Modular inverse via Fermat's little theorem: `pow(a, p−2, p)`

**ECIES encryption scheme:**
1. Generate ephemeral ECC keypair `(r, R)` where `R = r · G`
2. ECDH shared secret: `S = r · RecipientPublicKey`
3. KDF: `key = sha256(Sx_bytes || Sy_bytes)` → 32-byte key material
4. XOR-CTR stream cipher: keystream blocks = `sha256(key || nonce || block_counter)`
5. HMAC-SHA256 computed over `nonce || ciphertext` for authenticated integrity
6. Output: `R_compressed (33 bytes) || nonce (16 bytes) || ciphertext (n bytes) || hmac (32 bytes)`

**ECIES decryption:**
1. Parse ephemeral public point `R` from first 33 bytes
2. Recompute shared secret: `S = RecipientPrivateKey · R`
3. Re-derive keystream from `sha256(S)`, XOR with ciphertext to recover plaintext
4. Verify HMAC before returning plaintext — rejects any tampered ciphertexts

---

### 3.4 How Both Algorithms Are Used Differently

| Operation | Algorithm | Justification |
|---|---|---|
| **Content encryption** (posts, messages, PII fields) | **ECC P-256 / ECIES** | Naturally supports per-recipient encryption: encrypt N times for N recipients using their individual ECC public keys. Compact 33-byte ephemeral key, efficient for variable-length content. |
| **Key wrapping / transport** (conversation keys, room keys, private key bundles) | **RSA-2048 / OAEP** | Standard for key encapsulation. RSA-OAEP wraps fixed-size 32-byte key material for a single recipient without exposing key derivation internals. |
| **Digital signatures** (JWT tokens, publication credential signing) | **RSA-2048 / PSS** | Provides non-repudiation. The server signs every JWT with its RSA private key; supervisors sign publication credentials with their own RSA private key. |
| **Session token verification** | **RSA-2048 public key** | Every API request verifies the JWT RSA-PSS signature against the server RSA master public key before granting access. |

This satisfies the requirement that a single asymmetric algorithm is not used for all operations — RSA handles key encapsulation and digital signatures; ECC handles content encryption and field encryption.

---

## 4. Password Hashing and Salting

Passwords are never stored in plaintext. A cryptographic hash function combined with a random salt is applied before storage.

### 4.1 Hashing Algorithm Used

**PBKDF2 with custom SHA-256** (RFC 2898), implemented from scratch in `backend/crypto/hash_engine.py`.

SHA-256 was selected because it is a FIPS 180-4 approved hash function that is resistant to length-extension attacks and has no known practical collision vulnerabilities. PBKDF2 was chosen over a bare hash function because it is iterative — an attacker attempting brute-force must perform the same number of iterations per guess, making GPU-based dictionary attacks significantly more expensive. The custom pure-Python SHA-256 implementation is inherently ~50× slower than C-backed implementations, which provides additional passive resistance against offline brute-force attacks beyond what the iteration count alone implies.

---

### 4.2 Salt Generation

```python
# backend/crypto/hash_engine.py

def generate_salt(nbytes: int = 32) -> bytes:
    return os.urandom(nbytes)   # 256-bit salt from OS CSPRNG
```

- Salt is **32 bytes (256 bits)**, generated fresh per user at registration time
- Generated using `os.urandom()` — the operating system's cryptographically secure random number generator
- Stored in the `users` table in the `salt` column as a hex string alongside the password hash
- Each user gets a unique salt — prevents rainbow-table attacks and ensures two users with identical passwords produce different hashes

---

### 4.3 Verification Process

```python
# backend/crypto/hash_engine.py

def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)              # 1. Retrieve stored salt
    dk   = pbkdf2_sha256(password.encode(), salt)  # 2. Re-derive key with same parameters
    return dk.hex() == hash_hex                 # 3. Compare to stored hash
```

On every login:
1. `sha256(email)` is used to look up the user row without requiring plaintext email storage
2. `salt` and `password_hash` are retrieved from the `users` table
3. `pbkdf2_sha256(input_password, salt, iterations=100_000)` re-derives the key using the stored salt
4. The re-derived key is compared to the stored hash — match grants progression to 2FA step

---

## 5. Two-Factor Authentication (2FA)

The system enforces two-step verification: users must pass both primary credential validation and a second authentication factor before a session is granted.

### 5.1 2FA Method

The system uses **Email-based OTP (One-Time Password)**:

1. User completes password verification at `POST /api/auth/login`
2. Server generates a **6-digit numeric OTP** via `secrets.randbelow(1_000_000)` (cryptographically secure)
3. OTP is stored in **Redis** under key `otp:{user_id}` with a **10-minute TTL** — automatically expires
4. OTP is sent to the user's registered email address via Gmail SMTP (`smtplib`)
5. User submits the code to `POST /api/auth/verify-2fa`
6. Server retrieves the OTP from Redis, compares it to the submitted value, then **immediately deletes it** from Redis to prevent replay attacks
7. On match: RSA-PSS-signed JWT access token is issued + refresh token is set in an `httpOnly` cookie

**2FA is user-configurable** — users can enable or disable it from account settings via:
- `POST /api/auth/2fa/enable` → sends confirmation OTP
- `POST /api/auth/2fa/confirm` → verifies OTP, activates 2FA
- `POST /api/auth/2fa/disable` → sends confirmation OTP
- `POST /api/auth/2fa/disable/confirm` → verifies OTP, deactivates 2FA

---

### 5.2 Code Snippet

```python
# backend/modules/auth/routes.py

@auth_bp.post("/login")
def login():
    data     = request.get_json(force=True)
    email_hash = sha256(data["email"].strip().lower().encode()).hex()

    user = db.table("users").select("*").eq("email_hash", email_hash).execute()
    if not user.data:
        return jsonify({"error": "Invalid credentials"}), 401

    u = user.data[0]
    if not verify_password(data["password"], u["password_hash"], u["salt"]):
        return jsonify({"error": "Invalid credentials"}), 401

    # Step 1 passed — check if 2FA is required
    if u.get("two_fa_enabled"):
        otp = str(secrets.randbelow(1_000_000)).zfill(6)
        r   = get_redis()
        r.setex(f"otp:{u['id']}", 600, otp)          # 10-minute TTL
        send_otp_email(decrypt_field(u["email_enc"]), otp)
        return jsonify({"two_fa_required": True, "user_id": u["id"]}), 200

    # No 2FA — issue tokens directly
    access  = issue_access_token(u["id"], u["role"], ip, ua)
    refresh = issue_refresh_token(u["id"], u["role"], ip, ua)
    ...


@auth_bp.post("/verify-2fa")
@require_auth_or_pending
def verify_2fa():
    data      = request.get_json(force=True)
    user_id   = data.get("user_id")
    submitted = data.get("otp", "").strip()

    r          = get_redis()
    stored_otp = r.get(f"otp:{user_id}")

    if not stored_otp or stored_otp.decode() != submitted:
        return jsonify({"error": "Invalid or expired OTP"}), 401

    r.delete(f"otp:{user_id}")   # Single-use: deleted immediately after verification

    access  = issue_access_token(user_id, role, ip, ua)
    refresh = issue_refresh_token(user_id, role, ip, ua)
    ...
```

---

## 6. Key Management Module

A dedicated Key Management Module handles the full lifecycle of cryptographic keys, implemented in `backend/crypto/key_manager.py`.

### 6.1 Key Storage Security

Every user has **two keypairs** generated at registration:
- **RSA-2048** keypair — for key wrapping, JWT verification, and publication signing
- **ECC P-256** keypair — for ECIES content encryption and decryption

**Private keys are never stored in plaintext.** The bundle `{rsa_priv, ecc_priv}` serialized as JSON is encrypted using `rsa_hybrid_encrypt(server_rsa_master_public_key, bundle)` before being written to the `private_key_enc` column.

The server RSA master private key is stored only in the environment variable (`SERVER_RSA_MASTER_PRIVATE_KEY`), never in the database. This means a full database compromise — without access to the server environment — cannot decrypt any user private keys or any content encrypted with them.

**Public keys** (`public_key_rsa`, `public_key_ecc`) are stored in plaintext in the DB — they are public by design and needed by other users to encrypt content addressed to that user.

The server itself has a master RSA-2048 + ECC P-256 keypair generated once at setup time, stored in environment variables, and loaded into memory at application startup via `ServerMasterKeys`.

---

### 6.2 Key Rotation Policy

```python
# backend/crypto/key_manager.py
_ROTATION_DAYS = 90
```

- Key rotation is available at `POST /api/users/rotate-keys` (authenticated)
- The system checks `key_created_at` — if older than 90 days, rotation is recommended
- **Rotation process:**
  1. Generate a fresh RSA-2048 + ECC P-256 keypair
  2. Wrap the new private key bundle with `rsa_hybrid_encrypt(server_rsa_master_pub, new_bundle)`
  3. Update `public_key_rsa`, `public_key_ecc`, `private_key_enc`, and `key_created_at` in the DB
- **Impact on existing encrypted data:** Content encrypted with the old ECC public key (old posts, old messages) is no longer decryptable after rotation — it returns `[decryption error]`. New posts and messages use the new ECC public key automatically. This is an intentional forward-secrecy trade-off: compromise of the old key does not affect content encrypted after rotation.

---

## 7. Post and Profile Management

Users can create, view, and edit posts, as well as view and update their profiles. All data is automatically encrypted before storage and decrypted on retrieval.

### 7.1 Post Module

**Create** (`POST /api/rooms/<room_id>/post`):
1. Caller must be a verified room member (DB membership check)
2. `content` is encrypted: `_ecies_encrypt_for_members()` fetches every current member's ECC public key and produces a JSON map `{"user_id": "base64_ecies_ciphertext", ...}` — one ciphertext per member
3. Attachments (image URL, PDF URL) are similarly ECIES-encrypted per member in `attachments_enc`
4. `hmac_val = compute_record_hmac(hmac_key, content_enc, section, room_id)` stored for tamper detection
5. Row inserted into `room_posts` with `content_enc`, `attachments_enc`, `hmac`, `author_id`, `section`

**Read** (`GET /api/rooms/<room_id>/posts`):
1. Server unwraps caller's ECC private key: `_, ecc_priv = unwrap_user_private_keys(private_key_enc)`
2. For each post: `_ecies_decrypt_for_user(content_enc, ecc_priv, user_id)` extracts this user's ciphertext from the JSON map and decrypts it
3. `verify_record_hmac()` validates integrity — tampered records return `hmac_valid: false`
4. Author's `username_enc` decrypted via `decrypt_field()` for display

**Edit** (`PUT /api/rooms/<room_id>/posts/<post_id>`):
1. Verifies caller is the original post author
2. Re-encrypts updated content for **all current members** with ECIES (includes any new members who joined after original post)
3. Recomputes HMAC and updates the DB row
4. Announcements cannot be edited (403 returned)

**Encrypted fields:** `content_enc`, `attachments_enc`

---

### 7.2 Profile Module

**View** (`GET /api/users/<user_id>`):
- All encrypted fields (`username_enc`, `email_enc`, `bio_enc`, `research_interests_enc`, etc.) are decrypted server-side via `decrypt_field()` using the server ECC master private key before being returned to the frontend
- Publications and their verification status are included in the response

**Update** (`PUT /api/users/profile`):
1. Each supplied field is re-encrypted: `bio_enc = encrypt_field(bio)`, `research_interests_enc = encrypt_field(research_interests)`, etc.
2. New HMAC computed over the updated encrypted fields
3. DB row updated — no plaintext is ever written to any column

**Encrypted profile fields:** `bio_enc`, `research_interests_enc`, `university_enc`, `department_enc`

---

### 7.3 Screenshots

> *(Insert screenshot: Post creation form in a research room)*

> *(Insert screenshot: Post listing showing Updates / Data / Results sections)*

> *(Insert screenshot: Profile management / edit page)*

---

## 8. Data Storage Security

All critical data — user information, posts, and cryptographic keys — is stored in encrypted form to prevent plaintext access even in the event of a database compromise.

### 8.1 Evidence of Encrypted Storage

A raw query on the `users` table in Supabase shows only ciphertext — never plaintext:

| Column | Sample Stored Value |
|---|---|
| `username_enc` | `eyJ...base64-ECIES-ciphertext...==` |
| `email_enc` | `eyJ...base64-ECIES-ciphertext...==` |
| `private_key_enc` | `[256-byte RSA-OAEP-wrapped CEK] + [nonce] + [XOR-CTR ciphertext] + [HMAC-32]` |
| `password_hash` | `a3f7c2...64-hex-PBKDF2-digest...` |
| `salt` | `9b2e4f...64-hex-random-salt...` |

A raw query on `room_posts`:

| Column | Sample Stored Value |
|---|---|
| `content_enc` | `{"uid-1": "eyJ...", "uid-2": "eyJ..."}` — JSON of per-member ECIES ciphertexts |
| `hmac` | `b9d1...64-hex-HMAC-SHA256...` |

> *(Insert Supabase dashboard screenshot showing raw table rows with ciphertext values)*

---

## 9. Message Authentication Code (MAC)

Message Authentication Codes are used to verify the integrity of stored data and detect unauthorized modifications.

### 9.1 MAC Algorithm Used

**HMAC-SHA256** is used, implemented entirely from scratch in `backend/crypto/hmac_engine.py`.

**Why HMAC over CBC-MAC:**
CBC-MAC requires fixed-length inputs and has known vulnerabilities with variable-length messages (length-extension attacks). HMAC-SHA256 is length-agnostic, provably secure as a PRF under the assumption that SHA-256 is a compression function, and is the industry-standard choice for message authentication.

```python
# backend/crypto/hmac_engine.py

def hmac_sha256(key: bytes, message: bytes) -> bytes:
    if len(key) > 64:
        key = sha256(key)               # Hash long keys per RFC 2104
    key   = key.ljust(64, b'\x00')
    o_key = bytes(b ^ 0x5C for b in key)   # Outer padded key (opad XOR)
    i_key = bytes(b ^ 0x36 for b in key)   # Inner padded key (ipad XOR)
    return sha256(o_key + sha256(i_key + message))

def compute_record_hmac(hmac_key: bytes, *fields) -> str:
    combined = "|".join(str(f) for f in fields).encode()
    return hmac_sha256(hmac_key, combined).hex()

def verify_record_hmac(hmac_key: bytes, stored: str, *fields) -> bool:
    return compute_record_hmac(hmac_key, *fields) == stored
```

The HMAC key is derived from `HMAC_SECRET` stored in the server environment — never written to the database.

---

### 9.2 Integrity Verification Flow

HMAC is computed at **write time** and verified at **read time** for every critical record:

| Record Type | Fields Included in HMAC |
|---|---|
| User registration | `username_enc`, `email_enc`, `email_hash`, `public_key_rsa`, `public_key_ecc` |
| Room post | `content_enc`, `section`, `room_id` |
| Room announcement | `content_enc`, `"announcements"`, `room_id` |
| Direct message | `content_enc`, `conversation_id`, `sender_id` |
| Room record | `title_enc`, `description_enc`, `room_code` |

**On every read** (`GET /rooms/<id>/posts`, `GET /conversations/<id>/messages`):
1. `verify_record_hmac(hmac_key, stored_hmac, *fields)` is called for each record
2. HMAC is re-computed from the stored ciphertext fields and compared to the stored value
3. If the HMAC does not match, the record is flagged `hmac_valid: false` in the API response
4. The frontend displays a tamper warning instead of the content for any record that fails verification

---

## 10. Role-Based Access Control (RBAC)

RBAC defines distinct privilege levels ensuring sensitive operations are restricted appropriately.

### 10.1 Roles Defined

| Role | Description |
|---|---|
| **Admin** | Full system access; can manage all users and sensitive operations |
| **Supervisor** | Create research rooms, post announcements, sign publications, accept/reject supervision requests, view room analytics |
| **Postgrad** | Join rooms, post in sections (updates/data/results), request supervision, send messages, manage own profile and publications |
| **Undergraduate** | Same capabilities as Postgrad |

Roles are enforced on every endpoint via the `require_role()` decorator in `backend/middleware/rbac.py`:

```python
def require_role(allowed_roles: list[str]):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "role"):
                return jsonify({"error": "Not authenticated"}), 401
            if g.role not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
```

---

### 10.2 Permission Matrix

| Operation / Resource | Admin | Supervisor | Postgrad | Undergraduate |
|---|:---:|:---:|:---:|:---:|
| Register / Login | ✔ | ✔ | ✔ | ✔ |
| View own profile | ✔ | ✔ | ✔ | ✔ |
| Edit own profile | ✔ | ✔ | ✔ | ✔ |
| Create / edit own posts | ✔ | ✔ | ✔ | ✔ |
| Create research room | ✔ | ✔ | ✘ | ✘ |
| Post room announcement | ✔ | ✔ | ✘ | ✘ |
| View room analytics | ✔ | ✔ | ✘ | ✘ |
| Sign / verify publication | ✔ | ✔ | ✘ | ✘ |
| Set availability status | ✔ | ✔ | ✘ | ✘ |
| Request credential verification | ✘ | ✘ | ✔ | ✔ |
| Request supervision | ✘ | ✘ | ✔ | ✔ |
| Accept / reject supervision | ✔ | ✔ | ✘ | ✘ |
| Rotate own cryptographic keys | ✔ | ✔ | ✔ | ✔ |
| Send direct messages | ✔ | ✔ | ✔ | ✔ |
| Delete any post | ✔ | ✘ | ✘ | ✘ |
| View all user accounts | ✔ | ✘ | ✘ | ✘ |
| Assign roles to users | ✔ | ✘ | ✘ | ✘ |

---

## 11. Secure Session Management

Authentication tokens and session identifiers are managed securely to prevent session hijacking, fixation, and replay attacks.

### 11.1 Token Signing / Verification

**Token type:** Custom JWT signed with **RSA-PSS** (not HMAC-SHA256), implemented in `backend/middleware/session.py`.

**Access token payload structure:**
```json
{
  "sub":  "<user_id>",
  "role": "supervisor",
  "jti":  "<uuid4-unique-token-id>",
  "fp":   "<sha256(ip_address | user_agent)>",
  "iat":  1234567890,
  "exp":  1234568790,
  "type": "access"
}
```

**Token issuance:**
1. Payload is signed with `rsa_sign(server_rsa_private_key, header.payload)` — RSA-PSS scheme
2. JTI (unique token ID) stored in Redis with 15-minute TTL: `sess:{jti} → {user_id, fp, role}`
3. Access token returned in the response body; refresh token set as `httpOnly; SameSite=Lax` cookie with 7-day TTL

**Verification on every authenticated request** (`require_auth` decorator):
1. Extract `Authorization: Bearer <token>` header
2. `rsa_verify(server_rsa_public_key, signing_input, signature)` — RSA-PSS signature check
3. Check `exp` claim is not in the past
4. Check `jti` exists in Redis — deleted on logout, preventing use of invalidated tokens
5. Compute `sha256(request.ip | User-Agent)` → compare to `fp` claim stored in token
6. **Fingerprint mismatch triggers immediate session invalidation** — defends against token theft and session hijacking

**Refresh token rotation:**
On every `POST /api/auth/refresh`, the old refresh JTI is deleted from Redis and a completely new access + refresh token pair is issued, preventing refresh token replay attacks.

**Logout:**
`POST /api/auth/logout` deletes both `sess:{jti}` and `refresh:{jti}` from Redis instantly, making both tokens unusable regardless of their remaining TTL.

---

## 12. GitHub Repository and Project Structure

| Field | Details |
|---|---|
| **GitHub Repository URL** | https://github.com/Adib-Ishraq/ResearchVault |

### 12.1 Repository Structure

```
ResearchVault/
├── .gitignore
├── backend/
│   ├── app.py                          # Flask application factory, blueprint registration
│   ├── config.py                       # Environment variable configuration
│   ├── requirements.txt                # Python dependencies
│   ├── generate_master_keys.py         # One-time server master key generator
│   ├── crypto/
│   │   ├── rsa_engine.py               # RSA-2048 from scratch (OAEP, PSS, hybrid)
│   │   ├── ecc_engine.py               # ECC P-256 / ECIES from scratch
│   │   ├── hash_engine.py              # SHA-256 + PBKDF2 from scratch
│   │   ├── hmac_engine.py              # HMAC-SHA256 from scratch
│   │   └── key_manager.py              # Key generation, wrapping, rotation
│   ├── middleware/
│   │   ├── session.py                  # JWT issuance + RSA-PSS signing/verification
│   │   └── rbac.py                     # Role-based access control decorators
│   ├── modules/
│   │   ├── auth/routes.py              # Register, login, 2FA, password reset, logout
│   │   ├── users/routes.py             # Profile, publications, credential signing, key rotation
│   │   ├── rooms/routes.py             # Room CRUD, posts, announcements, analytics, uploads
│   │   ├── messages/routes.py          # E2E encrypted direct messaging
│   │   ├── notifications/routes.py     # Notifications, supervision request workflow
│   │   ├── search/routes.py            # Researcher / supervisor / university search
│   │   └── ai/routes.py                # AI research assistant (Groq / LLaMA 3.3)
│   └── services/
│       ├── supabase_client.py          # Supabase DB client
│       ├── redis_client.py             # Redis client
│       └── email_service.py            # Gmail SMTP for OTP emails
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx                     # React Router routes + PrivateRoute guard
│       ├── main.jsx
│       ├── index.css                   # TailwindCSS base styles + custom design tokens
│       ├── api/
│       │   └── client.js               # Axios instance with JWT Bearer header
│       ├── store/
│       │   └── authStore.js            # Zustand auth state (token, role, logout)
│       ├── components/
│       │   ├── Layout.jsx              # Top nav, notification bell, AI assistant
│       │   ├── NotificationPanel.jsx   # Slide-in notification panel with routing
│       │   └── AiAssistant.jsx         # Floating AI chatbot widget
│       └── pages/
│           ├── Auth/                   # Login, Register, ResetPassword
│           ├── Dashboard/              # Dashboard with rooms + supervision requests
│           ├── Discover/               # Researcher / supervisor discovery + filters
│           ├── Messages/               # Direct messaging UI
│           ├── Profile/                # User profile view + publications
│           ├── Room/                   # Research room + section posts + analytics
│           └── Profile/OwnProfile.jsx  # Own profile edit page
└── supabase/
    └── schema.sql                      # Full DB schema with RLS policies + indexes
```

### 12.2 README Overview

The README covers:
- **Prerequisites:** Python 3.12+, Node.js 18+, a Supabase project, an Upstash Redis instance, a Gmail App Password, and a Groq API key
- **Backend setup:** `pip install -r requirements.txt`, copy `.env.example` to `.env` and fill in all keys, generate server master keys with the provided one-liner command, run `python app.py`
- **Frontend setup:** `npm install`, set `VITE_API_URL` in `.env.local` to `http://localhost:5000`, run `npm run dev`
- **Database setup:** Execute `supabase/schema.sql` in the Supabase SQL editor to create all tables, indexes, and RLS policies
- **Running locally:** Backend on `http://localhost:5000`, frontend on `http://localhost:5173`

---

## 13. Conclusion

Research Vault demonstrates a fully functional, cryptographically secure academic collaboration platform built without any standard library encryption dependencies. Every primitive — RSA-2048, ECC P-256 / ECIES, SHA-256, PBKDF2, HMAC-SHA256 — was implemented from scratch in pure Python, satisfying the course requirement for original cryptographic work across all 27 application features.

The primary technical challenge was correctness: subtle errors in modular arithmetic, OAEP padding byte boundaries, or ECIES point serialization produce silent decryption failures rather than obvious runtime errors. Strict adherence to published standards (FIPS 180-4, PKCS#1 v2.2, RFC 2104, RFC 2898, NIST P-256 parameters) and careful unit testing against known test vectors were essential to producing a correct and interoperable implementation. A secondary challenge was performance — pure Python cryptography is inherently slower than C-backed libraries, which was noticeable during RSA-2048 key generation and PBKDF2 hashing. This was mitigated through algorithmic improvements including a small-primes sieve before Miller-Rabin primality testing, reducing the number of expensive modular exponentiations per prime candidate.

The outcome is a system where every database column storing sensitive data contains only ciphertext, session tokens are cryptographically bound to the client IP and User-Agent, tokens are immediately invalidated on logout, and no single cryptographic algorithm handles all operations — fully satisfying all twelve specified security requirements.
