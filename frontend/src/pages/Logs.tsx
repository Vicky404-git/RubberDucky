import { useEffect, useMemo, useState } from "react";
import { RefreshCw, ScrollText, Shield, Radio } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Field";
import { EmptyState, ErrorBanner, Skeleton } from "../components/ui/States";
import { formatClock, levelTone } from "../lib/format";
import { cn } from "../lib/cn";
import { useAppStore } from "../stores/appStore";

const LEVEL_STYLES = {
  debug: "text-zinc-500 border-zinc-600/30 bg-zinc-500/10",
  info: "text-sky-300 border-sky-400/20 bg-sky-400/[0.07]",
  warn: "text-amber-glow border-amber-glow/25 bg-amber-glow/[0.07]",
  error: "text-danger border-danger/25 bg-danger/[0.07]",
};

export function Logs() {
  const logs = useAppStore((state) => state.logs);
  const logPath = useAppStore((state) => state.logPath);
  const logsExist = useAppStore((state) => state.logsExist);
  const loading = useAppStore((state) => state.loading);
  const error = useAppStore((state) => state.errors.logs);
  const events = useAppStore((state) => state.events);
  const refreshLogs = useAppStore((state) => state.refreshLogs);

  const [tab, setTab] = useState<"log" | "events">("events");
  const [level, setLevel] = useState("ALL");
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    void refreshLogs();
  }, [refreshLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => void refreshLogs(), 5000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, refreshLogs]);

  const filtered = useMemo(() => {
    if (level === "ALL") return logs;
    return logs.filter((entry) => levelTone(entry.level) === level.toLowerCase());
  }, [logs, level]);

  const recentEvents = useMemo(() => events.slice(-150).reverse(), [events]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Diagnostics"
        title="Logs"
        description="Rotating debug.log metadata and the live bridge event stream. No transcripts, diffs, prompts, exception text or credentials are logged."
        actions={
          <Button size="sm" variant="ghost" onClick={() => void refreshLogs()} loading={loading.logs}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-xl border border-white/[0.08] bg-black/25 p-1">
          <button
            type="button"
            onClick={() => setTab("events")}
            className={cn(
              "focus-ring inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors",
              tab === "events" ? "bg-white/[0.08] text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
            )}
          >
            <Radio className="h-3.5 w-3.5" aria-hidden /> Live events
            <Badge tone="neutral" className="ml-1">{events.length}</Badge>
          </button>
          <button
            type="button"
            onClick={() => setTab("log")}
            className={cn(
              "focus-ring inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-colors",
              tab === "log" ? "bg-white/[0.08] text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
            )}
          >
            <ScrollText className="h-3.5 w-3.5" aria-hidden /> debug.log
            <Badge tone="neutral" className="ml-1">{logs.length}</Badge>
          </button>
        </div>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void refreshLogs()} /> : null}

      {tab === "events" ? (
        <Panel
          title="Live bridge events"
          subtitle="Newest first. These are the same events that drive the orb and session timeline."
          action={<Badge tone="duck" dot>streaming</Badge>}
        >
          {recentEvents.length === 0 ? (
            <EmptyState
              title="No events yet"
              description="Start a session to watch recording, STT, triage, LLM and TTS events arrive."
              icon={<Radio className="h-4 w-4" />}
            />
          ) : (
            <ul className="max-h-[560px] space-y-1 overflow-auto">
              {recentEvents.map((event, index) => (
                <li
                  key={`${event.timestamp}-${event.type}-${index}`}
                  className="flex items-start gap-3 rounded-lg border border-white/[0.04] bg-black/15 px-3 py-2 font-mono text-[11px]"
                >
                  <span className="shrink-0 text-zinc-600">{formatClock(event.timestamp)}</span>
                  <span
                    className={cn(
                      "shrink-0 rounded border px-1.5 py-0.5 text-[10px]",
                      event.type === "session_failed"
                        ? LEVEL_STYLES.error
                        : event.type.includes("completed")
                          ? "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300"
                          : "border-duck-400/20 bg-duck-400/[0.06] text-duck-200",
                    )}
                  >
                    {event.type}
                  </span>
                  <span className="min-w-0 flex-1 break-words text-zinc-400">
                    {event.message ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      ) : (
        <Panel
          title="Diagnostic log"
          subtitle={logPath ?? "debug.log"}
          action={
            <div className="flex items-center gap-2">
              <Select
                value={level}
                onChange={(event) => setLevel(event.target.value)}
                aria-label="Filter log level"
                className="h-8 w-28 py-1 text-xs"
              >
                {["ALL", "DEBUG", "INFO", "WARNING", "ERROR"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
              <button
                type="button"
                role="switch"
                aria-checked={autoRefresh}
                onClick={() => setAutoRefresh((value) => !value)}
                className={cn(
                  "focus-ring inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] transition-colors",
                  autoRefresh
                    ? "border-duck-400/30 bg-duck-400/10 text-duck-200"
                    : "border-white/[0.08] text-zinc-500 hover:text-zinc-300",
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", autoRefresh ? "bg-duck-400" : "bg-zinc-600")} />
                Auto
              </button>
            </div>
          }
        >
          {!logsExist ? (
            <EmptyState
              title="debug.log has not been created"
              description="The CLI or a session will create it on the first logged event."
            />
          ) : loading.logs && logs.length === 0 ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-8 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState title="No log entries at this level" />
          ) : (
            <ul className="max-h-[560px] space-y-1 overflow-auto">
              {filtered
                .slice()
                .reverse()
                .map((entry, index) => {
                  const tone = levelTone(entry.level);
                  return (
                    <li
                      key={`${entry.line}-${index}`}
                      className="flex items-start gap-3 rounded-lg border border-white/[0.04] bg-black/15 px-3 py-2 font-mono text-[11px]"
                    >
                      <span className={cn("shrink-0 rounded border px-1.5 py-0.5 text-[10px]", LEVEL_STYLES[tone])}>
                        {entry.level}
                      </span>
                      <span className="min-w-0 flex-1 break-words text-zinc-400">{entry.message}</span>
                    </li>
                  );
                })}
            </ul>
          )}
          <p className="mt-3 flex items-start gap-2 text-[11px] leading-relaxed text-zinc-600">
            <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            Log entries are re-sanitised in the bridge before they reach the UI.
          </p>
        </Panel>
      )}
    </div>
  );
}
