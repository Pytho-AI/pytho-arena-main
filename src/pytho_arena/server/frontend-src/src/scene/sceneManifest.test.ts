import { describe, expect, it } from "vitest";

import type { Scenario } from "../app/types";
import { resolveSceneManifest } from "./sceneManifest";

function scenario(overrides: Partial<Scenario> = {}): Scenario {
  return {
    scenario_id: "multi-faction-air-defense",
    version: 1,
    name: "Test",
    description: "",
    seed: 7,
    duration_seconds: 60,
    step_seconds: 1,
    world: { width: 100, height: 100, vertical_extent: 10 },
    factions: [],
    actor_groups: [
      {
        id: "red-strike",
        faction_id: "red",
        count: 12,
        mission: "attack_objective",
      },
      {
        id: "neutral-traffic",
        faction_id: "neutral",
        count: 6,
        mission: "transit",
      },
    ],
    sensors: [],
    responses: [],
    protected_zones: [],
    policy_bindings: [],
    ...overrides,
  };
}

describe("scene manifest resolver", () => {
  it("uses the bound default manifest only for the expected world and groups", () => {
    const manifest = resolveSceneManifest(scenario());
    expect(manifest.metersPerWorldUnit).toBe(10);
    expect(manifest.groups["neutral-traffic"]).toEqual({
      assetId: "mq_1l_usa",
      altitudeM: 90,
    });
  });

  it("builds an explicit generic manifest for edited and non-default scenarios", () => {
    const manifest = resolveSceneManifest(
      scenario({
        scenario_id: "custom-defense",
        world: { width: 200, height: 100, vertical_extent: 30 },
        actor_groups: [
          {
            id: "raid-alpha",
            faction_id: "x",
            count: 4,
            mission: "attack_objective",
          },
          {
            id: "corridor-traffic",
            faction_id: "y",
            count: 3,
            mission: "transit",
          },
        ],
      }),
    );
    expect(manifest.metersPerWorldUnit).toBe(5);
    expect(manifest.originWorld).toEqual([100, 50]);
    expect(manifest.groups).toEqual({
      "raid-alpha": { assetId: "uav_orion", altitudeM: 150 },
      "corridor-traffic": { assetId: "mq_1l_usa", altitudeM: 112.5 },
    });
  });

  it("uses an explicit metric scale for force-based physics worlds", () => {
    const manifest = resolveSceneManifest(
      scenario({
        scenario_id: "metric-multirotor",
        world: {
          width: 400,
          height: 300,
          vertical_extent: 120,
          meters_per_unit: 1,
        },
      }),
    );

    expect(manifest.metersPerWorldUnit).toBe(1);
  });

  it("maps imported surveillance groups to a multirotor surrogate", () => {
    const manifest = resolveSceneManifest(
      scenario({
        scenario_id: "document-surveillance",
        actor_groups: [
          {
            id: "persistent-watch",
            faction_id: "blue",
            count: 4,
            mission: "surveillance",
          },
        ],
      }),
    );
    expect(manifest.groups["persistent-watch"]).toEqual({
      assetId: "quadcopter_surrogate",
      altitudeM: 75,
    });
  });

  it("keeps document surveillance identifiers on multirotors when their mission attacks", () => {
    const manifest = resolveSceneManifest(
      scenario({
        scenario_id: "document-counter-uas",
        actor_groups: [
          {
            id: "surveillance-suas",
            faction_id: "threat",
            count: 8,
            mission: "attack_objective",
          },
        ],
      }),
    );
    expect(manifest.groups["surveillance-suas"]).toEqual({
      assetId: "quadcopter_surrogate",
      altitudeM: 100,
    });
  });
});
