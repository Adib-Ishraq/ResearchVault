import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

export default function Dashboard() {
  const { role } = useAuthStore();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get("/users/me").then((r) => r.data),
  });

  const { data: rooms = [] } = useQuery({
    queryKey: ["rooms"],
    queryFn: () => api.get("/rooms").then((r) => r.data),
  });

  const { data: supervisionRequests = [] } = useQuery({
    queryKey: ["supervision-incoming"],
    queryFn: () => api.get("/notifications/supervision/incoming").then((r) => r.data),
    enabled: role === "supervisor",
  });

  const initials = me?.username?.[0]?.toUpperCase() ?? "?";

  return (
    <Layout>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main column */}
        <div className="lg:col-span-2 space-y-5">

          {/* Welcome hero card */}
          <div className="card overflow-hidden p-0">
            <div className="h-2 bg-gradient-to-r from-accent to-accent-muted" />
            <div className="p-6 flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-accent-light flex items-center justify-center text-accent text-xl font-bold flex-shrink-0 border border-accent/10">
                {initials}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text leading-tight">
                  Welcome back{me?.username ? `, ${me.username}` : ""}
                </h2>
                <p className="text-muted text-sm mt-0.5 capitalize">{me?.role}</p>
              </div>
            </div>
          </div>

          {/* Supervision requests (supervisors only) */}
          {role === "supervisor" && supervisionRequests.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="font-medium text-text">Pending supervision requests</h3>
                <span className="text-xs bg-accent text-white px-2 py-0.5 rounded-full font-medium">
                  {supervisionRequests.length}
                </span>
              </div>
              <div className="space-y-3">
                {supervisionRequests.map((req) => (
                  <SupervisionRequestCard key={req.id} req={req} />
                ))}
              </div>
            </div>
          )}

          {/* Research rooms */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-text">Research rooms</h3>
              <Link
                to="/rooms"
                className="text-xs text-accent hover:text-accent-dark font-medium transition-colors flex items-center gap-0.5"
              >
                View all <span className="ml-0.5">→</span>
              </Link>
            </div>
            {rooms.length === 0 ? (
              <div className="py-6 text-center">
                <div className="w-10 h-10 rounded-xl bg-accent-light flex items-center justify-center mx-auto mb-3">
                  <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <p className="text-muted text-sm">
                  {role === "supervisor"
                    ? "Create a research room to collaborate with your team."
                    : "Join a research room using a code from your supervisor."}
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {rooms.slice(0, 4).map((room) => (
                  <Link
                    key={room.id}
                    to={`/rooms/${room.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 group transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-accent-light flex items-center justify-center text-accent text-xs font-bold flex-shrink-0">
                        {room.title?.[0]?.toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text">{room.title}</p>
                        <p className="text-xs text-muted capitalize">{room.my_role}</p>
                      </div>
                    </div>
                    <ChevronRight />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          {/* Quick actions */}
          <div className="card">
            <h3 className="font-medium text-text mb-4">Quick actions</h3>
            <div className="space-y-1">
              <QuickLink to="/discover" label="Discover researchers" />
              {role === "supervisor" && <QuickLink to="/rooms" label="Create a room" />}
              {(role === "postgrad" || role === "undergraduate") && (
                <QuickLink to="/discover?tab=supervisors" label="Find a supervisor" />
              )}
              <QuickLink to="/messages" label="Messages" />
              <QuickLink to="/profile/me" label="Edit profile" />
            </div>
          </div>

        </div>
      </div>
    </Layout>
  );
}

function QuickLink({ to, label }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between px-3 py-2 rounded-lg text-sm text-text hover:bg-accent-light hover:text-accent transition-all duration-150 group"
    >
      <span>{label}</span>
      <span className="text-muted group-hover:text-accent transition-colors text-xs">→</span>
    </Link>
  );
}

function SupervisionRequestCard({ req }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const respond = async (action) => {
    setLoading(true);
    try {
      await api.put(`/notifications/supervision/${req.id}/${action}`);
      setStatus(action);
    } finally {
      setLoading(false);
    }
  };

  if (status) {
    return (
      <div className="p-3 bg-gray-50 rounded-lg text-sm text-muted capitalize border border-border">
        Request {status}d
      </div>
    );
  }

  return (
    <div className="p-4 border border-border rounded-xl hover:border-accent/30 transition-colors">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-7 h-7 bg-accent-light rounded-full flex items-center justify-center text-accent text-xs font-semibold">
          {req.researcher_name?.[0]?.toUpperCase()}
        </div>
        <p className="text-sm font-medium text-text">{req.researcher_name}</p>
      </div>
      {req.message && <p className="text-xs text-muted mt-1 line-clamp-2 ml-9">{req.message}</p>}
      <div className="flex gap-2 mt-3">
        <button onClick={() => respond("accept")} disabled={loading} className="btn-primary text-xs px-3 py-1.5">
          Accept
        </button>
        <button onClick={() => respond("reject")} disabled={loading} className="btn-secondary text-xs px-3 py-1.5">
          Reject
        </button>
      </div>
    </div>
  );
}

function ChevronRight() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-muted group-hover:text-accent transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}
