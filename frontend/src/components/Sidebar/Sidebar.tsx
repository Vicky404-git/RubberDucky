import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  AudioWaveform,
  GitBranch,
  Gauge,
  Menu,
  MessagesSquare,
  ScrollText,
  Settings,
  ShieldOff,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/cn";
import { useAppStore } from "../../stores/appStore";

const NAV: ReadonlyArray<{ to: string; label: string; icon: LucideIcon; end?: boolean }> = [
  { to: "/", label: "Overview", icon: Gauge, end: true },
  { to: "/sessions", label: "Debug Sessions", icon: MessagesSquare },
  { to: "/git", label: "Git Context", icon: GitBranch },
  { to: "/ignore", label: "Ignore Manager", icon: ShieldOff },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/logs", label: "Logs", icon: ScrollText },
];

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex h-9 w-9 items-center justify-center rounded-full border border-duck-400/25 bg-ink-900 shadow-glow-sm">
        <span className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_35%_30%,rgba(255,233,122,0.55),rgba(255,180,60,0.08)_58%,transparent_72%)]" />
        <span className="relative h-3.5 w-3.5 rounded-full bg-duck-gradient shadow-[0_0_14px_rgba(255,203,5,0.7)]" />
      </div>
      {!compact ? (
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-zinc-100">RubberDucky</p>
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-600">Voice debugger</p>
        </div>
      ) : null}
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-1" aria-label="Primary">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "focus-ring group flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-all duration-200",
              isActive
                ? "border-duck-400/20 bg-duck-400/[0.08] text-duck-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                : "border-transparent text-zinc-500 hover:border-white/[0.06] hover:bg-white/[0.035] hover:text-zinc-200",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors",
                  isActive ? "text-duck-300" : "text-zinc-600 group-hover:text-zinc-400",
                )}
                aria-hidden
              />
              <span className="font-medium">{label}</span>
              {isActive ? (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-duck-400 shadow-[0_0_8px_rgba(255,203,5,0.8)]" />
              ) : null}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function RuntimeStatus() {
  const connection = useAppStore((state) => state.connection);
  const status = useAppStore((state) => state.status);
  const health = useAppStore((state) => state.health);

  const online = connection === "online";
  return (
    <div className="space-y-2.5 rounded-xl border border-white/[0.06] bg-black/20 p-3">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-500">Bridge</span>
        <span className={cn("flex items-center gap-1.5", online ? "text-emerald-300" : "text-danger")}>
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              online ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" : "bg-danger",
            )}
          />
          {connection === "connecting" ? "Connecting" : online ? "Online" : "Offline"}
        </span>
      </div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-500">Hotkey daemon</span>
        <span className={status?.daemon_running ? "text-emerald-300" : "text-zinc-500"}>
          {status?.daemon_running ? "Active" : "Not detected"}
        </span>
      </div>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-500">Credentials</span>
        <span className={cn(health?.has_gnani_key && health?.has_openrouter_key ? "text-zinc-300" : "text-amber-glow")}>
          {health?.has_gnani_key && health?.has_openrouter_key ? "Ready" : "Incomplete"}
        </span>
      </div>
      {status ? (
        <div className="flex items-center gap-2 border-t border-white/[0.06] pt-2.5 text-[11px] text-zinc-500">
          <GitBranch className="h-3 w-3" aria-hidden />
          <span className="truncate font-mono text-zinc-400">{status.branch}</span>
        </div>
      ) : null}
    </div>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);
  const status = useAppStore((state) => state.status);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-white/[0.07] bg-ink-950/85 px-4 backdrop-blur-xl lg:hidden">
        <BrandMark />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="focus-ring flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] text-zinc-400"
          aria-label="Open navigation"
        >
          <Menu className="h-4 w-4" />
        </button>
      </header>

      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[280px] flex-col border-r border-white/[0.08] bg-ink-950 p-4">
            <div className="mb-6 flex items-center justify-between">
              <BrandMark />
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="focus-ring flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 hover:bg-white/[0.05]"
                aria-label="Close navigation"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <NavItems onNavigate={() => setOpen(false)} />
            <div className="mt-auto pt-4">
              <RuntimeStatus />
            </div>
          </aside>
        </div>
      ) : null}

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] flex-col border-r border-white/[0.07] bg-ink-950/60 px-4 py-5 backdrop-blur-xl lg:flex">
        <div className="px-2">
          <BrandMark />
        </div>

        <div className="mt-8 flex-1 overflow-y-auto">
          <p className="eyebrow mb-3 px-3">Workspace</p>
          <NavItems />
          <div className="mt-6 rounded-xl border border-white/[0.06] bg-white/[0.018] p-3">
            <div className="flex items-center gap-2">
              <AudioWaveform className="h-3.5 w-3.5 text-duck-300/80" aria-hidden />
              <p className="text-[11px] font-medium text-zinc-300">Voice pipeline</p>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-600">
              Prisma STT · LAYA · OpenRouter · Timbre TTS
            </p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          <RuntimeStatus />
          <p className="px-1 text-[10px] leading-relaxed text-zinc-700">
            {status?.project_name ?? "RubberDucky"} · local bridge · 127.0.0.1
          </p>
        </div>
      </aside>

      <div className="h-16 lg:hidden" aria-hidden />
    </>
  );
}
