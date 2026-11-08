import { describe, expect, it } from "vitest";
import type { BridgeEvent, SessionStatus } from "../types/api";
import { orbStateFromBackend, orbStateFromEvent, stageLabel } from "./orb";

describe("orbStateFromBackend", () => {
  const cases: Array<[SessionStatus, string]> = [
    ["idle", "idle"],
    ["listening", "listening"],
    ["processing", "processing"],
    ["speaking", "speaking"],
    ["completed", "idle"],
    ["failed", "error"],
  ];

  it.each(cases)("maps %s to %s", (status, expected) => {
    expect(orbStateFromBackend(status)).toBe(expected);
  });
});

describe("orbStateFromEvent", () => {
  const event = (type: string): BridgeEvent => ({ type, timestamp: 1 });

  it("enters listening for session and recording events", () => {
    expect(orbStateFromEvent(event("session_started"))).toBe("listening");
    expect(orbStateFromEvent(event("recording_started"))).toBe("listening");
  });

  it("stays processing across the pipeline", () => {
    for (const type of [
      "recording_completed",
      "transcription_started",
      "transcription_completed",
      "git_context_collected",
      "triage_started",
      "triage_completed",
      "llm_started",
      "llm_completed",
      "tts_started",
    ]) {
      expect(orbStateFromEvent(event(type))).toBe("processing");
    }
  });

  it("enters speaking when audio is ready", () => {
    for (const type of ["tts_completed", "playback_ready", "playback_started"]) {
      expect(orbStateFromEvent(event(type))).toBe("speaking");
    }
  });

  it("returns to idle after playback and errors on failure", () => {
    expect(orbStateFromEvent(event("playback_completed"))).toBe("idle");
    expect(orbStateFromEvent(event("session_failed"))).toBe("error");
  });

  it("ignores unrelated events", () => {
    expect(orbStateFromEvent(event("config_updated"))).toBeNull();
    expect(orbStateFromEvent(event("ignore_updated"))).toBeNull();
  });
});

describe("stageLabel", () => {
  it("uses friendly labels and humanises unknown stages", () => {
    expect(stageLabel("transcription")).toBe("Transcribing with Gnani Prisma");
    expect(stageLabel("docker_logs")).toBe("docker logs");
    expect(stageLabel(null)).toBe("Idle");
  });
});
