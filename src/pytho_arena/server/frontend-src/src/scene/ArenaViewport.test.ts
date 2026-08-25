import { describe, expect, it } from "vitest";
import * as THREE from "three";

import { setObjectAttitude } from "./ArenaViewport";

function expectVector(
  actual: THREE.Vector3,
  expected: readonly [number, number, number],
): void {
  expect(actual.x).toBeCloseTo(expected[0], 8);
  expect(actual.y).toBeCloseTo(expected[1], 8);
  expect(actual.z).toBeCloseTo(expected[2], 8);
}

describe("viewport object attitude", () => {
  it("keeps heading clockwise from north", () => {
    const object = new THREE.Object3D();
    setObjectAttitude(object, { heading: 90, pitch: 0, roll: 0 });

    const forward = new THREE.Vector3(0, 0, 1).applyQuaternion(
      object.quaternion,
    );
    expectVector(forward, [1, 0, 0]);
  });

  it("renders positive pitch as nose-up and positive roll as right-wing-down", () => {
    const pitched = new THREE.Object3D();
    setObjectAttitude(pitched, { heading: 0, pitch: 30, roll: 0 });
    const pitchedForward = new THREE.Vector3(0, 0, 1).applyQuaternion(
      pitched.quaternion,
    );
    expectVector(pitchedForward, [0, 0.5, Math.sqrt(3) / 2]);

    const rolled = new THREE.Object3D();
    setObjectAttitude(rolled, { heading: 0, pitch: 0, roll: 30 });
    const rolledRight = new THREE.Vector3(1, 0, 0).applyQuaternion(
      rolled.quaternion,
    );
    expectVector(rolledRight, [Math.sqrt(3) / 2, -0.5, 0]);
  });

  it("applies asset base yaw in model-local space after body attitude", () => {
    const object = new THREE.Object3D();
    setObjectAttitude(
      object,
      { heading: 0, pitch: 30, roll: 0 },
      Math.PI / 2,
    );

    const modelForward = new THREE.Vector3(0, 0, 1).applyQuaternion(
      object.quaternion,
    );
    expectVector(modelForward, [1, 0, 0]);
  });
});
