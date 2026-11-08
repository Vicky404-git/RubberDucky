import { useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  Clock3,
  GitBranch,
  Mic2,
  RotateCcw,
  Trash2,
  Volume2,
} from "lucide-react";
import { CATEGORY_LABELS, stageLabel } from "../../lib/orb";
import {
  formatDuration,
  formatRelativeTime,
  formatTimestamp,
  statusLabel,
  statusTone,
} from "../../lib/format";
import { useAppStore } from "../../stores/appStore";
import type { SessionRecord } from "../../types/api";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Panel } from "../ui/Panel";
import { SessionTimeline } from "./SessionTimeline";

function InfoRow({
  icon: Icon,
  label,
  value,
  mono = false,
}: {
  icon: typeof GitBranch;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start gap-2.5 text-xs">
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-600" aria-hidden />
      <span className="w-24 shrink-0 text-zinc-500">{label}</span>
      <span className={mono ? "min-w-0 break-words font-mono text-zinc-300" : "min-w-0 text-zinc-300"}>
        {value}
      </span>
    </div>
  );
}

export function SessionDetail({
  session,
  onRetry,
}: {
  session: SessionRecord | null;
  onRetry?: (session: SessionRecord) => void;
}) {
  const retrySession = useAppStore((state) => state.retrySession);
  const deleteAudio = useAppStore((state) => state.deleteAudio);
  const actionLoading = useAppStore((state) => state.loading.action);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (!session) {
    return (
      <Panel title="Session detail">
        <p className="py-16 text-center text-sm text-zinc-500">
          Select a session to inspect its transcript, classification and diagnosis.
        </p>
      </Panel>
    );
  }

  const tone = statusTone(session.status);
  const success = session.status === "completed" || Boolean(session.diagnosis && !session.error);

  return (
    <div className="space-y-5">
      <Panel
        title={
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              tone={
                tone === "active" ? "duck" : tone === "error" ? "error" : tone === "success" ? "success" : "neutral"
              }
              dot
            >
              {statusLabel(session.status)}
            </Badge>
            <span className="font-mono text-[11px] text-zinc-500">{session.id}</span>
          </div>
        }
        subtitle={`${formatTimestamp(session.started_at)} · ${formatRelativeTime(session.updated_at)}`}
        action={
          session.status === "failed" && session.retryable ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                const retried = await retrySession(session.id);
                if (retried) onRetry?.(retried);
              }}
              disabled={actionLoading}
            >
              <RotateCcw className="h-3.5 w-3.5" /> Retry
            </Button>
          ) : null
        }
      >
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-3">
            <InfoRow icon={Mic2} label="Transcript" value={session.transcript ?? "Not available."} />
            <InfoRow
              icon={BrainCircuit}
              label="LAYA class"
              value={
                session.category
                  ? `${CATEGORY_LABELS[session.category] ?? session.category}${session.category_source ? ` · ${session.category_source}` : ""}`
                  : "Unclassified"
              }
            />
            <InfoRow
              icon={Clock3}
              label="Pipeline"
              value={`${stageLabel(session.stage)} · ${formatDuration(session.duration_ms)}`}
            />
            <InfoRow icon={GitBranch} label="Git context" value={session.git_summary ?? "Unavailable"} mono />
            {typeof session.log_probability === "number" && session.log_probability > 0 ? (
              <InfoRow
                icon={AlertTriangle}
                label="Log likelihood"
                value={`${(session.log_probability * 100).toFixed(0)}%`}
              />
            ) : null}
          </div>

          <div className="space-y-4">
            <div>
              <p className="eyebrow mb-2">Diagnosis</p>
              <div className="panel-inset whitespace-pre-wrap p-4 text-xs leading-relaxed text-zinc-300">
                {session.diagnosis ?? "No diagnosis generated."}
              </div>
            </div>
            <div>
              <p className="eyebrow mb-2">Spoken response</p>
              <div className="rounded-xl border border-duck-400/15 bg-duck-400/[0.05] p-4 text-xs leading-relaxed text-duck-100/90">
                {session.spoken_response ?? "No spoken response."}
              </div>
            </div>

            {session.error ? (
              <div className="flex items-start gap-2 rounded-xl border border-danger/25 bg-danger/[0.07] p-3 text-xs text-danger">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>{session.error}</span>
              </div>
            ) : null}

            {session.audio_url ? (
              <div className="space-y-2">
                <p className="eyebrow flex items-center gap-2">
                  <Volume2 className="h-3 w-3" aria-hidden /> Generated audio
                </p>
                <audio
                  controls
                  preload="none"
                  src={session.audio_url}
                  className="h-10 w-full"
                  aria-label="Generated response audio"
                />
                {confirmDelete ? (
                  <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                    <span>Delete this audio file?</span>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        void deleteAudio(session.id);
                        setConfirmDelete(false);
                      }}
                    >
                      Delete
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(true)}>
                    <Trash2 className="h-3.5 w-3.5" /> Delete audio
                  </Button>
                )}
              </div>
            ) : success ? (
              <p className="text-[11px] text-zinc-600">Audio is no longer stored for this session.</p>
            ) : null}
          </div>
        </div>
      </Panel>

      <Panel title="Pipeline timeline" subtitle="Safe event metadata only — no prompts or credentials.">
        <SessionTimeline entries={session.timeline} limit={30} />
      </Panel>
    </div>
  );
}
