import { useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Search } from "lucide-react";
import { SessionCard } from "../components/Session/SessionCard";
import { SessionDetail } from "../components/Session/SessionDetail";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Field";
import { EmptyState, Skeleton } from "../components/ui/States";
import { useAppStore } from "../stores/appStore";

export function Sessions() {
  const sessions = useAppStore((state) => state.sessions);
  const loading = useAppStore((state) => state.loading);
  const startSession = useAppStore((state) => state.startSession);
  const refreshSessions = useAppStore((state) => state.refreshSessions);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return sessions;
    return sessions.filter((session) =>
      [session.transcript, session.diagnosis, session.category, session.git_branch]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(term)),
    );
  }, [sessions, query]);

  const selected =
    filtered.find((session) => session.id === selectedId) ?? filtered[0] ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="History"
        title="Debug sessions"
        description="Every voice session with its transcript, LAYA classification, Git summary, AI diagnosis and spoken response. Secrets and ignored files are redacted by the backend."
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={() => void refreshSessions()} loading={loading.sessions}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button size="sm" variant="primary" onClick={() => void startSession()} disabled={loading.action}>
              <Plus className="h-3.5 w-3.5" /> New session
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(300px,0.82fr)_minmax(0,1.35fr)]">
        <div className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-600" aria-hidden />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search transcripts, categories, branches…"
              className="pl-9"
              aria-label="Search sessions"
            />
          </div>

          <div className="space-y-2">
            {loading.bootstrap && sessions.length === 0 ? (
              Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="skeleton h-[112px] w-full" />
              ))
            ) : filtered.length === 0 ? (
              <EmptyState
                title={query ? "No matching sessions" : "No sessions yet"}
                description={
                  query
                    ? "Try a different transcript, category or branch."
                    : "Start a voice debug session from the overview page."
                }
              />
            ) : (
              filtered.map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  selected={selected?.id === session.id}
                  onSelect={(next) => setSelectedId(next.id)}
                />
              ))
            )}
          </div>
        </div>

        <div>
          {selected ? (
            <SessionDetail
              session={selected}
              onRetry={(retriedSession) => {
                setQuery("");
                setSelectedId(retriedSession.id);
              }}
            />
          ) : (
            <Skeleton className="h-[420px] w-full" />
          )}
        </div>
      </div>
    </div>
  );
}
