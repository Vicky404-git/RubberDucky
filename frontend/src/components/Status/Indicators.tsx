import { useEffect, useRef } from "react";
import { getAudioLevel } from "../../lib/audioLevel";
import { ORB_COPY, type OrbState } from "../../lib/orb";
import { cn } from "../../lib/cn";
import { useAppStore } from "../../stores/appStore";
import { Badge } from "../ui/Badge";

const BAR_WEIGHTS = [0.5, 0.78, 0.62, 0.92, 0.7, 1, 0.66, 0.84, 0.56];

interface ActivityMeterProps {
  mode: "idle" | "listening" | "speaking";
  className?: string;
  bars?: number;
}

export function ActivityMeter({ mode, className, bars = 9 }: ActivityMeterProps) {
  const refs = useRef<Array<HTMLSpanElement | null>>([]);

  useEffect(() => {
    if (mode !== "speaking") {
      for (const bar of refs.current) {
        if (bar) bar.style.transform = "";
      }
      return;
    }
    let frame = 0;
    const loop = () => {
      const level = getAudioLevel();
      refs.current.forEach((bar, index) => {
        if (!bar) return;
        const weight = BAR_WEIGHTS[index % BAR_WEIGHTS.length] ?? 0.6;
        const value = 0.16 + Math.min(1, level * weight * 1.35) * 0.84;
        bar.style.transform = `scaleY(${value.toFixed(3)})`;
      });
      frame = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(frame);
  }, [mode]);

  return (
    <div
      className={cn("flex h-8 items-center gap-[3px]", className)}
      aria-label={mode === "speaking" ? "Audio level from generated speech" : "Microphone activity indicator"}
      role="img"
    >
      {Array.from({ length: bars }).map((_, index) => {
        const weight = BAR_WEIGHTS[index % BAR_WEIGHTS.length] ?? 0.6;
        return (
          <span
            key={index}
            ref={(element) => {
              refs.current[index] = element;
            }}
            className={cn(
              "w-[3px] origin-center rounded-full transition-transform duration-75",
              mode === "idle"
                ? "bg-zinc-700"
                : mode === "listening"
                  ? "animate-pulse-soft bg-duck-300/90"
                  : "bg-duck-300",
            )}
            style={{
              height: `${Math.round(8 + weight * 18)}px`,
              transform: mode === "idle" ? `scaleY(${0.28 + weight * 0.2})` : undefined,
              animationDelay: mode === "listening" ? `${index * 90}ms` : undefined,
              animationDuration: mode === "listening" ? `${900 + index * 70}ms` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}

export function OrbStatusPill({ state }: { state: OrbState }) {
  const copy = ORB_COPY[state];
  const tone =
    state === "error" ? "error" : state === "idle" ? "neutral" : "duck";
  return (
    <Badge tone={tone} dot className={cn(state !== "idle" && "uppercase tracking-wide")}>
      {copy.label}
    </Badge>
  );
}

export function ConnectionPill() {
  const connection = useAppStore((state) => state.connection);
  if (connection === "online") {
    return (
      <Badge tone="success" dot>
        Bridge online
      </Badge>
    );
  }
  if (connection === "connecting") {
    return (
      <Badge tone="neutral" dot>
        Connecting…
      </Badge>
    );
  }
  return (
    <Badge tone="error" dot>
      Bridge offline
    </Badge>
  );
}

export function CredentialDot({ label, ready }: { label: string; ready: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          ready ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" : "bg-amber-glow",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}
