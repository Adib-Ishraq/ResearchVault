# Research Vault

A secure academic research collaboration platform built for CSE447. Research Vault connects students and supervisors in a cryptographically protected environment — every piece of data is encrypted end-to-end using custom-built cryptographic primitives (no third-party crypto libraries).

---

## Features

- **User Authentication** — Register, login, logout with PBKDF2-SHA256 password hashing and RSA-PSS signed JWTs
- **Two-Factor Authentication (2FA)** — Email OTP for login and account changes, stored in Redis with 10-minute TTL
- **Role-Based Access Control** — Four roles: `admin`, `supervisor`, `postgrad`, `undergraduate`
- **Encrypted Profiles** — All personal data (bio, university, contact) is ECIES-encrypted per user
- **Research Rooms** — Supervisors create invite-only rooms; posts are ECIES-encrypted per member
- **Announcements** — Supervisors broadcast encrypted announcements to all room members
- **Publication Signing** — Supervisors RSA-PSS sign student credentials for verified badges
- **Direct Messaging** — E2E encrypted DMs using XOR-stream cipher (SHA-256 CTR) with per-conversation RSA-OAEP wrapped keys
- **Appointment Booking** — Students propose time slots; supervisors approve with confirmed meeting time
- **Discover** — Search supervisors and researchers by university and research domain
- **Notifications** — Real-time in-app notifications for all major events
- **AI Research Assistant** — Floating chat assistant powered by Groq (LLaMA 3.3 70B, free tier)
- **Room Analytics** — Supervisor dashboard with post counts, timelines, and contribution breakdowns
- **Key Rotation** — Automatic 90-day RSA + ECC keypair rotation per user
- **Session Security** — JWT fingerprint binding (IP + User-Agent), Redis JTI tracking, hijack detection

---

## Cryptographic Architecture

All cryptography is implemented from scratch in pure Python — no `cryptography`, `pycryptodome`, or similar libraries.

| Primitive | Implementation | Used for |
|---|---|---|
| RSA-2048 | Custom (Miller-Rabin, extended GCD) | Key wrapping, JWT signing (PSS), credential signing |
| ECC P-256 | Custom (point arithmetic) | ECIES encryption of all data fields |
| PBKDF2-SHA256 | Custom | Password hashing (100,000 iterations) |
| HMAC-SHA256 | Custom (RFC 2104) | Record integrity on every DB row |
| SHA-256 | Custom | Hashing, CTR keystream, fingerprinting |
| XOR-stream CTR | Custom | Direct message encryption |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TailwindCSS, TanStack Query |
| Backend | Flask 3, Python |
| Database | Supabase (PostgreSQL) |
| Session Store | Upstash Redis |
| AI Assistant | Groq API — LLaMA 3.3 70B |
| Email (OTP) | Gmail SMTP |
| Deployment | Vercel (frontend) + Render (backend) |

---

## Project Structure

```
research-vault/
├── backend/
│   ├── app.py                  # Flask app factory
│   ├── config.py               # Environment config
│   ├── requirements.txt
│   ├── crypto/
│   │   ├── rsa_engine.py       # RSA-2048 from scratch
│   │   ├── ecc_engine.py       # ECC P-256 + ECIES
│   │   ├── hash_engine.py      # SHA-256 + PBKDF2
│   │   ├── hmac_engine.py      # HMAC-SHA256
│   │   └── key_manager.py      # Key generation, wrapping, rotation
│   ├── middleware/
│   │   ├── session.py          # JWT issue/validate, Redis session store
│   │   └── rbac.py             # Role-based access decorator
│   ├── modules/
│   │   ├── auth/               # Register, login, 2FA, password reset
│   │   ├── users/              # Profile CRUD, publications, key rotation
│   │   ├── rooms/              # Research rooms, posts, announcements
│   │   ├── messages/           # Direct messaging (E2E encrypted)
│   │   ├── appointments/       # Appointment booking and approval
│   │   ├── notifications/      # Notifications, supervision requests
│   │   ├── search/             # Discover supervisors and researchers
│   │   └── ai/                 # Groq AI research assistant
│   └── services/
│       ├── supabase_client.py
│       ├── redis_client.py
│       └── email_service.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Auth/           # Login, Register, Reset Password
│   │   │   ├── Dashboard/
│   │   │   ├── Profile/        # View profile + Book appointment
│   │   │   ├── Discover/       # Search supervisors and researchers
│   │   │   ├── Room/           # Research room + posts
│   │   │   ├── Messages/       # Direct messaging
│   │   │   └── Appointments/   # Appointment management
│   │   ├── components/
│   │   │   ├── Layout.jsx
│   │   │   ├── NotificationPanel.jsx
│   │   │   └── AiAssistant.jsx
│   │   ├── store/authStore.js
│   │   └── api/client.js
│   └── package.json
└── supabase/
    └── schema.sql              # Full database schema with RLS policies
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (free)
- An [Upstash Redis](https://upstash.com) database (free)
- A [Groq](https://console.groq.com) API key (free)
- A Gmail account with an App Password enabled

---

### 1. Database

1. Open your Supabase project → **SQL Editor**
2. Paste the contents of `supabase/schema.sql` and click **Run**

---

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

REDIS_URL=rediss://default:password@your-upstash-host:6379

GROQ_API_KEY=gsk_...

GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

FLASK_SECRET_KEY=generate-with-secrets.token_hex-32
JWT_SECRET=generate-with-secrets.token_hex-32
HMAC_SECRET=generate-with-secrets.token_hex-32

FRONTEND_URL=http://localhost:5173

# Generate server master keys once:
# cd backend && python -c "from crypto.key_manager import ServerMasterKeys; m=ServerMasterKeys.generate_new(); [print(k,'=',v) for k,v in m.export_env_vars().items()]"
SERVER_RSA_MASTER_PUBLIC_KEY=...
SERVER_RSA_MASTER_PRIVATE_KEY=...
SERVER_ECC_MASTER_PUBLIC_KEY=...
SERVER_ECC_MASTER_PRIVATE_KEY=...
```

Run the backend:

```bash
python app.py
```

The API will be available at `http://localhost:5000`.

---

### 3. Frontend

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/`:

```env
VITE_API_URL=http://localhost:5000/api
```

Run the frontend:

```bash
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Deployment

| Service | Purpose | Free Tier |
|---|---|---|
| [Vercel](https://vercel.com) | Frontend hosting | Unlimited, no expiry |
| [Render](https://render.com) | Backend hosting | 1 web service, sleeps after 15 min idle |
| [Supabase](https://supabase.com) | Database | 500 MB, no expiry |
| [Upstash](https://upstash.com) | Redis | 10,000 req/day, no expiry |

To prevent Render from sleeping, set up a free cron job at [cron-job.org](https://cron-job.org) to ping `https://your-backend.onrender.com/api/health` every 10 minutes.

---

## Team

| Member | GitHub |
|---|---|
| Adib Ishraq | [@Adib-Ishraq](https://github.com/Adib-Ishraq) |
| Mahzabin Sandria | [@mahzabinsandria](https://github.com/mahzabinsandria) |

---

## Course

CSE447 — Security Lab Project  
BRAC University
