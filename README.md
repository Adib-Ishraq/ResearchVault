# Research Vault

> A secure academic collaboration platform where researchers, postgraduates, and supervisors collaborate inside encrypted research rooms.

All cryptographic primitives — SHA-256, RSA-2048, ECC P-256, HMAC-SHA256, PBKDF2 — are implemented **from scratch in pure Python** with no use of `hashlib`, `cryptography`, `pycryptodome`, or any standard library crypto module.

**Live demo:** [research-vault-opal.vercel.app](https://research-vault-opal.vercel.app)

---

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Custom Cryptography](#custom-cryptography)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Environment Variables](#environment-variables)
  - [Generating Master Keys](#generating-master-keys)
- [API Reference](#api-reference)
- [Security Model](#security-model)
- [Deployment](#deployment)
- [Team](#team)

---

## Features

### Authentication & Security
- **Email-verified registration** — A 6-digit OTP is sent to the user's email before the account is created; unverified accounts are never written to the database
- **Secure login** — PBKDF2-SHA256 password hashing (custom implementation) with a random 32-byte salt per user
- **Two-Factor Authentication (2FA)** — Optional OTP-based 2FA on login, stored in Redis with a 10-minute TTL
- **Password reset** — OTP-based recovery flow; email existence is not revealed to prevent enumeration
- **JWT sessions** — RSA-2048 signed access tokens (15-minute expiry) + HttpOnly refresh cookie with rotation and Redis JTI tracking
- **Session fingerprinting** — JWTs are bound to IP + User-Agent; mismatches are rejected
- **Role-based access control** — Supervisor, Postgraduate, Undergraduate roles enforced at every API endpoint

### Research Rooms
- **Encrypted workspaces** — Every room post is EC ElGamal encrypted per member using that member's ECC public key; only current members can decrypt content
- **Sections** — Four tabs: Updates, Data, Results, and Announcements
- **Post editing** — Authors can edit their own posts; content is re-encrypted for all current members on save
- **Announcements** — Supervisor-only broadcast with automatic in-app notification to all members
- **File attachments** — Image (jpg, png, gif, webp) and PDF uploads stored in Supabase Storage
- **Member management** — Supervisors can remove any member from the room; removed members are automatically excluded from future post encryptions
- **Activity analytics** — Total post counts, 30-day activity heatmap, per-member contribution breakdown, section breakdown chart
- **PDF activity report** — Supervisors can download a full printable HTML/PDF report of all room posts

### Collaboration
- **Discover** — Search and find other researchers by name or university
- **Direct Messaging** — Room-level messaging between members
- **Notifications** — In-app notification panel for room joins, announcements, and other events
- **Appointments** — Supervisors and students can schedule and manage appointments
- **AI Assistant** — Floating chat assistant powered by Groq (LLaMA 3.3 70B, free tier)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER (Browser)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VERCEL  (Frontend)                            │
│                                                                 │
│   React 18 + Vite + TailwindCSS                                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│   │  Auth    │ │Dashboard │ │  Rooms / │ │  Profile /       │  │
│   │  Pages   │ │Discover  │ │ Messages │ │  Appointments    │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│   Zustand (auth state)   Axios + React Query (data fetching)    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS  /api/*
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RENDER  (Backend)                             │
│              Flask + Gunicorn · Python 3.14                     │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  Custom Crypto Layer                        │ │
│  │  SHA-256 · PBKDF2-SHA256 · HMAC-SHA256                     │ │
│  │  RSA-2048 OAEP/PSS · ECC P-256 EC ElGamal                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  /auth   /rooms   /messages   /notifications   /ai   /users    │
│                                                                 │
│  RBAC Middleware · JWT (RSA-signed) · Session Management        │
└────────┬──────────────────┬─────────────────────┬──────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│  SUPABASE    │  │  UPSTASH REDIS   │  │       BREVO          │
│  (Postgres)  │  │  (Serverless)    │  │   (Email / OTP)      │
│              │  │                  │  │                      │
│ users        │  │ JWT sessions     │  │ Registration OTP     │
│ profiles     │  │ OTP tokens       │  │ 2FA codes            │
│ rooms        │  │ Pending signups  │  │ Password reset       │
│ room_members │  └──────────────────┘  └──────────────────────┘
│ room_posts   │
│ messages     │           ▼
│ notifications│  ┌──────────────────┐
│ appointments │  │    GROQ  (AI)    │
└──────────────┘  │  AI Assistant   │
                  └──────────────────┘
```

---

## Tech Stack

### Frontend

| Package | Version | Purpose |
|---|---|---|
| React | 18.3.1 | UI framework |
| Vite | 5.3.3 | Build tool & dev server |
| TailwindCSS | 3.4.6 | Utility-first styling |
| React Router DOM | 6.24.0 | Client-side routing |
| Zustand | 4.5.4 | Auth state management |
| Axios | 1.7.2 | HTTP client with interceptors |
| TanStack React Query | 5.50.1 | Server state caching & mutations |

### Backend

| Package | Version | Purpose |
|---|---|---|
| Flask | 3.0.3 | Web framework |
| Flask-CORS | 4.0.1 | Cross-origin request handling |
| Gunicorn | 22.0.0 | WSGI production server |
| Supabase | 2.5.0 | Database client (service role) |
| Redis | 5.0.7 | Session & OTP token storage |
| Requests | 2.32.3 | Brevo HTTP API calls |
| Groq | 0.11.0 | AI assistant inference |
| Python-dotenv | 1.0.1 | Environment variable loading |

---

## Custom Cryptography

Every cryptographic operation is implemented from scratch. No `hashlib`, `hmac`, `cryptography`, `pycryptodome`, or any other crypto library is used.

### Implementations

| Module | File | What it implements |
|---|---|---|
| SHA-256 | `crypto/hash_engine.py` | Full FIPS 180-4 — compression function, padding, digest |
| PBKDF2 | `crypto/hash_engine.py` | RFC 2898 PBKDF2 using custom HMAC-SHA256 as PRF |
| HMAC-SHA256 | `crypto/hmac_engine.py` | RFC 2104 HMAC built on custom SHA-256 |
| RSA-2048 | `crypto/rsa_engine.py` | Miller-Rabin primality, extended GCD, OAEP encrypt/decrypt, PSS sign/verify, chunked large-data encrypt |
| ECC P-256 | `crypto/ecc_engine.py` | Affine point arithmetic, scalar multiplication, Koblitz point encoding, EC ElGamal encrypt/decrypt |
| Key Manager | `crypto/key_manager.py` | Server master keys, user keypair generation/rotation, field encryption, room key wrapping |

### How post encryption works (EC ElGamal per-member)

Each room post is encrypted individually for every current room member using **pure EC ElGamal** — no symmetric cipher, no XOR stream, no derived key. Plaintext is embedded directly as elliptic curve points.

**Plaintext-to-point encoding (Koblitz-style):**
Each 30-byte chunk is embedded into a P-256 point:
```
x = m_int * 256 + attempt   (attempt = 0..255, stored in low 8 bits of x)
y = pow(x³ + ax + b, (p+1)//4, p)   — exact square root, valid since P-256 has p ≡ 3 (mod 4)
```

**Encryption — for each member, for each 30-byte chunk:**
```
r  ←  random scalar
C1 = r · G          (G = P-256 generator)
C2 = M + r · Q      (M = encoded plaintext point, Q = member ECC public key)
Store {user_id: base64([num_chunks][chunk_len][C1][C2]...)} in content_enc
```

**Decryption — for the requesting user:**
```
M = C2 − priv · C1
    = (M + r·Q) − priv·(r·G)
    = M + r·priv·G − priv·r·G  =  M
plaintext = x-coordinate of M >> 8  (strips the attempt counter byte)
```

No shared key, no symmetric cipher. Each member's ciphertext is fully independent. Removing a member automatically excludes them from all future encryptions because the encryption loop queries the live `room_members` table at write time.

### Record integrity

Every row written to the database (users, rooms, posts) includes an **HMAC-SHA256** over its encrypted fields, computed with a server-side secret key. This detects any direct database tampering independently of the application layer.

---

## Project Structure

```
research-vault/
│
├── backend/
│   ├── app.py                    # Flask application factory
│   ├── config.py                 # Loads all env vars into Config class
│   ├── requirements.txt
│   ├── generate_master_keys.py   # Run once — generates server RSA + ECC keypairs
│   │
│   ├── crypto/                   # All custom crypto (zero stdlib crypto)
│   │   ├── __init__.py
│   │   ├── hash_engine.py        # SHA-256, PBKDF2-SHA256, hash_password, verify_password
│   │   ├── hmac_engine.py        # HMAC-SHA256, compute_record_hmac, verify_record_hmac
│   │   ├── rsa_engine.py         # RSA-2048 — keygen, OAEP encrypt/decrypt, PSS sign/verify
│   │   ├── ecc_engine.py         # ECC P-256 — point arithmetic, Koblitz encoding, EC ElGamal encrypt/decrypt
│   │   └── key_manager.py        # ServerMasterKeys, generate_user_keys, encrypt_field, decrypt_field
│   │
│   ├── middleware/
│   │   ├── session.py            # issue_access_token, issue_refresh_token, require_auth
│   │   └── rbac.py               # require_role, supervisor_only, researcher_and_above
│   │
│   ├── models/
│   │   └── __init__.py
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   └── routes.py         # /register, /register/verify, /login, /verify-2fa,
│   │   │                         # /logout, /refresh, /reset-password, /2fa/*
│   │   ├── rooms/
│   │   │   └── routes.py         # /create, /join, /, /<id>, /<id>/members/<uid>,
│   │   │                         # /<id>/post, /<id>/posts, /<id>/posts/<pid>,
│   │   │                         # /<id>/announce, /<id>/analytics, /<id>/upload-*
│   │   ├── messages/
│   │   │   └── routes.py         # Room messaging endpoints
│   │   ├── notifications/
│   │   │   └── routes.py         # Fetch notifications, mark as read
│   │   ├── users/
│   │   │   └── routes.py         # /me, profile fetch and update
│   │   ├── posts/
│   │   │   └── routes.py         # General posts / discover feed
│   │   ├── search/
│   │   │   └── routes.py         # User search by name/university
│   │   ├── appointments/
│   │   │   └── routes.py         # Create, list, manage appointments
│   │   └── ai/
│   │       └── routes.py         # Groq AI assistant chat endpoint
│   │
│   └── services/
│       ├── supabase_client.py    # Supabase singleton (service role key)
│       ├── redis_client.py       # Upstash Redis singleton
│       └── email_service.py      # Brevo HTTP API — send_otp_email()
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── vercel.json               # SPA catch-all rewrite rule
    │
    └── src/
        ├── main.jsx
        ├── App.jsx               # Router, PublicRoute, PrivateRoute guards
        │
        ├── api/
        │   └── client.js         # Axios instance, Bearer auth, silent token refresh
        │
        ├── store/
        │   └── authStore.js      # Zustand — accessToken (memory), role (persisted)
        │
        ├── components/
        │   ├── Layout.jsx        # App shell with sidebar navigation
        │   ├── NotificationPanel.jsx
        │   └── AiAssistant.jsx
        │
        └── pages/
            ├── Auth/
            │   ├── Login.jsx         # Step 1: credentials · Step 2: 2FA OTP
            │   ├── Register.jsx      # Step 1: form · Step 2: email OTP verification
            │   └── ResetPassword.jsx # Step 1: email · Step 2: OTP + new password
            ├── Dashboard/
            │   └── Dashboard.jsx
            ├── Discover/
            │   └── Discover.jsx      # Search researchers by name / university
            ├── Room/
            │   ├── RoomList.jsx      # Create room / join by code / list rooms
            │   └── Room.jsx          # Posts, announcements, analytics, member management
            ├── Messages/
            │   └── Messages.jsx
            ├── Profile/
            │   ├── Profile.jsx       # View another user's profile
            │   └── OwnProfile.jsx    # Edit own profile
            └── Appointments/
                └── Appointments.jsx
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (free)
- An [Upstash](https://upstash.com) Redis database (free)
- A [Brevo](https://brevo.com) account with a verified sender email (free — 300 emails/day)
- A [Groq](https://console.groq.com) API key (free)

---

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/Adib-Ishraq/ResearchVault.git
cd ResearchVault/backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env   # then edit .env with your credentials

# Generate server master keys (run ONCE only — keep the output safe)
python generate_master_keys.py
# Paste the printed SERVER_* values into your .env

# Start the development server
python app.py
```

Backend runs at `http://localhost:5000`

---

### Frontend Setup

```bash
cd ResearchVault/frontend

# Install dependencies
npm install

# Create local environment file
echo "VITE_API_URL=http://localhost:5000/api" > .env.local

# Start the development server
npm run dev
```

Frontend runs at `http://localhost:5173`

---

### Environment Variables

#### Backend — `backend/.env`

```env
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Upstash Redis
REDIS_URL=rediss://default:...@....upstash.io:6379

# Brevo (transactional email / OTP)
BREVO_API_KEY=xkeysib-...

# Flask
FLASK_SECRET_KEY=        # python -c "import secrets; print(secrets.token_hex(32))"
FLASK_DEBUG=false

# JWT
JWT_SECRET=              # python -c "import secrets; print(secrets.token_hex(32))"

# HMAC (record integrity)
HMAC_SECRET=             # python -c "import secrets; print(secrets.token_hex(32))"

# Groq AI (free at console.groq.com)
GROQ_API_KEY=gsk_...

# CORS — set to your Vercel URL in production
FRONTEND_URL=http://localhost:5173

# Server master keypairs — generated by generate_master_keys.py
SERVER_RSA_MASTER_PUBLIC_KEY=
SERVER_RSA_MASTER_PRIVATE_KEY=
SERVER_ECC_MASTER_PUBLIC_KEY=
SERVER_ECC_MASTER_PRIVATE_KEY=
```

#### Frontend — `frontend/.env.local`

```env
VITE_API_URL=http://localhost:5000/api
```

---

### Generating Master Keys

The server requires a long-lived RSA-2048 keypair (JWT signing, private key wrapping, room key wrapping) and an ECC P-256 keypair (EC ElGamal field and post encryption). Generate them once:

```bash
cd backend
python generate_master_keys.py
```

The script prints the four `SERVER_*` env vars. Paste them into your `.env`.

> **Warning:** Never regenerate these keys in production. Doing so makes all existing encrypted data permanently unreadable.

---

## API Reference

### Auth — `/api/auth`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/register` | — | Validate form, hash password, send OTP to email |
| POST | `/register/verify` | — | Verify OTP → create account in database |
| POST | `/login` | — | Verify credentials; returns token or 2FA challenge |
| POST | `/verify-2fa` | — | Submit OTP → receive access + refresh token |
| POST | `/logout` | JWT | Invalidate access and refresh tokens |
| POST | `/refresh` | Cookie | Rotate refresh token → new access token |
| POST | `/reset-password` | — | Send OTP to registered email |
| POST | `/reset-password/confirm` | — | Verify OTP → update password |
| POST | `/2fa/enable` | JWT | Send OTP to start 2FA enrollment |
| POST | `/2fa/confirm` | JWT | Confirm OTP → enable 2FA |
| POST | `/2fa/disable` | JWT | Send OTP to disable 2FA |
| POST | `/2fa/disable/confirm` | JWT | Confirm OTP → disable 2FA |

### Rooms — `/api/rooms`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/create` | Supervisor | Create a new research room |
| POST | `/join` | JWT | Join a room by room code |
| GET | `/` | JWT | List all rooms the user belongs to |
| GET | `/<room_id>` | Member | Room details + decrypted member list |
| DELETE | `/<room_id>/members/<user_id>` | Supervisor | Remove a member from the room |
| POST | `/<room_id>/post` | Member | Create a post in a section (updates/data/results) |
| GET | `/<room_id>/posts` | Member | Fetch + decrypt posts for the requesting user |
| PUT | `/<room_id>/posts/<post_id>` | Author | Edit own post (re-encrypts for all members) |
| POST | `/<room_id>/announce` | Supervisor | Post announcement + notify all members |
| GET | `/<room_id>/analytics` | Supervisor | Aggregate metadata (no content decryption) |
| GET | `/<room_id>/analytics/posts` | Supervisor | Full decrypted content for PDF report |
| POST | `/<room_id>/upload-image` | Member | Upload image to Supabase Storage |
| POST | `/<room_id>/upload-pdf` | Member | Upload PDF to Supabase Storage |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Returns `{"status": "ok"}` — used for uptime monitoring |

---

## Security Model

### Password storage
Passwords are hashed with a custom **PBKDF2-SHA256** implementation using a random 32-byte salt per user. The plaintext password is never stored or logged anywhere.

### Email privacy
Emails are never stored in plaintext. A **SHA-256 hash** of the email is stored in `email_hash` for fast duplicate-checking and lookup. The actual email address is stored only in the `email_enc` column, encrypted with **EC ElGamal** using the server ECC master public key.

### Field-level encryption
All PII fields (username, email, contact, university) and room metadata (title, description) are encrypted with **ECC P-256 EC ElGamal** before being written to the database. Only the server (holding the master ECC private key) can decrypt them. No symmetric cipher is used at any point.

### JWT tokens
- Access tokens are **RSA-2048 signed** (custom PSS implementation), expire after 15 minutes
- Refresh tokens are stored in Redis with a 7-day TTL and rotated on every use
- Both token types track a JTI (JWT ID) in Redis; logout invalidates both immediately
- Tokens are fingerprinted with IP + User-Agent; mismatches trigger re-authentication

### Post encryption
Room posts use **EC ElGamal per-member encryption** — each member gets their own independent encrypted copy, tied to their ECC public key. There is no shared key and no symmetric cipher anywhere in the pipeline. Removing a member immediately stops them from being included in new post encryptions.

### Record integrity
Every database row (users, rooms, posts) includes an **HMAC-SHA256** over its encrypted fields, signed with a server secret. Any direct database tampering is detectable at the application layer.

### OTP security
All OTPs (registration, 2FA, password reset) are 6-digit numeric codes stored in Redis with a 10-minute TTL and deleted immediately after successful verification. They are single-use.

---

## Deployment

| Service | Purpose | Free Tier Limits |
|---|---|---|
| [Vercel](https://vercel.com) | Frontend hosting | Unlimited bandwidth, no sleep |
| [Render](https://render.com) | Backend hosting | 750 hrs/month; sleeps after 15 min idle |
| [Supabase](https://supabase.com) | PostgreSQL database | 500 MB; pauses after 1 week of inactivity |
| [Upstash](https://upstash.com) | Redis (sessions/OTP) | 10,000 commands/day |
| [Brevo](https://brevo.com) | Transactional email | 300 emails/day |
| [Groq](https://console.groq.com) | AI inference | Free tier (rate limited) |

### Quick deploy steps

1. Push all code to GitHub
2. **Render** — New Web Service → connect repo → Root Directory: `backend` → Start Command: `gunicorn "app:create_app()"` → add all env vars from `.env`
3. **Vercel** — New Project → connect repo → Root Directory: `frontend` → add `VITE_API_URL=https://<your-render-url>/api`
4. Update `FRONTEND_URL` on Render to your Vercel domain
5. Add `BREVO_API_KEY` and `RESEND_API_KEY` to Render environment

> **Tip:** To prevent Render's free tier from sleeping, set up a free uptime monitor at [cron-job.org](https://cron-job.org) to ping `https://your-backend.onrender.com/api/health` every 10 minutes.

---

## Team

| Member | GitHub |
|---|---|
| Adib Ishraq | [@Adib-Ishraq](https://github.com/Adib-Ishraq) |
| Mahzabin Sandria | [@mahzabinsandria](https://github.com/mahzabinsandria) |

---

## Course

**CSE447 — Cryptography & Network Security**  
BRAC University · Spring 2026

---

## License

This project was built for academic purposes. All custom cryptographic implementations are for educational demonstration only and should not be used in production security-critical systems without a thorough independent security audit.
