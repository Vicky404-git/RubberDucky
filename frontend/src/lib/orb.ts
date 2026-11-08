import type { BridgeEvent, SessionStatus } from "../types/api";

export type OrbState = "idle" | "listening" | "processing" | "speaking" | "error";

export interface OrbCopy {
  label: string;
  detail: string;
}

export const ORB_COPY: Record<OrbState, OrbCopy> = {
  idle: {
    label: "Idle",
    detail: "Ready when you are. Start a voice debug session.",
  },
  listening: {
    label: "Listening...",
    detail: "Speak your bug in Hinglish. Recording through ALSA.",
  },
  processing: {
    label: "Processing",
    detail: "Transcribing, triaging and gathering context.",
  },
  speaking: {
    label: "Speaking",
    detail: "Playing the generated Hinglish response.",
  },
  error: {
    label: "Needs attention",
    detail: "The last session did not complete. Retry when ready.",
  },
};

export const STAGE_LABELS: Record<string, string> = {
  idle: "Idle",
  recording: "Recording microphone",
  transcription: "Transcribing with Gnani Prisma",
  triage: "Running LAYA triage",
  git: "Collecting Git context",
  llm: "Diagnosing with OpenRouter",
  tts: "Synthesizing with Gnani Timbre",
  playback: "Playing response",
};

export function orbStateFromBackend(state: SessionStatus): OrbState {
  if (state === "listening") return "listening";
  if (state === "processing") return "processing";
  if (state === "speaking") return "speaking";
  if (state === "failed") return "error";
  return "idle";
}

export function orbStateFromEvent(event: BridgeEvent): OrbState | null {
  switch (event.type) {
    case "session_started":
    case "recording_started":
      return "listening";
    case "recording_completed":
    case "transcription_started":
    case "transcription_completed":
    case "git_context_collected":
    case "triage_started":
    case "triage_completed":
    case "docker_logs_started":
    case "docker_logs_completed":
    case "llm_started":
    case "llm_completed":
    case "tts_started":
    case "tts_completed":
    case "playback_ready":
    case "playback_started":
      return event.type === "tts_completed" || event.type === "playback_ready" || event.type === "playback_started"
        ? "speaking"
        : "processing";
    case "session_failed":
      return "error";
    case "playback_completed":
      return "idle";
    default:
      return null;
  }
}

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return STAGE_LABELS.idle ?? "Idle";
  return STAGE_LABELS[stage] ?? stage.replaceAll("_", " ");
}

export const CATEGORY_LABELS: Record<string, string> = {
  infrastructure: "Infrastructure",
  git_issue: "Git / repository",
  syntax_error: "Syntax error",
  logic_bug: "Logic bug",
  unknown: "Unclassified",
};
