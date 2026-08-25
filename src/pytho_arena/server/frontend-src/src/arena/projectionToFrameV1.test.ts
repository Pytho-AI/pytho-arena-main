import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { create, fromBinary } from "@bufbuild/protobuf";
import { describe, expect, it } from "vitest";

import { CommandEnvelopeSchema } from "../contracts/pytho/sim/v1/commands_pb";
import {
  ProjectionFrameSchema,
  type ProjectionFrame,
} from "../contracts/pytho/sim/v1/projection_pb";
import { EntityStateSchema } from "../contracts/pytho/sim/v1/state_pb";
import { resolveSceneManifest } from "../scene/sceneManifest";
import { projectionToFrameV1 } from "./projectionToFrameV1";
import { adaptArenaReplayFrame, sceneStateToFrameV1 } from "./replayAdapter";
import type { ArenaReplayFrame, ArenaSceneState, NativeFrameV1 } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../../../../../..");
const CONTRACT_FIXTURES = resolve(REPO_ROOT, "contracts-import/fixtures");

const ravenFixture = JSON.parse(
  readFileSync(resolve(HERE, "__fixtures__/raven_frame.json"), "utf-8"),
) as { scenario: Parameters<typeof resolveSceneManifest>[0]; frame: ArenaReplayFrame };

/** Quaternion for a pure heading (degrees clockwise from north): rotation
 *  about world +z by theta = 90deg - heading. */
function quatFromHeading(headingDeg: number): { w: number; x: number; y: number; z: number } {
  const theta = ((90 - headingDeg) * Math.PI) / 180;
  return { w: Math.cos(theta / 2), x: 0, y: 0, z: Math.sin(theta / 2) };
}

function projectionFromScene(scene: ArenaSceneState, frame: ArenaReplayFrame): ProjectionFrame {
  const statusById = new Map(frame.truth.map((entity) => [entity.id, entity.status]));
  return create(ProjectionFrameSchema, {
    protocolVersion: 1,
    viewId: "operator:test",
    sequence: 1n,
    simTimeNs: BigInt(Math.round(scene.simTimeSec * 1e9)),
    kind: 1,
    frameId: `snap-${scene.step}`,
    entities: [
      ...scene.truthEntities.map((entity) => ({
        viewEntityId: entity.id,
        factionId: entity.factionId,
        groupId: entity.groupId,
        assetId: entity.assetId,
        positionM: { x: entity.positionM.east, y: entity.positionM.north, z: entity.positionM.up },
        velocityMps: {
          x: entity.velocityMps.east,
          y: entity.velocityMps.north,
          z: entity.velocityMps.up,
        },
        statusFlags: [statusById.get(entity.id) ?? "active"],
      })),
      ...scene.sensors.map((sensor) => ({
        viewEntityId: sensor.id,
        factionId: sensor.factionId,
        assetId: sensor.assetId,
        positionM: { x: sensor.positionM.east, y: sensor.positionM.north, z: sensor.positionM.up },
        orientation: quatFromHeading(sensor.attitudeDeg.heading),
        statusFlags: ["active"],
      })),
      ...scene.responses.map((response) => ({
        viewEntityId: response.id,
        factionId: response.factionId,
        assetId: response.assetId,
        positionM: {
          x: response.positionM.east,
          y: response.positionM.north,
          z: response.positionM.up,
        },
        orientation: quatFromHeading(0),
        statusFlags: ["active"],
      })),
    ],
    tracks: scene.tracks.map((track) => ({
      trackId: track.id,
      estimatedPositionM: {
        x: track.positionM.east,
        y: track.positionM.north,
        z: track.positionM.up,
      },
      confidence: track.confidence,
    })),
    effects: scene.events.map((event) => ({
      effectId: event.id,
      effectType: event.eventType,
      positionM: { x: event.positionM.east, y: event.positionM.north, z: event.positionM.up },
      targetViewEntityId: event.truthTargetId,
      outcome: event.success ? "success" : "failed",
    })),
  });
}

function expectFrameClose(actual: NativeFrameV1, expected: NativeFrameV1): void {
  expect(actual.schemaVersion).toBe(expected.schemaVersion);
  expect(actual.runId).toBe(expected.runId);
  expect(actual.sequence).toBe(expected.sequence);
  expect(actual.simTimeSec).toBeCloseTo(expected.simTimeSec, 9);
  expect(actual.coordinateFrame).toBe("ENU");
  expect(actual.entities.map((entity) => entity.id)).toEqual(
    expected.entities.map((entity) => entity.id),
  );
  actual.entities.forEach((entity, index) => {
    const want = expected.entities[index];
    expect(entity.entityClass).toBe(want.entityClass);
    expect(entity.assetId).toBe(want.assetId);
    expect(entity.status).toBe(want.status);
    expect(entity.visible).toBe(want.visible);
    for (const axis of ["east", "up", "north"] as const) {
      expect(entity.positionM[axis]).toBeCloseTo(want.positionM[axis], 9);
    }
    for (const angle of ["heading", "pitch", "roll"] as const) {
      expect(entity.attitudeDeg[angle]).toBeCloseTo(want.attitudeDeg[angle], 9);
    }
  });
  expect(actual.tracks).toEqual(expected.tracks);
  expect(actual.events).toEqual(expected.events);
}

describe("projectionToFrameV1", () => {
  it("reproduces the proven frame-v1 output for a real Raven frame", () => {
    const manifest = resolveSceneManifest(ravenFixture.scenario);
    const scene = adaptArenaReplayFrame(ravenFixture.frame, manifest);
    const expected = sceneStateToFrameV1("parity-run", 7, scene);
    const actual = projectionToFrameV1(
      "parity-run",
      7,
      projectionFromScene(scene, ravenFixture.frame),
    );
    expect(expected.entities.length).toBeGreaterThan(0);
    expectFrameClose(actual, expected);
  });

  it("rejects an unsupported asset id", () => {
    const frame = create(ProjectionFrameSchema, {
      entities: [{ viewEntityId: "x", assetId: "not_a_real_asset" }],
    });
    expect(() => projectionToFrameV1("run", 0, frame)).toThrow(/unsupported asset/);
  });
});

describe("cross-repo golden fixtures", () => {
  it("parses the entity fixture with exact 64-bit ids as bigint", () => {
    const bytes = readFileSync(resolve(CONTRACT_FIXTURES, "entity_state.binpb"));
    const entity = fromBinary(EntityStateSchema, bytes);
    expect(entity.entityId?.value).toBe(9223372036854780050n);
    expect(entity.entityId!.value > BigInt(Number.MAX_SAFE_INTEGER)).toBe(true);
    expect(entity.identity?.displayName).toBe("Raven UAS Tráck");
    expect(entity.transform?.orientation?.w).toBeCloseTo(0.7071067811865476, 15);
  });

  it("parses the command envelope fixture with its oneof intact", () => {
    const bytes = readFileSync(resolve(CONTRACT_FIXTURES, "command_envelope.binpb"));
    const cmd = fromBinary(CommandEnvelopeSchema, bytes);
    expect(cmd.payload.case).toBe("effectAuthorization");
    expect(cmd.payload.case === "effectAuthorization" && cmd.payload.value.requestId).toBe(
      "roe-req-17",
    );
    expect(cmd.targetEntity?.value).toBe(9223372036854780050n);
  });

  it("parses the projection frame fixture with a beyond-2^53 sequence", () => {
    const bytes = readFileSync(resolve(CONTRACT_FIXTURES, "projection_frame.binpb"));
    const frame = fromBinary(ProjectionFrameSchema, bytes);
    expect(frame.sequence).toBe(9007199254741091n);
    expect(frame.tracks[0]?.trackId).toBe("track-003");
  });
});
