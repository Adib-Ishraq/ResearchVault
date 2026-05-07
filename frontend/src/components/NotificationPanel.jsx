import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

function navDestination(n) {
  const p = n.payload;
  switch (n.type) {
    case "supervision_request":               return p ? `/profile/${p}` : null;
    case "supervision_accepted":              return p ? `/profile/${p}` : null;
    case "supervision_rejected":              return p ? `/profile/${p}` : null;
    case "room_invite":                       return p ? `/rooms/${p}` : null;
    case "room_announcement":                 return p ? `/rooms/${p}` : null;
    case "credential_verification_request":   return p ? `/profile/${p}` : null;
    case "credential_verified":               return "/profile/me";
    default: return null;
  }
}

export default function NotificationPanel({ onClose }) {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get("/notifications").then((r) => r.data),
  });

  const markRead = useMutation({
    mutationFn: (id) => api.put(`/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries(["notifications"]),
  });

  const markAllRead = useMutation({
    mutationFn: () => api.put("/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries(["notifications"]),
  });

  const typeLabel = {
    supervision_request: "Supervision request received",
    supervision_accepted: "Supervision request accepted",
    supervision_rejected: "Supervision request rejected",
    room_invite: "New member joined your room",
    room_announcement: "New announcement in your room",
    credential_verification_request: "Credential verification requested",
    credential_verified: "Your credential has been verified",
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />

      {/* Panel */}
      <aside className="fixed right-0 top-0 h-full w-96 bg-surface shadow-xl z-50 flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-text">Notifications</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => markAllRead.mutate()}
              className="text-xs text-accent hover:underline"
            >
              Mark all read
            </button>
            <button onClick={onClose} className="text-muted hover:text-text">
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {notifications.length === 0 ? (
            <p className="text-muted text-sm p-6 text-center">No notifications yet</p>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                className={`p-4 border-b border-border flex gap-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                  !n.is_read ? "bg-accent-light" : ""
                }`}
                onClick={() => {
                  if (!n.is_read) markRead.mutate(n.id);
                  const dest = navDestination(n);
                  if (dest) { onClose(); navigate(dest); }
                }}
              >
                <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${n.is_read ? "bg-gray-300" : "bg-accent"}`} />
                <div>
                  <p className="text-sm text-text">{typeLabel[n.type] || n.type}</p>
                  <p className="text-xs text-muted mt-0.5">
                    {new Date(n.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
}
