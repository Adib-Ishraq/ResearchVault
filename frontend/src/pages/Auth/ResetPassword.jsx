import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../api/client";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1=request, 2=confirm
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const requestReset = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await api.post("/auth/reset-password", { email });
      setMessage("Check your email for a reset code.");
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || "Failed");
    } finally { setLoading(false); }
  };

  const confirmReset = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await api.post("/auth/reset-password/confirm", { email, otp, new_password: newPassword });
      navigate("/login");
    } catch (err) {
      setError(err.response?.data?.error || "Failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-text">Reset password</h1>
        </div>
        <div className="card">
          {step === 1 ? (
            <form onSubmit={requestReset} className="space-y-4">
              <div>
                <label className="label">Email</label>
                <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              {error && <p className="text-danger text-sm">{error}</p>}
              {message && <p className="text-accent text-sm">{message}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? "Sending…" : "Send reset code"}
              </button>
            </form>
          ) : (
            <form onSubmit={confirmReset} className="space-y-4">
              <div>
                <label className="label">Reset code</label>
                <input className="input text-center tracking-[0.3em]" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value)} required />
              </div>
              <div>
                <label className="label">New password</label>
                <input type="password" className="input" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
              </div>
              {error && <p className="text-danger text-sm">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? "Resetting…" : "Set new password"}
              </button>
            </form>
          )}
          <p className="text-center text-sm text-muted mt-4">
            <Link to="/login" className="text-accent hover:underline">Back to sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
