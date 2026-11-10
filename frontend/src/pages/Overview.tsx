import { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  GitBranch,
  Keyboard,
  Mic,
  Play,
  RotateCcw,
  Server,
  ShieldCheck,
  Sparkles,
  Volume2,
} from "lucide-react";
import { ActivityMeter, OrbStatusPill, ConnectionPill } from "../components/Status/Indicators";
import { PlaybackBar } from "../components/Status/PlaybackBar";
import { Orb } from "../components/Orb/Orb";
import { SessionTimeline } from "../components/Session/SessionTimeline";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorBanner, Skeleton } from "../components/ui/States";
import { CATEGORY_LABELS, ORB_COPY, stageLabel } from "../lib/orb";
import { formatRelativeTime, truncate } from "../lib/format";
import { cn } from "../lib/cn";
import { useAppStore } from "../stores/appStore";

const STEPS = ["recording", "transcription", "triage", "llm", "tts", "playback"];

function stageIndex(stage: string | null | undefined): number {
  if (!stage) return -1;
  return STEPS.indexOf(stage);
}

export function Overview() {
  const orbState = useAppStore((state) => state.orbState);
  const stage = useAppStore((state) => state.stage);
  const status = useAppStore((state) => state.status);
  const latest = useAppStore((state) => state.latest);
  const audio = useAppStore((state) => state.audio);
  const health = useAppStore((state) => state.health);
  const errorMessage = useAppStore((state) => state.errorMessage);
  const loading = useAppStore((state) => state.loading);
  const errors = useAppStore((state) => state.errors);
  const startSession = useAppStore((state) => state.startSession);
  const retrySession = useAppStore((state) => state.retrySession);
  const refreshStatus = useAppStore((state) => state.refreshStatus);
  const refreshSessions = useAppStore((state) => state.refreshSessions);

  useEffect(() => {
    void refreshStatus();
    void refreshSessions();
  }, [refreshStatus, refreshSessions]);

  const copy = ORB_COPY[orbState];
  const active = Boolean(status?.active) || orbState === "listening" || orbState === "processing";
  const canRetry = orbState === "error" && latest?.retryable;
  const selectedLlmProvider = useAppStore((state) => state.providers).find(
    (provider) => provider.kind === "llm" && provider.selected,
  );
  const llmKeyMissing = selectedLlmProvider
    ? !selectedLlmProvider.configured
    : !health?.has_openrouter_key;
  const missingCredentialNames = [
    ...(!health?.has_gnani_key ? ["GNANI_API"] : []),
    ...(llmKeyMissing ? [selectedLlmProvider?.env_var ?? "OPENROUTER_API_KEY"] : []),
  ];
  const missingCredentials = missingCredentialNames.length > 0;
  const currentIndex = stageIndex(stage);

  const handlePrimary = () => {
    if (active) return;
    if (canRetry && latest) {
      void retrySession(latest.id);
    } else {
      void startSession();
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Voice workspace"
        title="Debug out loud."
        description="Speak a bug. RubberDucky transcribes it, classifies the incident, reads your Git context and answers with a Hinglish diagnosis."
        actions={
          <>
            <ConnectionPill />
            <Link
              to="/sessions"
              className="focus-ring inline-flex h-9 items-center gap-1.5 rounded-lg border border-white/[0.08] px-3 text-xs text-zinc-400 transition-colors hover:border-white/[0.14] hover:text-zinc-100"
            >
              Session history <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </>
        }
      />

      {errors.bootstrap ? (
        <ErrorBanner message={errors.bootstrap} onRetry={() => void refreshStatus()} />
      ) : null}

      {missingCredentials ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-amber-glow/20 bg-amber-glow/[0.055] px-4 py-3 text-xs text-amber-glow">
          <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden />
          <span>
            Credentials incomplete: {missingCredentialNames.join(" · ")} missing. Add them in{" "}
            <Link to="/settings" className="underline underline-offset-2">
              Settings
            </Link>
            .
          </span>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
        <div className="glass-panel relative overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4">
            <div className="flex items-center gap-2">
              <OrbStatusPill state={orbState} />
              <Badge tone="neutral" className="font-mono text-[10px]">
                {stageLabel(stage)}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-500">
              <ActivityMeter
                mode={orbState === "listening" ? "listening" : audio ? "speaking" : "idle"}
                className="h-6"
              />
              <span className="hidden sm:inline">
                {orbState === "listening"
                  ? "Recording"
                  : audio
                    ? "Live amplitude"
                    : "Standing by"}
              </span>
            </div>
          </div>

          <div className="relative px-4 pb-2 pt-4 sm:px-8">
            <Orb
              state={orbState}
              className="mx-auto h-[min(56vh,540px)] w-full max-w-[600px]"
            />

            <div className="pointer-events-none absolute inset-x-0 top-6 flex flex-col items-center px-6 text-center">
              <p className="font-display text-[11px] uppercase tracking-[0.28em] text-zinc-500">
                {orbState === "idle" ? "RubberDucky" : "Current state"}
              </p>
              <h2 className="mt-1.5 text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">
                {copy.label}
              </h2>
              <p className="mt-1.5 max-w-sm text-balance text-xs leading-relaxed text-zinc-500">
                {orbState === "error" && errorMessage ? errorMessage : copy.detail}
              </p>
            </div>

            <div className="pointer-events-none absolute inset-x-0 bottom-4 flex flex-col items-center gap-2 px-6 text-center">
              <div className="pointer-events-auto">
                <Button
                  size="lg"
                  variant={canRetry ? "danger" : "primary"}
                  onClick={handlePrimary}
                  disabled={active || loading.action}
                  loading={loading.action}
                  className="min-w-[232px]"
                >
                  {canRetry ? (
                    <>
                      <RotateCcw className="h-4 w-4" /> Retry session
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4" /> {active ? "Session running" : "Start debug session"}
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[10px] text-zinc-600">
                {active
                  ? "The existing pipeline is recording through ALSA. Keep speaking."
                  : `Or press ${status ? `${status.hotkey.modifiers}+${status.hotkey.key.toUpperCase()}` : "the global hotkey"} with the daemon running.`}
              </p>
            </div>
          </div>

          <div className="border-t border-white/[0.06] px-5 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-zinc-500">
              <span className="inline-flex items-center gap-1.5">
                <Mic className="h-3 w-3" aria-hidden />
                {orbState === "listening"
                  ? "Timed waveform · mic amplitude stays inside ALSA"
                  : orbState === "speaking"
                    ? "Real amplitude from generated speech"
                    : "Microphone idle"}
              </span>
              <span className="inline-flex items-center gap-1.5 font-mono">
                <GitBranch className="h-3 w-3" aria-hidden />
                {status?.branch ?? "—"}
              </span>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <Panel
            title="Session"
            subtitle={latest ? `Last activity ${formatRelativeTime(latest.updated_at)}` : "No sessions yet"}
            action={
              latest ? (
                <Badge tone={latest.status === "failed" ? "error" : "neutral"}>
                  {latest.status}
                </Badge>
              ) : null
            }
          >
            <div className="space-y-5">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="eyebrow">Pipeline</p>
                  <span className="text-[10px] text-zinc-600">{stageLabel(stage)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {STEPS.map((step, index) => {
                    const done = currentIndex >= 0 && index < currentIndex;
                    const current = index === currentIndex;
                    return (
                      <div
                        key={step}
                        className={cn(
                          "h-1.5 flex-1 rounded-full transition-colors duration-500",
                          current
                            ? "bg-duck-400 shadow-[0_0_10px_rgba(255,203,5,0.5)]"
                            : done
                              ? "bg-duck-400/45"
                              : "bg-white/[0.07]",
                        )}
                        title={stageLabel(step)}
                      />
                    );
                  })}
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-[11px]">
                  <div>
                    <p className="text-zinc-600">Project</p>
                    <p className="mt-0.5 truncate font-medium text-zinc-300">
                      {status?.project_name ?? "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-zinc-600">Branch</p>
                    <p className="mt-0.5 truncate font-mono text-zinc-300">
                      {status?.branch ?? "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-zinc-600">Hotkey</p>
                    <p className="mt-0.5 inline-flex items-center gap-1 truncate font-mono text-zinc-300">
                      <Keyboard className="h-3 w-3" aria-hidden />
                      {status ? `${status.hotkey.modifiers}+${status.hotkey.key.toUpperCase()}` : "—"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="panel-inset px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-wide text-zinc-600">Daemon</p>
                  <p className={cn("mt-1 flex items-center gap-1.5 text-xs", status?.daemon_running ? "text-emerald-300" : "text-zinc-400")}>
                    <Server className="h-3 w-3" aria-hidden />
                    {status?.daemon_running ? "Active" : "Not detected"}
                  </p>
                </div>
                <div className="panel-inset px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-wide text-zinc-600">Sessions</p>
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-zinc-300">
                    <Sparkles className="h-3 w-3 text-duck-300" aria-hidden />
                    {status?.session_count ?? 0} stored
                  </p>
                </div>
              </div>

              <PlaybackBar audio={audio} />
            </div>
          </Panel>

          <Panel
            title="Last diagnosis"
            subtitle={
              latest?.category
                ? `${CATEGORY_LABELS[latest.category] ?? latest.category} · ${formatRelativeTime(latest.updated_at)}`
                : "LAYA classification appears here"
            }
            action={
              latest ? (
                <Link
                  to="/sessions"
                  className="focus-ring inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-duck-200"
                >
                  Open <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              ) : null
            }
          >
            {loading.bootstrap ? (
              <div className="space-y-2">
                <Skeleton className="h-3 w-5/6" />
                <Skeleton className="h-3 w-4/6" />
                <Skeleton className="h-3 w-3/6" />
              </div>
            ) : latest?.diagnosis ? (
              <div className="space-y-3">
                <p className="line-clamp-6 whitespace-pre-wrap text-xs leading-relaxed text-zinc-300">
                  {latest.diagnosis}
                </p>
                {latest.spoken_response ? (
                  <div className="flex items-start gap-2 rounded-lg border border-duck-400/15 bg-duck-400/[0.05] px-3 py-2.5">
                    <Volume2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-duck-300/80" aria-hidden />
                    <p className="text-[11px] leading-relaxed text-duck-100/85">
                      {truncate(latest.spoken_response, 180)}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No diagnosis yet"
                description="Start a session and speak a bug. The first diagnosis will appear here."
                icon={<Sparkles className="h-4 w-4" />}
              />
            )}
          </Panel>

          <Panel
            title="Activity"
            subtitle="Live pipeline events from the bridge"
            action={
              <Link
                to="/logs"
                className="focus-ring inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-duck-200"
              >
                Logs <ArrowRight className="h-3 w-3" aria-hidden />
              </Link>
            }
          >
            <SessionTimeline
              entries={latest?.timeline ?? []}
              limit={5}
              emptyLabel="Waiting for a session"
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}
