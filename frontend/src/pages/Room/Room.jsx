import React, { useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Layout from "../../components/Layout";
import api from "../../api/client";

const SECTIONS = ["updates", "data", "results"];
const QUERYABLE = ["updates", "data", "results", "announcements"];
const TABS_MEMBER     = ["announcements", "updates", "data", "results"];
const TABS_SUPERVISOR = ["announcements", "updates", "data", "results", "analytics"];

export default function Room() {
  const { roomId } = useParams();
  const qc = useQueryClient();
  const [activeSection, setActiveSection] = useState("updates");
  const [newPost, setNewPost] = useState("");
  const [postError, setPostError] = useState("");
  const [newAnnouncement, setNewAnnouncement] = useState("");
  const [announceError, setAnnounceError] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);
  const fileInputRef = useRef(null);
  const pdfInputRef = useRef(null);
  const [editingPostId, setEditingPostId] = useState(null);
  const [editContent, setEditContent] = useState("");

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get("/users/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: room, isLoading } = useQuery({
    queryKey: ["room", roomId],
    queryFn: () => api.get(`/rooms/${roomId}`).then((r) => r.data),
  });

  const { data: posts = [], isFetching: loadingPosts } = useQuery({
    queryKey: ["room-posts", roomId, activeSection],
    queryFn: () =>
      api.get(`/rooms/${roomId}/posts`, { params: { section: activeSection } }).then((r) => r.data),
    enabled: QUERYABLE.includes(activeSection),
    refetchInterval: 30_000,
  });

  const postMutation = useMutation({
    mutationFn: async () => {
      let image_url = null;
      let pdf_url = null;
      if (imageFile) {
        const form = new FormData();
        form.append("image", imageFile);
        const res = await api.post(`/rooms/${roomId}/upload-image`, form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        image_url = res.data.image_url;
      }
      if (pdfFile) {
        const form = new FormData();
        form.append("pdf", pdfFile);
        const res = await api.post(`/rooms/${roomId}/upload-pdf`, form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        pdf_url = res.data.pdf_url;
      }
      return api.post(`/rooms/${roomId}/post`, {
        section: activeSection,
        content: newPost,
        ...(image_url && { image_url }),
        ...(pdf_url && { pdf_url }),
      });
    },
    onSuccess: () => {
      setNewPost("");
      setImageFile(null);
      setImagePreview(null);
      setPdfFile(null);
      qc.invalidateQueries(["room-posts", roomId, activeSection]);
    },
    onError: (err) => setPostError(err.response?.data?.error || "Failed to post"),
  });

  const announceMutation = useMutation({
    mutationFn: () => api.post(`/rooms/${roomId}/announce`, { content: newAnnouncement }),
    onSuccess: () => {
      setNewAnnouncement("");
      qc.invalidateQueries(["room-posts", roomId, "announcements"]);
    },
    onError: (err) => setAnnounceError(err.response?.data?.error || "Failed to post"),
  });

  const editMutation = useMutation({
    mutationFn: ({ postId, content }) =>
      api.put(`/rooms/${roomId}/posts/${postId}`, { content }),
    onSuccess: () => {
      setEditingPostId(null);
      setEditContent("");
      qc.invalidateQueries(["room-posts", roomId, activeSection]);
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId) => api.delete(`/rooms/${roomId}/members/${userId}`),
    onSuccess: () => qc.invalidateQueries(["room", roomId]),
  });

  const handleImagePick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    e.target.value = "";
  };

  const handlePdfPick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPdfFile(file);
    e.target.value = "";
  };

  if (isLoading) return <Layout><p className="text-muted">Loading…</p></Layout>;
  if (!room) return <Layout><p className="text-muted">Room not found</p></Layout>;

  const isSupervisor = room.my_role === "supervisor";
  const visibleTabs = isSupervisor ? TABS_SUPERVISOR : TABS_MEMBER;

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Room header */}
        <div className="card">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-text">{room.title}</h1>
              {room.description && <p className="text-muted text-sm mt-1">{room.description}</p>}
            </div>
            {isSupervisor && (
              <div className="text-right">
                <p className="text-xs text-muted">Room code</p>
                <p className="font-mono font-semibold text-text">{room.room_code}</p>
              </div>
            )}
          </div>

          {/* Members */}
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted uppercase tracking-wide mb-2">Members ({room.members?.length})</p>
            <div className="flex flex-wrap gap-2">
              {room.members?.map((m) => (
                <div key={m.user_id} className="flex items-center gap-1.5 bg-gray-50 rounded-full px-3 py-1">
                  <div className="w-5 h-5 rounded-full bg-accent-light flex items-center justify-center text-accent text-xs font-semibold">
                    {m.username[0]?.toUpperCase()}
                  </div>
                  <span className="text-xs text-text">{m.username}</span>
                  {m.room_role === "supervisor" && (
                    <span className="text-xs text-accent">·&nbsp;Supervisor</span>
                  )}
                  {isSupervisor && m.room_role !== "supervisor" && (
                    <button
                      onClick={() => {
                        if (window.confirm(`Remove ${m.username} from this room?`))
                          removeMemberMutation.mutate(m.user_id);
                      }}
                      className="text-muted hover:text-danger text-xs leading-none ml-1"
                      title={`Remove ${m.username}`}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Section / Analytics tabs */}
        <div className="flex border border-border rounded-lg overflow-hidden w-fit">
          {visibleTabs.map((s) => (
            <button
              key={s}
              onClick={() => setActiveSection(s)}
              className={`px-5 py-2.5 text-sm font-medium capitalize transition-colors ${
                activeSection === s
                  ? s === "analytics"
                    ? "bg-indigo-600 text-white"
                    : s === "announcements"
                    ? "bg-amber-500 text-white"
                    : "bg-accent text-white"
                  : "text-muted hover:text-text"
              }`}
            >
              {s === "analytics" ? "Analytics" : s === "announcements" ? "📢 Announcements" : s}
            </button>
          ))}
        </div>

        {/* Analytics panel */}
        {activeSection === "analytics" && isSupervisor && (
          <AnalyticsPanel roomId={roomId} />
        )}

        {/* Announcements */}
        {activeSection === "announcements" && (
          <div className="space-y-4">
            {/* Supervisor compose form */}
            {isSupervisor && (
              <div className="card border-amber-200 bg-amber-50 space-y-3">
                <p className="text-sm font-semibold text-amber-800">Post an Announcement</p>
                <textarea
                  className="w-full border border-amber-300 rounded-lg px-4 py-2.5 text-text bg-white focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400 transition-colors resize-none"
                  rows={3}
                  placeholder="Write an announcement for all room members…"
                  value={newAnnouncement}
                  onChange={(e) => { setNewAnnouncement(e.target.value); setAnnounceError(""); }}
                />
                {announceError && <p className="text-danger text-sm">{announceError}</p>}
                <div className="flex justify-end">
                  <button
                    onClick={() => announceMutation.mutate()}
                    disabled={announceMutation.isPending || !newAnnouncement.trim()}
                    className="bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    {announceMutation.isPending ? "Posting…" : "Post Announcement"}
                  </button>
                </div>
              </div>
            )}

            {loadingPosts && posts.length === 0 && (
              <p className="text-muted text-sm">Loading announcements…</p>
            )}
            {posts.length === 0 && !loadingPosts ? (
              <div className="card text-center py-8">
                <p className="text-muted text-sm">No announcements yet</p>
              </div>
            ) : (
              posts.map((post) => (
                <div key={post.id} className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-card">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-amber-600 text-base">📢</span>
                    <div>
                      <p className="text-sm font-semibold text-amber-900">{post.author_name}</p>
                      <p className="text-xs text-amber-600">{new Date(post.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <p className="text-sm text-amber-900 whitespace-pre-line">{post.content}</p>
                </div>
              ))
            )}
          </div>
        )}

        {/* Posts */}
        {SECTIONS.includes(activeSection) && (
          <>
            <div className="space-y-4">
              {loadingPosts && posts.length === 0 && <p className="text-muted text-sm">Loading posts…</p>}

              {posts.length === 0 && !loadingPosts ? (
                <div className="card text-center py-8">
                  <p className="text-muted text-sm">No posts in {activeSection} yet</p>
                </div>
              ) : (
                posts.map((post) => {
                  const isEditing = editingPostId === post.id;
                  const isMyPost = post.author_id === me?.id;
                  return (
                    <div key={post.id} className="card">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-accent-light flex items-center justify-center text-accent text-xs font-semibold">
                            {post.author_name[0]?.toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-text">{post.author_name}</p>
                            <p className="text-xs text-muted">{new Date(post.created_at).toLocaleString()}</p>
                          </div>
                        </div>
                        {isMyPost && !isEditing && (
                          <button
                            onClick={() => { setEditingPostId(post.id); setEditContent(post.content); }}
                            className="text-xs text-muted hover:text-accent px-2 py-1 rounded hover:bg-gray-100 transition-colors flex-shrink-0"
                          >
                            Edit
                          </button>
                        )}
                      </div>

                      {isEditing ? (
                        <div className="space-y-2">
                          <textarea
                            className="input resize-none w-full"
                            rows={4}
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            autoFocus
                          />
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => { setEditingPostId(null); setEditContent(""); }}
                              className="btn-secondary text-xs px-3 py-1.5"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => editMutation.mutate({ postId: post.id, content: editContent })}
                              disabled={editMutation.isPending || !editContent.trim()}
                              className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50"
                            >
                              {editMutation.isPending ? "Saving…" : "Save"}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-text whitespace-pre-line">{post.content}</p>
                      )}

                      {post.image_url && (
                        <img
                          src={post.image_url}
                          alt="attachment"
                          className="mt-3 rounded-lg max-h-80 object-contain border border-border"
                        />
                      )}
                      {post.pdf_url && (
                        <a
                          href={post.pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 inline-flex items-center gap-1.5 text-xs text-accent hover:underline border border-border rounded-lg px-3 py-2 bg-gray-50"
                        >
                          <PdfIcon /> View PDF
                        </a>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* New post composer */}
            <div className="card space-y-3">
              <p className="text-sm font-medium text-text capitalize">Post to {activeSection}</p>
              <textarea
                className="input resize-none"
                rows={4}
                placeholder={`Share ${activeSection === "updates" ? "a progress update" : activeSection === "data" ? "data or findings" : "results or conclusions"}…`}
                value={newPost}
                onChange={(e) => { setNewPost(e.target.value); setPostError(""); }}
              />

              {/* Image preview */}
              {imagePreview && (
                <div className="relative w-fit">
                  <img
                    src={imagePreview}
                    alt="preview"
                    className="max-h-40 rounded-lg border border-border object-contain"
                  />
                  <button
                    onClick={() => { setImageFile(null); setImagePreview(null); }}
                    className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-surface border border-border text-muted hover:text-danger flex items-center justify-center text-xs leading-none"
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* PDF preview */}
              {pdfFile && (
                <div className="flex items-center gap-2 bg-gray-50 border border-border rounded-lg px-3 py-2 w-fit">
                  <PdfIcon />
                  <span className="text-xs text-text truncate max-w-[200px]">{pdfFile.name}</span>
                  <button
                    onClick={() => setPdfFile(null)}
                    className="text-muted hover:text-danger text-xs leading-none ml-1"
                  >
                    ✕
                  </button>
                </div>
              )}

              {postError && <p className="text-danger text-sm">{postError}</p>}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleImagePick}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-1.5 text-sm text-muted hover:text-text px-3 py-1.5 rounded-lg hover:bg-surface-subtle border border-border transition-all duration-150"
                    title="Attach image"
                  >
                    <ImageIcon />
                    <span className="hidden sm:inline">Image</span>
                  </button>
                  {activeSection === "updates" && (
                    <>
                      <input
                        ref={pdfInputRef}
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={handlePdfPick}
                      />
                      <button
                        type="button"
                        onClick={() => pdfInputRef.current?.click()}
                        className="flex items-center gap-1.5 text-sm text-muted hover:text-text px-3 py-1.5 rounded-lg hover:bg-surface-subtle border border-border transition-all duration-150"
                        title="Attach PDF"
                      >
                        <PdfIcon />
                        <span className="hidden sm:inline">PDF</span>
                      </button>
                    </>
                  )}
                </div>
                <button
                  onClick={() => postMutation.mutate()}
                  disabled={postMutation.isPending || !newPost.trim()}
                  className="btn-primary text-sm"
                >
                  {postMutation.isPending ? "Posting…" : "Post"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}

// ── Analytics panel ────────────────────────────────────────────────────────────
function AnalyticsPanel({ roomId }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["room-analytics", roomId],
    queryFn: () => api.get(`/rooms/${roomId}/analytics`).then((r) => r.data),
    staleTime: 60_000,
  });

  if (isLoading) return <p className="text-muted text-sm">Loading analytics…</p>;
  if (isError) return <p className="text-danger text-sm">Failed to load analytics.</p>;

  const maxDay = Math.max(1, ...data.timeline.map((d) => d.count));

  const downloadReport = async () => {
    try {
      const res = await api.get(`/rooms/${roomId}/analytics/posts`);
      const { room_title, posts, generated_at } = res.data;
      const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const sectionColor = { updates: "#3b82f6", data: "#8b5cf6", results: "#10b981", announcements: "#f59e0b" };
      const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Activity Report — ${esc(room_title)}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Helvetica Neue',Arial,sans-serif;padding:48px;color:#111;background:#fff}
h1{font-size:24px;font-weight:700;margin-bottom:4px}
h2{font-size:15px;font-weight:500;color:#555;margin-bottom:6px}
.meta{color:#777;font-size:12px;margin-bottom:36px}
.post{border-left:4px solid #6366f1;padding:14px 18px;margin-bottom:16px;background:#fafafa;border-radius:0 8px 8px 0;page-break-inside:avoid}
.ph{display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap}
.author{font-weight:600;font-size:13px}
.badge{font-size:10px;padding:2px 8px;border-radius:9999px;font-weight:600;color:#fff;text-transform:capitalize}
.date{color:#999;font-size:11px}
.body{font-size:13px;white-space:pre-wrap;line-height:1.65;color:#333}
@media print{body{padding:20mm}}</style>
</head><body>
<h1>Activity Report</h1>
<h2>${esc(room_title)}</h2>
<p class="meta">Generated: ${new Date(generated_at).toLocaleString()} &nbsp;·&nbsp; ${posts.length} post${posts.length !== 1 ? "s" : ""}</p>
${posts.map((p) => {
  const c = sectionColor[p.section] || "#6366f1";
  return `<div class="post" style="border-left-color:${c}">
<div class="ph"><span class="author">${esc(p.author_name)}</span>
<span class="badge" style="background:${c}">${esc(p.section)}</span>
<span class="date">${new Date(p.created_at).toLocaleString()}</span></div>
<div class="body">${esc(p.content)}</div></div>`;
}).join("")}
</body></html>`;
      const win = window.open("", "_blank");
      win.document.write(html);
      win.document.close();
      setTimeout(() => win.print(), 300);
    } catch {
      /* silently ignore — user can retry */
    }
  };

  return (
    <div className="space-y-5">
      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total posts" value={data.total_posts} />
        <StatCard label="Updates" value={data.section_counts.updates} color="text-blue-600" />
        <StatCard label="Data" value={data.section_counts.data} color="text-purple-600" />
        <StatCard label="Results" value={data.section_counts.results} color="text-green-600" />
        <StatCard label="Contributors" value={data.member_contributions.filter((m) => m.post_count > 0).length} />
      </div>

      {/* Activity heatmap — last 30 days */}
      <div className="card">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-4">
          Activity — last 30 days
        </h3>
        <div className="flex gap-1 flex-wrap">
          {data.timeline.map((day) => {
            const intensity = day.count === 0 ? 0 : Math.ceil((day.count / maxDay) * 4);
            const bg = ["bg-gray-100", "bg-green-200", "bg-green-400", "bg-green-500", "bg-green-700"][intensity];
            return (
              <div
                key={day.date}
                title={`${day.date}: ${day.count} post${day.count !== 1 ? "s" : ""}`}
                className={`w-6 h-6 rounded-sm ${bg} cursor-default transition-colors`}
              />
            );
          })}
        </div>
        <div className="flex items-center gap-1.5 mt-3">
          <span className="text-[10px] text-muted">Less</span>
          {["bg-gray-100", "bg-green-200", "bg-green-400", "bg-green-500", "bg-green-700"].map((c) => (
            <div key={c} className={`w-3 h-3 rounded-sm ${c}`} />
          ))}
          <span className="text-[10px] text-muted">More</span>
        </div>
      </div>

      {/* Member contributions */}
      <div className="card">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-4">
          Contributions by member
        </h3>
        {data.member_contributions.length === 0 ? (
          <p className="text-sm text-muted">No posts yet.</p>
        ) : (
          <div className="space-y-2">
            {data.member_contributions.map((m) => {
              const pct = data.total_posts > 0 ? Math.round((m.post_count / data.total_posts) * 100) : 0;
              return (
                <div key={m.user_id} className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-full bg-accent-light flex items-center justify-center text-accent text-xs font-semibold flex-shrink-0">
                    {m.username[0]?.toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-text truncate">{m.username}</span>
                      <span className="text-xs text-muted ml-2 flex-shrink-0">{m.post_count} posts</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Section breakdown */}
      <div className="card">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-widest mb-4">
          Section breakdown
        </h3>
        <div className="space-y-2">
          {[
            ["Updates", data.section_counts.updates, "bg-blue-400"],
            ["Data", data.section_counts.data, "bg-purple-400"],
            ["Results", data.section_counts.results, "bg-green-500"],
          ].map(([label, count, color]) => {
            const pct = data.total_posts > 0 ? Math.round((count / data.total_posts) * 100) : 0;
            return (
              <div key={label} className="flex items-center gap-3">
                <span className="text-sm text-text w-16 flex-shrink-0">{label}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs text-muted w-8 text-right flex-shrink-0">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Download report */}
      <div className="card flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-text">Download activity report</p>
          <p className="text-xs text-muted mt-0.5">
            PDF with contributor names, sections, and post contents.
            Generated: {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
        <button onClick={downloadReport} className="btn-secondary text-sm flex-shrink-0 flex items-center gap-1.5">
          <PdfIcon /> Download PDF
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-text" }) {
  return (
    <div className="card py-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-muted mt-1">{label}</p>
    </div>
  );
}

function ImageIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 21H17a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 13h2.5a1.5 1.5 0 010 3H8v-3zm0 0V11m4 5h1m2-5v5" />
    </svg>
  );
}
