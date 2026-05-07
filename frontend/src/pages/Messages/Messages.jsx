import React, { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Layout from "../../components/Layout";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

export default function Messages() {
  const [activeConvId, setActiveConvId] = useState(null);
  const [newMessage, setNewMessage] = useState("");
  const [sendError, setSendError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const messagesEndRef = useRef(null);
  const qc = useQueryClient();
  const { user } = useAuthStore();

  // ── Conversations list ────────────────────────────────────────────────────
  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.get("/messages/conversations").then((r) => r.data),
    refetchInterval: 15_000,
  });

  // ── Messages in active conversation ──────────────────────────────────────
  const { data: messages = [], isFetching: loadingMessages } = useQuery({
    queryKey: ["messages", activeConvId],
    queryFn: () =>
      api.get(`/messages/conversations/${activeConvId}/messages`).then((r) => r.data),
    enabled: !!activeConvId,
    refetchInterval: 10_000,
  });

  // Scroll to bottom when messages load or new ones arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send message ──────────────────────────────────────────────────────────
  const sendMutation = useMutation({
    mutationFn: () =>
      api.post(`/messages/conversations/${activeConvId}/messages`, {
        content: newMessage,
      }),
    onSuccess: () => {
      setNewMessage("");
      setSendError("");
      qc.invalidateQueries(["messages", activeConvId]);
      qc.invalidateQueries(["conversations"]);
    },
    onError: (err) => setSendError(err.response?.data?.error || "Failed to send"),
  });

  const handleSend = (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sendMutation.isPending) return;
    sendMutation.mutate();
  };

  // ── Start new conversation via user search ────────────────────────────────
  const handleSearch = async (q) => {
    setSearchQuery(q);
    if (q.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await api.get("/search/researchers", { params: { name: q } });
      setSearchResults(res.data || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const startConversation = async (peerId) => {
    try {
      const res = await api.post(`/messages/conversations/${peerId}`);
      setActiveConvId(res.data.id);
      setSearchQuery("");
      setSearchResults([]);
      qc.invalidateQueries(["conversations"]);
    } catch (err) {
      console.error("Failed to start conversation", err);
    }
  };

  const activeConv = conversations.find((c) => c.id === activeConvId);

  return (
    <Layout>
      <div className="flex gap-0 h-[calc(100vh-7rem)] rounded-xl overflow-hidden border border-border">

        {/* ── Left sidebar: conversation list ───────────────────────── */}
        <aside className="w-72 flex-shrink-0 border-r border-border flex flex-col bg-surface">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-text text-sm mb-3">Messages</h2>
            {/* Search to start new conversation */}
            <div className="relative">
              <input
                className="input text-sm py-2"
                placeholder="Search users to message…"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
              />
              {searching && (
                <span className="absolute right-3 top-2.5 text-xs text-muted">…</span>
              )}
            </div>

            {/* Search results dropdown */}
            {searchResults.length > 0 && (
              <div className="mt-1 border border-border rounded-lg overflow-hidden shadow-sm bg-surface">
                {searchResults.slice(0, 6).map((u) => (
                  <button
                    key={u.id}
                    onClick={() => startConversation(u.id)}
                    className="w-full text-left px-3 py-2.5 hover:bg-gray-50 flex items-center gap-2 transition-colors"
                  >
                    <Avatar name={u.username} size="sm" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text truncate">{u.username}</p>
                      <p className="text-xs text-muted capitalize">{u.role}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <p className="text-muted text-xs text-center mt-8 px-4">
                Search for a user above to start a conversation
              </p>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => setActiveConvId(conv.id)}
                  className={`w-full text-left px-4 py-3.5 flex items-center gap-3 border-b border-border transition-colors ${
                    activeConvId === conv.id
                      ? "bg-accent-light"
                      : "hover:bg-gray-50"
                  }`}
                >
                  <Avatar name={conv.peer_name} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-text truncate">{conv.peer_name}</p>
                    <p className="text-xs text-muted">
                      {new Date(conv.last_message_at).toLocaleDateString()}
                    </p>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* ── Right: message thread ──────────────────────────────────── */}
        <div className="flex-1 flex flex-col bg-bg min-w-0">
          {!activeConvId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <p className="text-muted text-sm">Select a conversation</p>
                <p className="text-muted text-xs mt-1">or search for someone to message</p>
              </div>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="px-5 py-3.5 border-b border-border bg-surface flex items-center gap-3">
                {activeConv && <Avatar name={activeConv.peer_name} />}
                <p className="font-medium text-text text-sm">
                  {activeConv?.peer_name ?? "…"}
                </p>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
                {loadingMessages && messages.length === 0 && (
                  <p className="text-muted text-xs text-center">Loading…</p>
                )}
                {messages.length === 0 && !loadingMessages && (
                  <p className="text-muted text-xs text-center mt-8">
                    No messages yet — say hello!
                  </p>
                )}
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Composer */}
              <form
                onSubmit={handleSend}
                className="px-4 py-3 border-t border-border bg-surface flex gap-2 items-end"
              >
                <textarea
                  className="input resize-none flex-1 text-sm py-2.5 max-h-32"
                  rows={1}
                  placeholder="Type a message…"
                  value={newMessage}
                  onChange={(e) => {
                    setNewMessage(e.target.value);
                    setSendError("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend(e);
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={sendMutation.isPending || !newMessage.trim()}
                  className="btn-primary text-sm px-4 py-2.5 flex-shrink-0"
                >
                  {sendMutation.isPending ? "…" : "Send"}
                </button>
              </form>

              {sendError && (
                <p className="text-danger text-xs px-4 pb-2">{sendError}</p>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}

function MessageBubble({ msg }) {
  return (
    <div className={`flex ${msg.is_mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[70%] ${msg.is_mine ? "items-end" : "items-start"} flex flex-col gap-0.5`}>
        {!msg.is_mine && (
          <span className="text-xs text-muted ml-1">{msg.sender_name}</span>
        )}
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
            msg.is_mine
              ? "bg-accent text-white rounded-br-sm"
              : "bg-surface border border-border text-text rounded-bl-sm"
          }`}
        >
          {msg.content}
        </div>
        <span className="text-[11px] text-muted mx-1">
          {new Date(msg.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}

function Avatar({ name = "", size = "md" }) {
  const dim = size === "sm" ? "w-7 h-7 text-xs" : "w-9 h-9 text-sm";
  return (
    <div
      className={`${dim} rounded-full bg-accent-light flex items-center justify-center text-accent font-semibold flex-shrink-0`}
    >
      {name[0]?.toUpperCase() ?? "?"}
    </div>
  );
}
