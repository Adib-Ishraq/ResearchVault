import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

export default function RoomList() {
  const { role } = useAuthStore();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [createForm, setCreateForm] = useState({ title: "", description: "" });
  const [roomCode, setRoomCode] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const { data: rooms = [], isLoading } = useQuery({
    queryKey: ["rooms"],
    queryFn: () => api.get("/rooms").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/rooms/create", createForm),
    onSuccess: () => {
      qc.invalidateQueries(["rooms"]);
      setShowCreate(false);
      setCreateForm({ title: "", description: "" });
      setActionMsg("Room created");
    },
  });

  const joinMutation = useMutation({
    mutationFn: () => api.post("/rooms/join", { room_code: roomCode }),
    onSuccess: () => {
      qc.invalidateQueries(["rooms"]);
      setShowJoin(false);
      setRoomCode("");
      setActionMsg("Joined room");
    },
    onError: (err) => setActionMsg(err.response?.data?.error || "Failed to join"),
  });

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-semibold text-text">Research rooms</h1>
          <div className="flex gap-2">
            {role === "supervisor" && (
              <button onClick={() => setShowCreate(!showCreate)} className="btn-primary text-sm">
                Create room
              </button>
            )}
            <button onClick={() => setShowJoin(!showJoin)} className="btn-secondary text-sm">
              Join with code
            </button>
          </div>
        </div>

        {actionMsg && (
          <div className="bg-accent-light text-accent text-sm rounded-lg px-4 py-2 mb-4">{actionMsg}</div>
        )}

        {/* Create room form */}
        {showCreate && (
          <div className="card mb-6 space-y-3">
            <h3 className="font-medium text-text">Create new room</h3>
            <div>
              <label className="label">Room title</label>
              <input className="input" placeholder="e.g. ML in Healthcare — 2025" value={createForm.title}
                onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))} />
            </div>
            <div>
              <label className="label">Description (optional)</label>
              <textarea className="input resize-none" rows={2} value={createForm.description}
                onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))} />
            </div>
            <button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !createForm.title}
              className="btn-primary text-sm">
              {createMutation.isPending ? "Creating…" : "Create"}
            </button>
          </div>
        )}

        {/* Join room form */}
        {showJoin && (
          <div className="card mb-6 space-y-3">
            <h3 className="font-medium text-text">Join a room</h3>
            <div>
              <label className="label">Room code</label>
              <input className="input font-mono" placeholder="e.g. aB3xYz" value={roomCode}
                onChange={(e) => setRoomCode(e.target.value.trim())} />
            </div>
            <button onClick={() => joinMutation.mutate()} disabled={joinMutation.isPending || !roomCode}
              className="btn-primary text-sm">
              {joinMutation.isPending ? "Joining…" : "Join"}
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="text-muted">Loading…</p>
        ) : rooms.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-muted">
              {role === "supervisor"
                ? "Create your first research room to collaborate with students."
                : "Join a room using the code from your supervisor."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {rooms.map((room) => (
              <Link key={room.id} to={`/rooms/${room.id}`} className="card hover:shadow-md transition-shadow block">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-text">{room.title}</h3>
                    <p className="text-xs text-muted capitalize mt-0.5">{room.my_role}</p>
                    {room.my_role === "supervisor" && (
                      <p className="text-xs text-muted mt-1 font-mono">Code: {room.room_code}</p>
                    )}
                  </div>
                  <span className="text-xs text-muted">{new Date(room.created_at).toLocaleDateString()}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
