// frame-v1 compatibility mapper: converts a pytho.sim.v1 ProjectionFrame (the
// renderer-neutral RenderProjection stream from COA) into the existing
// NativeFrameV1 wire shape consumed by the loopback relay, the Dagor client,
// and the browser publisher. This keeps every current frame-v1 consumer
// rendering while authority migrates to COA (docs/adr/0001, coa ADR 0002).
//
// The wire `sequence` is per-connection and supplied by the caller, mirroring
// sceneStateToFrameV1(runId, sequence, scene); the ProjectionFrame's own
// 64-bit sequence stays server-side.
import type {
  ProjectedEffect,
  ProjectedEntity,
  ProjectionFrame,
} from "../contracts/pytho/sim/v1/projection_pb";
import type { Vec3 } from "../contracts/pytho/sim/v1/common_pb";
import {
  FRAME_V1_ENTITY_LIMIT,
  FRAME_V1_ITEM_LIMIT,
  attitudeFromQuaternion,
  headingFromVelocity,
  nativeStatus,
} from "./replayAdapter";
import {
  ASSET_DEFINITIONS,
  type ArenaTruthStatus,
  type AssetId,
  type AttitudeDeg,
  type EnuPosition,
  type NativeEntity,
  type NativeFrameV1,
  type NativeTrack,
  type SceneEvent,
} from "./types";

const TRUTH_STATUS_FLAGS: readonly ArenaTruthStatus[] = [
  "active",
  "inactive",
  "intercepted",
  "attack-failed",
  "attack-succeeded",
];

function enu(v: Vec3 | undefined, label: string): EnuPosition {
  const east = v?.x ?? 0;
  const north = v?.y ?? 0;
  const up = v?.z ?? 0;
  if (!Number.isFinite(east) || !Number.isFinite(north) || !Number.isFinite(up)) {
    throw new TypeError(`${label} must be finite`);
  }
  return { east, up, north };
}

function entityAttitude(entity: ProjectedEntity): AttitudeDeg {
  const q = entity.orientation;
  if (q && (q.w !== 0 || q.x !== 0 || q.y !== 0 || q.z !== 0)) {
    return attitudeFromQuaternion([q.w, q.x, q.y, q.z]);
  }
  const v = entity.velocityMps;
  return { heading: headingFromVelocity([v?.x ?? 0, v?.y ?? 0]), pitch: 0, roll: 0 };
}

function entityStatus(entity: ProjectedEntity): NativeEntity["status"] {
  const flag = entity.statusFlags.find((candidate): candidate is ArenaTruthStatus =>
    (TRUTH_STATUS_FLAGS as readonly string[]).includes(candidate),
  );
  return nativeStatus(flag ?? "active");
}

function assetIdOf(entity: ProjectedEntity): AssetId {
  if (!(entity.assetId in ASSET_DEFINITIONS)) {
    throw new Error(`projection entity ${entity.viewEntityId} has unsupported asset: ${entity.assetId}`);
  }
  return entity.assetId as AssetId;
}

function effectToEvent(effect: ProjectedEffect): SceneEvent {
  if (effect.effectType !== "intercept" && effect.effectType !== "attack") {
    throw new Error(`unsupported frame-v1 effect type: ${effect.effectType}`);
  }
  return {
    id: effect.effectId,
    eventType: effect.effectType,
    truthTargetId: effect.targetViewEntityId,
    positionM: enu(effect.positionM, `effect ${effect.effectId} position`),
    success: effect.outcome === "success",
  };
}

export function projectionToFrameV1(
  runId: string,
  sequence: number,
  frame: ProjectionFrame,
): NativeFrameV1 {
  if (!runId) throw new Error("runId must be a non-empty string");
  if (!Number.isSafeInteger(sequence) || sequence < 0) {
    throw new RangeError("sequence must be a non-negative integer");
  }

  const entities: NativeEntity[] = frame.entities
    .map((entity) => {
      const assetId = assetIdOf(entity);
      return {
        id: entity.viewEntityId,
        entityClass: ASSET_DEFINITIONS[assetId],
        assetId,
        positionM: enu(entity.positionM, `entity ${entity.viewEntityId} position`),
        attitudeDeg: entityAttitude(entity),
        status: entityStatus(entity),
        visible: true,
      };
    })
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  if (entities.length > FRAME_V1_ENTITY_LIMIT) {
    throw new RangeError(
      `frame-v1 supports at most ${FRAME_V1_ENTITY_LIMIT} entities; received ${entities.length}`,
    );
  }
  const ids = new Set<string>();
  for (const entity of entities) {
    if (ids.has(entity.id)) throw new Error(`duplicate frame-v1 entity id: ${entity.id}`);
    ids.add(entity.id);
  }

  const tracks: NativeTrack[] = frame.tracks.map((track) => ({
    id: track.trackId,
    positionM: enu(track.estimatedPositionM, `track ${track.trackId} position`),
    confidence: track.confidence,
  }));

  const events = frame.effects.map(effectToEvent);
  const renderedItems =
    entities.length + tracks.length + events.filter((event) => event.success).length;
  if (renderedItems > FRAME_V1_ITEM_LIMIT) {
    throw new RangeError(
      `frame-v1 supports at most ${FRAME_V1_ITEM_LIMIT} rendered items; received ` +
        `${renderedItems} (entities + tracks + effects)`,
    );
  }

  return {
    schemaVersion: 1,
    type: "frame",
    runId,
    sequence,
    simTimeSec: Number(frame.simTimeNs) / 1e9,
    coordinateFrame: "ENU",
    entities,
    tracks,
    events,
  };
}
