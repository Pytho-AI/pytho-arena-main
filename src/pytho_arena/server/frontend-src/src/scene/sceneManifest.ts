import { multiFactionAirDefenseScene, type ArenaSceneManifest } from "../arena";
import type { Scenario } from "../app/types";

const DEFAULT_SCENARIO_ID = "multi-faction-air-defense";
const DEFAULT_GROUPS = ["neutral-traffic", "red-strike"];

function isBoundDefaultScenario(scenario: Scenario): boolean {
  const groupIds = scenario.actor_groups.map((group) => group.id).sort();
  return (
    scenario.scenario_id === DEFAULT_SCENARIO_ID &&
    scenario.world.width === 100 &&
    scenario.world.height === 100 &&
    groupIds.length === DEFAULT_GROUPS.length &&
    groupIds.every((id, index) => id === DEFAULT_GROUPS[index])
  );
}

function assetForGroup(
  group: Scenario["actor_groups"][number],
): "uav_orion" | "mq_1l_usa" | "quadcopter_surrogate" {
  const identity = `${group.id} ${group.mission}`.toLowerCase();
  if (
    /surveill|s-?uas|recon|observe|monitor|quadcopter|multirotor/.test(identity)
  )
    return "quadcopter_surrogate";
  if (group.mission === "attack_objective") return "uav_orion";
  return "mq_1l_usa";
}

export function resolveSceneManifest(scenario: Scenario): ArenaSceneManifest {
  if (isBoundDefaultScenario(scenario)) return multiFactionAirDefenseScene;

  const metersPerWorldUnit =
    scenario.world.meters_per_unit
    ?? 1_000 / Math.max(scenario.world.width, scenario.world.height);
  const airborneAltitude = Math.max(
    80,
    scenario.world.vertical_extent * metersPerWorldUnit,
  );
  return {
    metersPerWorldUnit,
    originWorld: [scenario.world.width / 2, scenario.world.height / 2],
    groups: Object.fromEntries(
      scenario.actor_groups.map((group) => [
        group.id,
        {
          assetId: assetForGroup(group),
          altitudeM:
            group.mission === "attack_objective"
              ? airborneAltitude
              : airborneAltitude * 0.75,
        },
      ]),
    ),
    sensor: { assetId: "range_watch_tower", altitudeM: 0 },
    response: { assetId: "nasams_fcs", altitudeM: 0 },
  };
}
