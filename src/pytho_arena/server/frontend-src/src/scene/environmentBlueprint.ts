import type {
  Scenario,
  ScenarioEnvironment,
  ScenarioStaticAssetKind,
} from "../app/types";

export const STATIC_ASSET_KINDS = [
  "warehouse",
  "mixed_block",
  "office_block",
  "storage_tank",
  "marina_pier",
  "cargo_stack",
  "utility_tower",
  "fence_segment",
  "gatehouse",
  "sensor_tower",
  "response_vehicle",
  "patrol_boat",
] as const satisfies readonly ScenarioStaticAssetKind[];

const staticAssetKinds = new Set<string>(STATIC_ASSET_KINDS);
const MAX_STATIC_ASSETS = 512;

export interface NormalizedStaticAssetPlacement {
  id: string;
  kind: ScenarioStaticAssetKind;
  east: number;
  north: number;
  headingDegrees: number;
  scale: number;
}

export interface EnvironmentBlueprint {
  environment: ScenarioEnvironment;
  staticAssets: NormalizedStaticAssetPlacement[];
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object"
    ? (value as Record<string, unknown>)
    : null;
}

function normalizedHeading(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return ((value % 360) + 360) % 360;
}

function normalizedScale(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 1;
  return Math.min(4, Math.max(0.25, value));
}

export function resolveScenarioEnvironment(
  scenario: Scenario | null,
): ScenarioEnvironment {
  return scenario?.visualization?.environment === "coastal_urban"
    ? "coastal_urban"
    : "gulf_airbase";
}

export function normalizeEnvironmentBlueprint(
  scenario: Scenario | null,
): EnvironmentBlueprint {
  const environment = resolveScenarioEnvironment(scenario);
  const visualization = record(scenario?.visualization);
  const candidates = Array.isArray(visualization?.static_assets)
    ? visualization.static_assets.slice(0, MAX_STATIC_ASSETS)
    : [];
  const ids = new Set<string>();
  const staticAssets: NormalizedStaticAssetPlacement[] = [];

  for (const candidate of candidates) {
    const placement = record(candidate);
    if (!placement) continue;
    const id = typeof placement.id === "string" ? placement.id.trim() : "";
    const kind = typeof placement.kind === "string" ? placement.kind : "";
    const position = Array.isArray(placement.position)
      ? placement.position
      : [];
    const east = position[0];
    const north = position[1];
    if (
      !id ||
      ids.has(id) ||
      !staticAssetKinds.has(kind) ||
      typeof east !== "number" ||
      !Number.isFinite(east) ||
      typeof north !== "number" ||
      !Number.isFinite(north)
    )
      continue;

    ids.add(id);
    staticAssets.push({
      id,
      kind: kind as ScenarioStaticAssetKind,
      east,
      north,
      headingDegrees: normalizedHeading(placement.heading_degrees),
      scale: normalizedScale(placement.scale),
    });
  }

  return { environment, staticAssets };
}

export function environmentBlueprintKey(
  blueprint: EnvironmentBlueprint,
): string {
  return JSON.stringify(blueprint);
}
