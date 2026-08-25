import { describe, expect, it } from "vitest";

import type { Scenario } from "../app/types";
import {
  environmentBlueprintKey,
  normalizeEnvironmentBlueprint,
  resolveScenarioEnvironment,
} from "./environmentBlueprint";

function scenario(overrides: Partial<Scenario> = {}): Scenario {
  return {
    scenario_id: "document-import",
    version: 1,
    name: "Document import",
    description: "",
    seed: 7,
    duration_seconds: 60,
    step_seconds: 1,
    world: { width: 100, height: 100, vertical_extent: 10 },
    factions: [],
    actor_groups: [],
    sensors: [],
    responses: [],
    protected_zones: [],
    policy_bindings: [],
    ...overrides,
  };
}

describe("manifest environment selection", () => {
  it("keeps absent and gulf manifests on the existing air-base environment", () => {
    expect(resolveScenarioEnvironment(scenario())).toBe("gulf_airbase");
    expect(
      resolveScenarioEnvironment(
        scenario({
          visualization: { environment: "gulf_airbase" },
        }),
      ),
    ).toBe("gulf_airbase");
  });

  it("selects coastal urban and changes the runtime blueprint key", () => {
    const gulf = normalizeEnvironmentBlueprint(scenario());
    const coastal = normalizeEnvironmentBlueprint(
      scenario({
        visualization: { environment: "coastal_urban" },
      }),
    );
    expect(coastal.environment).toBe("coastal_urban");
    expect(environmentBlueprintKey(coastal)).not.toBe(
      environmentBlueprintKey(gulf),
    );
  });
});

describe("blueprint normalization", () => {
  it("keeps typed ENU placements and normalizes heading and scale", () => {
    const blueprint = normalizeEnvironmentBlueprint(
      scenario({
        visualization: {
          environment: "coastal_urban",
          static_assets: [
            {
              id: " imported-sensor ",
              kind: "sensor_tower",
              position: [125, -48],
              heading_degrees: -90,
              scale: 8,
            },
            {
              id: "generic-response",
              kind: "response_vehicle",
              position: [-220, 75],
            },
            {
              id: "harbor-patrol",
              kind: "patrol_boat",
              position: [-510, 120],
              heading_degrees: 450,
              scale: 0.1,
            },
          ],
        },
      }),
    );

    expect(blueprint.staticAssets).toEqual([
      {
        id: "imported-sensor",
        kind: "sensor_tower",
        east: 125,
        north: -48,
        headingDegrees: 270,
        scale: 4,
      },
      {
        id: "generic-response",
        kind: "response_vehicle",
        east: -220,
        north: 75,
        headingDegrees: 0,
        scale: 1,
      },
      {
        id: "harbor-patrol",
        kind: "patrol_boat",
        east: -510,
        north: 120,
        headingDegrees: 90,
        scale: 0.25,
      },
    ]);
  });

  it("drops duplicate, unknown, and non-finite placements from imported data", () => {
    const imported = {
      ...scenario(),
      visualization: {
        environment: "coastal_urban",
        static_assets: [
          { id: "valid", kind: "warehouse", position: [10, 20] },
          { id: "valid", kind: "warehouse", position: [30, 40] },
          { id: "unknown", kind: "exact-real-installation", position: [0, 0] },
          {
            id: "infinite",
            kind: "office_block",
            position: [Number.POSITIVE_INFINITY, 0],
          },
        ],
      },
    } as unknown as Scenario;

    expect(normalizeEnvironmentBlueprint(imported).staticAssets).toEqual([
      {
        id: "valid",
        kind: "warehouse",
        east: 10,
        north: 20,
        headingDegrees: 0,
        scale: 1,
      },
    ]);
  });
});
