import type { ArenaSceneState, AssetId, EnuPosition, SceneTruthEntity } from "../arena";
import type { Role } from "../app/types";

export const DETAIL_ENTITY_LIMIT = 100;

export interface DetectionInstance {
  id: string;
  positionM: EnuPosition;
}

export interface RenderPlan {
  truthByAsset: Map<AssetId, SceneTruthEntity[]>;
  detections: DetectionInstance[];
  truthCount: number;
}

export function buildRenderPlan(scene: ArenaSceneState, role: Role): RenderPlan {
  const truthByAsset = new Map<AssetId, SceneTruthEntity[]>();
  if (role === "analyst") {
    for (const entity of scene.truthEntities) {
      const group = truthByAsset.get(entity.assetId) ?? [];
      group.push(entity);
      truthByAsset.set(entity.assetId, group);
    }
  }

  return {
    truthByAsset,
    truthCount: role === "analyst" ? scene.truthEntities.length : 0,
    detections: scene.rawDetections.map((detection, index) => ({
      id: `${detection.sensorId}:${detection.truthEntityId}:${index}`,
      positionM: detection.positionM,
    })),
  };
}

export function countPlannedInstances(plan: RenderPlan): number {
  let count = plan.detections.length;
  for (const entities of plan.truthByAsset.values()) count += entities.length;
  return count;
}

export function usesInstancedTruth(truthCount: number, role: Role): boolean {
  return role === "analyst" && truthCount >= DETAIL_ENTITY_LIMIT;
}
