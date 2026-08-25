import { describe, expect, it } from "vitest";

import {
  adaptArenaReplayFrame,
  attitudeFromQuaternion,
  headingFromVelocity,
  sceneStateToFrameV1,
} from "./replayAdapter";
import type {
  ArenaDecisionRequest,
  ArenaReplayFrame,
  ArenaSceneManifest,
  ArenaTrack,
  ArenaTruthEntity,
} from "./types";

const manifest: ArenaSceneManifest = {
  metersPerWorldUnit: 100,
  originWorld: [50, 50],
  groups: {
    "red-strike": { assetId: "uav_orion", altitudeM: 1_200 },
    "neutral-traffic": { assetId: "cargo_ship_liberty", altitudeM: 0 },
  },
  sensor: { assetId: "range_watch_tower", altitudeM: 4 },
  response: { assetId: "nasams_fcs", altitudeM: 2 },
};

function truth(overrides: Partial<ArenaTruthEntity> = {}): ArenaTruthEntity {
  return {
    id: "red-strike-01",
    factionId: "red",
    groupId: "red-strike",
    position: [51, 48],
    velocity: [2, 0],
    active: true,
    status: "active",
    detected: true,
    enteredZone: false,
    ...overrides,
  };
}

function track(overrides: Partial<ArenaTrack> = {}): ArenaTrack {
  return {
    trackId: "track-001",
    position: [51, 48],
    velocity: [2, 0],
    classification: "hostile",
    confidence: 0.88,
    ageSeconds: 0.5,
    sourceSensorIds: ["sensor-north"],
    evidenceReportIds: ["sensor-north-00007-track-001"],
    requestId: "roe-001",
    disposition: null,
    ...overrides,
  };
}

function decision(overrides: Partial<ArenaDecisionRequest> = {}): ArenaDecisionRequest {
  return {
    requestId: "roe-001",
    trackId: "track-001",
    effectorId: "blue-response-alpha",
    rationale: "track-001 closed on blue-response-alpha for 2 consecutive updates",
    step: 7,
    timeSeconds: 3.5,
    classification: "hostile",
    disposition: null,
    decisionId: null,
    decisionStep: null,
    pending: true,
    ...overrides,
  };
}

function replayFrame(entity: ArenaTruthEntity = truth()): ArenaReplayFrame {
  return {
    step: 7,
    time: 3.5,
    truth: [entity],
    detections: [{ sensorId: "sensor-north", entityId: entity.id, position: [50.5, 48.5] }],
    sensors: [{
      id: "sensor-north",
      factionId: "blue",
      position: [46, 66],
      range: 50,
      fovDegrees: 115,
      headingRadians: 0,
    }],
    responses: [{
      id: "blue-response-alpha",
      factionId: "blue",
      position: [70, 50],
      engagementRange: 32,
    }],
    events: { intercepts: [], attacks: [] },
  };
}

describe("Arena replay adapter", () => {
  it("centers world coordinates and applies explicit meter and altitude mappings", () => {
    const scene = adaptArenaReplayFrame(replayFrame(), manifest);

    expect(scene.truthEntities[0].positionM).toEqual({ east: 100, up: 1_200, north: -200 });
    expect(scene.truthEntities[0].velocityMps).toEqual({ east: 200, up: 0, north: 0 });
    expect(scene.sensors[0].positionM).toEqual({ east: -400, up: 4, north: 1_600 });
    expect(scene.sensors[0].rangeM).toBe(5_000);
    expect(scene.responses[0].engagementRangeM).toBe(3_200);
  });

  it("uses north=0 and east=90 headings derived from velocity", () => {
    expect(headingFromVelocity([0, 1])).toBe(0);
    expect(headingFromVelocity([1, 0])).toBe(90);
    expect(headingFromVelocity([0, -1])).toBe(180);
    expect(headingFromVelocity([-1, 0])).toBe(270);
    expect(headingFromVelocity([0, 0])).toBe(0);
  });

  it("uses simulated altitude, vertical velocity, and quaternion attitude", () => {
    const halfRollRadians = Math.PI / 12;
    const entity = truth({
      position: [51, 48, 15],
      velocity: [2, 0, 1],
      orientationWxyz: [Math.cos(halfRollRadians), Math.sin(halfRollRadians), 0, 0],
    });
    const scene = adaptArenaReplayFrame(replayFrame(entity), manifest);

    expect(scene.truthEntities[0].positionM).toEqual({ east: 100, up: 1_500, north: -200 });
    expect(scene.truthEntities[0].velocityMps).toEqual({ east: 200, up: 100, north: 0 });
    expect(scene.truthEntities[0].attitudeDeg.heading).toBeCloseTo(90, 8);
    expect(scene.truthEntities[0].attitudeDeg.pitch).toBeCloseTo(0, 8);
    expect(scene.truthEntities[0].attitudeDeg.roll).toBeCloseTo(30, 8);
    const nativeEntity = sceneStateToFrameV1("run-3d", 7, scene).entities.find(
      (item) => item.id === entity.id,
    );
    expect(nativeEntity?.attitudeDeg.roll).toBeCloseTo(30, 8);
  });

  it("rejects a zero quaternion", () => {
    expect(() => attitudeFromQuaternion([0, 0, 0, 0])).toThrow("nonzero norm");
  });

  it.each([
    ["active", "active"],
    ["intercepted", "neutralized"],
    ["attack-succeeded", "penetrated"],
    ["attack-failed", "complete"],
    ["inactive", "offline"],
  ] as const)("maps Arena status %s to frame-v1 status %s", (source, expected) => {
    const scene = adaptArenaReplayFrame(replayFrame(truth({ status: source })), manifest);
    expect(scene.truthEntities[0].status).toBe(expected);
  });

  it("keeps truth and raw detections separate and never promotes measurements to tracks", () => {
    const scene = adaptArenaReplayFrame(replayFrame(), manifest);

    expect(scene.truthEntities[0].positionM).toEqual({ east: 100, up: 1_200, north: -200 });
    expect(scene.rawDetections[0]).toEqual({
      sensorId: "sensor-north",
      truthEntityId: "red-strike-01",
      positionM: { east: 50, up: 1_200, north: -150 },
    });
    expect(scene.tracks).toEqual([]);

    const native = sceneStateToFrameV1("run-1", 9, scene);
    expect(native.tracks).toEqual([]);
    expect(native).not.toHaveProperty("rawDetections");
  });

  it("uses only manifest assets from the fixed allowlist", () => {
    const unsupported = {
      ...manifest,
      groups: { "red-strike": { assetId: "remote_url_model", altitudeM: 1_200 } },
    } as unknown as ArenaSceneManifest;

    expect(() => adaptArenaReplayFrame(replayFrame(), unsupported)).toThrow(
      "unsupported asset: remote_url_model",
    );
    expect(() => adaptArenaReplayFrame(replayFrame(), {
      ...manifest,
      sensor: { assetId: "uav_orion", altitudeM: 0 },
    })).toThrow("sensor manifest asset must have entity class sensor");
  });

  it("requires an explicit mapping for every replay group", () => {
    const unknownGroup = replayFrame(truth({ groupId: "unmapped-group" }));
    expect(() => adaptArenaReplayFrame(unknownGroup, manifest)).toThrow(
      "scene manifest has no mapping for group: unmapped-group",
    );
  });

  it("accepts 2,000 total frame entities and rejects 2,001 with the received count", () => {
    const entities = Array.from({ length: 1_998 }, (_, index) => truth({
      id: `red-strike-${String(index + 1).padStart(4, "0")}`,
    }));
    const frame = { ...replayFrame(), truth: entities, detections: [] };
    const scene = adaptArenaReplayFrame(frame, manifest);
    expect(sceneStateToFrameV1("run-1", 0, scene).entities).toHaveLength(2_000);

    const overflow = adaptArenaReplayFrame({
      ...frame,
      truth: [...entities, truth({ id: "red-strike-overflow" })],
    }, manifest);
    expect(() => sceneStateToFrameV1("run-1", 1, overflow)).toThrow(
      "frame-v1 supports at most 2000 entities; received 2001",
    );
  });

  it("rejects duplicate IDs across truth and scenario entities", () => {
    const collision = replayFrame(truth({ id: "sensor-north" }));
    const scene = adaptArenaReplayFrame(collision, manifest);
    expect(() => sceneStateToFrameV1("run-1", 0, scene)).toThrow(
      "duplicate frame-v1 entity id: sensor-north",
    );
  });

  it("places fused tracks on the ground plane and keeps them free of truth identity", () => {
    const scene = adaptArenaReplayFrame(
      { ...replayFrame(), tracks: [track()], decisions: [decision()] },
      manifest,
    );

    expect(scene.tracks).toHaveLength(1);
    expect(scene.tracks[0].id).toBe("track-001");
    expect(scene.tracks[0].positionM).toEqual({ east: 100, up: 0, north: -200 });
    expect(scene.tracks[0].classification).toBe("hostile");
    expect(JSON.stringify(scene.tracks[0])).not.toContain("red-strike-01");
    expect(scene.decisions[0].requestId).toBe("roe-001");
  });

  it("treats a replay without counter-UAS data as a frame with no tracks", () => {
    const scene = adaptArenaReplayFrame(replayFrame(), manifest);
    expect(scene.tracks).toEqual([]);
    expect(scene.decisions).toEqual([]);
    expect(sceneStateToFrameV1("run-1", 0, scene).tracks).toEqual([]);
  });

  it("publishes tracks on the wire with only id, position, and confidence", () => {
    const scene = adaptArenaReplayFrame({ ...replayFrame(), tracks: [track()] }, manifest);
    expect(sceneStateToFrameV1("run-1", 0, scene).tracks).toEqual([
      { id: "track-001", positionM: { east: 100, up: 0, north: -200 }, confidence: 0.88 },
    ]);
  });

  it("counts entities, tracks, and effects against one 2,000 item render budget", () => {
    const entities = Array.from({ length: 1_990 }, (_, index) => truth({
      id: `red-strike-${String(index + 1).padStart(4, "0")}`,
    }));
    const tracks = Array.from({ length: 8 }, (_, index) => track({
      trackId: `track-${String(index + 1).padStart(3, "0")}`,
    }));
    const withinBudget = adaptArenaReplayFrame(
      { ...replayFrame(), truth: entities, detections: [], tracks },
      manifest,
    );
    expect(sceneStateToFrameV1("run-1", 0, withinBudget).tracks).toHaveLength(8);

    const overflow = adaptArenaReplayFrame(
      {
        ...replayFrame(),
        truth: entities,
        detections: [],
        tracks: [...tracks, track({ trackId: "track-009" })],
      },
      manifest,
    );
    expect(() => sceneStateToFrameV1("run-1", 1, overflow)).toThrow(
      "frame-v1 supports at most 2000 rendered items; received 2001 (entities + tracks + effects)",
    );
  });
});
