import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Layout from "../../components/Layout";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

function VerificationBadge({ verification }) {
  const [hovered, setHovered] = useState(false);
  if (!verification || verification.status !== "verified") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-[10px] font-medium border border-gray-200 mt-1">
        Self-reported
      </span>
    );
  }
  return (
    <span
      className="relative inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-[10px] font-medium border border-green-200 mt-1 cursor-default select-none"
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

export default function Profile() {
  const { userId } = useParams();
  const { role } = useAuthStore();
  const qc = useQueryClient();
  const [supMessage, setSupMessage] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const { data: user, isLoading } = useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.get(`/users/${userId}`).then((r) => r.data),
  });

  // Fetch current user's ID (stale-while-revalidate — cheap after first load)
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get("/users/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const signMutation = useMutation({
    mutationFn: (pubId) => api.put(`/users/publications/${pubId}/sign`),
    onSuccess: () => {
      setActionMsg("Credential signed and verified");
      qc.invalidateQueries(["user", userId]);
    },
  });

  const supervisionMutation = useMutation({
    mutationFn: () =>
      api.post(`/notifications/supervision/request/${userId}`, { message: supMessage }),
    onSuccess: () => {
      setActionMsg("Supervision request sent");
      setSupMessage("");
      qc.invalidateQueries(["my-supervision-requests"]);
    },
  });

  const { data: myRequests = [] } = useQuery({
    queryKey: ["my-supervision-requests"],
    queryFn: () => api.get("/notifications/supervision/my-requests").then((r) => r.data),
    enabled: !!(role === "postgrad" || role === "undergraduate"),
    staleTime: 30_000,
  });

  if (isLoading)
    return (
      <Layout>
        <div className="max-w-2xl mx-auto mt-16 text-center text-muted text-sm">
          Loading profile…
        </div>
      </Layout>
    );

  if (!user)
    return (
      <Layout>
        <div className="max-w-2xl mx-auto mt-16 text-center text-muted text-sm">
          User not found.
        </div>
      </Layout>
    );

  const profile = user.profile || {};
  const isSupervisor = user.role === "supervisor";
  const isStudent = role === "postgrad" || role === "undergraduate";
  const supervisorUnavailable = isSupervisor && user.is_available === false;
  const studentBlocked = supervisorUnavailable && isStudent;

  // null | 'pending' | 'accepted' | 'rejected'
  const supervisionStatus = (isSupervisor && isStudent)
    ? (myRequests.find((r) => r.supervisor_id === userId)?.status ?? null)
    : null;
  const canRequestSupervision = supervisionStatus === null || supervisionStatus === "rejected";

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-5 pb-12">

        {/* ── Header card ──────────────────────────────────────────── */}
        <div className="card overflow-hidden p-0">
          <div className="h-24 bg-gradient-to-r from-accent to-accent-light" />
          <div className="px-6 pb-6">
            <div className="flex items-end justify-between -mt-10 mb-4">
              <div className="w-[72px] h-[72px] rounded-2xl bg-white border-[3px] border-white shadow flex items-center justify-center text-accent text-2xl font-bold select-none">
                {user.username?.[0]?.toUpperCase()}
              </div>
              {/* Availability badge — supervisors only */}
              {isSupervisor && (
                <div
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium ${
                    supervisorUnavailable
                      ? "bg-red-50 border-red-200 text-red-600"
                      : "bg-green-50 border-green-200 text-green-700"
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      supervisorUnavailable ? "bg-red-500" : "bg-green-500"
                    }`}
                  />
                  {supervisorUnavailable ? "Unavailable" : "Available"}
                </div>
              )}
            </div>

            <h1 className="text-xl font-semibold text-text leading-tight">{user.username}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-accent-light text-accent capitalize border border-accent/20">
                {user.role}
              </span>
              {profile.university && (
                <span className="text-sm text-muted">{profile.university}</span>
              )}
              {profile.department && (
                <span className="text-xs text-muted">· {profile.department}</span>
              )}
            </div>

            {/* Action feedback */}
            {actionMsg && (
              <p className="text-sm text-accent mt-3 font-medium">{actionMsg}</p>
            )}

            {/* Unavailability notice for students */}
            {studentBlocked && (
              <p className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                This supervisor is currently unavailable and not accepting new requests.
              </p>
            )}

            {/* Action buttons */}
            {isSupervisor && isStudent && (
              <div className="mt-4">
                {supervisionStatus === "accepted" ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-green-50 text-green-700 border border-green-200">
                    <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                    Supervision accepted
                  </span>
                ) : supervisionStatus === "pending" ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                    Request pending…
                  </span>
                ) : (
                  <>
                    <button
                      onClick={() => supervisionMutation.mutate()}
                      disabled={supervisionMutation.isPending || supervisorUnavailable}
                      title={supervisorUnavailable ? "Supervisor is currently unavailable" : undefined}
                      className={`btn-primary text-sm ${supervisorUnavailable ? "opacity-40 cursor-not-allowed" : ""}`}
                    >
                      {supervisionStatus === "rejected" ? "Request supervision again" : "Request supervision"}
                    </button>
                    {!supervisorUnavailable && (
                      <div className="mt-3">
                        <textarea
                          className="input resize-none text-sm"
                          rows={2}
                          placeholder="Message (optional) — why you'd like supervision"
                          value={supMessage}
                          onChange={(e) => setSupMessage(e.target.value)}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── About ─────────────────────────────────────────────────── */}
        {profile.bio && (
          <div className="card">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
              About
            </h3>
            <p className="text-sm text-text whitespace-pre-line leading-relaxed">
              {profile.bio}
            </p>
          </div>
        )}

        {/* ── Research interests ────────────────────────────────────── */}
        {profile.research_interests && (
          <div className="card">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
              Research interests
            </h3>
            <p className="text-sm text-text leading-relaxed">{profile.research_interests}</p>
          </div>
        )}

        {/* ── Publications ─────────────────────────────────────────── */}
        {user.publications?.length > 0 && (
          <div className="card">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-4">
              Publications
            </h3>
            <div className="divide-y divide-border">
              {user.publications.map((pub) => {
                const isPendingForMe =
                  pub.verification?.status === "pending" &&
                  pub.verification?.verifier_id === me?.id &&
                  (role === "supervisor" || role === "admin");
                return (
                  <div
                    key={pub.id}
                    className="py-3 first:pt-0 last:pb-0 pl-3 border-l-2 border-accent"
                  >
                    <p className="text-sm font-medium text-text">{pub.title}</p>
                    {pub.published_year && (
                      <p className="text-xs text-muted mt-0.5">{pub.published_year}</p>
                    )}
                    {pub.abstract && (
                      <p className="text-xs text-muted mt-1 line-clamp-2">{pub.abstract}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      <VerificationBadge verification={pub.verification} />
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
                      {isPendingForMe && (
                        <button
                          onClick={() => signMutation.mutate(pub.id)}
                          disabled={signMutation.isPending}
                          className="text-xs px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors font-medium disabled:opacity-50"
                        >
                          {signMutation.isPending ? "Signing…" : "Sign & verify"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
