-- Research Vault — Full Database Schema
-- Run this on your Supabase project via the SQL editor.
-- All sensitive text fields store Base64-encoded ciphertext (ECC/RSA encrypted).

-- ─── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role TEXT NOT NULL CHECK (role IN ('admin', 'supervisor', 'postgrad', 'undergraduate')),
  username_enc TEXT NOT NULL,           -- ECIES-encrypted username
  email_enc TEXT NOT NULL,              -- ECIES-encrypted email
  email_hash TEXT NOT NULL UNIQUE,      -- SHA-256(email) for O(1) lookup
  contact_enc TEXT,                     -- ECIES-encrypted phone/contact
  password_hash TEXT NOT NULL,          -- PBKDF2-SHA256 hex
  salt TEXT NOT NULL,                   -- PBKDF2 salt hex
  public_key_rsa TEXT NOT NULL,         -- User RSA public key (Base64 JSON)
  public_key_ecc TEXT NOT NULL,         -- User ECC public key (Base64 JSON)
  private_key_enc TEXT NOT NULL,        -- Both private keys wrapped with server RSA master key
  two_fa_secret_enc TEXT,               -- 2FA TOTP secret, ECIES-encrypted
  two_fa_enabled BOOLEAN DEFAULT FALSE,
  is_available BOOLEAN NOT NULL DEFAULT TRUE, -- supervisors only: visibility to students
  hmac TEXT NOT NULL,                   -- HMAC-SHA256 over all encrypted fields
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Profiles ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  bio_enc TEXT,                         -- ECIES-encrypted
  university_enc TEXT,                  -- ECIES-encrypted
  university_plaintext TEXT,            -- Plaintext for filter/search only
  department_enc TEXT,
  academic_credentials_enc TEXT,
  work_experience_enc TEXT,
  google_scholar_url_enc TEXT,
  research_interest_enc TEXT,
  profile_pic_url TEXT,                 -- Supabase Storage public URL
  hmac TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Publications ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS publications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title_enc TEXT NOT NULL,
  abstract_enc TEXT,
  file_url TEXT,                        -- Supabase Storage URL for PDF
  published_year_enc TEXT,
  hmac TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Connections ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (requester_id, recipient_id)
);

-- ─── Supervision Requests ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supervision_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  researcher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  supervisor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
  message_enc TEXT,
  hmac TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Research Rooms ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supervisor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title_enc TEXT NOT NULL,
  description_enc TEXT,
  room_code TEXT UNIQUE NOT NULL,       -- Short code for joining (plaintext, random)
  room_key_enc TEXT NOT NULL,           -- Room symmetric key, RSA-OAEP encrypted with server master pub
  hmac TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Room Members ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS room_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id UUID NOT NULL REFERENCES research_rooms(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('supervisor', 'member')) DEFAULT 'member',
  room_key_enc TEXT NOT NULL,           -- Room key RSA-OAEP encrypted with this member's public key
  joined_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (room_id, user_id)
);

-- ─── Room Posts ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS room_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id UUID NOT NULL REFERENCES research_rooms(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  section TEXT NOT NULL CHECK (section IN ('updates', 'data', 'results')),
  content_enc TEXT NOT NULL,            -- ECIES-encrypted with room key as the ECC private scalar
  attachments_enc TEXT,
  hmac TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Key Store ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS key_store (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
  key_type TEXT NOT NULL CHECK (key_type IN ('rsa_private', 'ecc_private', 'room_key', 'server_master')),
  key_enc TEXT NOT NULL,
  rotation_due TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Notifications ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN (
    'supervision_request', 'supervision_accepted', 'supervision_rejected',
    'room_invite', 'connection_request', 'connection_accepted'
  )),
  payload_enc TEXT,
  is_read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Session Audit Log ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  jti TEXT NOT NULL UNIQUE,             -- JWT ID (stored in Redis as key)
  ip_hash TEXT,                         -- SHA-256(ip) for privacy-preserving audit
  user_agent_hash TEXT,
  issued_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ,
  invalidated BOOLEAN DEFAULT FALSE
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_email_hash ON users(email_hash);
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_university ON profiles(university_plaintext);
CREATE INDEX IF NOT EXISTS idx_publications_user_id ON publications(user_id);
CREATE INDEX IF NOT EXISTS idx_connections_requester ON connections(requester_id);
CREATE INDEX IF NOT EXISTS idx_connections_recipient ON connections(recipient_id);
CREATE INDEX IF NOT EXISTS idx_supervision_researcher ON supervision_requests(researcher_id);
CREATE INDEX IF NOT EXISTS idx_supervision_supervisor ON supervision_requests(supervisor_id);
CREATE INDEX IF NOT EXISTS idx_room_members_room ON room_members(room_id);
CREATE INDEX IF NOT EXISTS idx_room_members_user ON room_members(user_id);
CREATE INDEX IF NOT EXISTS idx_room_posts_room ON room_posts(room_id);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id, is_read);
CREATE INDEX IF NOT EXISTS idx_session_audit_user ON session_audit(user_id);
CREATE INDEX IF NOT EXISTS idx_session_audit_jti ON session_audit(jti);

-- ─── Row Level Security (Supabase) ────────────────────────────────────────────
-- We use the service role key from the backend, so RLS can be permissive.
-- The backend enforces authorization via RBAC decorators.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE supervision_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE room_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE room_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE key_store ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (backend uses service role key)
CREATE POLICY "service_role_all_users" ON users FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_profiles" ON profiles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_publications" ON publications FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_connections" ON connections FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_supervision" ON supervision_requests FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_rooms" ON research_rooms FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_room_members" ON room_members FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_room_posts" ON room_posts FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_notifications" ON notifications FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_session_audit" ON session_audit FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_key_store" ON key_store FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ─── Direct Messaging ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_a UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  participant_b UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conv_key_enc_a TEXT NOT NULL,         -- 32-byte conv key RSA-OAEP wrapped for participant_a
  conv_key_enc_b TEXT NOT NULL,         -- 32-byte conv key RSA-OAEP wrapped for participant_b
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (participant_a, participant_b)
);

CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_enc TEXT NOT NULL,            -- XOR-stream cipher with conv key (SHA-256 CTR)
  hmac TEXT NOT NULL,                   -- HMAC-SHA256 over content_enc + conv_id + sender_id
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_a ON conversations(participant_a);
CREATE INDEX IF NOT EXISTS idx_conversations_b ON conversations(participant_b);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_conversations" ON conversations FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_messages" ON messages FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ─── Credential Verifications ────────────────────────────────────────────────
-- One verification record per publication. The verifier RSA-PSS signs
-- f"credential:{pub_id}:{verifier_id}" to attest a PDF credential is genuine.

CREATE TABLE IF NOT EXISTS credential_verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  publication_id UUID NOT NULL REFERENCES publications(id) ON DELETE CASCADE UNIQUE,
  requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  verifier_id UUID REFERENCES users(id) ON DELETE SET NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'verified', 'rejected')) DEFAULT 'pending',
  signature_b64 TEXT,           -- RSA-PSS signature bytes, Base64-encoded
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credential_verif_pub ON credential_verifications(publication_id);
CREATE INDEX IF NOT EXISTS idx_credential_verif_verifier ON credential_verifications(verifier_id);

ALTER TABLE credential_verifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_credential_verifications" ON credential_verifications
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Extend notification type enum to include credential + appointment events.
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_type_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_type_check CHECK (type IN (
  'supervision_request', 'supervision_accepted', 'supervision_rejected',
  'room_invite', 'room_announcement',
  'connection_request', 'connection_accepted',
  'credential_verification_request', 'credential_verified',
  'appointment_request', 'appointment_approved', 'appointment_rejected'
));

-- ─── Appointments ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS appointments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  supervisor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title_enc TEXT NOT NULL,              -- ECIES-encrypted appointment purpose
  note_enc TEXT,                        -- ECIES-encrypted student note (optional)
  proposed_times JSONB NOT NULL DEFAULT '[]', -- array of ISO datetime strings (plaintext)
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')) DEFAULT 'pending',
  confirmed_time TIMESTAMPTZ,           -- supervisor sets this on approval
  supervisor_note_enc TEXT,             -- ECIES-encrypted supervisor response note
  hmac TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_appointments_student ON appointments(student_id);
CREATE INDEX IF NOT EXISTS idx_appointments_supervisor ON appointments(supervisor_id, status);

ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_appointments" ON appointments FOR ALL TO service_role USING (true) WITH CHECK (true);
