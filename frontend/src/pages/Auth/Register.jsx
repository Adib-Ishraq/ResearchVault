import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../api/client";

const rules = [
  { id: "len",     label: "At least 8 characters",        test: (p) => p.length >= 8 },
  { id: "upper",   label: "One uppercase letter (A–Z)",   test: (p) => /[A-Z]/.test(p) },
  { id: "lower",   label: "One lowercase letter (a–z)",   test: (p) => /[a-z]/.test(p) },
  { id: "number",  label: "One number (0–9)",              test: (p) => /[0-9]/.test(p) },
  { id: "special", label: "One special character (!@#…)", test: (p) => /[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]/.test(p) },
];

function PasswordStrength({ password }) {
  if (!password) return null;
  const passed = rules.filter((r) => r.test(password)).length;
  const colors = ["bg-red-400", "bg-red-400", "bg-amber-400", "bg-amber-400", "bg-green-500"];
  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-1">
        {rules.map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
              i < passed ? colors[passed - 1] : "bg-gray-200"
            }`}
          />
        ))}
      </div>
      <ul className="space-y-0.5">
        {rules.map((r) => {
          const ok = r.test(password);
          return (
            <li key={r.id} className={`flex items-center gap-1.5 text-xs ${ok ? "text-green-600" : "text-muted"}`}>
              <span className={`w-3.5 h-3.5 rounded-full flex items-center justify-center flex-shrink-0 ${ok ? "bg-green-100" : "bg-gray-100"}`}>
                {ok ? "✓" : "·"}
              </span>
              {r.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    role: "postgrad",
    university: "",
  });
  const [step, setStep] = useState(1);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const allRulesPassed = rules.every((r) => r.test(form.password));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!allRulesPassed) {
      setError("Password does not meet the requirements below");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/register", {
        username: form.username,
        email: form.email,
        password: form.password,
        role: form.role,
        university: form.university,
      });
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/register/verify", { email: form.email, otp });
      navigate("/login");
    } catch (err) {
      setError(err.response?.data?.error || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setError("");
    setOtp("");
    setLoading(true);
    try {
      await api.post("/auth/register", {
        username: form.username,
        email: form.email,
        password: form.password,
        role: form.role,
        university: form.university,
      });
    } catch (err) {
      setError(err.response?.data?.error || "Failed to resend OTP");
    } finally {
      setLoading(false);
    }
  };

  const logo = (
    <div className="flex flex-col items-center mb-8">
      <div className="w-11 h-11 rounded-2xl bg-accent flex items-center justify-center shadow-md mb-4">
        <svg className="w-6 h-6 text-white" viewBox="0 0 16 16" fill="currentColor">
          <path d="M2 2a1 1 0 011-1h10a1 1 0 011 1v2H2V2zm-1 4h14v7a1 1 0 01-1 1H2a1 1 0 01-1-1V6zm5 2.5a.5.5 0 000 1h4a.5.5 0 000-1H6z" />
        </svg>
      </div>
      <h1 className="text-2xl font-semibold text-text tracking-tight">Research Vault</h1>
    </div>
  );

  if (step === 2) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12"
        style={{ background: "radial-gradient(ellipse 80% 60% at 50% 0%, #E8F5F3 0%, #F7F7F5 55%)" }}>
        <div className="w-full max-w-sm animate-fade-up">
          {logo}
          <div className="card shadow-card-hover">
            <div className="flex flex-col items-center mb-6">
              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mb-3">
                <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-text">Verify your email</h2>
              <p className="text-sm text-muted text-center mt-1">
                We sent a 6-digit code to <span className="font-medium text-text">{form.email}</span>
              </p>
            </div>
            <form onSubmit={handleVerify} className="space-y-4">
              <div>
                <label className="label">Verification code</label>
                <input
                  className="input text-center text-2xl tracking-widest font-mono"
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                />
              </div>

              {error && (
                <p className="text-danger text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Verifying…" : "Verify & create account"}
              </button>

              <p className="text-center text-sm text-muted">
                Didn't receive it?{" "}
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={loading}
                  className="text-accent hover:text-accent-dark font-medium transition-colors disabled:opacity-50"
                >
                  Resend code
                </button>
              </p>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12"
      style={{ background: "radial-gradient(ellipse 80% 60% at 50% 0%, #E8F5F3 0%, #F7F7F5 55%)" }}>
      <div className="w-full max-w-sm animate-fade-up">

        <div className="flex flex-col items-center mb-8">
          <div className="w-11 h-11 rounded-2xl bg-accent flex items-center justify-center shadow-md mb-4">
            <svg className="w-6 h-6 text-white" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2 2a1 1 0 011-1h10a1 1 0 011 1v2H2V2zm-1 4h14v7a1 1 0 01-1 1H2a1 1 0 01-1-1V6zm5 2.5a.5.5 0 000 1h4a.5.5 0 000-1H6z" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-text tracking-tight">Create account</h1>
          <p className="text-muted text-sm mt-1">Join the Research Vault community</p>
        </div>

        <div className="card shadow-card-hover">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Full name</label>
              <input className="input" placeholder="Dr. Jane Smith" value={form.username} onChange={update("username")} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" placeholder="you@university.edu" value={form.email} onChange={update("email")} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Role</label>
                <select className="input" value={form.role} onChange={update("role")}>
                  <option value="undergraduate">Undergraduate</option>
                  <option value="postgrad">Postgraduate</option>
                  <option value="supervisor">Supervisor</option>
                </select>
              </div>
              <div>
                <label className="label">University</label>
                <input className="input" placeholder="e.g. UoA" value={form.university} onChange={update("university")} />
              </div>
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                placeholder="Create a strong password"
                value={form.password}
                onChange={update("password")}
                required
                autoComplete="new-password"
              />
              <PasswordStrength password={form.password} />
            </div>
            <div>
              <label className="label">Confirm password</label>
              <input
                type="password"
                className="input"
                placeholder="••••••••"
                value={form.confirmPassword}
                onChange={update("confirmPassword")}
                required
                autoComplete="new-password"
              />
              {form.confirmPassword && form.password !== form.confirmPassword && (
                <p className="text-xs text-danger mt-1">Passwords do not match</p>
              )}
            </div>

            {error && (
              <p className="text-danger text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !allRulesPassed || form.password !== form.confirmPassword}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Sending code…" : "Continue"}
            </button>

            <p className="text-center text-sm text-muted">
              Already have an account?{" "}
              <Link to="/login" className="text-accent hover:text-accent-dark font-medium transition-colors">
                Sign in →
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
