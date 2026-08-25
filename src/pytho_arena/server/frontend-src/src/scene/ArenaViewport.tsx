import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import type {
  ArenaSceneState,
  AssetId,
  AttitudeDeg,
  EnuPosition,
  SceneTrack,
  SceneTruthEntity,
} from "../arena";
import type { Role, Scenario } from "../app/types";
import {
  disposeDetailedAssets,
  loadDetailedAssets,
  type DetailedAsset,
  type DetailedAssetLibrary,
} from "./assetLibrary";
import { coastalSurfaceHeight, makeCoastalUrban } from "./coastalUrban";
import {
  environmentBlueprintKey,
  normalizeEnvironmentBlueprint,
  type EnvironmentBlueprint,
} from "./environmentBlueprint";
import { buildRenderPlan, usesInstancedTruth } from "./renderPlan";

const MAX_INSTANCES = 2_000;

type EventVisual = {
  id: string;
  group: THREE.Group;
  origin: THREE.Vector3;
  startMs: number;
  fire: THREE.Mesh;
  smoke: THREE.Mesh[];
  shockwave: THREE.Mesh;
  light: THREE.PointLight;
};

type Runtime = {
  environment: EnvironmentBlueprint["environment"];
  terrainHeight: (east: number, north: number) => number;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  controls: OrbitControls;
  truthMeshes: Map<AssetId, THREE.InstancedMesh>;
  detections: THREE.InstancedMesh;
  details: THREE.Group;
  detailObjects: Map<string, THREE.Object3D>;
  tactical: THREE.Group;
  tracks: THREE.Group;
  objectives: THREE.Group;
  effects: THREE.Group;
  airbaseAircraft: THREE.Group;
  eventVisuals: Map<string, EventVisual>;
  lastEffectSimTimeSec: number | null;
  focus: THREE.Group;
  groundEffectMaterial: THREE.ShaderMaterial;
  effectTextures: { fire: THREE.Texture; smoke: THREE.Texture };
  animationId: number;
  resizeObserver: ResizeObserver;
};

type ArenaViewportProps = {
  sceneState: ArenaSceneState | null;
  scenario: Scenario | null;
  role: Role;
  onFps: (fps: number) => void;
  selectedEntityId: string | null;
  focusRequest: { id: string; nonce: number } | null;
};

const dummy = new THREE.Object3D();
const color = new THREE.Color();
const EMPTY_TEMPLATES = new Map<AssetId, DetailedAsset>();
const attitudeEuler = new THREE.Euler();
const baseYawQuaternion = new THREE.Quaternion();
const upAxis = new THREE.Vector3(0, 1, 0);

export function setObjectAttitude(
  object: THREE.Object3D,
  attitudeDeg: AttitudeDeg,
  baseYaw = 0,
): void {
  attitudeEuler.set(
    THREE.MathUtils.degToRad(-attitudeDeg.pitch),
    THREE.MathUtils.degToRad(attitudeDeg.heading),
    THREE.MathUtils.degToRad(-attitudeDeg.roll),
    "YXZ",
  );
  object.quaternion.setFromEuler(attitudeEuler);
  if (baseYaw !== 0) {
    baseYawQuaternion.setFromAxisAngle(upAxis, baseYaw);
    object.quaternion.multiply(baseYawQuaternion);
  }
}

function droneGeometry(): THREE.BufferGeometry {
  const shape = new THREE.Shape();
  shape.moveTo(0, 8);
  shape.lineTo(-1.1, 1.7);
  shape.lineTo(-8.2, -1.4);
  shape.lineTo(-8, -2.6);
  shape.lineTo(-1.15, -1.8);
  shape.lineTo(-3.1, -6.2);
  shape.lineTo(0, -5.1);
  shape.lineTo(3.1, -6.2);
  shape.lineTo(1.15, -1.8);
  shape.lineTo(8, -2.6);
  shape.lineTo(8.2, -1.4);
  shape.lineTo(1.1, 1.7);
  shape.closePath();
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 0.8,
    bevelEnabled: true,
    bevelSize: 0.22,
    bevelThickness: 0.18,
    bevelSegments: 1,
  });
  geometry.center();
  geometry.rotateX(Math.PI / 2);
  return geometry;
}

function quadcopterGeometry(): THREE.BufferGeometry {
  const body = new THREE.SphereGeometry(1.45, 12, 8);
  body.scale(1.25, 0.62, 1.25);
  const armA = new THREE.BoxGeometry(8.8, 0.34, 0.5);
  armA.rotateY(Math.PI / 4);
  const armB = new THREE.BoxGeometry(8.8, 0.34, 0.5);
  armB.rotateY(-Math.PI / 4);
  const pieces: THREE.BufferGeometry[] = [body, armA, armB];
  for (const [east, north] of [
    [-3.1, -3.1],
    [-3.1, 3.1],
    [3.1, -3.1],
    [3.1, 3.1],
  ] as const) {
    const rotor = new THREE.TorusGeometry(1.55, 0.16, 6, 18);
    rotor.rotateX(Math.PI / 2);
    rotor.translate(east, 0.2, north);
    pieces.push(rotor);
  }
  const geometry = mergeGeometries(pieces, false);
  pieces.forEach((piece) => piece.dispose());
  if (!geometry) throw new Error("failed to create quadcopter geometry");
  return geometry;
}

function geometryFor(assetId: AssetId): THREE.BufferGeometry {
  switch (assetId) {
    case "uav_orion":
    case "mq_1l_usa":
      return droneGeometry();
    case "quadcopter_surrogate":
      return quadcopterGeometry();
    case "cargo_ship_liberty": {
      const geometry = new THREE.CapsuleGeometry(5.5, 23, 4, 10);
      geometry.rotateX(Math.PI / 2);
      geometry.scale(1, 0.62, 2.3);
      return geometry;
    }
    case "range_watch_tower":
      return new THREE.CylinderGeometry(1.1, 3, 18, 8);
    case "nasams_fcs":
      return new THREE.BoxGeometry(10, 4.5, 4.5);
  }
}

function materialFor(assetId: AssetId): THREE.MeshStandardMaterial {
  const base =
    assetId === "cargo_ship_liberty"
      ? 0xe0e5df
      : assetId === "range_watch_tower"
        ? 0xd0d9d1
        : assetId === "nasams_fcs"
          ? 0xc4cdbd
          : 0xe2e6e1;
  return new THREE.MeshStandardMaterial({
    color: base,
    roughness: 0.72,
    metalness: 0.04,
    emissive: 0x111714,
    emissiveIntensity: 0.24,
    vertexColors: true,
  });
}

function disposeTree(root: THREE.Object3D, disposeTextures = false): void {
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material)
      ? object.material
      : [object.material];
    materials.forEach((material) => {
      if (disposeTextures) {
        Object.values(material).forEach((value) => {
          if (value instanceof THREE.Texture) value.dispose();
        });
      }
      material.dispose();
    });
  });
}

function factionColor(factionId: string, scenario: Scenario): string {
  return (
    scenario.factions.find((faction) => faction.id === factionId)?.color ??
    "#c6d3cb"
  );
}

function positionObject(
  object: THREE.Object3D,
  position: EnuPosition,
  attitudeDeg: AttitudeDeg,
  heightAt = terrainHeight,
  baseYaw = 0,
): void {
  const up =
    position.up <= 5
      ? position.up + heightAt(position.east, position.north)
      : position.up;
  object.position.set(position.east, up, position.north);
  setObjectAttitude(object, attitudeDeg, baseYaw);
}

function terrainHeight(east: number, north: number): number {
  const distance = Math.hypot(east, north);
  const desertUndulation =
    Math.sin(east * 0.012 + north * 0.006) * 0.7 +
    Math.cos(east * 0.021 - north * 0.017) * 0.35;
  const westRidge =
    18 * Math.exp(-(((east + 610) / 190) ** 2 + ((north - 160) / 330) ** 2));
  const northRidge =
    11 * Math.exp(-(((east - 170) / 430) ** 2 + ((north - 650) / 150) ** 2));
  const distantRise = THREE.MathUtils.smoothstep(distance, 700, 2_600) * 24;
  const drainage =
    -1.2 *
    Math.exp(-(((north + 360) / 32) ** 2)) *
    (0.35 + 0.65 * Math.sin(east * 0.018) ** 2);
  const desert =
    3.2 + desertUndulation + westRidge + northRidge + distantRise + drainage;
  const flatEast = 1 - THREE.MathUtils.smoothstep(Math.abs(east), 500, 680);
  const flatNorth =
    1 - THREE.MathUtils.smoothstep(Math.abs(north - 80), 280, 420);
  return THREE.MathUtils.lerp(desert, 3.2, flatEast * flatNorth);
}

function makeAirBase(scene: THREE.Scene): {
  groundEffectMaterial: THREE.ShaderMaterial;
  airbaseAircraft: THREE.Group;
} {
  const texture = new THREE.TextureLoader().load(
    `${import.meta.env.BASE_URL}assets/gulf_arid_terrain_albedo.jpg`,
  );
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(24, 24);
  texture.center.set(0.5, 0.5);
  texture.rotation = 0.12;
  texture.anisotropy = 8;

  const geometry = new THREE.PlaneGeometry(7_000, 7_000, 144, 144);
  const positions = geometry.attributes.position;
  const colors: number[] = [];
  for (let index = 0; index < positions.count; index += 1) {
    const x = positions.getX(index);
    const y = positions.getY(index);
    const height = terrainHeight(x, -y);
    positions.setZ(index, height);
    const high = THREE.MathUtils.smoothstep(height, 7, 22);
    const terrainColor = new THREE.Color(0xb8a06f).lerp(
      new THREE.Color(0x75664e),
      high * 0.56,
    );
    colors.push(terrainColor.r, terrainColor.g, terrainColor.b);
  }
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  geometry.rotateX(-Math.PI / 2);
  const ground = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      vertexColors: true,
      roughness: 0.97,
      metalness: 0,
    }),
  );
  ground.receiveShadow = true;
  scene.add(ground);

  const airbase = new THREE.Group();
  scene.add(airbase);
  const elevation = terrainHeight(0, 0);
  const runwayMaterial = new THREE.MeshStandardMaterial({
    color: 0x383b3c,
    roughness: 0.94,
  });
  const taxiMaterial = new THREE.MeshStandardMaterial({
    color: 0x4a4b49,
    roughness: 0.92,
  });
  const apronMaterial = new THREE.MeshStandardMaterial({
    color: 0x8f8c82,
    roughness: 0.95,
  });
  const concreteMaterial = new THREE.MeshStandardMaterial({
    color: 0xbdb293,
    roughness: 0.91,
  });
  const buildingMaterial = new THREE.MeshStandardMaterial({
    color: 0x9f8f6d,
    roughness: 0.88,
  });
  const hangarMaterial = new THREE.MeshStandardMaterial({
    color: 0x9da29e,
    roughness: 0.73,
    metalness: 0.14,
  });
  const darkMaterial = new THREE.MeshStandardMaterial({
    color: 0x2e3436,
    roughness: 0.78,
    metalness: 0.12,
  });
  const safetyMaterial = new THREE.MeshStandardMaterial({
    color: 0xd9a441,
    roughness: 0.78,
  });

  const addBox = (
    size: [number, number, number],
    position: [number, number, number],
    material: THREE.Material,
    parent = airbase,
  ): THREE.Mesh => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
    mesh.position.set(...position);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  };

  addBox([2_600, 1.1, 46], [0, elevation + 0.45, -68], runwayMaterial);
  addBox([2_430, 0.8, 24], [0, elevation + 0.55, 52], taxiMaterial);
  for (const east of [-920, -360, 110, 760]) {
    addBox([28, 0.75, 98], [east, elevation + 0.58, -8], taxiMaterial);
    addBox([3, 0.12, 94], [east, elevation + 1, -8], safetyMaterial);
    addBox([28, 0.13, 1.2], [east, elevation + 1.03, 32], safetyMaterial);
    addBox([28, 0.13, 1.2], [east, elevation + 1.04, 27], safetyMaterial);
  }
  addBox([355, 0.9, 195], [255, elevation + 0.58, 175], apronMaterial);
  addBox([330, 0.9, 190], [-300, elevation + 0.58, 175], apronMaterial);
  addBox([1_240, 0.7, 18], [0, elevation + 0.48, 320], taxiMaterial);

  const markingMaterial = new THREE.MeshBasicMaterial({
    color: 0xe7e3d5,
    toneMapped: false,
  });
  for (let east = -1_160; east <= 1_160; east += 76) {
    addBox([34, 0.12, 1.2], [east, elevation + 1.08, -68], markingMaterial);
  }
  for (const east of [-1_260, 1_260]) {
    for (let offset = -15; offset <= 15; offset += 6) {
      addBox(
        [42, 0.12, 2.3],
        [east, elevation + 1.09, -68 + offset],
        markingMaterial,
      );
    }
  }
  addBox([2_550, 0.11, 0.65], [0, elevation + 0.98, -44.5], markingMaterial);
  addBox([2_550, 0.11, 0.65], [0, elevation + 0.98, -91.5], markingMaterial);
  addBox([2_390, 0.12, 0.8], [0, elevation + 1, 52], safetyMaterial);

  const jointMaterial = new THREE.MeshBasicMaterial({
    color: 0x6f706b,
    transparent: true,
    opacity: 0.34,
  });
  for (let east = 90; east <= 420; east += 42) {
    addBox([0.45, 0.1, 187], [east, elevation + 1.08, 175], jointMaterial);
  }
  for (let north = 96; north <= 254; north += 38) {
    addBox([345, 0.1, 0.45], [255, elevation + 1.09, north], jointMaterial);
  }
  for (const east of [96, 180, 264, 348]) {
    addBox([1.2, 0.13, 80], [east, elevation + 1.1, 126], safetyMaterial);
    addBox([14, 0.13, 1.2], [east, elevation + 1.1, 166], safetyMaterial);
  }

  const runwayLightMaterial = new THREE.MeshStandardMaterial({
    color: 0xf3f1d8,
    emissive: 0xf3f1d8,
    emissiveIntensity: 3.8,
  });
  const taxiLightMaterial = new THREE.MeshStandardMaterial({
    color: 0x4b8fce,
    emissive: 0x4b8fce,
    emissiveIntensity: 4.5,
  });
  const lightGeometry = new THREE.SphereGeometry(0.65, 8, 6);
  const runwayLights = new THREE.InstancedMesh(
    lightGeometry,
    runwayLightMaterial,
    128,
  );
  const taxiLights = new THREE.InstancedMesh(
    lightGeometry,
    taxiLightMaterial,
    128,
  );
  let runwayLightIndex = 0;
  let taxiLightIndex = 0;
  for (let east = -1_260; east <= 1_260; east += 44) {
    for (const north of [-92, -44]) {
      dummy.position.set(east, elevation + 1.7, north);
      dummy.scale.setScalar(1);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      runwayLights.setMatrixAt(runwayLightIndex, dummy.matrix);
      runwayLightIndex += 1;
    }
    for (const north of [39, 65]) {
      dummy.position.set(east, elevation + 1.5, north);
      dummy.updateMatrix();
      taxiLights.setMatrixAt(taxiLightIndex, dummy.matrix);
      taxiLightIndex += 1;
    }
  }
  runwayLights.count = runwayLightIndex;
  taxiLights.count = taxiLightIndex;
  airbase.add(runwayLights, taxiLights);

  const makeHangar = (east: number, north: number): void => {
    const width = 160;
    const depth = 76;
    const wallHeight = 26;
    const profile = new THREE.Shape();
    profile.moveTo(-width / 2, 0);
    profile.lineTo(-width / 2, wallHeight);
    profile.quadraticCurveTo(0, wallHeight + 22, width / 2, wallHeight);
    profile.lineTo(width / 2, 0);
    profile.closePath();
    const shell = new THREE.Mesh(
      new THREE.ExtrudeGeometry(profile, {
        depth,
        bevelEnabled: false,
        curveSegments: 16,
      }),
      hangarMaterial,
    );
    shell.position.set(east, elevation, north - depth / 2);
    shell.castShadow = true;
    shell.receiveShadow = true;
    airbase.add(shell);
    addBox(
      [138, 23, 1.4],
      [east, elevation + 12, north - depth / 2 - 0.9],
      darkMaterial,
    );
    for (const offset of [-52, -26, 0, 26, 52]) {
      addBox(
        [1, 22, 1.1],
        [east + offset, elevation + 11, north - depth / 2 - 1.8],
        hangarMaterial,
      );
    }
    for (const offset of [-48, 0, 48]) {
      addBox(
        [12, 2.5, 10],
        [east + offset, elevation + 43, north + 5],
        darkMaterial,
      );
    }
  };
  for (const [east, north] of [
    [-300, 270],
    [-115, 270],
  ] as const) {
    makeHangar(east, north);
  }

  for (const [east, north] of [
    [96, 155],
    [180, 155],
    [264, 155],
    [96, 230],
    [180, 230],
    [264, 230],
  ] as const) {
    const roofProfile = new THREE.Shape();
    roofProfile.moveTo(-29, 0);
    roofProfile.quadraticCurveTo(0, 10, 29, 0);
    roofProfile.lineTo(26, -1.6);
    roofProfile.quadraticCurveTo(0, 6.6, -26, -1.6);
    roofProfile.closePath();
    const roof = new THREE.Mesh(
      new THREE.ExtrudeGeometry(roofProfile, {
        depth: 38,
        bevelEnabled: false,
        curveSegments: 12,
      }),
      concreteMaterial,
    );
    roof.position.set(east, elevation + 13, north - 19);
    roof.castShadow = true;
    roof.receiveShadow = true;
    airbase.add(roof);
    for (const offsetEast of [-25, 25]) {
      for (const offsetNorth of [-16, 16]) {
        addBox(
          [1.3, 13, 1.3],
          [east + offsetEast, elevation + 6.5, north + offsetNorth],
          darkMaterial,
        );
      }
    }
    addBox(
      [54, 2.2, 1.2],
      [east, elevation + 1.7, north + 21],
      buildingMaterial,
    );
  }

  for (const [east, north, width, depth, height] of [
    [355, 330, 92, 58, 18],
    [455, 330, 74, 52, 16],
    [370, 410, 110, 44, 14],
    [495, 410, 88, 44, 14],
    [255, 405, 84, 50, 13],
    [-430, 320, 112, 64, 18],
  ] as const) {
    addBox(
      [width, height, depth],
      [east, elevation + height / 2, north],
      buildingMaterial,
    );
    addBox(
      [width + 5, 1.4, depth + 5],
      [east, elevation + height + 0.7, north],
      concreteMaterial,
    );
  }

  const tower = new THREE.Group();
  addBox([15, 54, 15], [430, elevation + 27, 230], concreteMaterial, tower);
  addBox([31, 9, 31], [430, elevation + 57, 230], darkMaterial, tower);
  addBox([2, 16, 2], [430, elevation + 69, 230], darkMaterial, tower);
  airbase.add(tower);

  for (const east of [510, 545]) {
    const tank = new THREE.Mesh(
      new THREE.CylinderGeometry(12, 12, 20, 24),
      new THREE.MeshStandardMaterial({ color: 0xc8c5b8, roughness: 0.78 }),
    );
    tank.position.set(east, elevation + 10, 475);
    tank.castShadow = true;
    airbase.add(tank);
  }

  for (const east of [-440, -300, -150, 40, 220, 410]) {
    addBox([1.4, 34, 1.4], [east, elevation + 17, 112], darkMaterial);
    addBox([8, 1.2, 3], [east, elevation + 34, 112], runwayLightMaterial);
  }

  for (let index = 0; index < 14; index += 1) {
    const east = -430 + (index % 7) * 46;
    const north = 135 + Math.floor(index / 7) * 62;
    addBox(
      [18, 4.2, 7],
      [east, elevation + 2.7, north],
      index % 3 === 0 ? safetyMaterial : darkMaterial,
    );
  }
  for (let index = 0; index < 18; index += 1) {
    const east = -435 + (index % 9) * 32;
    const north = 245 + Math.floor(index / 9) * 22;
    addBox([12, 2.8, 8], [east, elevation + 2, north], concreteMaterial);
  }

  const makeHeavyAircraft = (length: number, wingSpan: number): THREE.Group => {
    const aircraft = new THREE.Group();
    const aircraftMaterial = new THREE.MeshStandardMaterial({
      color: 0x858f92,
      roughness: 0.58,
      metalness: 0.2,
    });
    const cockpitMaterial = new THREE.MeshStandardMaterial({
      color: 0x1b2c32,
      roughness: 0.28,
      metalness: 0.32,
    });
    const engineMaterial = new THREE.MeshStandardMaterial({
      color: 0x5f696c,
      roughness: 0.48,
      metalness: 0.38,
    });
    const fuselage = new THREE.Mesh(
      new THREE.CapsuleGeometry(3.7, length - 7.4, 8, 18),
      aircraftMaterial,
    );
    fuselage.rotation.z = Math.PI / 2;
    fuselage.castShadow = true;
    aircraft.add(fuselage);

    const wingShape = new THREE.Shape();
    wingShape.moveTo(-length * 0.18, 0);
    wingShape.lineTo(length * 0.08, wingSpan / 2);
    wingShape.lineTo(length * 0.2, wingSpan / 2);
    wingShape.lineTo(length * 0.12, 0);
    wingShape.lineTo(length * 0.2, -wingSpan / 2);
    wingShape.lineTo(length * 0.08, -wingSpan / 2);
    wingShape.closePath();
    const wing = new THREE.Mesh(
      new THREE.ShapeGeometry(wingShape),
      aircraftMaterial,
    );
    wing.rotation.x = -Math.PI / 2;
    wing.position.y = 0.25;
    wing.castShadow = true;
    aircraft.add(wing);

    const tailShape = new THREE.Shape();
    tailShape.moveTo(length * 0.31, 0);
    tailShape.lineTo(length * 0.43, wingSpan * 0.2);
    tailShape.lineTo(length * 0.5, wingSpan * 0.2);
    tailShape.lineTo(length * 0.45, 0);
    tailShape.lineTo(length * 0.5, -wingSpan * 0.2);
    tailShape.lineTo(length * 0.43, -wingSpan * 0.2);
    tailShape.closePath();
    const tailPlane = new THREE.Mesh(
      new THREE.ShapeGeometry(tailShape),
      aircraftMaterial,
    );
    tailPlane.rotation.x = -Math.PI / 2;
    tailPlane.position.y = 1.4;
    tailPlane.castShadow = true;
    aircraft.add(tailPlane);

    const finShape = new THREE.Shape();
    finShape.moveTo(length * 0.34, 1.8);
    finShape.lineTo(length * 0.45, 11.5);
    finShape.lineTo(length * 0.49, 2);
    finShape.closePath();
    const fin = new THREE.Mesh(
      new THREE.ShapeGeometry(finShape),
      aircraftMaterial,
    );
    fin.position.z = -0.15;
    fin.castShadow = true;
    aircraft.add(fin);

    const cockpit = new THREE.Mesh(
      new THREE.SphereGeometry(3.2, 16, 10),
      cockpitMaterial,
    );
    cockpit.scale.set(1.7, 0.42, 0.82);
    cockpit.position.set(-length * 0.35, 2.1, 0);
    cockpit.castShadow = true;
    aircraft.add(cockpit);
    for (const x of [-length * 0.04, length * 0.12]) {
      for (const z of [-wingSpan * 0.21, wingSpan * 0.21]) {
        const engine = new THREE.Mesh(
          new THREE.CylinderGeometry(2.2, 1.8, 9, 14),
          engineMaterial,
        );
        engine.rotation.z = Math.PI / 2;
        engine.position.set(x, -0.8, z);
        engine.castShadow = true;
        aircraft.add(engine);
      }
    }
    return aircraft;
  };
  const tanker = makeHeavyAircraft(74, 66);
  tanker.position.set(-365, elevation + 6.2, 155);
  airbase.add(tanker);
  const transport = makeHeavyAircraft(62, 52);
  transport.position.set(-205, elevation + 5.7, 208);
  airbase.add(transport);

  const scrubGeometry = new THREE.ConeGeometry(1.4, 2.8, 6);
  const scrubMaterial = new THREE.MeshStandardMaterial({
    color: 0x6f6a46,
    roughness: 1,
  });
  const scrub = new THREE.InstancedMesh(scrubGeometry, scrubMaterial, 260);
  let scrubIndex = 0;
  for (let index = 0; index < 520 && scrubIndex < 260; index += 1) {
    const east = Math.sin(index * 42.71) * 1_450 + Math.sin(index * 4.31) * 190;
    const north =
      Math.cos(index * 31.19) * 1_250 + Math.cos(index * 2.17) * 240;
    if (Math.abs(east) < 1_420 && north > -130 && north < 510) continue;
    dummy.position.set(east, terrainHeight(east, north) + 0.8, north);
    dummy.rotation.set(0, index * 0.79, 0);
    const scale = 0.45 + (index % 7) * 0.12;
    dummy.scale.set(scale, scale * 0.7, scale);
    dummy.updateMatrix();
    scrub.setMatrixAt(scrubIndex, dummy.matrix);
    scrubIndex += 1;
  }
  scrub.count = scrubIndex;
  scrub.castShadow = true;
  airbase.add(scrub);

  const airbaseAircraft = new THREE.Group();
  airbase.add(airbaseAircraft);

  const groundEffectMaterial = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    uniforms: {
      time: { value: 0 },
      hazeColor: { value: new THREE.Color(0xe1bd87) },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float time;
      uniform vec3 hazeColor;
      varying vec2 vUv;
      void main() {
        float band = sin(vUv.y * 110.0 + time * 2.2 + sin(vUv.x * 35.0) * 1.4);
        float alpha = (0.018 + max(0.0, band) * 0.018) * smoothstep(0.0, 0.2, vUv.y);
        gl_FragColor = vec4(hazeColor, alpha);
      }
    `,
  });
  const heatHaze = new THREE.Mesh(
    new THREE.PlaneGeometry(860, 58),
    groundEffectMaterial,
  );
  heatHaze.rotation.x = -Math.PI / 2;
  heatHaze.position.set(0, elevation + 2.1, -68);
  heatHaze.renderOrder = 2;
  airbase.add(heatHaze);

  return { groundEffectMaterial, airbaseAircraft };
}

function createRuntime(
  host: HTMLDivElement,
  onFps: (fps: number) => void,
  blueprint: EnvironmentBlueprint,
): Runtime {
  const isCoastal = blueprint.environment === "coastal_urban";
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(isCoastal ? 0x78949b : 0x8ca5ad);
  scene.fog = new THREE.FogExp2(
    isCoastal ? 0x91a39f : 0xb99f7f,
    isCoastal ? 0.00042 : 0.0003,
  );

  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(7_500, 32, 18),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: {
        horizonColor: {
          value: new THREE.Color(isCoastal ? 0xb4b9ae : 0xd0b891),
        },
        zenithColor: {
          value: new THREE.Color(isCoastal ? 0x315e6b : 0x234c68),
        },
        hazeColor: { value: new THREE.Color(isCoastal ? 0xc5bda8 : 0xd8bd98) },
      },
      vertexShader: `
        varying vec3 vWorldPosition;
        void main() {
          vec4 worldPosition = modelMatrix * vec4(position, 1.0);
          vWorldPosition = worldPosition.xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 horizonColor;
        uniform vec3 zenithColor;
        uniform vec3 hazeColor;
        varying vec3 vWorldPosition;
        void main() {
          vec3 direction = normalize(vWorldPosition);
          float heightMix = smoothstep(-0.03, 0.13, direction.y);
          float warmHaze = pow(max(0.0, 1.0 - abs(direction.y)), 6.0) * 0.18;
          vec3 skyColor = mix(horizonColor, zenithColor, heightMix);
          gl_FragColor = vec4(mix(skyColor, hazeColor, warmHaze), 1.0);
        }
      `,
    }),
  );
  sky.frustumCulled = false;
  scene.add(sky);

  const camera = new THREE.PerspectiveCamera(44, 1, 0.5, 12_000);
  if (isCoastal) camera.position.set(820, 310, -820);
  else camera.position.set(620, 245, -560);

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.88;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  host.append(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  if (isCoastal) controls.target.set(170, 24, -40);
  else controls.target.set(115, 17, 145);
  controls.enableDamping = true;
  controls.dampingFactor = 0.065;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minDistance = 180;
  controls.maxDistance = 1_800;

  scene.add(
    new THREE.HemisphereLight(
      isCoastal ? 0xd5e2df : 0xd9e3df,
      isCoastal ? 0x455653 : 0x67543c,
      1.35,
    ),
  );
  scene.add(new THREE.AmbientLight(isCoastal ? 0x889b96 : 0xa3937e, 0.18));
  const sun = new THREE.DirectionalLight(
    isCoastal ? 0xffe5bd : 0xffddb0,
    isCoastal ? 3.8 : 4.4,
  );
  if (isCoastal) sun.position.set(-520, 420, -680);
  else sun.position.set(-760, 330, -420);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -750;
  sun.shadow.camera.right = 750;
  sun.shadow.camera.top = 750;
  sun.shadow.camera.bottom = -750;
  scene.add(sun);
  const cameraFill = new THREE.DirectionalLight(
    isCoastal ? 0xa9cdd0 : 0xaec9d1,
    0.62,
  );
  cameraFill.position.set(460, 280, 620);
  scene.add(cameraFill);
  let airbaseAircraft: THREE.Group;
  let groundEffectMaterial: THREE.ShaderMaterial;
  let heightAt: (east: number, north: number) => number;
  if (isCoastal) {
    airbaseAircraft = new THREE.Group();
    scene.add(airbaseAircraft);
    groundEffectMaterial = makeCoastalUrban(scene, blueprint.staticAssets);
    heightAt = coastalSurfaceHeight;
  } else {
    const airbase = makeAirBase(scene);
    groundEffectMaterial = airbase.groundEffectMaterial;
    airbaseAircraft = airbase.airbaseAircraft;
    heightAt = terrainHeight;
  }

  const truthMeshes = new Map<AssetId, THREE.InstancedMesh>();
  for (const assetId of [
    "uav_orion",
    "mq_1l_usa",
    "quadcopter_surrogate",
    "cargo_ship_liberty",
    "range_watch_tower",
    "nasams_fcs",
  ] as AssetId[]) {
    const mesh = new THREE.InstancedMesh(
      geometryFor(assetId),
      materialFor(assetId),
      MAX_INSTANCES,
    );
    mesh.count = 0;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    truthMeshes.set(assetId, mesh);
    scene.add(mesh);
  }

  const detectionGeometry = new THREE.TorusGeometry(7, 0.72, 6, 24);
  detectionGeometry.rotateX(Math.PI / 2);
  const detections = new THREE.InstancedMesh(
    detectionGeometry,
    new THREE.MeshBasicMaterial({ color: 0x9ee9ff, toneMapped: false }),
    MAX_INSTANCES,
  );
  detections.count = 0;
  detections.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(detections);

  const details = new THREE.Group();
  const tactical = new THREE.Group();
  const tracks = new THREE.Group();
  const objectives = new THREE.Group();
  const effects = new THREE.Group();
  const focus = new THREE.Group();
  scene.add(details, tactical, tracks, objectives, effects, focus);
  const textureLoader = new THREE.TextureLoader();
  const effectTextures = {
    fire: textureLoader.load(
      `${import.meta.env.BASE_URL}assets/explosion_vfx.png`,
    ),
    smoke: textureLoader.load(
      `${import.meta.env.BASE_URL}assets/explosion_smoke_vfx.png`,
    ),
  };
  effectTextures.fire.colorSpace = THREE.SRGBColorSpace;
  effectTextures.smoke.colorSpace = THREE.SRGBColorSpace;

  const resize = () => {
    const { width, height } = host.getBoundingClientRect();
    renderer.setSize(Math.max(1, width), Math.max(1, height), false);
    camera.aspect = Math.max(1, width) / Math.max(1, height);
    camera.updateProjectionMatrix();
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);
  resize();

  let frames = 0;
  let sampleStart = performance.now();
  let animationId = 0;
  const animate = (now: number) => {
    controls.update();
    groundEffectMaterial.uniforms.time.value = now / 1_000;
    animateEventVisuals(runtime, now);
    renderer.render(scene, camera);
    frames += 1;
    if (now - sampleStart >= 1_000) {
      onFps((frames * 1_000) / (now - sampleStart));
      frames = 0;
      sampleStart = now;
    }
    animationId = requestAnimationFrame(animate);
  };
  animationId = requestAnimationFrame(animate);

  const runtime: Runtime = {
    environment: blueprint.environment,
    terrainHeight: heightAt,
    scene,
    camera,
    renderer,
    controls,
    truthMeshes,
    detections,
    details,
    detailObjects: new Map(),
    tactical,
    tracks,
    objectives,
    effects,
    airbaseAircraft,
    eventVisuals: new Map(),
    lastEffectSimTimeSec: null,
    focus,
    groundEffectMaterial,
    effectTextures,
    animationId,
    resizeObserver,
  };
  return runtime;
}

function clearGroup(group: THREE.Group): void {
  while (group.children.length) group.remove(group.children[0]);
}

function clearDisposableGroup(
  group: THREE.Group,
  disposeTextures = false,
): void {
  group.children.forEach((child) => disposeTree(child, disposeTextures));
  clearGroup(group);
}

function makeLabel(
  text: string,
  colorValue: string,
  width = 72,
  height = 11,
): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 384;
  canvas.height = 64;
  const context = canvas.getContext("2d")!;
  context.fillStyle = "rgba(11,17,21,.88)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = colorValue;
  context.lineWidth = 3;
  context.strokeRect(1.5, 1.5, canvas.width - 3, canvas.height - 3);
  context.fillStyle = "#c6d3cb";
  context.font = "700 22px monospace";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text.toUpperCase(), canvas.width / 2, canvas.height / 2);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map, depthTest: false }),
  );
  sprite.scale.set(width, height, 1);
  sprite.renderOrder = 20;
  return sprite;
}

function blackKeyMaterial(
  texture: THREE.Texture,
  featherEdges: boolean,
): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    depthWrite: false,
    transparent: true,
    uniforms: {
      map: { value: texture },
      opacity: { value: 0 },
      brightness: { value: 1 },
      featherEdges: { value: featherEdges ? 1 : 0 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D map;
      uniform float opacity;
      uniform float brightness;
      uniform float featherEdges;
      varying vec2 vUv;
      void main() {
        vec3 color = texture2D(map, vUv).rgb;
        float intensity = max(color.r, max(color.g, color.b));
        vec2 centered = abs(vUv * 2.0 - 1.0);
        float horizontalFeather = 1.0 - smoothstep(0.72, 1.0, centered.x);
        float verticalFeather = 1.0 - smoothstep(0.70, 1.0, centered.y);
        float edgeMask = mix(1.0, horizontalFeather * verticalFeather, featherEdges);
        float alphaStart = mix(0.012, 0.001, featherEdges);
        float alphaEnd = mix(0.16, 0.018, featherEdges);
        float alpha = smoothstep(alphaStart, alphaEnd, intensity) * opacity * edgeMask;
        if (alpha < 0.012) discard;
        vec3 smokeLift = mix(vec3(0.0), vec3(0.055), featherEdges);
        gl_FragColor = vec4(color * brightness + smokeLift, alpha);
      }
    `,
  });
}

function createEventVisual(
  runtime: Runtime,
  event: ArenaSceneState["events"][number],
): EventVisual {
  const origin = new THREE.Vector3(
    event.positionM.east,
    event.positionM.up + 8,
    event.positionM.north,
  );
  const group = new THREE.Group();
  const fire = new THREE.Mesh(
    new THREE.PlaneGeometry(48, 48),
    blackKeyMaterial(runtime.effectTextures.fire, false),
  );
  fire.position.copy(origin);
  fire.renderOrder = 24;
  group.add(fire);
  const smoke = [
    { delay: 0, x: -8, z: 4, rotation: -0.12, scale: 0.88, rise: 8.2 },
    { delay: 0.18, x: 7, z: -5, rotation: 0.16, scale: 1, rise: 9.4 },
    { delay: 0.36, x: 1, z: 8, rotation: -0.24, scale: 0.74, rise: 10.6 },
  ].map((settings, index) => {
    const plate = new THREE.Mesh(
      new THREE.PlaneGeometry(58, 58),
      blackKeyMaterial(runtime.effectTextures.smoke, true),
    );
    plate.position.copy(origin);
    plate.visible = false;
    plate.renderOrder = 23 - index;
    Object.assign(plate.userData, settings);
    group.add(plate);
    return plate;
  });
  const shockwave = new THREE.Mesh(
    new THREE.RingGeometry(9, 11, 64),
    new THREE.MeshBasicMaterial({
      color: 0xffd29b,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  shockwave.rotation.x = -Math.PI / 2;
  shockwave.position.copy(origin);
  shockwave.renderOrder = 22;
  group.add(shockwave);
  const light = new THREE.PointLight(
    event.eventType === "attack" ? 0xe35d50 : 0xffb76b,
    0,
    110,
    2,
  );
  light.position.copy(origin);
  group.add(light);
  runtime.effects.add(group);
  return {
    id: event.id,
    group,
    origin,
    startMs: performance.now(),
    fire,
    smoke,
    shockwave,
    light,
  };
}

function animateEventVisuals(runtime: Runtime, now: number): void {
  for (const [id, visual] of runtime.eventVisuals) {
    const age = (now - visual.startMs) / 1_000;
    const fireMaterial = visual.fire.material as THREE.ShaderMaterial;
    visual.fire.quaternion.copy(runtime.camera.quaternion);
    const fireScale = 0.4 + Math.min(1, age * 3.6) * 0.9;
    visual.fire.scale.set(
      fireScale,
      fireScale * (1 + Math.min(0.2, age * 0.08)),
      fireScale,
    );
    visual.fire.position.copy(visual.origin);
    visual.fire.position.y += Math.min(13, age * 3.2);
    fireMaterial.uniforms.opacity.value = Math.max(
      0,
      Math.min(1, age * 10) * (1 - Math.max(0, age - 0.75) / 1.25),
    );
    fireMaterial.uniforms.brightness.value = Math.max(0.64, 1.14 - age * 0.2);
    const shockwaveMaterial = visual.shockwave
      .material as THREE.MeshBasicMaterial;
    const shockwaveAge = Math.min(1, age / 0.85);
    visual.shockwave.scale.setScalar(0.5 + shockwaveAge * 4.8);
    shockwaveMaterial.opacity = Math.max(0, 0.46 * (1 - shockwaveAge));
    visual.smoke.forEach((plate) => {
      const smokeAge = Math.max(0, age - 0.3 - Number(plate.userData.delay));
      plate.visible = smokeAge > 0;
      plate.quaternion.copy(runtime.camera.quaternion);
      plate.rotateZ(
        Number(plate.userData.rotation) + Math.sin(smokeAge * 0.42) * 0.025,
      );
      const layerScale = Number(plate.userData.scale);
      const smokeScale =
        layerScale * (0.42 + Math.min(1, smokeAge * 0.62) * 0.94);
      plate.scale.set(
        smokeScale,
        smokeScale * (1.04 + Math.min(0.42, smokeAge * 0.12)),
        smokeScale,
      );
      plate.position.copy(visual.origin);
      plate.position.x += Number(plate.userData.x);
      plate.position.z += Number(plate.userData.z);
      plate.position.y += Math.min(48, smokeAge * Number(plate.userData.rise));
      const material = plate.material as THREE.ShaderMaterial;
      material.uniforms.opacity.value = Math.max(
        0,
        Math.min(0.72, smokeAge * 1.35) * (1 - smokeAge / 6.4),
      );
      material.uniforms.brightness.value = 1.72;
    });
    visual.light.intensity = Math.max(0, 55 * (1 - age * 4.8));
    if (age <= 8) continue;
    runtime.effects.remove(visual.group);
    disposeTree(visual.group);
    runtime.eventVisuals.delete(id);
  }
}

function updateTactical(
  runtime: Runtime,
  scene: ArenaSceneState,
  scenario: Scenario,
): void {
  clearDisposableGroup(runtime.tactical, true);
  for (const sensor of scene.sensors) {
    const sensorColor = new THREE.Color(
      factionColor(sensor.factionId, scenario),
    );
    const wedge = new THREE.Mesh(
      new THREE.RingGeometry(
        8,
        sensor.rangeM,
        72,
        1,
        0,
        THREE.MathUtils.degToRad(sensor.fovDegrees),
      ),
      new THREE.MeshBasicMaterial({
        color: sensorColor,
        transparent: true,
        opacity: 0.045,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    wedge.rotation.x = -Math.PI / 2;
    wedge.rotation.z =
      -THREE.MathUtils.degToRad(sensor.attitudeDeg.heading) -
      Math.PI / 2 -
      THREE.MathUtils.degToRad(sensor.fovDegrees) / 2;
    wedge.position.set(
      sensor.positionM.east,
      runtime.terrainHeight(sensor.positionM.east, sensor.positionM.north) +
        0.8,
      sensor.positionM.north,
    );
    runtime.tactical.add(wedge);
    const sensorRing = new THREE.Mesh(
      new THREE.RingGeometry(5.2, 6.4, 28),
      new THREE.MeshBasicMaterial({
        color: sensorColor,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
      }),
    );
    sensorRing.rotation.x = -Math.PI / 2;
    sensorRing.position.set(
      sensor.positionM.east,
      runtime.terrainHeight(sensor.positionM.east, sensor.positionM.north) + 1,
      sensor.positionM.north,
    );
    runtime.tactical.add(sensorRing);
    const label = makeLabel(sensor.id, `#${sensorColor.getHexString()}`);
    label.position.set(
      sensor.positionM.east,
      runtime.terrainHeight(sensor.positionM.east, sensor.positionM.north) + 27,
      sensor.positionM.north,
    );
    runtime.tactical.add(label);
  }
  for (const response of scene.responses) {
    const responseColor = new THREE.Color(
      factionColor(response.factionId, scenario),
    );
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(
        response.engagementRangeM - 1.1,
        response.engagementRangeM,
        96,
      ),
      new THREE.MeshBasicMaterial({
        color: responseColor,
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(
      response.positionM.east,
      runtime.terrainHeight(response.positionM.east, response.positionM.north) +
        1.2,
      response.positionM.north,
    );
    runtime.tactical.add(ring);
    const label = makeLabel(response.id, `#${responseColor.getHexString()}`);
    label.position.set(
      response.positionM.east,
      runtime.terrainHeight(response.positionM.east, response.positionM.north) +
        20,
      response.positionM.north,
    );
    runtime.tactical.add(label);
  }
}

function updateObjectives(
  runtime: Runtime,
  scene: ArenaSceneState,
  scenario: Scenario,
): void {
  clearDisposableGroup(runtime.objectives, true);
  for (const zone of scenario.protected_zones) {
    const east =
      (zone.center[0] - scene.originWorld[0]) * scene.metersPerWorldUnit;
    const north =
      (zone.center[1] - scene.originWorld[1]) * scene.metersPerWorldUnit;
    const radius = zone.radius * scene.metersPerWorldUnit;
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(radius - 2.2, radius, 96),
      new THREE.MeshBasicMaterial({
        color: 0xd9a441,
        transparent: true,
        opacity: 0.82,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    const groundY = runtime.terrainHeight(east, north);
    ring.position.set(east, groundY + 1.4, north);
    runtime.objectives.add(ring);

    if (scenario.scenario_id === "strait-sentinel-airbase") {
      const label = makeLabel(
        "Raven airfield",
        "#d9a441",
        48,
        6.5,
      );
      label.position.set(east, groundY + 42, north);
      runtime.objectives.add(label);
      continue;
    }

    const facility = new THREE.Group();
    const padMaterial = new THREE.MeshStandardMaterial({
      color: 0x55574f,
      roughness: 0.9,
    });
    const wallMaterial = new THREE.MeshStandardMaterial({
      color: 0x8d8977,
      roughness: 0.82,
    });
    const roofMaterial = new THREE.MeshStandardMaterial({
      color: 0x4c534f,
      roughness: 0.7,
      metalness: 0.16,
    });
    const pad = new THREE.Mesh(
      new THREE.CylinderGeometry(radius * 0.5, radius * 0.5, 1.2, 48),
      padMaterial,
    );
    pad.position.set(east, groundY + 0.1, north);
    pad.receiveShadow = true;
    facility.add(pad);
    for (const [x, z, width, depth, height] of [
      [-28, -17, 34, 22, 10],
      [16, -19, 28, 18, 8],
      [-8, 22, 22, 18, 14],
    ] as const) {
      const localGround = runtime.terrainHeight(east + x, north + z);
      const building = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        wallMaterial,
      );
      building.position.set(east + x, localGround + height / 2, north + z);
      building.castShadow = true;
      building.receiveShadow = true;
      facility.add(building);
      const roof = new THREE.Mesh(
        new THREE.ConeGeometry(Math.max(width, depth) * 0.57, 5, 4),
        roofMaterial,
      );
      roof.rotation.y = Math.PI / 4;
      roof.scale.z = depth / width;
      roof.position.set(east + x, localGround + height + 2.2, north + z);
      roof.castShadow = true;
      facility.add(roof);
    }
    const tower = new THREE.Mesh(
      new THREE.CylinderGeometry(2.2, 3.1, 24, 10),
      roofMaterial,
    );
    tower.position.set(east + 25, groundY + 12, north + 20);
    tower.castShadow = true;
    facility.add(tower);
    const radome = new THREE.Mesh(
      new THREE.SphereGeometry(5, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0xc6d3cb, roughness: 0.5 }),
    );
    radome.position.set(east + 25, groundY + 24, north + 20);
    facility.add(radome);
    const perimeter = new THREE.Mesh(
      new THREE.RingGeometry(radius * 0.56 - 0.7, radius * 0.56, 64),
      new THREE.MeshBasicMaterial({
        color: 0x777c70,
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide,
      }),
    );
    perimeter.rotation.x = -Math.PI / 2;
    perimeter.position.set(east, groundY + 0.9, north);
    facility.add(perimeter);
    const label = makeLabel(zone.id, "#d9a441");
    label.position.set(east, groundY + 34, north);
    facility.add(label);
    runtime.objectives.add(facility);
  }
}

function updateEffects(runtime: Runtime, scene: ArenaSceneState): void {
  const previousTime = runtime.lastEffectSimTimeSec;
  if (
    previousTime !== null &&
    (scene.simTimeSec < previousTime ||
      Math.abs(scene.simTimeSec - previousTime) > 2)
  ) {
    clearDisposableGroup(runtime.effects);
    runtime.eventVisuals.clear();
  }
  runtime.lastEffectSimTimeSec = scene.simTimeSec;
  let focusedNewEvent = false;
  for (const event of scene.events) {
    if (!event.success || runtime.eventVisuals.has(event.id)) continue;
    const visual = createEventVisual(runtime, event);
    runtime.eventVisuals.set(event.id, visual);
    if (!focusedNewEvent) {
      runtime.controls.target.copy(visual.origin);
      runtime.camera.position
        .copy(visual.origin)
        .add(new THREE.Vector3(105, 72, 118));
      runtime.controls.update();
      focusedNewEvent = true;
    }
  }
}

type DetailSpec = {
  id: string;
  assetId: AssetId;
  positionM: EnuPosition;
  attitudeDeg: AttitudeDeg;
};

function updateDetails(
  runtime: Runtime,
  specs: DetailSpec[],
  templates: Map<AssetId, DetailedAsset>,
): void {
  const keep = new Set(specs.map((spec) => spec.id));
  for (const [id, object] of runtime.detailObjects) {
    if (keep.has(id)) continue;
    runtime.details.remove(object);
    runtime.detailObjects.delete(id);
  }
  for (const spec of specs) {
    const template = templates.get(spec.assetId);
    if (!template) continue;
    let object = runtime.detailObjects.get(spec.id);
    if (!object) {
      object = new THREE.Group();
      const model = template.object.clone(true);
      model.scale.setScalar(template.scale);
      object.add(model);
      runtime.details.add(object);
      runtime.detailObjects.set(spec.id, object);
    }
    positionObject(
      object,
      spec.positionM,
      spec.attitudeDeg,
      runtime.terrainHeight,
      template.baseYaw,
    );
  }
}

function updateFocusMarker(
  runtime: Runtime,
  scene: ArenaSceneState,
  scenario: Scenario,
  role: Role,
  selectedEntityId: string | null,
): void {
  clearDisposableGroup(runtime.focus, true);
  if (role !== "analyst" || !selectedEntityId) return;
  const entity = scene.truthEntities.find(
    (candidate) => candidate.id === selectedEntityId,
  );
  if (!entity) return;
  const markerColor = factionColor(entity.factionId, scenario);
  const groundY =
    runtime.terrainHeight(entity.positionM.east, entity.positionM.north) + 0.8;
  const topY = Math.max(groundY + 5, entity.positionM.up);
  const stemHeight = topY - groundY;
  const stem = new THREE.Mesh(
    new THREE.CylinderGeometry(0.28, 0.28, stemHeight, 8),
    new THREE.MeshBasicMaterial({
      color: markerColor,
      transparent: true,
      opacity: 0.72,
    }),
  );
  stem.position.set(
    entity.positionM.east,
    groundY + stemHeight / 2,
    entity.positionM.north,
  );
  runtime.focus.add(stem);
  for (const y of [groundY, topY]) {
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(9.5, 11, 40),
      new THREE.MeshBasicMaterial({
        color: markerColor,
        transparent: true,
        opacity: 0.86,
        side: THREE.DoubleSide,
      }),
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.set(entity.positionM.east, y, entity.positionM.north);
    runtime.focus.add(halo);
  }
  const label = makeLabel(entity.id, markerColor, 22, 3.7);
  label.position.set(entity.positionM.east, topY + 7, entity.positionM.north);
  runtime.focus.add(label);
}

const TRACK_COLORS: Record<SceneTrack["classification"], string> = {
  hostile: "#d15c45",
  suspect: "#d9a441",
  friendly: "#53a5c8",
  unknown: "#85938c",
};

/**
 * Fused tracks, drawn for both roles. A track is a measurement, not a platform,
 * so it renders as a tactical marker on the ground plane rather than a model,
 * and its label carries the opaque track id only.
 */
function updateTracks(runtime: Runtime, scene: ArenaSceneState): void {
  clearDisposableGroup(runtime.tracks, true);
  for (const track of scene.tracks) {
    const color = TRACK_COLORS[track.classification];
    const groundY =
      runtime.terrainHeight(track.positionM.east, track.positionM.north) + 0.6;
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(6.5, 8, 4),
      new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.5 + 0.45 * Math.min(1, Math.max(0, track.confidence)),
        side: THREE.DoubleSide,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.rotation.z = Math.PI / 4;
    ring.position.set(track.positionM.east, groundY, track.positionM.north);
    runtime.tracks.add(ring);
    if (track.requestId) {
      const pendingHalo = new THREE.Mesh(
        new THREE.RingGeometry(11, 12.5, 32),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: track.disposition ? 0.35 : 0.9,
          side: THREE.DoubleSide,
        }),
      );
      pendingHalo.rotation.x = -Math.PI / 2;
      pendingHalo.position.set(
        track.positionM.east,
        groundY + 0.1,
        track.positionM.north,
      );
      runtime.tracks.add(pendingHalo);
    }
    const label = makeLabel(track.id, color, 20, 3.4);
    label.position.set(
      track.positionM.east,
      groundY + 12,
      track.positionM.north,
    );
    runtime.tracks.add(label);
  }
}

function focusCamera(
  runtime: Runtime,
  scene: ArenaSceneState,
  entityId: string,
): void {
  const entity = scene.truthEntities.find(
    (candidate) => candidate.id === entityId,
  );
  if (!entity) return;
  const target = new THREE.Vector3(
    entity.positionM.east,
    entity.positionM.up,
    entity.positionM.north,
  );
  const distance = entity.assetId === "cargo_ship_liberty" ? 150 : 82;
  runtime.controls.target.copy(target);
  runtime.camera.position.set(
    target.x + distance,
    target.y + distance * 0.48,
    target.z + distance,
  );
  runtime.camera.lookAt(target);
  runtime.controls.update();
}

function setCameraPreset(
  runtime: Runtime,
  preset: "overview" | "flightline" | "ground",
): void {
  if (runtime.environment === "coastal_urban") {
    const positions = {
      overview: new THREE.Vector3(820, 310, -820),
      flightline: new THREE.Vector3(-720, 85, -520),
      ground: new THREE.Vector3(-420, 30, -560),
    };
    const targets = {
      overview: new THREE.Vector3(170, 24, -40),
      flightline: new THREE.Vector3(-220, 20, -150),
      ground: new THREE.Vector3(-100, 18, -230),
    };
    runtime.camera.position.copy(positions[preset]);
    runtime.controls.target.copy(targets[preset]);
    runtime.camera.lookAt(targets[preset]);
    runtime.controls.update();
    return;
  }
  const positions = {
    overview: new THREE.Vector3(620, 245, -560),
    flightline: new THREE.Vector3(410, 82, -45),
    ground: new THREE.Vector3(430, 17, 35),
  };
  const targets = {
    overview: new THREE.Vector3(115, 17, 145),
    flightline: new THREE.Vector3(185, 7, 158),
    ground: new THREE.Vector3(180, 5, 165),
  };
  runtime.camera.position.copy(positions[preset]);
  runtime.controls.target.copy(targets[preset]);
  runtime.camera.lookAt(targets[preset]);
  runtime.controls.update();
}

function writeInstances(
  mesh: THREE.InstancedMesh,
  entities: SceneTruthEntity[],
  scenario: Scenario,
  detailedAsset?: DetailedAsset,
): void {
  mesh.count = Math.min(entities.length, MAX_INSTANCES);
  for (let index = 0; index < mesh.count; index += 1) {
    const entity = entities[index];
    dummy.position.set(
      entity.positionM.east,
      entity.positionM.up,
      entity.positionM.north,
    );
    setObjectAttitude(
      dummy,
      entity.attitudeDeg,
      detailedAsset?.baseYaw ?? 0,
    );
    const statusScale =
      (entity.status === "neutralized" ? 0.72 : 1) *
      (detailedAsset?.scale ?? 1);
    dummy.scale.setScalar(statusScale);
    dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix);
    color.set(
      entity.status === "neutralized"
        ? "#343837"
        : factionColor(entity.factionId, scenario),
    );
    mesh.setColorAt(index, color);
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.computeBoundingSphere();
}

function updateRuntime(
  runtime: Runtime,
  scene: ArenaSceneState | null,
  scenario: Scenario | null,
  role: Role,
  templates: Map<AssetId, DetailedAsset>,
  selectedEntityId: string | null,
): void {
  runtime.truthMeshes.forEach((mesh) => {
    mesh.count = 0;
  });
  templates.forEach((template, assetId) => {
    const mesh = runtime.truthMeshes.get(assetId);
    if (mesh && mesh.geometry !== template.instancedGeometry) {
      mesh.geometry.dispose();
      mesh.geometry = template.instancedGeometry;
    }
  });
  runtime.detections.count = 0;
  if (!scene || !scenario) {
    updateDetails(runtime, [], templates);
    clearDisposableGroup(runtime.tactical, true);
    clearDisposableGroup(runtime.tracks, true);
    clearDisposableGroup(runtime.objectives, true);
    clearDisposableGroup(runtime.effects);
    clearDisposableGroup(runtime.focus, true);
    return;
  }

  const plan = buildRenderPlan(scene, role);
  const useDetails =
    role === "analyst" && !usesInstancedTruth(plan.truthCount, role);
  const detailSpecs: DetailSpec[] = [];
  for (const [assetId, entities] of plan.truthByAsset) {
    if (useDetails && templates.has(assetId)) {
      detailSpecs.push(
        ...entities.map((entity) => ({
          id: entity.id,
          assetId,
          positionM: entity.positionM,
          attitudeDeg: entity.attitudeDeg,
        })),
      );
    } else {
      writeInstances(
        runtime.truthMeshes.get(assetId)!,
        entities,
        scenario,
        templates.get(assetId),
      );
    }
  }
  detailSpecs.push(
    ...scene.sensors.map((sensor) => ({
      id: sensor.id,
      assetId: sensor.assetId,
      positionM: sensor.positionM,
      attitudeDeg: sensor.attitudeDeg,
    })),
  );
  detailSpecs.push(
    ...scene.responses.map((response) => ({
      id: response.id,
      assetId: response.assetId,
      positionM: response.positionM,
      attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
    })),
  );
  updateDetails(runtime, detailSpecs, templates);
  if (!templates.has("range_watch_tower")) {
    writeInstances(
      runtime.truthMeshes.get("range_watch_tower")!,
      scene.sensors.map((sensor) => ({
        id: sensor.id,
        factionId: sensor.factionId,
        groupId: sensor.id,
        assetId: sensor.assetId,
        entityClass: "sensor",
        positionM: sensor.positionM,
        velocityMps: { east: 0, up: 0, north: 0 },
        attitudeDeg: sensor.attitudeDeg,
        status: "active",
        active: true,
        detected: true,
        enteredZone: false,
      })),
      scenario,
    );
  }
  if (!templates.has("nasams_fcs")) {
    writeInstances(
      runtime.truthMeshes.get("nasams_fcs")!,
      scene.responses.map((response) => ({
        id: response.id,
        factionId: response.factionId,
        groupId: response.id,
        assetId: response.assetId,
        entityClass: "ground-vehicle",
        positionM: response.positionM,
        velocityMps: { east: 0, up: 0, north: 0 },
        attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
        status: "active",
        active: true,
        detected: true,
        enteredZone: false,
      })),
      scenario,
    );
  }

  runtime.detections.count = Math.min(plan.detections.length, MAX_INSTANCES);
  for (let index = 0; index < runtime.detections.count; index += 1) {
    const detection = plan.detections[index];
    dummy.position.set(
      detection.positionM.east,
      detection.positionM.up + 2,
      detection.positionM.north,
    );
    dummy.rotation.set(0, 0, 0);
    dummy.scale.setScalar(1);
    dummy.updateMatrix();
    runtime.detections.setMatrixAt(index, dummy.matrix);
  }
  runtime.detections.instanceMatrix.needsUpdate = true;

  updateTactical(runtime, scene, scenario);
  updateTracks(runtime, scene);
  updateObjectives(runtime, scene, scenario);
  updateEffects(runtime, scene);
  updateFocusMarker(runtime, scene, scenario, role, selectedEntityId);
}

export function ArenaViewport({
  sceneState,
  scenario,
  role,
  onFps,
  selectedEntityId,
  focusRequest,
}: ArenaViewportProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<Runtime | null>(null);
  const [assetLibrary, setAssetLibrary] = useState<DetailedAssetLibrary | null>(
    null,
  );
  const environmentBlueprint = useMemo(
    () => normalizeEnvironmentBlueprint(scenario),
    [scenario?.visualization],
  );
  const runtimeKey = useMemo(
    () => environmentBlueprintKey(environmentBlueprint),
    [environmentBlueprint],
  );

  useEffect(() => {
    let live = true;
    let loaded: DetailedAssetLibrary | null = null;
    loadDetailedAssets()
      .then((assets) => {
        if (live) {
          loaded = assets;
          setAssetLibrary(assets);
        } else {
          disposeDetailedAssets(assets);
        }
      })
      .catch(() => {
        if (live) setAssetLibrary(null);
      });
    return () => {
      live = false;
      if (loaded) disposeDetailedAssets(loaded);
    };
  }, []);

  useEffect(() => {
    if (!hostRef.current) return;
    const runtime = createRuntime(hostRef.current, onFps, environmentBlueprint);
    runtimeRef.current = runtime;
    return () => {
      cancelAnimationFrame(runtime.animationId);
      runtime.resizeObserver.disconnect();
      runtime.controls.dispose();
      runtime.effectTextures.fire.dispose();
      runtime.effectTextures.smoke.dispose();
      runtime.renderer.dispose();
      runtime.renderer.domElement.remove();
      disposeTree(runtime.scene, true);
      runtimeRef.current = null;
    };
  }, [onFps, runtimeKey]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    clearGroup(runtime.airbaseAircraft);
    if (!assetLibrary || runtime.environment !== "gulf_airbase") return;
    for (const [east, north, rotation] of [
      [96, 121, 0],
      [180, 121, 0],
      [264, 121, 0],
      [96, 226, Math.PI],
      [180, 226, Math.PI],
      [264, 226, Math.PI],
      [360, 52, Math.PI],
    ] as const) {
      const fighter = assetLibrary.airbaseFighter.clone(true);
      fighter.position.set(
        east,
        runtime.terrainHeight(east, north) + 1.05,
        north,
      );
      fighter.rotation.y = rotation;
      runtime.airbaseAircraft.add(fighter);
    }
  }, [assetLibrary, runtimeKey]);

  useEffect(() => {
    if (runtimeRef.current) {
      updateRuntime(
        runtimeRef.current,
        sceneState,
        scenario,
        role,
        assetLibrary?.templates ?? EMPTY_TEMPLATES,
        selectedEntityId,
      );
    }
  }, [role, sceneState, scenario, selectedEntityId, assetLibrary, runtimeKey]);

  useEffect(() => {
    if (
      runtimeRef.current &&
      sceneState &&
      role === "analyst" &&
      focusRequest
    ) {
      focusCamera(runtimeRef.current, sceneState, focusRequest.id);
    }
  }, [focusRequest, role, runtimeKey]);

  return (
    <>
      <div
        className="arena-viewport"
        ref={hostRef}
        aria-label="Three-dimensional mission replay"
      />
      <div className="camera-presets" role="group" aria-label="Camera preset">
        <button
          type="button"
          onClick={() =>
            runtimeRef.current &&
            setCameraPreset(runtimeRef.current, "overview")
          }
        >
          OVERVIEW
        </button>
        <button
          type="button"
          onClick={() =>
            runtimeRef.current &&
            setCameraPreset(runtimeRef.current, "flightline")
          }
        >
          {scenario?.visualization?.environment === "coastal_urban"
            ? "HARBOR"
            : "FLIGHTLINE"}
        </button>
        <button
          type="button"
          onClick={() =>
            runtimeRef.current && setCameraPreset(runtimeRef.current, "ground")
          }
        >
          {scenario?.visualization?.environment === "coastal_urban"
            ? "STREET"
            : "GROUND"}
        </button>
      </div>
    </>
  );
}
