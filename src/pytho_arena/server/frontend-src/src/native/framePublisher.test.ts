import { afterEach, describe, expect, it, vi } from "vitest";

import type { ArenaSceneState } from "../arena";
import { FRAME_V1_LOOPBACK_URL, FrameV1Publisher } from "./framePublisher";

class MemorySocket {
  readyState: number = WebSocket.CONNECTING;
  bufferedAmount = 0;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  messages: string[] = [];

  open(): void {
    this.readyState = WebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  send(payload: string): void { this.messages.push(payload); }

  close(): void { this.readyState = WebSocket.CLOSED; }
}

function scene(): ArenaSceneState {
  return {
    step: 0,
    simTimeSec: 12,
    coordinateFrame: "ENU",
    metersPerWorldUnit: 10,
    originWorld: [50, 50],
    truthEntities: [{
      id: "red-1",
      factionId: "red",
      groupId: "red-strike",
      assetId: "uav_orion",
      entityClass: "fixed-wing",
      positionM: { east: 4, up: 120, north: 6 },
      velocityMps: { east: 10, up: 0, north: 0 },
      attitudeDeg: { heading: 90, pitch: 0, roll: 0 },
      status: "active",
      active: true,
      detected: true,
      enteredZone: false,
    }],
    rawDetections: [],
    sensors: [],
    responses: [],
    tracks: [],
    decisions: [],
    events: [],
  };
}

afterEach(() => vi.useRealTimers());

describe("frame-v1 publisher", () => {
  it("connects only to the fixed loopback URL and publishes at 20 Hz", () => {
    vi.useFakeTimers();
    const socket = new MemorySocket();
    let requestedUrl = "";
    const publisher = new FrameV1Publisher((url) => {
      requestedUrl = url;
      return socket;
    });
    publisher.setFrame("run-1", scene());
    publisher.start();
    socket.open();
    vi.advanceTimersByTime(200);

    expect(requestedUrl).toBe(FRAME_V1_LOOPBACK_URL);
    expect(socket.messages).toHaveLength(5);
    expect(socket.messages.map((message) => JSON.parse(message).sequence)).toEqual([0, 1, 2, 3, 4]);
    publisher.stop();
  });

  it("publishes a scrub frame immediately and resets sequence for a new run", () => {
    const socket = new MemorySocket();
    const publisher = new FrameV1Publisher(() => socket);
    publisher.start();
    socket.open();
    socket.messages.length = 0;
    publisher.setFrame("run-a", scene(), true);
    publisher.setFrame("run-a", { ...scene(), simTimeSec: 40 }, true);
    publisher.setFrame("run-b", scene(), true);

    expect(socket.messages.map((message) => {
      const frame = JSON.parse(message);
      return [frame.runId, frame.sequence, frame.simTimeSec];
    })).toEqual([
      ["run-a", 0, 12],
      ["run-a", 1, 40],
      ["run-b", 0, 12],
    ]);
    publisher.stop();
  });

  it("skips a backed-up socket and reports overflow including sensors and responses", () => {
    const socket = new MemorySocket();
    const errors: string[] = [];
    const publisher = new FrameV1Publisher(() => socket, () => undefined, (message) => {
      if (message) errors.push(message);
    });
    publisher.start();
    socket.open();
    socket.messages.length = 0;
    socket.bufferedAmount = 2_000_000;
    publisher.setFrame("run-buffered", scene(), true);
    expect(socket.messages).toHaveLength(0);

    socket.bufferedAmount = 0;
    const base = scene();
    publisher.setFrame("run-overflow", {
      ...base,
      truthEntities: Array.from({ length: 1_999 }, (_, index) => ({
        ...base.truthEntities[0],
        id: `truth-${index}`,
      })),
      sensors: [{
        id: "sensor-1",
        factionId: "blue",
        assetId: "range_watch_tower",
        positionM: { east: 0, up: 0, north: 0 },
        rangeM: 100,
        fovDegrees: 90,
        attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
      }],
      responses: [{
        id: "response-1",
        factionId: "blue",
        assetId: "nasams_fcs",
        positionM: { east: 0, up: 0, north: 0 },
        engagementRangeM: 100,
      }],
    }, true);
    expect(errors.at(-1)).toContain("received 2001");
    expect(socket.messages).toHaveLength(0);
    publisher.stop();
  });
});
