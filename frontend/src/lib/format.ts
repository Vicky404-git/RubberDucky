import type { SessionStatus } from "../types/api";

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatRelativeTime(timestamp: number, now = Date.now()): string {
  const seconds = Math.round((timestamp * 1000 - now) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 45) return "just now";
  if (absolute < 3600) return RELATIVE.format(Math.round(seconds / 60), "minute");
  if (absolute < 86400) return RELATIVE.format(Math.round(seconds / 3600), "hour");
  return RELATIVE.format(Math.round(seconds / 86400), "day");
}

export function formatTimestamp(timestamp: number): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp * 1000));
}

export function formatClock(timestamp: number): string {
  return new Intl.DateTimeFormat("en", { timeStyle: "medium" }).format(
    new Date(timestamp * 1000),
  );
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || ms <= 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function truncate(value: string | null | undefined, limit = 140): string {
  if (!value) return "";
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > limit ? `${normalized.slice(0, limit - 1)}…` : normalized;
}

export function statusTone(status: SessionStatus): "idle" | "active" | "success" | "error" {
  if (status === "listening" || status === "processing" || status === "speaking") {
    return "active";
  }
  if (status === "failed") return "error";
  if (status === "completed") return "success";
  return "idle";
}

export function statusLabel(status: SessionStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function levelTone(level: string): "debug" | "info" | "warn" | "error" {
  const normalized = level.toUpperCase();
  if (normalized === "DEBUG") return "debug";
  if (normalized === "WARNING" || normalized === "WARN") return "warn";
  if (normalized === "ERROR" || normalized === "CRITICAL") return "error";
  return "info";
}
