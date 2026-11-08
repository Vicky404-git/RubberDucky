import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileDiff } from "lucide-react";
import { cn } from "../../lib/cn";
import { EmptyState } from "../ui/States";

interface DiffViewerProps {
  title: string;
  diff: string;
  emptyHint: string;
  defaultOpen?: boolean;
}

function lineTone(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff --git")) {
    return "text-zinc-500";
  }
  if (line.startsWith("@@")) return "text-sky-300/80";
  if (line.startsWith("+")) return "text-emerald-300/90";
  if (line.startsWith("-")) return "text-danger/80";
  return "text-zinc-400";
}

export function DiffViewer({ title, diff, emptyHint, defaultOpen = false }: DiffViewerProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isEmpty = !diff || diff.startsWith("No ") || diff.trim().length === 0;
  const lines = useMemo(() => (isEmpty ? [] : diff.split("\n")), [diff, isEmpty]);

  return (
    <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-black/25">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="focus-ring flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
        )}
        <FileDiff className="h-3.5 w-3.5 text-duck-300/70" aria-hidden />
        <span className="text-xs font-medium text-zinc-300">{title}</span>
        <span className="ml-auto text-[10px] text-zinc-600">
          {isEmpty ? "clean" : `${lines.length} lines · redacted`}
        </span>
      </button>
      {open ? (
        isEmpty ? (
          <div className="border-t border-white/[0.06] p-4">
            <EmptyState title={emptyHint} className="border-0 py-6" />
          </div>
        ) : (
          <pre className="max-h-[420px] overflow-auto border-t border-white/[0.06] p-4 font-mono text-[11px] leading-relaxed">
            {lines.map((line, index) => (
              <div key={index} className={cn("whitespace-pre", lineTone(line))}>
                {line || " "}
              </div>
            ))}
          </pre>
        )
      ) : null}
    </div>
  );
}
