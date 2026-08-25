import * as THREE from "three";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { ConvexGeometry } from "three/examples/jsm/geometries/ConvexGeometry.js";

import type { AssetId } from "../arena";

export interface DetailedAsset {
  object: THREE.Object3D;
  instancedGeometry: THREE.BufferGeometry;
  scale: number;
  baseYaw: number;
}

export interface DetailedAssetLibrary {
  templates: Map<AssetId, DetailedAsset>;
  airbaseFighter: THREE.Object3D;
}

function lowCostHull(object: THREE.Object3D): THREE.BufferGeometry {
  object.updateMatrixWorld(true);
  const sources: Array<{ mesh: THREE.Mesh; positions: THREE.BufferAttribute | THREE.InterleavedBufferAttribute }> = [];
  let total = 0;
  object.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    const positions = child.geometry.getAttribute("position");
    sources.push({ mesh: child, positions });
    total += positions.count;
  });
  const step = Math.max(1, Math.ceil(total / 1_500));
  const points: THREE.Vector3[] = [];
  let sourceIndex = 0;
  sources.forEach(({ mesh, positions }) => {
    for (let index = 0; index < positions.count; index += step) {
      const alignedIndex = Math.min(positions.count - 1, index + (sourceIndex % step));
      points.push(new THREE.Vector3().fromBufferAttribute(positions, alignedIndex).applyMatrix4(mesh.matrixWorld));
    }
    sourceIndex += positions.count;
  });
  return points.length >= 4 ? new ConvexGeometry(points) : new THREE.BoxGeometry(8, 2, 12);
}

function asset(object: THREE.Object3D, scale: number, baseYaw: number): DetailedAsset {
  return { object, instancedGeometry: lowCostHull(object), scale, baseYaw };
}

const root = `${import.meta.env.BASE_URL}assets/`;

function loadObj(name: string, materialName?: string): Promise<THREE.Object3D> {
  if (!materialName) {
    return new Promise((resolve, reject) => {
      new OBJLoader().setPath(root).load(name, (object) => {
        const material = new THREE.MeshStandardMaterial({
          color: 0x7d857f,
          roughness: 0.72,
          metalness: 0.18,
        });
        object.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.material = material;
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        resolve(object);
      }, undefined, reject);
    });
  }

  return new Promise((resolve, reject) => {
    new MTLLoader().setPath(root).load(materialName, (materials) => {
      materials.preload();
      new OBJLoader().setMaterials(materials).setPath(root).load(name, (object) => {
        object.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            const childMaterials = Array.isArray(child.material) ? child.material : [child.material];
            childMaterials.forEach((material) => {
              if (material instanceof THREE.MeshPhongMaterial) {
                material.shininess = 18;
                material.specular.set(0x30393a);
                material.emissive.set(0x111514);
                material.emissiveIntensity = 0.34;
                if (material.map) material.map.colorSpace = THREE.SRGBColorSpace;
              }
            });
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        resolve(object);
      }, undefined, reject);
    }, undefined, reject);
  });
}

function prepareAirbaseFighter(object: THREE.Object3D): THREE.Object3D {
  const airframeMaterial = new THREE.MeshStandardMaterial({
    color: 0x8d989d,
    roughness: 0.58,
    metalness: 0.24,
  });
  const glassMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x263b43,
    roughness: 0.2,
    metalness: 0.08,
    transmission: 0.08,
    transparent: true,
    opacity: 0.82,
  });
  const tireMaterial = new THREE.MeshStandardMaterial({ color: 0x111416, roughness: 0.94 });
  const hiddenParts = /jet_flame|flare|sniper|litening|gpu_5a|optic3|pylon|launcher|lau_|370gal/i;
  const replacedMaterials = new Set<THREE.Material>();
  object.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    const childMaterials = Array.isArray(child.material) ? child.material : [child.material];
    childMaterials.forEach((material) => replacedMaterials.add(material));
    if (hiddenParts.test(child.name)) {
      child.visible = false;
      return;
    }
    child.material = /blister/i.test(child.name)
      ? glassMaterial
      : /wheel/i.test(child.name)
        ? tireMaterial
        : airframeMaterial;
    child.castShadow = true;
    child.receiveShadow = true;
  });
  replacedMaterials.forEach((material) => material.dispose());

  object.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  object.traverse((child) => {
    if (!(child instanceof THREE.Mesh) || !child.visible) return;
    child.geometry.computeBoundingBox();
    const childBounds = child.geometry.boundingBox?.clone().applyMatrix4(child.matrixWorld);
    if (childBounds) bounds.union(childBounds);
  });
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const scale = 15.1 / Math.max(size.x, size.z);
  object.position.set(-center.x * scale, -bounds.min.y * scale, -center.z * scale);
  object.scale.setScalar(scale);
  const normalized = new THREE.Group();
  normalized.add(object);
  return normalized;
}

export async function loadDetailedAssets(): Promise<DetailedAssetLibrary> {
  const [orion, mq1, ship, response, tower, airbaseFighter] = await Promise.all([
    loadObj("orion_ucav.obj", "orion_ucav.mtl"),
    loadObj("mq_1l_usa_lod2.obj", "mq_1l_usa_lod2.mtl"),
    loadObj("liberty_cargo_ship.obj", "liberty_cargo_ship.mtl"),
    loadObj("nasams_fcs_vehicle.obj"),
    loadObj("range_watch_tower.obj"),
    loadObj("f_16c_block_50_lod2.obj"),
  ]);

  return {
    templates: new Map<AssetId, DetailedAsset>([
      ["uav_orion", asset(orion, 1.25, 0)],
      ["mq_1l_usa", asset(mq1, 1.25, 0)],
      ["cargo_ship_liberty", asset(ship, 0.72, -Math.PI / 2)],
      ["nasams_fcs", asset(response, 2, -Math.PI / 2)],
      ["range_watch_tower", asset(tower, 1.4, 0)],
    ]),
    airbaseFighter: prepareAirbaseFighter(airbaseFighter),
  };
}

export function disposeDetailedAssets(assets: DetailedAssetLibrary): void {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  assets.templates.forEach(({ object, instancedGeometry }) => {
    geometries.add(instancedGeometry);
    object.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      geometries.add(child.geometry);
      const childMaterials = Array.isArray(child.material) ? child.material : [child.material];
      childMaterials.forEach((material) => {
        materials.add(material);
        Object.values(material).forEach((value) => {
          if (value instanceof THREE.Texture) textures.add(value);
        });
      });
    });
  });
  assets.airbaseFighter.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    geometries.add(child.geometry);
    const childMaterials = Array.isArray(child.material) ? child.material : [child.material];
    childMaterials.forEach((material) => materials.add(material));
  });
  textures.forEach((texture) => texture.dispose());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}
