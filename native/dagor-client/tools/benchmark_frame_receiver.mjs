import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const clientRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const receiver = resolve(clientRoot, "build/pytho-frame-receiver");
const counts = [100, 500, 2_000];
const frameCount = 100;
const assetIds = [
  ["fixed-wing", "uav_orion"],
  ["multirotor", "quadcopter_surrogate"],
  ["ground-vehicle", "nasams_fcs"],
  ["ship", "cargo_ship_liberty"],
];

function makeFrame(entityCount, sequence) {
  const entities = Array.from({ length: entityCount }, (_, index) => {
    const [entityClass, assetId] = assetIds[index % assetIds.length];
    return {
      id: `entity-${String(index).padStart(4, "0")}`,
      entityClass,
      assetId,
      positionM: { east: index * 2 + sequence, up: 50 + index % 80, north: index * 3 },
      attitudeDeg: { heading: (index + sequence) % 360, pitch: 0, roll: 0 },
      status: "active",
      visible: true,
    };
  });
  return JSON.stringify({
    schemaVersion: 1,
    type: "frame",
    runId: `load-${entityCount}`,
    sequence,
    simTimeSec: sequence / 20,
    coordinateFrame: "ENU",
    entities,
    tracks: [],
    events: [],
  });
}

for (const entityCount of counts) {
  const lines = Array.from({ length: frameCount }, (_, sequence) => makeFrame(entityCount, sequence));
  const input = `${lines.join("\n")}\n`;
  const startedAt = process.hrtime.bigint();
  const result = spawnSync(receiver, { input, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  const elapsedSec = Number(process.hrtime.bigint() - startedAt) / 1e9;
  if (result.status !== 0) {
    process.stderr.write(result.stderr);
    process.exit(result.status ?? 1);
  }
  const outputFrames = result.stdout.trim().split("\n").filter(Boolean).length;
  if (outputFrames !== frameCount) {
    throw new Error(`receiver produced ${outputFrames} results for ${frameCount} frames`);
  }
  const payloadBytes = Buffer.byteLength(lines[0]);
  const framesPerSec = frameCount / elapsedSec;
  process.stdout.write(
    `${entityCount} entities: ${payloadBytes} bytes/frame, ${framesPerSec.toFixed(1)} validated frames/s\n`,
  );
}
