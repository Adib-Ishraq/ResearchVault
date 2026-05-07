import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Layout from "../../components/Layout";
import api from "../../api/client";

export default function OwnProfile() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [banner, setBanner] = useState(null); // { text, type }

  // 2FA state
  const [twoFAStep, setTwoFAStep] = useState(null); // null | "enable_otp" | "disable_otp"
  const [otpInput, setOtpInput] = useState("");
  const [twoFAMsg, setTwoFAMsg] = useState("");

  const { data: me, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get("/users/me").then((r) => r.data),
    onSuccess: (data) => {
      setForm({
        username: data.username || "",
        bio: data.profile?.bio || "",
        university: data.profile?.university || "",
        department: data.profile?.department || "",
        research_interests: data.profile?.research_interests || "",
        google_scholar_url: data.profile?.google_scholar_url || "",
        work_experience: data.profile?.work_experience || "",
        academic_credentials: data.profile?.academic_credentials || "",
      });
    },
  });

  const showBanner = (text, type = "success") => {
    setBanner({ text, type });
    setTimeout(() => setBanner(null), 3500);
  };

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const saveMutation = useMutation({
    mutationFn: () => api.put("/users/profile", form),
    onSuccess: () => {
      setEditing(false);
      showBanner("Profile updated successfully");
      qc.invalidateQueries(["me"]);
    },
  });

  const newPubMutation = useMutation({
    mutationFn: (data) => api.post("/users/publications", data),
    onSuccess: () => qc.invalidateQueries(["me"]),
  });

  // 2FA mutations
  const enable2FAMutation = useMutation({
    mutationFn: () => api.post("/auth/2fa/enable"),
    onSuccess: () => {
      setTwoFAStep("enable_otp");
      setTwoFAMsg("A 6-digit code has been sent to your email. Enter it below to activate 2FA.");
    },
    onError: () => setTwoFAMsg("Failed to send code. Please try again."),
  });

  const confirm2FAMutation = useMutation({
    mutationFn: () => api.post("/auth/2fa/confirm", { otp: otpInput }),
    onSuccess: () => {
      setTwoFAStep(null);
      setOtpInput("");
      setTwoFAMsg("");
      showBanner("Two-factor authentication enabled");
      qc.invalidateQueries(["me"]);
    },
    onError: () => setTwoFAMsg("Invalid or expired code. Please try again."),
  });

  const disable2FARequestMutation = useMutation({
    mutationFn: () => api.post("/auth/2fa/disable"),
    onSuccess: () => {
      setTwoFAStep("disable_otp");
      setTwoFAMsg("A 6-digit code has been sent to your email. Enter it below to deactivate 2FA.");
    },
    onError: () => setTwoFAMsg("Failed to send code. Please try again."),
  });

  const disable2FAConfirmMutation = useMutation({
    mutationFn: () => api.post("/auth/2fa/disable/confirm", { otp: otpInput }),
    onSuccess: () => {
      setTwoFAStep(null);
      setOtpInput("");
      setTwoFAMsg("");
      showBanner("Two-factor authentication disabled");
      qc.invalidateQueries(["me"]);
    },
    onError: () => setTwoFAMsg("Invalid or expired code. Please try again."),
  });

  // Availability mutation (supervisor only)
  const availabilityMutation = useMutation({
    mutationFn: (is_available) => api.put("/users/availability", { is_available }),
    onSuccess: (_, is_available) => {
      showBanner(is_available ? "Status set to available" : "Status set to unavailable");
      qc.invalidateQueries(["me"]);
    },
  });

  const twoFALoading =
    enable2FAMutation.isPending ||
    confirm2FAMutation.isPending ||
    disable2FARequestMutation.isPending ||
    disable2FAConfirmMutation.isPending;

  if (isLoading)
    return (
      <Layout>
        <div className="max-w-2xl mx-auto mt-16 text-center text-muted text-sm">
          Loading profile…
        </div>
      </Layout>
    );

  const isAvailable = me?.is_available !== false;

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-5 pb-12">

        {/* ── Profile header card ───────────────────────────────────── */}
        <div className="card overflow-hidden p-0">
          <div className="h-24 bg-gradient-to-r from-accent to-accent-light" />
          <div className="px-6 pb-6">
            <div className="flex items-end justify-between -mt-10 mb-4">
              <div className="w-[72px] h-[72px] rounded-2xl bg-white border-[3px] border-white shadow flex items-center justify-center text-accent text-2xl font-bold select-none">
                {me?.username?.[0]?.toUpperCase()}
              </div>
              <button
                onClick={() => setEditing(!editing)}
                className="btn-secondary text-sm"
              >
                {editing ? "Cancel" : "Edit profile"}
              </button>
            </div>

            <h1 className="text-xl font-semibold text-text leading-tight">{me?.username}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-accent-light text-accent capitalize border border-accent/20">
                {me?.role}
              </span>
              {me?.profile?.university && (
                <span className="text-sm text-muted">{me.profile.university}</span>
              )}
              {me?.profile?.department && (
                <span className="text-xs text-muted">· {me.profile.department}</span>
              )}
            </div>
          </div>
        </div>

        {/* ── Banner ───────────────────────────────────────────────── */}
        {banner && (
          <div
            className={`text-sm rounded-lg px-4 py-3 border ${
              banner.type === "success"
                ? "bg-green-50 text-green-700 border-green-200"
                : "bg-red-50 text-red-700 border-red-200"
            }`}
          >
            {banner.text}
          </div>
        )}

        {/* ── Profile details ───────────────────────────────────────── */}
        {editing ? (
          <div className="card">
            <SectionHeader title="Edit Profile" />
            <div className="mt-4">
              <ProfileEditForm
                form={form}
                update={update}
                onSave={() => saveMutation.mutate()}
                saving={saveMutation.isPending}
              />
            </div>
          </div>
        ) : (
          <ProfileView profile={me?.profile} />
        )}

        {/* ── Publications ─────────────────────────────────────────── */}
        <PublicationsSection
          publications={me?.publications || []}
          onAdd={newPubMutation.mutate}
          onVerificationChange={() => qc.invalidateQueries(["me"])}
        />

        {/* ── Availability (supervisor only) ───────────────────────── */}
        {me?.role === "supervisor" && (
          <AvailabilitySection
            isAvailable={isAvailable}
            onToggle={(val) => availabilityMutation.mutate(val)}
            loading={availabilityMutation.isPending}
          />
        )}

        {/* ── Security / 2FA ───────────────────────────────────────── */}
        <SecuritySection
          twoFAEnabled={me?.two_fa_enabled}
          twoFAStep={twoFAStep}
          otpInput={otpInput}
          setOtpInput={setOtpInput}
          twoFAMsg={twoFAMsg}
          onEnable={() => enable2FAMutation.mutate()}
          onConfirmEnable={() => confirm2FAMutation.mutate()}
          onDisable={() => disable2FARequestMutation.mutate()}
          onConfirmDisable={() => disable2FAConfirmMutation.mutate()}
          onCancel={() => {
            setTwoFAStep(null);
            setOtpInput("");
            setTwoFAMsg("");
          }}
          loading={twoFALoading}
        />
      </div>
    </Layout>
  );
}

// ── Shared section header ──────────────────────────────────────────────────────
function SectionHeader({ title }) {
  return (
    <h2 className="text-xs font-semibold text-muted uppercase tracking-widest">{title}</h2>
  );
}

// ── Profile view (read-only) ───────────────────────────────────────────────────
function ProfileView({ profile }) {
  if (!profile) return null;
  const fields = [
    ["Bio", profile.bio],
    ["Research interests", profile.research_interests],
    ["Department", profile.department],
    ["Academic credentials", profile.academic_credentials],
    ["Work experience", profile.work_experience],
    ["Google Scholar", profile.google_scholar_url],
  ];
  const visible = fields.filter(([, v]) => v);
  if (!visible.length) return null;

  return (
    <div className="card">
      <SectionHeader title="Profile Details" />
      <div className="mt-4 divide-y divide-border">
        {visible.map(([label, value]) => (
          <div key={label} className="py-3 first:pt-0 last:pb-0">
            <p className="text-xs font-medium text-muted uppercase tracking-wide mb-1">{label}</p>
            <p className="text-sm text-text whitespace-pre-line">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Profile edit form ──────────────────────────────────────────────────────────
function ProfileEditForm({ form, update, onSave, saving }) {
  const fields = [
    ["username", "Full name", "text"],
    ["bio", "Bio", "textarea"],
    ["university", "University", "text"],
    ["department", "Department", "text"],
    ["research_interests", "Research interests", "textarea"],
    ["academic_credentials", "Academic credentials", "textarea"],
    ["work_experience", "Work experience", "textarea"],
    ["google_scholar_url", "Google Scholar URL", "text"],
  ];
  return (
    <div className="space-y-4">
      {fields.map(([field, label, type]) => (
        <div key={field}>
          <label className="label">{label}</label>
          {type === "textarea" ? (
            <textarea
              className="input resize-none"
              rows={3}
              value={form[field] || ""}
              onChange={update(field)}
            />
          ) : (
            <input
              type={type}
              className="input"
              value={form[field] || ""}
              onChange={update(field)}
            />
          )}
        </div>
      ))}
      <button onClick={onSave} disabled={saving} className="btn-primary">
        {saving ? "Saving…" : "Save changes"}
      </button>
    </div>
  );
}

// ── Availability section ───────────────────────────────────────────────────────
function AvailabilitySection({ isAvailable, onToggle, loading }) {
  return (
    <div className="card">
      <SectionHeader title="Availability" />
      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-text">Student supervision requests</p>
          <p className="text-xs text-muted mt-1 leading-relaxed">
            {isAvailable
              ? "You are visible and open to incoming supervision and connection requests from students."
              : "You are unavailable. Students cannot send you supervision or connection requests."}
          </p>
          <div className="flex items-center gap-1.5 mt-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isAvailable ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span
              className={`text-xs font-medium ${
                isAvailable ? "text-green-700" : "text-red-600"
              }`}
            >
              {isAvailable ? "Available" : "Unavailable"}
            </span>
          </div>
        </div>

        <div className="flex gap-2 flex-shrink-0 mt-0.5">
          <button
            onClick={() => onToggle(true)}
            disabled={loading || isAvailable}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
              isAvailable
                ? "bg-green-500 text-white border-green-500 shadow-sm cursor-default"
                : "bg-surface text-green-700 border-green-300 hover:bg-green-50 disabled:opacity-50"
            }`}
          >
            Available
          </button>
          <button
            onClick={() => onToggle(false)}
            disabled={loading || !isAvailable}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
              !isAvailable
                ? "bg-red-500 text-white border-red-500 shadow-sm cursor-default"
                : "bg-surface text-red-700 border-red-300 hover:bg-red-50 disabled:opacity-50"
            }`}
          >
            Unavailable
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Security / 2FA section ─────────────────────────────────────────────────────
function SecuritySection({
  twoFAEnabled,
  twoFAStep,
  otpInput,
  setOtpInput,
  twoFAMsg,
  onEnable,
  onConfirmEnable,
  onDisable,
  onConfirmDisable,
  onCancel,
  loading,
}) {
  return (
    <div className="card">
      <SectionHeader title="Security" />

      <div className="mt-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-medium text-text">Two-factor authentication</p>
              {twoFAEnabled ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-xs font-medium border border-green-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                  Enabled
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-muted text-xs font-medium border border-border">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />
                  Disabled
                </span>
              )}
            </div>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              {twoFAEnabled
                ? "Your account is protected. A verification code is required at each login."
                : "Require an email verification code on every login for added security."}
            </p>
          </div>

          {!twoFAStep && (
            twoFAEnabled ? (
              <button
                onClick={onDisable}
                disabled={loading}
                className="flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50 bg-surface"
              >
                Disable
              </button>
            ) : (
              <button
                onClick={onEnable}
                disabled={loading}
                className="btn-primary text-sm flex-shrink-0"
              >
                Enable
              </button>
            )
          )}
        </div>

        {twoFAStep && (
          <div className="mt-4 pt-4 border-t border-border">
            {twoFAMsg && (
              <p className="text-xs text-muted mb-3 leading-relaxed">{twoFAMsg}</p>
            )}
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="000000"
                value={otpInput}
                onChange={(e) =>
                  setOtpInput(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                className="input text-center tracking-[0.4em] text-lg font-mono w-36"
              />
              <button
                onClick={twoFAStep === "enable_otp" ? onConfirmEnable : onConfirmDisable}
                disabled={loading || otpInput.length !== 6}
                className="btn-primary text-sm"
              >
                {loading ? "Verifying…" : "Verify"}
              </button>
              <button onClick={onCancel} className="btn-secondary text-sm">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Verification badge (own profile shows all states) ─────────────────────────
function OwnVerificationBadge({ verification }) {
  const [hovered, setHovered] = useState(false);
  if (!verification || verification.status === "rejected") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-[10px] font-medium border border-gray-200">
        Self-reported
      </span>
    );
  }
  if (verification.status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[10px] font-medium border border-amber-200">
        Pending verification
      </span>
    );
  }
  return (
    <span
      className="relative inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-[10px] font-medium border border-green-200 cursor-default select-none"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
      Verified
      {hovered && (
        <span className="absolute bottom-full left-0 mb-1.5 z-10 w-48 bg-gray-900 text-white text-[10px] rounded-lg px-2.5 py-2 shadow-lg pointer-events-none leading-relaxed">
          Verified by {verification.verifier_name}
          {verification.verified_at && (
            <><br />{new Date(verification.verified_at).toLocaleDateString()}</>
          )}
        </span>
      )}
    </span>
  );
}

// ── Request verification sub-form ──────────────────────────────────────────────
function RequestVerificationForm({ pubId, onClose, onSuccess }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  const requestMutation = useMutation({
    mutationFn: (verifierId) =>
      api.post(`/users/publications/${pubId}/request-verification`, { verifier_id: verifierId }),
    onSuccess: () => {
      onSuccess();
      onClose();
    },
    onError: (err) => setError(err.response?.data?.error || "Failed to send request"),
  });

  const handleSearch = async (q) => {
    setQuery(q);
    setError("");
    if (q.trim().length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const res = await api.get("/search/researchers", { params: { name: q } });
      // Filter to supervisors and admins only
      setResults((res.data || []).filter((u) => u.role === "supervisor" || u.role === "admin"));
    } catch { setResults([]); }
    finally { setSearching(false); }
  };

  return (
    <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-border space-y-2">
      <p className="text-xs font-medium text-text">Request verification from a supervisor or admin</p>
      <div className="relative">
        <input
          className="input text-sm py-2"
          placeholder="Search by name…"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          autoFocus
        />
        {searching && <span className="absolute right-3 top-2.5 text-xs text-muted">…</span>}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      {results.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden bg-surface shadow-sm">
          {results.slice(0, 5).map((u) => (
            <button
              key={u.id}
              onClick={() => requestMutation.mutate(u.id)}
              disabled={requestMutation.isPending}
              className="w-full text-left px-3 py-2.5 hover:bg-gray-50 flex items-center gap-2 transition-colors border-b border-border last:border-0 disabled:opacity-50"
            >
              <div className="w-7 h-7 rounded-full bg-accent-light flex items-center justify-center text-accent text-xs font-semibold flex-shrink-0">
                {u.username?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-text truncate">{u.username}</p>
                <p className="text-xs text-muted capitalize">{u.role}</p>
              </div>
            </button>
          ))}
        </div>
      )}
      <button onClick={onClose} className="text-xs text-muted hover:text-text">Cancel</button>
    </div>
  );
}

// ── Publications section ───────────────────────────────────────────────────────
function PublicationsSection({ publications, onAdd, onVerificationChange }) {
  const [adding, setAdding] = useState(false);
  const [newPub, setNewPub] = useState({ title: "", abstract: "", published_year: "" });
  const [requestingVerifFor, setRequestingVerifFor] = useState(null);

  const handleAdd = () => {
    onAdd(newPub);
    setAdding(false);
    setNewPub({ title: "", abstract: "", published_year: "" });
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <SectionHeader title="Publications" />
        <button
          onClick={() => setAdding(!adding)}
          className="text-sm text-accent hover:underline font-medium"
        >
          {adding ? "Cancel" : "+ Add"}
        </button>
      </div>

      {adding && (
        <div className="mt-4 space-y-3 p-4 bg-gray-50 rounded-lg border border-border">
          <input
            className="input"
            placeholder="Title"
            value={newPub.title}
            onChange={(e) => setNewPub((p) => ({ ...p, title: e.target.value }))}
          />
          <textarea
            className="input resize-none"
            rows={2}
            placeholder="Abstract (optional)"
            value={newPub.abstract}
            onChange={(e) => setNewPub((p) => ({ ...p, abstract: e.target.value }))}
          />
          <input
            className="input"
            placeholder="Year (e.g. 2024)"
            value={newPub.published_year}
            onChange={(e) => setNewPub((p) => ({ ...p, published_year: e.target.value }))}
          />
          <button onClick={handleAdd} className="btn-primary text-sm">
            Add publication
          </button>
        </div>
      )}

      <div className="mt-4">
        {publications.length === 0 ? (
          <p className="text-sm text-muted">No publications added yet.</p>
        ) : (
          <div className="divide-y divide-border">
            {publications.map((pub) => {
              const canRequest = !pub.verification || pub.verification.status === "rejected";
              const isRequestingThis = requestingVerifFor === pub.id;
              return (
                <div key={pub.id} className="py-3 first:pt-0 last:pb-0 pl-3 border-l-2 border-accent">
                  <p className="text-sm font-medium text-text">{pub.title}</p>
                  {pub.published_year && (
                    <p className="text-xs text-muted mt-0.5">{pub.published_year}</p>
                  )}
                  {pub.abstract && (
                    <p className="text-xs text-muted mt-1 line-clamp-2">{pub.abstract}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <OwnVerificationBadge verification={pub.verification} />
                    {pub.file_url && (
                      <a
                        href={pub.file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-accent hover:underline"
                      >
                        View PDF →
                      </a>
                    )}
                    {canRequest && !isRequestingThis && (
                      <button
                        onClick={() => setRequestingVerifFor(pub.id)}
                        className="text-xs text-muted hover:text-accent underline"
                      >
                        Request verification
                      </button>
                    )}
                  </div>
                  {isRequestingThis && (
                    <RequestVerificationForm
                      pubId={pub.id}
                      onClose={() => setRequestingVerifFor(null)}
                      onSuccess={onVerificationChange}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
