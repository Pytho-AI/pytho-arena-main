import * as THREE from "three";

import type { NormalizedStaticAssetPlacement } from "./environmentBlueprint";

const WATER_LEVEL = -2.4;

type Materials = {
  concrete: THREE.MeshStandardMaterial;
  asphalt: THREE.MeshStandardMaterial;
  paleWall: THREE.MeshStandardMaterial;
  rustWall: THREE.MeshStandardMaterial;
  darkRoof: THREE.MeshStandardMaterial;
  glass: THREE.MeshStandardMaterial;
  steel: THREE.MeshStandardMaterial;
  safety: THREE.MeshStandardMaterial;
  fence: THREE.MeshStandardMaterial;
  vegetation: THREE.MeshStandardMaterial;
};

export function coastalTerrainHeight(east: number, north: number): number {
  const shorelineEast = -470 + north * 0.035 + Math.sin(north * 0.004) * 35;
  const inland = east - shorelineEast;
  const landMix = THREE.MathUtils.smoothstep(inland, -28, 54);
  const seabed =
    WATER_LEVEL - 6.5 + Math.sin(east * 0.009 + north * 0.004) * 0.65;
  const urbanRelief =
    Math.sin(east * 0.006) * 0.32 + Math.cos(north * 0.008) * 0.28;
  const easternRise = THREE.MathUtils.smoothstep(east, 900, 2_400) * 24;
  return THREE.MathUtils.lerp(seabed, 4.2 + urbanRelief + easternRise, landMix);
}

export function coastalSurfaceHeight(east: number, north: number): number {
  return Math.max(WATER_LEVEL, coastalTerrainHeight(east, north));
}

function materials(): Materials {
  return {
    concrete: new THREE.MeshStandardMaterial({
      color: 0xa9a28f,
      roughness: 0.94,
    }),
    asphalt: new THREE.MeshStandardMaterial({
      color: 0x343b3c,
      roughness: 0.97,
    }),
    paleWall: new THREE.MeshStandardMaterial({
      color: 0xc1b89f,
      roughness: 0.88,
    }),
    rustWall: new THREE.MeshStandardMaterial({
      color: 0x754737,
      roughness: 0.86,
    }),
    darkRoof: new THREE.MeshStandardMaterial({
      color: 0x3b4545,
      roughness: 0.78,
      metalness: 0.12,
    }),
    glass: new THREE.MeshStandardMaterial({
      color: 0x47636a,
      roughness: 0.28,
      metalness: 0.22,
    }),
    steel: new THREE.MeshStandardMaterial({
      color: 0x667174,
      roughness: 0.6,
      metalness: 0.34,
    }),
    safety: new THREE.MeshStandardMaterial({
      color: 0xd2aa4f,
      roughness: 0.78,
    }),
    fence: new THREE.MeshStandardMaterial({
      color: 0x596363,
      roughness: 0.7,
      metalness: 0.35,
    }),
    vegetation: new THREE.MeshStandardMaterial({
      color: 0x69705a,
      roughness: 1,
    }),
  };
}

function mesh(
  geometry: THREE.BufferGeometry,
  material: THREE.Material,
  position: [number, number, number],
): THREE.Mesh {
  const object = new THREE.Mesh(geometry, material);
  object.position.set(...position);
  object.castShadow = true;
  object.receiveShadow = true;
  return object;
}

function box(
  group: THREE.Group,
  size: [number, number, number],
  position: [number, number, number],
  material: THREE.Material,
): THREE.Mesh {
  const object = mesh(new THREE.BoxGeometry(...size), material, position);
  group.add(object);
  return object;
}

function cylinder(
  group: THREE.Group,
  radius: number,
  height: number,
  position: [number, number, number],
  material: THREE.Material,
  sides = 20,
): THREE.Mesh {
  const object = mesh(
    new THREE.CylinderGeometry(radius, radius, height, sides),
    material,
    position,
  );
  group.add(object);
  return object;
}

function makeStaticAsset(
  kind: NormalizedStaticAssetPlacement["kind"],
  palette: Materials,
): THREE.Group {
  const group = new THREE.Group();
  switch (kind) {
    case "warehouse":
      box(group, [74, 18, 44], [0, 9, 0], palette.rustWall);
      box(group, [78, 2.2, 48], [0, 19, 0], palette.darkRoof);
      box(group, [18, 10, 1], [-22, 6, -22.6], palette.steel);
      box(group, [18, 10, 1], [22, 6, -22.6], palette.steel);
      break;
    case "mixed_block":
      box(group, [38, 38, 34], [0, 19, 0], palette.paleWall);
      for (const level of [8, 17, 26, 35]) {
        box(group, [40, 1.1, 3], [0, level, -18], palette.darkRoof);
      }
      box(group, [14, 5, 12], [8, 40.5, 4], palette.darkRoof);
      break;
    case "office_block":
      box(group, [30, 60, 30], [0, 30, 0], palette.glass);
      for (const level of [10, 20, 30, 40, 50]) {
        box(group, [32, 1.2, 32], [0, level, 0], palette.concrete);
      }
      box(group, [34, 2, 34], [0, 61, 0], palette.darkRoof);
      break;
    case "storage_tank":
      cylinder(group, 14, 23, [0, 11.5, 0], palette.concrete, 28);
      cylinder(group, 12.5, 1.4, [0, 23.5, 0], palette.darkRoof, 28);
      box(group, [1.1, 25, 1.1], [15.5, 12.5, 0], palette.steel);
      break;
    case "marina_pier":
      box(group, [9, 1.4, 78], [0, 1.2, 0], palette.darkRoof);
      for (const north of [-32, -12, 8, 28]) {
        cylinder(group, 0.65, 7, [-4, -1.5, north], palette.steel, 10);
        cylinder(group, 0.65, 7, [4, -1.5, north], palette.steel, 10);
      }
      break;
    case "cargo_stack":
      for (const [east, up, north, material] of [
        [-7, 2.3, -7, palette.rustWall],
        [7, 2.3, -7, palette.safety],
        [0, 2.3, 7, palette.darkRoof],
        [-7, 6.9, -7, palette.darkRoof],
      ] as const)
        box(group, [13, 4.5, 5.2], [east, up, north], material);
      break;
    case "utility_tower":
      cylinder(group, 1.3, 38, [0, 19, 0], palette.steel, 10);
      for (const up of [12, 24, 36]) {
        box(group, [16, 0.8, 1], [0, up, 0], palette.steel);
      }
      cylinder(group, 3.2, 1.8, [0, 40, 0], palette.safety, 16);
      break;
    case "fence_segment":
      for (const east of [-21, -10.5, 0, 10.5, 21]) {
        cylinder(group, 0.32, 4.2, [east, 2.1, 0], palette.fence, 8);
      }
      box(group, [42, 0.28, 0.28], [0, 1.1, 0], palette.fence);
      box(group, [42, 0.28, 0.28], [0, 3.5, 0], palette.fence);
      break;
    case "gatehouse":
      box(group, [18, 7, 11], [0, 3.5, 0], palette.concrete);
      box(group, [20, 1.1, 13], [0, 7.5, 0], palette.darkRoof);
      box(group, [1, 4.5, 22], [13, 2.4, 5], palette.safety);
      break;
    case "sensor_tower": {
      cylinder(group, 1.5, 28, [0, 14, 0], palette.steel, 10);
      box(group, [10, 1, 10], [0, 28, 0], palette.steel);
      const radome = mesh(
        new THREE.SphereGeometry(4.8, 20, 12),
        palette.paleWall,
        [0, 33, 0],
      );
      group.add(radome);
      break;
    }
    case "response_vehicle":
      box(group, [18, 3.2, 7], [0, 3.2, 0], palette.darkRoof);
      box(group, [6, 5.5, 7], [5, 6.1, 0], palette.paleWall);
      box(group, [8, 3.8, 6], [-4, 5.4, 0], palette.steel);
      for (const east of [-6, 6]) {
        for (const north of [-3.4, 3.4]) {
          cylinder(
            group,
            1.3,
            0.9,
            [east, 1.3, north],
            palette.fence,
            14,
          ).rotation.x = Math.PI / 2;
        }
      }
      break;
    case "patrol_boat": {
      const hull = mesh(
        new THREE.CapsuleGeometry(2.6, 17, 5, 12),
        palette.darkRoof,
        [0, 2.2, 0],
      );
      hull.rotation.z = Math.PI / 2;
      hull.scale.set(1, 0.58, 1.8);
      group.add(hull);
      box(group, [7, 3.8, 6], [1, 4.2, 0], palette.paleWall);
      box(group, [2, 4, 0.6], [-1, 7.4, 0], palette.steel);
      break;
    }
  }
  return group;
}

function placeAsset(
  parent: THREE.Group,
  placement: NormalizedStaticAssetPlacement,
  palette: Materials,
): void {
  const asset = makeStaticAsset(placement.kind, palette);
  asset.name = `static:${placement.id}`;
  asset.position.set(
    placement.east,
    coastalSurfaceHeight(placement.east, placement.north) + 0.15,
    placement.north,
  );
  asset.rotation.y = THREE.MathUtils.degToRad(placement.headingDegrees);
  asset.scale.setScalar(placement.scale);
  parent.add(asset);
}

function builtInPlacements(): NormalizedStaticAssetPlacement[] {
  const placements: NormalizedStaticAssetPlacement[] = [];
  for (let row = 0; row < 7; row += 1) {
    for (let column = 0; column < 7; column += 1) {
      if ((row === 5 && column > 3) || (row === 4 && column > 4)) continue;
      placements.push({
        id: `block-${row}-${column}`,
        kind: (row + column) % 5 === 0 ? "office_block" : "mixed_block",
        east: 250 + column * 112,
        north: -610 + row * 145,
        headingDegrees: (row % 2) * 90,
        scale: 0.78 + ((row * 7 + column) % 4) * 0.08,
      });
    }
  }
  for (let index = 0; index < 8; index += 1) {
    placements.push({
      id: `harbor-warehouse-${index}`,
      kind: "warehouse",
      east: -80 + (index % 2) * 95,
      north: -520 + Math.floor(index / 2) * 150,
      headingDegrees: 0,
      scale: 0.9,
    });
  }
  for (let index = 0; index < 6; index += 1) {
    placements.push({
      id: `marina-pier-${index}`,
      kind: "marina_pier",
      east: -560 - (index % 2) * 70,
      north: 250 + Math.floor(index / 2) * 115,
      headingDegrees: 90,
      scale: 0.86,
    });
  }
  for (let index = 0; index < 12; index += 1) {
    placements.push({
      id: `marina-boat-${index}`,
      kind: "patrol_boat",
      east: -590 - (index % 3) * 30,
      north: 235 + Math.floor(index / 3) * 65,
      headingDegrees: index % 2 ? 180 : 0,
      scale: 0.46 + (index % 3) * 0.05,
    });
  }
  return placements;
}

function addRoad(
  parent: THREE.Group,
  size: [number, number],
  position: [number, number],
  headingDegrees: number,
  material: THREE.Material,
): void {
  const road = box(
    parent,
    [size[0], 0.55, size[1]],
    [
      position[0],
      coastalSurfaceHeight(position[0], position[1]) + 0.45,
      position[1],
    ],
    material,
  );
  road.rotation.y = THREE.MathUtils.degToRad(headingDegrees);
}

function addGenericInstallation(parent: THREE.Group, palette: Materials): void {
  const centerEast = 720;
  const centerNorth = 390;
  const installation = new THREE.Group();
  installation.name = "fictional-generic-installation";
  for (const north of [-125, 125]) {
    for (const east of [-126, -84, -42, 0, 42, 84, 126]) {
      placeAsset(
        installation,
        {
          id: `fence-ns-${north}-${east}`,
          kind: "fence_segment",
          east,
          north,
          headingDegrees: 0,
          scale: 1,
        },
        palette,
      );
    }
  }
  for (const east of [-147, 147]) {
    for (const north of [-104, -62, -20, 22, 64, 106]) {
      placeAsset(
        installation,
        {
          id: `fence-ew-${east}-${north}`,
          kind: "fence_segment",
          east,
          north,
          headingDegrees: 90,
          scale: 1,
        },
        palette,
      );
    }
  }
  for (const placement of [
    {
      id: "gate",
      kind: "gatehouse" as const,
      east: 0,
      north: -132,
      headingDegrees: 0,
      scale: 1,
    },
    {
      id: "admin",
      kind: "mixed_block" as const,
      east: -55,
      north: 15,
      headingDegrees: 0,
      scale: 0.72,
    },
    {
      id: "utility",
      kind: "warehouse" as const,
      east: 52,
      north: 30,
      headingDegrees: 90,
      scale: 0.72,
    },
    {
      id: "tank-a",
      kind: "storage_tank" as const,
      east: 80,
      north: -58,
      headingDegrees: 0,
      scale: 0.68,
    },
    {
      id: "tank-b",
      kind: "storage_tank" as const,
      east: 112,
      north: -58,
      headingDegrees: 0,
      scale: 0.68,
    },
  ])
    placeAsset(installation, placement, palette);
  installation.position.set(centerEast, 0, centerNorth);
  parent.add(installation);
}

export function makeCoastalUrban(
  scene: THREE.Scene,
  staticAssets: NormalizedStaticAssetPlacement[],
): THREE.ShaderMaterial {
  const palette = materials();
  const environment = new THREE.Group();
  environment.name = "coastal-urban-environment";
  scene.add(environment);

  const terrainGeometry = new THREE.PlaneGeometry(7_000, 7_000, 128, 128);
  const positions = terrainGeometry.attributes.position;
  const colors: number[] = [];
  for (let index = 0; index < positions.count; index += 1) {
    const east = positions.getX(index);
    const north = -positions.getY(index);
    const height = coastalTerrainHeight(east, north);
    positions.setZ(index, height);
    const shore = 1 - THREE.MathUtils.smoothstep(height, WATER_LEVEL - 1, 5);
    const urban = THREE.MathUtils.smoothstep(east, -180, 520);
    const terrainColor = new THREE.Color(0x776f5c)
      .lerp(new THREE.Color(0x929077), urban * 0.7)
      .lerp(new THREE.Color(0x5e6e69), shore * 0.7);
    colors.push(terrainColor.r, terrainColor.g, terrainColor.b);
  }
  terrainGeometry.setAttribute(
    "color",
    new THREE.Float32BufferAttribute(colors, 3),
  );
  terrainGeometry.computeVertexNormals();
  terrainGeometry.rotateX(-Math.PI / 2);
  const terrain = mesh(
    terrainGeometry,
    new THREE.MeshStandardMaterial({
      color: 0xffffff,
      vertexColors: true,
      roughness: 0.99,
    }),
    [0, 0, 0],
  );
  environment.add(terrain);

  const waterMaterial = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {
      time: { value: 0 },
      deepColor: { value: new THREE.Color(0x18353f) },
      shallowColor: { value: new THREE.Color(0x567878) },
    },
    vertexShader: `
      uniform float time;
      varying vec2 vUv;
      varying float vWave;
      void main() {
        vUv = uv;
        vec3 transformed = position;
        float wave = sin(position.x * 0.014 + time * 0.9) * 0.22
          + sin(position.y * 0.022 - time * 0.7) * 0.13;
        transformed.z += wave;
        vWave = wave;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 deepColor;
      uniform vec3 shallowColor;
      varying vec2 vUv;
      varying float vWave;
      void main() {
        float glint = smoothstep(0.2, 0.34, vWave) * 0.12;
        vec3 water = mix(deepColor, shallowColor, 0.22 + vUv.x * 0.3);
        gl_FragColor = vec4(water + glint, 0.96);
      }
    `,
  });
  const water = mesh(
    new THREE.PlaneGeometry(4_200, 7_000, 96, 96),
    waterMaterial,
    [-2_050, WATER_LEVEL, 0],
  );
  water.rotation.x = -Math.PI / 2;
  water.renderOrder = 1;
  environment.add(water);

  addRoad(environment, [34, 1_650], [155, 40], 0, palette.asphalt);
  addRoad(environment, [28, 1_250], [650, -40], 0, palette.asphalt);
  for (const north of [-540, -390, -240, -90, 60, 210, 360, 510]) {
    addRoad(environment, [1_080, 22], [520, north], 0, palette.asphalt);
  }
  addRoad(environment, [1_250, 30], [250, 690], -8, palette.asphalt);

  const quay = box(
    environment,
    [235, 2.2, 1_160],
    [-155, coastalSurfaceHeight(-155, 0) + 0.4, -30],
    palette.concrete,
  );
  quay.receiveShadow = true;
  for (const north of [-510, -210, 90, 390]) {
    placeAsset(
      environment,
      {
        id: `quay-cargo-${north}`,
        kind: "cargo_stack",
        east: -105,
        north,
        headingDegrees: 0,
        scale: 0.9,
      },
      palette,
    );
    placeAsset(
      environment,
      {
        id: `quay-crane-${north}`,
        kind: "utility_tower",
        east: -215,
        north: north + 55,
        headingDegrees: 0,
        scale: 1.2,
      },
      palette,
    );
  }

  for (const placement of builtInPlacements())
    placeAsset(environment, placement, palette);
  addGenericInstallation(environment, palette);
  for (const placement of staticAssets)
    placeAsset(environment, placement, palette);

  const rockGeometry = new THREE.DodecahedronGeometry(3.4, 0);
  const rockMaterial = new THREE.MeshStandardMaterial({
    color: 0x585f58,
    roughness: 0.98,
  });
  const rocks = new THREE.InstancedMesh(rockGeometry, rockMaterial, 180);
  const transform = new THREE.Object3D();
  for (let index = 0; index < 180; index += 1) {
    const north = -1_050 + index * 12;
    const east = -470 + north * 0.035 + Math.sin(north * 0.004) * 35 - 18;
    const scale = 0.55 + (index % 7) * 0.09;
    transform.position.set(east, WATER_LEVEL + 2.2, north);
    transform.rotation.set(index * 0.17, index * 0.61, 0);
    transform.scale.set(scale, scale * 0.7, scale);
    transform.updateMatrix();
    rocks.setMatrixAt(index, transform.matrix);
  }
  rocks.castShadow = true;
  rocks.receiveShadow = true;
  environment.add(rocks);

  const treeGeometry = new THREE.ConeGeometry(3.2, 11, 7);
  const trees = new THREE.InstancedMesh(treeGeometry, palette.vegetation, 120);
  for (let index = 0; index < 120; index += 1) {
    const east = 210 + (index % 15) * 76;
    const north = -720 + Math.floor(index / 15) * 190 + (index % 3) * 18;
    transform.position.set(
      east,
      coastalSurfaceHeight(east, north) + 5.4,
      north,
    );
    transform.rotation.set(0, index * 0.73, 0);
    transform.scale.setScalar(0.68 + (index % 5) * 0.08);
    transform.updateMatrix();
    trees.setMatrixAt(index, transform.matrix);
  }
  trees.castShadow = true;
  environment.add(trees);

  return waterMaterial;
}
