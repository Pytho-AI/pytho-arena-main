export type Point2 = readonly [number, number];
export type Point3 = readonly [number, number, number];
export type ArenaPoint = Point2 | Point3;
export type QuaternionWxyz = readonly [number, number, number, number];

export type ArenaTruthStatus =
  | "active"
  | "inactive"
  | "intercepted"
  | "attack-failed"
  | "attack-succeeded";

export interface ArenaTruthEntity {
  id: string;
  factionId: string;
  groupId: string;
  position: ArenaPoint;
  velocity: ArenaPoint;
  orientationWxyz?: QuaternionWxyz;
  active: boolean;
  status: ArenaTruthStatus;
  detected: boolean;
  enteredZone: boolean;
}

export interface ArenaDetection {
  sensorId: string;
  entityId: string;
  position: ArenaPoint;
}

export interface ArenaSensor {
  id: string;
  factionId: string;
  position: ArenaPoint;
  range: number;
  fovDegrees: number;
  headingRadians: number;
}

export interface ArenaResponse {
  id: string;
  factionId: string;
  position: ArenaPoint;
  engagementRange: number;
}

export type TrackClassification = "unknown" | "friendly" | "suspect" | "hostile";
export type RoeDisposition = "hold" | "deny" | "authorize";

/**
 * One fused track as the operator sees it. Positions are measurements in world
 * units; the track id is opaque, so nothing here identifies a truth entity.
 */
export interface ArenaTrack {
  trackId: string;
  position: ArenaPoint;
  velocity: ArenaPoint;
  classification: TrackClassification;
  confidence: number;
  ageSeconds: number;
  sourceSensorIds: readonly string[];
  evidenceReportIds: readonly string[];
  requestId: string | null;
  disposition: RoeDisposition | null;
}

/** One authority request in the operator decision queue. */
export interface ArenaDecisionRequest {
  requestId: string;
  trackId: string;
  effectorId: string;
  rationale: string;
  step: number;
  timeSeconds: number;
  classification: TrackClassification;
  disposition: RoeDisposition | null;
  decisionId: string | null;
  decisionStep: number | null;
  pending: boolean;
}

export interface ArenaReplayFrame {
  step: number;
  time: number;
  truth: readonly ArenaTruthEntity[];
  detections: readonly ArenaDetection[];
  sensors: readonly ArenaSensor[];
  responses: readonly ArenaResponse[];
  events: {
    intercepts: readonly { entityId: string; position: ArenaPoint }[];
    attacks: readonly { entityId: string; position: ArenaPoint; succeeded: boolean }[];
  };
  /** Present only for runs of a scenario that declares a typed effector. */
  tracks?: readonly ArenaTrack[];
  decisions?: readonly ArenaDecisionRequest[];
}

export interface EnuPosition {
  east: number;
  up: number;
  north: number;
}

export interface AttitudeDeg {
  heading: number;
  pitch: number;
  roll: number;
}

export type NativeEntityStatus =
  | "active"
  | "neutralized"
  | "penetrated"
  | "complete"
  | "offline";

export type NativeEntityClass =
  | "fixed-wing"
  | "multirotor"
  | "sensor"
  | "ground-vehicle"
  | "ship"
  | "effect";

export interface SceneTruthEntity {
  id: string;
  factionId: string;
  groupId: string;
  assetId: AssetId;
  entityClass: NativeEntityClass;
  positionM: EnuPosition;
  velocityMps: EnuPosition;
  attitudeDeg: AttitudeDeg;
  status: NativeEntityStatus;
  active: boolean;
  detected: boolean;
  enteredZone: boolean;
}

export interface SceneRawDetection {
  sensorId: string;
  truthEntityId: string;
  positionM: EnuPosition;
}

export interface SceneSensor {
  id: string;
  factionId: string;
  assetId: AssetId;
  positionM: EnuPosition;
  rangeM: number;
  fovDegrees: number;
  attitudeDeg: AttitudeDeg;
}

export interface SceneResponse {
  id: string;
  factionId: string;
  assetId: AssetId;
  positionM: EnuPosition;
  engagementRangeM: number;
}

export interface SceneEvent {
  id: string;
  eventType: "intercept" | "attack";
  truthTargetId: string;
  positionM: EnuPosition;
  success: boolean;
}

/** A fused track placed in the scene. Drawn for both roles: it holds no truth. */
export interface SceneTrack {
  id: string;
  classification: TrackClassification;
  confidence: number;
  ageSeconds: number;
  positionM: EnuPosition;
  velocityMps: EnuPosition;
  requestId: string | null;
  disposition: RoeDisposition | null;
  evidenceReportIds: readonly string[];
}

export interface ArenaSceneState {
  step: number;
  simTimeSec: number;
  coordinateFrame: "ENU";
  metersPerWorldUnit: number;
  originWorld: Point2;
  truthEntities: SceneTruthEntity[];
  rawDetections: SceneRawDetection[];
  sensors: SceneSensor[];
  responses: SceneResponse[];
  tracks: SceneTrack[];
  decisions: ArenaDecisionRequest[];
  events: SceneEvent[];
}

export interface NativeEntity {
  id: string;
  entityClass: NativeEntityClass;
  assetId: AssetId;
  positionM: EnuPosition;
  attitudeDeg: AttitudeDeg;
  status: NativeEntityStatus;
  visible: boolean;
}

/** The wire shape of a track, matching `$defs/track` in frame-v1.schema.json. */
export interface NativeTrack {
  id: string;
  positionM: EnuPosition;
  confidence: number;
}

export interface NativeFrameV1 {
  schemaVersion: 1;
  type: "frame";
  runId: string;
  sequence: number;
  simTimeSec: number;
  coordinateFrame: "ENU";
  entities: NativeEntity[];
  tracks: NativeTrack[];
  events: SceneEvent[];
}

export const ASSET_DEFINITIONS = {
  uav_orion: "fixed-wing",
  mq_1l_usa: "fixed-wing",
  quadcopter_surrogate: "multirotor",
  nasams_fcs: "ground-vehicle",
  range_watch_tower: "sensor",
  cargo_ship_liberty: "ship",
} as const satisfies Record<string, NativeEntityClass>;

export type AssetId = keyof typeof ASSET_DEFINITIONS;

export interface SceneManifestEntry {
  assetId: AssetId;
  altitudeM: number;
}

export interface ArenaSceneManifest {
  metersPerWorldUnit: number;
  originWorld: Point2;
  groups: Readonly<Record<string, SceneManifestEntry>>;
  sensor: SceneManifestEntry;
  response: SceneManifestEntry;
}
