import { ChevronRight, GitBranch, Mic2 } from "lucide-react";
import { CATEGORY_LABELS } from "../../lib/orb";
import { formatRelativeTime, statusLabel, statusTone, truncate } from "../../lib/format";
import { cn } from "../../lib/cn";
import type { SessionRecord } from "../../types/api";
import { Badge } from "../ui/Badge";

interface SessionCardProps {
  session: SessionRecord;
  selected: boolean;
  onSelect: (session: SessionRecord) => void;
}

export function SessionCard({ session, selected, onSelect }: SessionCardProps) {
  const tone = statusTone(session.status);
  return (
    <button
      type="button"
      onClick={() => onSelect(session)}
      aria-pressed={selected}
      className={cn(
        "focus-ring group w-full rounded-xl border px-4 py-3 text-left transition-all duration-200",
        selected
          ? "border-duck-400/25 bg-duck-400/[0.07]"
          : "border-white/[0.07] bg-white/[0.018] hover:border-white/[0.12] hover:bg-white/[0.035]",
      )}
    >
      <div className="flex items-center gap-2">
        <Badge
          tone={tone === "active" ? "duck" : tone === "error" ? "error" : tone === "success" ? "success" : "neutral"}
          dot
        >
          {statusLabel(session.status)}
        </Badge>
        <span className="ml-auto text-[11px] text-zinc-600">
          {formatRelativeTime(session.updated_at)}
        </span>
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 transition-transform",
            selected ? "text-duck-300" : "text-zinc-700 group-hover:translate-x-0.5",
          )}
          aria-hidden
        />
      </div>

      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-300">
        {session.transcript ? truncate(session.transcript, 150) : "Transcript pending…"}
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-zinc-600">
        <span className="inline-flex items-center gap-1">
          <Mic2 className="h-3 w-3" aria-hidden />
          {session.category ? (CATEGORY_LABELS[session.category] ?? session.category) : "Unclassified"}
        </span>
        <span className="inline-flex min-w-0 items-center gap-1">
          <GitBranch className="h-3 w-3 shrink-0" aria-hidden />
          <span className="truncate font-mono">{session.git_branch ?? "no branch"}</span>
        </span>
      </div>
    </button>
  );
}
