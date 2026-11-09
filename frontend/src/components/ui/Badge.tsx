import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Tone = "duck" | "active" | "success" | "error" | "neutral" | "info";

const TONES: Record<Tone, string> = {
  duck: "border-duck-400/30 bg-duck-400/10 text-duck-200",
  active: "border-duck-400/30 bg-duck-400/10 text-duck-200",
  success: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  error: "border-danger/30 bg-danger/10 text-danger",
  neutral: "border-white/[0.09] bg-white/[0.04] text-zinc-400",
  info: "border-sky-400/25 bg-sky-400/10 text-sky-300",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
}

export function Badge({ tone = "neutral", dot = false, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-5",
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden /> : null}
      {children}
    </span>
  );
}
