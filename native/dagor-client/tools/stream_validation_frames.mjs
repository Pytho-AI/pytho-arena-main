const entityCount = Number(process.argv[2] ?? 100);
const durationSec = Number(process.argv[3] ?? 12);
const runId = process.argv[4] ?? `native-load-${entityCount}`;

if (![100, 500, 2_000].includes(entityCount)) {
  throw new RangeError("entity count must be 100, 500, or 2000");
}
if (!Number.isFinite(durationSec) || durationSec <= 0 || durationSec > 120) {
  throw new RangeError("duration must be between 0 and 120 seconds");
}

const assets = [
  ["fixed-wing", "uav_orion"],
  ["fixed-wing", "mq_1l_usa"],
  ["ground-vehicle", "nasams_fcs"],
  ["sensor", "range_watch_tower"],
  ["ship", "cargo_ship_liberty"],
];
const side = Math.ceil(Math.sqrt(entityCount));

function makeFrame(sequence) {
  const entities = Array.from({ length: entityCount }, (_, index) => {
    const [entityClass, assetId] = assets[index % assets.length];
    const east = ((index % side) - side / 2) * 14;
    // Keep the stress-test grid clear of East District's default camera near
    // the scene origin. Large ship assets can otherwise surround the camera
    // and make the on-screen FPS sample meaningless.
    const north = 600 + (Math.floor(index / side) - side / 2) * 14;
    const up = entityClass === "fixed-wing" ? 55 + (index % 5) * 8 : 1;
    return {
      id: `native-${String(index).padStart(4, "0")}`,
      entityClass,
      assetId,
      positionM: { east: east + Math.sin(sequence / 20) * 2, up, north },
      attitudeDeg: { heading: (index * 37 + sequence * 2) % 360, pitch: 0, roll: 0 },
      status: "active",
      visible: true,
    };
  });
  return JSON.stringify({
    schemaVersion: 1,
    type: "frame",
    runId,
    sequence,
    simTimeSec: sequence / 20,
    coordinateFrame: "ENU",
    entities,
    tracks: [],
    events: [],
  });
}

const socket = new WebSocket("ws://127.0.0.1:46000/");
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", () => reject(new Error("failed to connect to frame relay")), { once: true });
});

const frameCount = Math.ceil(durationSec * 20);
let sequence = 0;
await new Promise((resolve) => {
  const timer = setInterval(() => {
    socket.send(makeFrame(sequence));
    sequence += 1;
    if (sequence >= frameCount) {
      clearInterval(timer);
      resolve();
    }
  }, 50);
});

socket.close();
process.stdout.write(`sent ${frameCount} frame-v1 snapshots with ${entityCount} entities at 20 Hz for run ${runId}\n`);
