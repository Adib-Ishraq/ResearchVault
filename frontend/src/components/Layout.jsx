import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import api from "../api/client";
import NotificationPanel from "./NotificationPanel";
import AiAssistant from "./AiAssistant";

export default function Layout({ children }) {
  const { logout, role } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [showNotifs, setShowNotifs] = useState(false);

  const handleLogout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    logout();
    navigate("/login");
  };

  const navLink = (to, label) => {
    const active = location.pathname.startsWith(to);
    return (
      <Link
        to={to}
        className={`text-sm font-medium transition-colors duration-150 relative py-1 ${
          active ? "text-accent" : "text-muted hover:text-text"
        }`}
      >
        {label}
        {active && (
          <span className="absolute -bottom-[17px] left-0 right-0 h-[2px] bg-accent rounded-full" />
        )}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* Top nav — glassmorphism */}
      <header className="bg-white/80 backdrop-blur-md border-b border-border/60 sticky top-0 z-30 shadow-nav">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center shadow-sm group-hover:bg-accent-dark transition-colors duration-150 flex-shrink-0">
              <svg className="w-4 h-4 text-white" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 2a1 1 0 011-1h10a1 1 0 011 1v2H2V2zm-1 4h14v7a1 1 0 01-1 1H2a1 1 0 01-1-1V6zm5 2.5a.5.5 0 000 1h4a.5.5 0 000-1H6z" />
              </svg>
            </div>
            <span className="text-text font-semibold tracking-tight">Research Vault</span>
          </Link>

          <nav className="hidden md:flex items-center gap-6">
            {navLink("/dashboard", "Dashboard")}
            {navLink("/discover", "Discover")}
            {navLink("/rooms", "Rooms")}
            {navLink("/messages", "Messages")}
            {navLink("/appointments", "Appointments")}
          </nav>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowNotifs(true)}
              className="w-9 h-9 flex items-center justify-center text-muted hover:text-text hover:bg-gray-100 rounded-lg transition-all duration-150"
            >
              <BellIcon />
            </button>
            <Link
              to="/profile/me"
              className="w-9 h-9 flex items-center justify-center text-muted hover:text-text hover:bg-gray-100 rounded-lg transition-all duration-150 text-sm font-medium"
            >
              <UserIcon />
            </Link>
            <button
              onClick={handleLogout}
              className="ml-1 text-sm text-muted hover:text-danger px-3 py-1.5 rounded-lg hover:bg-red-50 transition-all duration-150"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 animate-fade-up">{children}</main>

      {showNotifs && <NotificationPanel onClose={() => setShowNotifs(false)} />}
      <AiAssistant />
    </div>
  );
}

function BellIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}
