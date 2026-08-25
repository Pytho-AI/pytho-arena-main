import { describe, expect, it } from "vitest";

import type { ArenaSceneState, SceneTruthEntity } from "../arena";
import { buildRenderPlan, countPlannedInstances, usesInstancedTruth } from "./renderPlan";

const entity = (index: number): SceneTruthEntity => ({
  id: `uav-${index}`,
  factionId: "red",
  groupId: "red-strike",
  assetId: "uav_orion",
  entityClass: "fixed-wing",
  positionM: { east: index, up: 120, north: index },
  velocityMps: { east: 1, up: 0, north: 0 },
  attitudeDeg: { heading: 90, pitch: 0, roll: 0 },
  status: "active",
  active: true,
  detected: true,
  enteredZone: false,
});

function scene(size: number): ArenaSceneState {
  return {
    step: 0,
    simTimeSec: 0,
    coordinateFrame: "ENU",
    metersPerWorldUnit: 10,
    originWorld: [50, 50],
    truthEntities: Array.from({ length: size }, (_, index) => entity(index)),
    rawDetections: [{
      sensorId: "sensor-north",
      truthEntityId: "uav-0",
      positionM: { east: 4, up: 120, north: 2 },
    }],
    sensors: [],
    responses: [],
    tracks: [],
    decisions: [],
    events: [],
  };
}

describe("render plan", () => {
  it("keeps analyst truth in one instanced asset batch at 100, 500, and 2,000 entities", () => {
    for (const size of [100, 500, 2_000]) {
      const plan = buildRenderPlan(scene(size), "analyst");
      expect(plan.truthByAsset.size).toBe(1);
      expect(plan.truthByAsset.get("uav_orion")).toHaveLength(size);
      expect(countPlannedInstances(plan)).toBe(size + 1);
      expect(usesInstancedTruth(size, "analyst")).toBe(true);
    }
  });

  it("hides all truth from the operator while retaining raw sensor measurements", () => {
    const plan = buildRenderPlan(scene(100), "operator");
    expect(plan.truthCount).toBe(0);
    expect(plan.truthByAsset.size).toBe(0);
    expect(plan.detections).toHaveLength(1);
    expect(usesInstancedTruth(2_000, "operator")).toBe(false);
  });
});
