import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import Layout from "../../components/Layout";
import api from "../../api/client";

export default function Discover() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") || "supervisors";
  const [selectedUniversity, setSelectedUniversity] = useState("");
  const [uniSearch, setUniSearch] = useState("");
  const [nameSearch, setNameSearch] = useState("");
  const [domainSearch, setDomainSearch] = useState("");

  // Reset domain search when switching tabs
  useEffect(() => {
    setDomainSearch("");
  }, [tab]);

  const { data: universities = [] } = useQuery({
    queryKey: ["universities"],
    queryFn: () => api.get("/search/universities").then((r) => r.data),
  });

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["search", tab, selectedUniversity, nameSearch],
    queryFn: () =>
      api.get(`/search/${tab === "supervisors" ? "supervisors" : "researchers"}`, {
        params: {
          university: selectedUniversity || undefined,
          name: nameSearch || undefined,
          role: tab === "researchers" ? "postgrad" : undefined,
        },
      }).then((r) => r.data),
    keepPreviousData: true,
  });

  // Client-side domain filter applied on top of server results
  const displayResults = domainSearch && tab === "supervisors"
    ? results.filter((u) =>
        u.research_interests?.toLowerCase().includes(domainSearch.toLowerCase())
      )
    : results;

  const filteredUniversities = uniSearch
    ? universities.filter((u) => u.toLowerCase().includes(uniSearch.toLowerCase()))
    : universities;

  return (
    <Layout>
      <div className="flex gap-6 min-h-[70vh]">
        {/* Left panel — university filter */}
        <aside className="w-56 flex-shrink-0">
          <div className="card p-0 overflow-hidden">
            <div className="px-3 py-3 border-b border-border">
              <p className="text-xs font-medium text-muted uppercase tracking-wide mb-2">Universities</p>
              <input
                className="input text-sm py-1.5"
                placeholder="Search universities…"
                value={uniSearch}
                onChange={(e) => setUniSearch(e.target.value)}
              />
            </div>
            <div className="max-h-[55vh] overflow-y-auto">
              <button
                onClick={() => setSelectedUniversity("")}
                className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                  !selectedUniversity ? "bg-accent-light text-accent" : "text-text hover:bg-gray-50"
                }`}
              >
                All universities
              </button>
              {filteredUniversities.map((uni) => (
                <button
                  key={uni}
                  onClick={() => setSelectedUniversity(uni)}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                    selectedUniversity === uni ? "bg-accent-light text-accent" : "text-text hover:bg-gray-50"
                  }`}
                >
                  {uni}
                </button>
              ))}
              {filteredUniversities.length === 0 && uniSearch && (
                <p className="px-4 py-3 text-xs text-muted">No matches</p>
              )}
            </div>
          </div>
        </aside>

        {/* Right panel — results */}
        <div className="flex-1 space-y-4">
          {/* Tabs + search inputs */}
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <div className="flex border border-border rounded-lg overflow-hidden">
                {["supervisors", "researchers"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setSearchParams({ tab: t })}
                    className={`px-4 py-2 text-sm font-medium transition-colors capitalize ${
                      tab === t ? "bg-accent text-white" : "text-muted hover:text-text"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <input
                className="input flex-1"
                placeholder="Search by name…"
                value={nameSearch}
                onChange={(e) => setNameSearch(e.target.value)}
              />
            </div>
            {tab === "supervisors" && (
              <input
                className="input"
                placeholder="Filter by research domain (e.g. machine learning, bioinformatics)…"
                value={domainSearch}
                onChange={(e) => setDomainSearch(e.target.value)}
              />
            )}
          </div>

          {isFetching && <p className="text-muted text-sm">Loading…</p>}

          {displayResults.length === 0 && !isFetching ? (
            <div className="card text-center py-12">
              <p className="text-muted">No results found</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {displayResults.map((user) => (
                <ResearcherCard key={user.id} user={user} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

function ResearcherCard({ user }) {
  return (
    <Link to={`/profile/${user.id}`} className="card hover:shadow-md transition-shadow block">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-accent-light flex items-center justify-center text-accent font-semibold flex-shrink-0">
          {user.username?.[0]?.toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="font-medium text-text truncate">{user.username}</p>
          <p className="text-xs text-muted capitalize">{user.role}</p>
          {user.university && <p className="text-xs text-muted mt-0.5">{user.university}</p>}
          {user.research_interests && (
            <p className="text-xs text-muted mt-1 line-clamp-2">{user.research_interests}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
