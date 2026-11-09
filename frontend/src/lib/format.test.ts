import { describe, expect, it } from "vitest";
import {
  formatDuration,
  formatRelativeTime,
  levelTone,
  statusLabel,
  statusTone,
  truncate,
} from "./format";

describe("formatRelativeTime", () => {
  const now = Date.UTC(2026, 0, 1, 12, 0, 0);

  it("accepts second-based timestamps", () => {
    expect(formatRelativeTime(now / 1000 - 10, now)).toBe("just now");
  });

  it("formats minutes, hours and days", () => {
    expect(formatRelativeTime(now / 1000 - 120, now)).toBe("2 minutes ago");
    expect(formatRelativeTime(now / 1000 - 7200, now)).toBe("2 hours ago");
    expect(formatRelativeTime(now / 1000 - 2 * 86400, now)).toBe("2 days ago");
  });
});

describe("formatDuration", () => {
  it("handles missing and sub-second durations", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(0)).toBe("—");
    expect(formatDuration(450)).toBe("450 ms");
  });

  it("formats seconds with one decimal", () => {
    expect(formatDuration(1500)).toBe("1.5 s");
  });
});

describe("truncate", () => {
  it("normalises whitespace and ellipsises long values", () => {
    expect(truncate("  hello\n\nworld  ")).toBe("hello world");
    expect(truncate("abcdefghij", 5)).toBe("abcd…");
    expect(truncate(null)).toBe("");
  });
});

describe("status helpers", () => {
  it("maps statuses to tones", () => {
    expect(statusTone("listening")).toBe("active");
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("failed")).toBe("error");
    expect(statusTone("idle")).toBe("idle");
    expect(statusLabel("processing")).toBe("Processing");
  });

  it("maps log levels defensively", () => {
    expect(levelTone("DEBUG")).toBe("debug");
    expect(levelTone("warn")).toBe("warn");
    expect(levelTone("CRITICAL")).toBe("error");
    expect(levelTone("INFO")).toBe("info");
    expect(levelTone("anything")).toBe("info");
  });
});
