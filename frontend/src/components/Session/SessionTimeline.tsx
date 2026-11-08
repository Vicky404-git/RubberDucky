import {
  AlertTriangle,
  AudioLines,
  BrainCircuit,
  GitBranch,
  Mic,
  Play,
  Radio,
  Volume2,
} from "lucide-react";
import { formatClock } from "../../lib/format";
import { cn } from "../../lib/cn";
import type { TimelineEntry } from "../../types/api";
import { EmptyState } from "../ui/States";

function iconFor(type: string) {
  if (type.startsWith("recording")) return Mic;
  if (type.startsWith("transcription") || type.startsWith("stt")) return AudioLines;
  if (type.startsWith("git")) return GitBranch;
  if (type.startsWith("triage")) return BrainCircuit;
  if (type.startsWith("llm")) return BrainCircuit;
  if (type.startsWith("tts")) return Volume2;
  if (type.startsWith("playback")) return Play;
  if (type.startsWith("session_failed")) return AlertTriangle;
  return Radio;
}

function toneFor(type: string): string {
  if (type === "session_failed") return "text-danger border-danger/25 bg-danger/10";
  if (type.includes("completed")) return "text-emerald-300 border-emerald-400/20 bg-emerald-400/[0.07]";
  if (type.includes("started")) return "text-duck-200 border-duck-400/25 bg-duck-400/[0.08]";
  return "text-zinc-400 border-white/[0.09] bg-white/[0.03]";
}

interface SessionTimelineProps {
  entries: TimelineEntry[];
  className?: string;
  limit?: number;
  emptyLabel?: string;
}

export function SessionTimeline({
  entries,
  className,
  limit,
  emptyLabel = "No activity yet.",
}: SessionTimelineProps) {
  const visible = limit ? entries.slice(-limit) : entries;

  if (visible.length === 0) {
    return <EmptyState title={emptyLabel} description="Start a debug session to see the pipeline live." />;
  }

  return (
    <ol className={cn("relative space-y-3", className)}>
      {visible.map((entry, index) => {
        const Icon = iconFor(entry.type);
        return (
          <li key={`${entry.timestamp}-${entry.type}-${index}`} className="flex gap-3">
            <span
              className={cn(
                "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
                toneFor(entry.type),
              )}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1 border-b border-white/[0.05] pb-3 last:border-0 last:pb-0">
              <p className="text-xs leading-relaxed text-zinc-300">{entry.message}</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-zinc-600">
                {formatClock(entry.timestamp)} · {entry.type.replaceAll("_", " ")}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
