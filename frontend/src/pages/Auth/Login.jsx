import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

export default function Login() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [needs2FA, setNeeds2FA] = useState(false);
  const [preToken, setPreToken] = useState("");
  const [otp, setOtp] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { email, password });
      if (res.data.requires_2fa) {
        setPreToken(res.data.pre_token);
        setNeeds2FA(true);
      } else {
        setAuth(res.data.access_token, res.data.role);
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err.response?.data?.error || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handle2FA = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/verify-2fa", { pre_token: preToken, otp });
      setAuth(res.data.access_token, res.data.role);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.error || "OTP verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "radial-gradient(ellipse 80% 60% at 50% 0%, #E8F5F3 0%, #F7F7F5 55%)" }}>
      <div className="w-full max-w-sm animate-fade-up">

        {/* Logo mark */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-11 h-11 rounded-2xl bg-accent flex items-center justify-center shadow-md mb-4">
            <svg className="w-6 h-6 text-white" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2 2a1 1 0 011-1h10a1 1 0 011 1v2H2V2zm-1 4h14v7a1 1 0 01-1 1H2a1 1 0 01-1-1V6zm5 2.5a.5.5 0 000 1h4a.5.5 0 000-1H6z" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-text tracking-tight">Research Vault</h1>
          <p className="text-muted text-sm mt-1">Secure academic collaboration</p>
        </div>

        <div className="card shadow-card-hover">
          {!needs2FA ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  className="input"
                  placeholder="you@university.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>
              <div>
                <label className="label">Password</label>
                <input
                  type="password"
                  className="input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>

              {error && (
                <p className="text-danger text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                {loading ? "Signing in…" : "Sign in"}
              </button>

              <div className="flex justify-between text-sm pt-1">
                <Link to="/reset-password" className="text-muted hover:text-accent transition-colors">
                  Forgot password?
                </Link>
                <Link to="/register" className="text-accent hover:text-accent-dark font-medium transition-colors">
                  Create account →
                </Link>
              </div>
            </form>
          ) : (
            <form onSubmit={handle2FA} className="space-y-4">
              <div className="text-center mb-2">
                <div className="w-10 h-10 rounded-full bg-accent-light flex items-center justify-center mx-auto mb-3">
                  <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <p className="text-sm text-text font-medium">Two-step verification</p>
                <p className="text-xs text-muted mt-1">Enter the 6-digit code sent to your email</p>
              </div>
              <div>
                <label className="label">Verification code</label>
                <input
                  type="text"
                  className="input text-center tracking-[0.5em] text-xl font-mono"
                  placeholder="000000"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  required
                  autoFocus
                />
              </div>

              {error && (
                <p className="text-danger text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? "Verifying…" : "Verify"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
