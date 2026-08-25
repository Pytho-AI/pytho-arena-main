import {
  ASSET_DEFINITIONS,
  type ArenaPoint,
  type ArenaReplayFrame,
  type ArenaSceneManifest,
  type ArenaSceneState,
  type ArenaTruthStatus,
  type AttitudeDeg,
  type EnuPosition,
  type NativeEntity,
  type NativeEntityStatus,
  type NativeFrameV1,
  type NativeTrack,
  type QuaternionWxyz,
  type SceneManifestEntry,
  type SceneTrack,
} from "./types";

export const FRAME_V1_ENTITY_LIMIT = 2_000;

/**
 * Total items the native client will draw for one frame: visible entities plus
 * tracks plus successful effects. This mirrors the render-count guard in
 * `pytho_frame_overlay.das`, so a frame this publisher accepts is a frame the
 * native overlay accepts.
 */
export const FRAME_V1_ITEM_LIMIT = 2_000;

function finite(value: number, label: string): number {
  if (!Number.isFinite(value)) throw new TypeError(`${label} must be finite`);
  return value;
}

function validateManifestEntry(entry: SceneManifestEntry, label: string): void {
  if (!(entry.assetId in ASSET_DEFINITIONS)) {
    throw new Error(`${label} uses unsupported asset: ${String(entry.assetId)}`);
  }
  finite(entry.altitudeM, `${label}.altitudeM`);
}

function validateManifest(manifest: ArenaSceneManifest): void {
  if (!Number.isFinite(manifest.metersPerWorldUnit) || manifest.metersPerWorldUnit <= 0) {
    throw new RangeError("metersPerWorldUnit must be a positive finite number");
  }
  finite(manifest.originWorld[0], "originWorld[0]");
  finite(manifest.originWorld[1], "originWorld[1]");
  Object.entries(manifest.groups).forEach(([groupId, entry]) => {
    validateManifestEntry(entry, `groups.${groupId}`);
  });
  validateManifestEntry(manifest.sensor, "sensor");
  validateManifestEntry(manifest.response, "response");
  if (ASSET_DEFINITIONS[manifest.sensor.assetId] !== "sensor") {
    throw new Error("sensor manifest asset must have entity class sensor");
  }
  if (ASSET_DEFINITIONS[manifest.response.assetId] !== "ground-vehicle") {
    throw new Error("response manifest asset must have entity class ground-vehicle");
  }
}

function positionToEnu(
  position: ArenaPoint,
  fallbackAltitudeM: number,
  manifest: ArenaSceneManifest,
): EnuPosition {
  const scale = manifest.metersPerWorldUnit;
  return {
    east: (finite(position[0], "position[0]") - manifest.originWorld[0]) * scale,
    up:
      position.length === 3
        ? finite(position[2], "position[2]") * scale
        : fallbackAltitudeM,
    north: (finite(position[1], "position[1]") - manifest.originWorld[1]) * scale,
  };
}

function velocityToEnu(velocity: ArenaPoint, scale: number): EnuPosition {
  return {
    east: finite(velocity[0], "velocity[0]") * scale,
    up: velocity.length === 3 ? finite(velocity[2], "velocity[2]") * scale : 0,
    north: finite(velocity[1], "velocity[1]") * scale,
  };
}

function normalizedDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

export function headingFromVelocity(velocity: ArenaPoint): number {
  const east = finite(velocity[0], "velocity[0]");
  const north = finite(velocity[1], "velocity[1]");
  if (Math.hypot(east, north) <= Number.EPSILON) return 0;
  return normalizedDegrees(Math.atan2(east, north) * (180 / Math.PI));
}

function headingFromArenaRadians(radians: number): number {
  return normalizedDegrees(90 - finite(radians, "headingRadians") * (180 / Math.PI));
}

function attitude(heading: number): AttitudeDeg {
  return { heading, pitch: 0, roll: 0 };
}

export function attitudeFromQuaternion(quaternion: QuaternionWxyz): AttitudeDeg {
  const w = finite(quaternion[0], "orientationWxyz[0]");
  const x = finite(quaternion[1], "orientationWxyz[1]");
  const y = finite(quaternion[2], "orientationWxyz[2]");
  const z = finite(quaternion[3], "orientationWxyz[3]");
  const norm = Math.hypot(w, x, y, z);
  if (norm <= Number.EPSILON) throw new RangeError("orientationWxyz must have nonzero norm");
  const qw = w / norm;
  const qx = x / norm;
  const qy = y / norm;
  const qz = z / norm;
  const forwardEast = 1 - 2 * (qy * qy + qz * qz);
  const forwardNorth = 2 * (qx * qy + qw * qz);
  const forwardUp = 2 * (qx * qz - qw * qy);
  const leftUp = 2 * (qy * qz + qw * qx);
  const upUp = 1 - 2 * (qx * qx + qy * qy);
  return {
    heading: normalizedDegrees(Math.atan2(forwardEast, forwardNorth) * (180 / Math.PI)),
    pitch: Math.asin(Math.max(-1, Math.min(1, forwardUp))) * (180 / Math.PI),
    roll: Math.atan2(leftUp, upUp) * (180 / Math.PI),
  };
}

export function nativeStatus(status: ArenaTruthStatus): NativeEntityStatus {
  switch (status) {
    case "active":
      return "active";
    case "intercepted":
      return "neutralized";
    case "attack-succeeded":
      return "penetrated";
    case "attack-failed":
      return "complete";
    case "inactive":
      return "offline";
  }
}

function compareIds(left: { id: string }, right: { id: string }): number {
  return left.id < right.id ? -1 : left.id > right.id ? 1 : 0;
}

export function adaptArenaReplayFrame(
  frame: ArenaReplayFrame,
  manifest: ArenaSceneManifest,
): ArenaSceneState {
  validateManifest(manifest);
  if (!Number.isSafeInteger(frame.step) || frame.step < 0) {
    throw new RangeError("frame.step must be a non-negative integer");
  }
  if (!Number.isFinite(frame.time) || frame.time < 0) {
    throw new RangeError("frame.time must be a non-negative finite number");
  }

  const truthById = new Map(frame.truth.map((entity) => [entity.id, entity]));
  const truthEntities = frame.truth.map((entity) => {
    const mapping = manifest.groups[entity.groupId];
    if (!mapping) throw new Error(`scene manifest has no mapping for group: ${entity.groupId}`);
    const positionM = positionToEnu(entity.position, mapping.altitudeM, manifest);
    const velocityMps = velocityToEnu(entity.velocity, manifest.metersPerWorldUnit);
    return {
      id: entity.id,
      factionId: entity.factionId,
      groupId: entity.groupId,
      assetId: mapping.assetId,
      entityClass: ASSET_DEFINITIONS[mapping.assetId],
      positionM,
      velocityMps,
      attitudeDeg: entity.orientationWxyz
        ? attitudeFromQuaternion(entity.orientationWxyz)
        : attitude(headingFromVelocity(entity.velocity)),
      status: nativeStatus(entity.status),
      active: entity.active,
      detected: entity.detected,
      enteredZone: entity.enteredZone,
    };
  }).sort(compareIds);

  const rawDetections = frame.detections.map((detection) => {
    const truth = truthById.get(detection.entityId);
    if (!truth) throw new Error(`detection references unknown truth entity: ${detection.entityId}`);
    const mapping = manifest.groups[truth.groupId];
    if (!mapping) throw new Error(`scene manifest has no mapping for group: ${truth.groupId}`);
    return {
      sensorId: detection.sensorId,
      truthEntityId: detection.entityId,
      positionM: positionToEnu(detection.position, mapping.altitudeM, manifest),
    };
  });

  const sensors = frame.sensors.map((sensor) => ({
    id: sensor.id,
    factionId: sensor.factionId,
    assetId: manifest.sensor.assetId,
    positionM: positionToEnu(sensor.position, manifest.sensor.altitudeM, manifest),
    rangeM: sensor.range * manifest.metersPerWorldUnit,
    fovDegrees: sensor.fovDegrees,
    attitudeDeg: attitude(headingFromArenaRadians(sensor.headingRadians)),
  })).sort(compareIds);

  const responses = frame.responses.map((response) => ({
    id: response.id,
    factionId: response.factionId,
    assetId: manifest.response.assetId,
    positionM: positionToEnu(response.position, manifest.response.altitudeM, manifest),
    engagementRangeM: response.engagementRange * manifest.metersPerWorldUnit,
  })).sort(compareIds);

  const eventAltitude = (entityId: string): number => {
    const truth = truthById.get(entityId);
    return truth ? manifest.groups[truth.groupId]?.altitudeM ?? 0 : 0;
  };
  const events = [
    ...frame.events.intercepts.map((event, index) => ({
      id: `intercept:${frame.step}:${event.entityId}:${index}`,
      eventType: "intercept" as const,
      truthTargetId: event.entityId,
      positionM: positionToEnu(event.position, eventAltitude(event.entityId), manifest),
      success: true,
    })),
    ...frame.events.attacks.map((event, index) => ({
      id: `attack:${frame.step}:${event.entityId}:${index}`,
      eventType: "attack" as const,
      truthTargetId: event.entityId,
      positionM: positionToEnu(event.position, eventAltitude(event.entityId), manifest),
      success: event.succeeded,
    })),
  ];

  // Tracks are measurements with no declared altitude, so they anchor to the
  // ground plane and the viewport draws them as tactical markers, not models.
  const tracks: SceneTrack[] = (frame.tracks ?? [])
    .map((track) => ({
      id: track.trackId,
      classification: track.classification,
      confidence: finite(track.confidence, "track.confidence"),
      ageSeconds: finite(track.ageSeconds, "track.ageSeconds"),
      positionM: positionToEnu(track.position, 0, manifest),
      velocityMps: velocityToEnu(track.velocity, manifest.metersPerWorldUnit),
      requestId: track.requestId,
      disposition: track.disposition,
      evidenceReportIds: track.evidenceReportIds,
    }))
    .sort(compareIds);

  return {
    step: frame.step,
    simTimeSec: frame.time,
    coordinateFrame: "ENU",
    metersPerWorldUnit: manifest.metersPerWorldUnit,
    originWorld: manifest.originWorld,
    truthEntities,
    rawDetections,
    sensors,
    responses,
    tracks,
    decisions: [...(frame.decisions ?? [])],
    events,
  };
}

function assertUniqueIds(entities: readonly NativeEntity[]): void {
  const ids = new Set<string>();
  for (const entity of entities) {
    if (ids.has(entity.id)) throw new Error(`duplicate frame-v1 entity id: ${entity.id}`);
    ids.add(entity.id);
  }
}

export function sceneStateToFrameV1(
  runId: string,
  sequence: number,
  scene: ArenaSceneState,
): NativeFrameV1 {
  if (!runId) throw new Error("runId must be a non-empty string");
  if (!Number.isSafeInteger(sequence) || sequence < 0) {
    throw new RangeError("sequence must be a non-negative integer");
  }

  const entities: NativeEntity[] = [
    ...scene.truthEntities.map((entity) => ({
      id: entity.id,
      entityClass: entity.entityClass,
      assetId: entity.assetId,
      positionM: entity.positionM,
      attitudeDeg: entity.attitudeDeg,
      status: entity.status,
      visible: true,
    })),
    ...scene.sensors.map((sensor) => ({
      id: sensor.id,
      entityClass: "sensor" as const,
      assetId: sensor.assetId,
      positionM: sensor.positionM,
      attitudeDeg: sensor.attitudeDeg,
      status: "active" as const,
      visible: true,
    })),
    ...scene.responses.map((response) => ({
      id: response.id,
      entityClass: "ground-vehicle" as const,
      assetId: response.assetId,
      positionM: response.positionM,
      attitudeDeg: attitude(0),
      status: "active" as const,
      visible: true,
    })),
  ].sort(compareIds);

  if (entities.length > FRAME_V1_ENTITY_LIMIT) {
    throw new RangeError(
      `frame-v1 supports at most ${FRAME_V1_ENTITY_LIMIT} entities; received ${entities.length}`,
    );
  }
  assertUniqueIds(entities);

  const tracks: NativeTrack[] = scene.tracks.map((track) => ({
    id: track.id,
    positionM: track.positionM,
    confidence: track.confidence,
  }));
  const renderedItems =
    entities.filter((entity) => entity.visible).length +
    tracks.length +
    scene.events.filter((event) => event.success).length;
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
    simTimeSec: scene.simTimeSec,
    coordinateFrame: "ENU",
    entities,
    tracks,
    events: scene.events,
  };
}
