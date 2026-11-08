import { useEffect } from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "../../lib/cn";
import { useAppStore } from "../../stores/appStore";

export function NoticeToast() {
  const notice = useAppStore((state) => state.notice);
  const clearNotice = useAppStore((state) => state.clearNotice);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(clearNotice, 5200);
    return () => window.clearTimeout(timer);
  }, [notice, clearNotice]);

  if (!notice) return null;

  const Icon =
    notice.kind === "success" ? CheckCircle2 : notice.kind === "error" ? XCircle : Info;

  return (
    <div
      role="status"
      className="fixed bottom-5 left-1/2 z-[60] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 animate-fade-up"
    >
      <div
        className={cn(
          "flex items-start gap-3 rounded-xl border bg-ink-900/95 px-4 py-3 shadow-glass backdrop-blur-xl",
          notice.kind === "success"
            ? "border-emerald-400/25 text-emerald-200"
            : notice.kind === "error"
              ? "border-danger/30 text-danger"
              : "border-duck-400/25 text-duck-100",
        )}
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p className="flex-1 text-xs leading-relaxed">{notice.message}</p>
        <button
          type="button"
          onClick={clearNotice}
          className="focus-ring rounded text-[11px] text-zinc-500 hover:text-zinc-200"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
