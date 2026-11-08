import { describe, expect, it } from "vitest";
import { getAudioLevel, setAudioLevel } from "./audioLevel";

describe("audioLevel", () => {
  it("clamps values to a 0..1 range", () => {
    setAudioLevel(0.42);
    expect(getAudioLevel()).toBe(0.42);

    setAudioLevel(4);
    expect(getAudioLevel()).toBe(1);

    setAudioLevel(-2);
    expect(getAudioLevel()).toBe(0);
  });
});
