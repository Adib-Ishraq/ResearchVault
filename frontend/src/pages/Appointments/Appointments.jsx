import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Layout from "../../components/Layout";
import api from "../../api/client";
import { useAuthStore } from "../../store/authStore";

const STATUS_STYLES = {
  pending:   "bg-amber-50 text-amber-700 border-amber-200",
  approved:  "bg-green-50 text-green-700 border-green-200",
  rejected:  "bg-red-50 text-red-600 border-red-200",
  cancelled: "bg-gray-100 text-gray-500 border-gray-200",
};

function fmt(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function StudentCard({ appt, onCancel }) {
  return (
    <div className="card space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-text text-sm">{appt.title}</p>
          <p className="text-xs text-muted mt-0.5">
            With{" "}
            <Link to={`/profile/${appt.supervisor_id}`} className="text-accent hover:underline">
              {appt.other_user_name}
            </Link>
            {" "}· {fmt(appt.created_at)}
          </p>
        </div>
        <span className={`flex-shrink-0 text-xs font-medium px-2.5 py-0.5 rounded-full border ${STATUS_STYLES[appt.status]}`}>
          {appt.status}
        </span>
      </div>

      {appt.note && (
        <p className="text-xs text-muted bg-gray-50 rounded-lg px-3 py-2 border border-border">
          Your note: {appt.note}
        </p>
      )}

      {appt.status === "pending" && appt.proposed_times?.length > 0 && (
        <div>
          <p className="text-xs text-muted font-medium mb-1">Proposed times:</p>
          <div className="flex flex-wrap gap-1.5">
            {appt.proposed_times.map((t, i) => (
              <span key={i} className="text-xs bg-gray-100 text-text px-2 py-0.5 rounded-md border border-border">
                {fmt(t)}
              </span>
            ))}
          </div>
        </div>
      )}

      {appt.status === "approved" && appt.confirmed_time && (
        <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          <CalendarIcon />
          <span>Confirmed: <strong>{fmt(appt.confirmed_time)}</strong></span>
        </div>
      )}

      {appt.supervisor_note && (
        <p className="text-xs text-muted bg-gray-50 rounded-lg px-3 py-2 border border-border">
          Supervisor note: {appt.supervisor_note}
        </p>
      )}

      {(appt.status === "pending" || appt.status === "approved") && (
        <button onClick={() => onCancel(appt.id)} className="text-xs text-danger hover:underline mt-1">
          Cancel appointment
        </button>
      )}
    </div>
  );
}

function SupervisorCard({ appt, onRespond }) {
  const [expanded, setExpanded] = useState(false);
  const [confirmedTime, setConfirmedTime] = useState(appt.proposed_times?.[0] || "");
  const [note, setNote] = useState("");
  const [acting, setActing] = useState(null);

  if (appt.status !== "pending") {
    return (
      <div className="card space-y-2 opacity-80">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-medium text-text text-sm">{appt.title}</p>
            <p className="text-xs text-muted mt-0.5">
              From{" "}
              <Link to={`/profile/${appt.student_id}`} className="text-accent hover:underline">
                {appt.other_user_name}
              </Link>
              {" "}· {fmt(appt.created_at)}
            </p>
          </div>
          <span className={`flex-shrink-0 text-xs font-medium px-2.5 py-0.5 rounded-full border ${STATUS_STYLES[appt.status]}`}>
            {appt.status}
          </span>
        </div>
        {appt.status === "approved" && appt.confirmed_time && (
          <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
            <CalendarIcon />
            <span>Confirmed: <strong>{fmt(appt.confirmed_time)}</strong></span>
          </div>
        )}
        {appt.supervisor_note && (
          <p className="text-xs text-muted bg-gray-50 rounded-lg px-3 py-2 border border-border">
            Your note: {appt.supervisor_note}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="card space-y-3 border-l-4 border-l-amber-400">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-text text-sm">{appt.title}</p>
          <p className="text-xs text-muted mt-0.5">
            From{" "}
            <Link to={`/profile/${appt.student_id}`} className="text-accent hover:underline">
              {appt.other_user_name}
            </Link>
            {" "}· {fmt(appt.created_at)}
          </p>
        </div>
        <span className="flex-shrink-0 text-xs font-medium px-2.5 py-0.5 rounded-full border bg-amber-50 text-amber-700 border-amber-200">
          pending
        </span>
      </div>

      {appt.note && (
        <p className="text-xs text-muted bg-gray-50 rounded-lg px-3 py-2 border border-border">
          Student note: {appt.note}
        </p>
      )}

      {appt.proposed_times?.length > 0 && (
        <div>
          <p className="text-xs text-muted font-medium mb-1">Student proposed times — click one to select:</p>
          <div className="flex flex-wrap gap-1.5">
            {appt.proposed_times.map((t, i) => (
              <button
                key={i}
                onClick={() => setConfirmedTime(t)}
                className={`text-xs px-2 py-0.5 rounded-md border transition-colors ${
                  confirmedTime === t
                    ? "bg-accent text-white border-accent"
                    : "bg-gray-100 text-text border-border hover:bg-accent-light"
                }`}
              >
                {fmt(t)}
              </button>
            ))}
          </div>
        </div>
      )}

      {!expanded ? (
        <button onClick={() => setExpanded(true)} className="text-xs text-accent hover:underline">
          Respond to this request →
        </button>
      ) : (
        <div className="space-y-3 pt-3 border-t border-border">
          <div>
            <label className="text-xs text-muted font-medium">Confirm meeting time</label>
            <input
              type="datetime-local"
              className="input text-sm mt-1"
              value={confirmedTime}
              onChange={(e) => setConfirmedTime(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-muted font-medium">Note to student (optional)</label>
            <textarea
              className="input text-sm resize-none mt-1"
              rows={2}
              placeholder="e.g. Room 301, or Google Meet link…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button
              disabled={!confirmedTime || acting === "approve"}
              onClick={() => {
                setActing("approve");
                onRespond(appt.id, "approve", confirmedTime, note).finally(() => setActing(null));
              }}
              className="btn-primary text-sm disabled:opacity-50"
            >
              {acting === "approve" ? "Approving…" : "Approve"}
            </button>
            <button
              disabled={acting === "reject"}
              onClick={() => {
                setActing("reject");
                onRespond(appt.id, "reject", null, note).finally(() => setActing(null));
              }}
              className="text-sm px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {acting === "reject" ? "Rejecting…" : "Reject"}
            </button>
            <button onClick={() => setExpanded(false)} className="btn-secondary text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Appointments() {
  const { role } = useAuthStore();
  const qc = useQueryClient();
  const [tab, setTab] = useState("pending");
  const isSupervisor = role === "supervisor";

  const { data: appointments = [], isLoading } = useQuery({
    queryKey: ["appointments"],
    queryFn: () => api.get("/appointments/").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const cancelMutation = useMutation({
    mutationFn: (id) => api.put(`/appointments/${id}/cancel`),
    onSuccess: () => qc.invalidateQueries(["appointments"]),
  });

  const respond = (id, action, confirmed_time, note) =>
    api
      .put(`/appointments/${id}/respond`, { action, confirmed_time, note })
      .then(() => qc.invalidateQueries(["appointments"]));

  const pending  = appointments.filter((a) => a.status === "pending");
  const upcoming = appointments.filter((a) => a.status === "approved");
  const past     = appointments.filter((a) => a.status === "rejected" || a.status === "cancelled");

  const tabs = isSupervisor
    ? [
        { key: "pending",  label: `Requests${pending.length ? ` (${pending.length})` : ""}` },
        { key: "upcoming", label: "Upcoming" },
        { key: "past",     label: "Past" },
      ]
    : [
        { key: "upcoming", label: "Upcoming" },
        { key: "pending",  label: "Pending" },
        { key: "past",     label: "Past" },
      ];

  const displayed = tab === "pending" ? pending : tab === "upcoming" ? upcoming : past;

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-text">Appointments</h1>
          <p className="text-sm text-muted mt-0.5">
            {isSupervisor
              ? "Review and manage appointment requests from students."
              : "Track your appointment requests with supervisors."}
          </p>
        </div>

        {!isSupervisor && (
          <p className="text-xs text-muted bg-accent-light border border-accent/20 rounded-lg px-4 py-2.5">
            To book a new appointment, visit a supervisor profile and click{" "}
            <strong>Book Appointment</strong>.
          </p>
        )}

        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 text-sm py-1.5 rounded-lg font-medium transition-all ${
                tab === t.key ? "bg-white text-text shadow-sm" : "text-muted hover:text-text"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {isLoading && (
          <div className="text-center text-sm text-muted py-12">Loading…</div>
        )}

        {!isLoading && displayed.length === 0 && (
          <div className="text-center text-sm text-muted py-16 card">
            {tab === "pending" && isSupervisor
              ? "No pending requests."
              : tab === "pending"
              ? "No pending appointments."
              : tab === "upcoming"
              ? "No upcoming appointments."
              : "No past appointments."}
          </div>
        )}

        <div className="space-y-3">
          {displayed.map((appt) =>
            isSupervisor ? (
              <SupervisorCard key={appt.id} appt={appt} onRespond={respond} />
            ) : (
              <StudentCard key={appt.id} appt={appt} onCancel={(id) => cancelMutation.mutate(id)} />
            )
          )}
        </div>
      </div>
    </Layout>
  );
}

function CalendarIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}
