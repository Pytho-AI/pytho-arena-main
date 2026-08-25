import { describe, expect, it } from "vitest";

import { playbackStartFrame } from "./playback";

describe("playback", () => {
  it("restarts at frame zero when Play is pressed at the end", () => {
    expect(playbackStartFrame(120, 120)).toBe(0);
    expect(playbackStartFrame(80, 120)).toBe(80);
  });
});
