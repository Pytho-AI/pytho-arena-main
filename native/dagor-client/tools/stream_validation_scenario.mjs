const socket = new WebSocket("ws://127.0.0.1:46000/");

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", () => reject(new Error("failed to connect to frame relay")), { once: true });
});

const entities = [
  {
    id: "heading-north",
    entityClass: "fixed-wing",
    assetId: "uav_orion",
    positionM: { east: -12, up: 18, north: 45 },
    attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
    status: "active",
    visible: true,
  },
  {
    id: "heading-east",
    entityClass: "fixed-wing",
    assetId: "mq_1l_usa",
    positionM: { east: 12, up: 18, north: 45 },
    attitudeDeg: { heading: 90, pitch: 0, roll: 0 },
    status: "active",
    visible: true,
  },
  {
    id: "scale-origin",
    entityClass: "sensor",
    assetId: "range_watch_tower",
    positionM: { east: -50, up: 1, north: 80 },
    attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
    status: "active",
    visible: true,
  },
  {
    id: "scale-100m-east",
    entityClass: "sensor",
    assetId: "range_watch_tower",
    positionM: { east: 50, up: 1, north: 80 },
    attitudeDeg: { heading: 0, pitch: 0, roll: 0 },
    status: "active",
    visible: true,
  },
  {
    id: "response-vehicle",
    entityClass: "ground-vehicle",
    assetId: "nasams_fcs",
    positionM: { east: 0, up: 1, north: 32 },
    attitudeDeg: { heading: 180, pitch: 0, roll: 0 },
    status: "active",
    visible: true,
  },
];

function frame(runId, sequence, simTimeSec) {
  return JSON.stringify({
    schemaVersion: 1,
    type: "frame",
    runId,
    sequence,
    simTimeSec,
    coordinateFrame: "ENU",
    entities,
    tracks: [
      { id: "geometry-track", positionM: { east: 0, up: 22, north: 55 }, confidence: 0.97 },
    ],
    events: [
      {
        id: `${runId}-intercept`,
        eventType: "intercept",
        positionM: { east: 0, up: 8, north: 38 },
        success: true,
      },
    ],
  });
}

async function streamPhase(runId, initialSimTimeSec) {
  for (let sequence = 0; sequence < 80; sequence += 1) {
    socket.send(frame(runId, sequence, initialSimTimeSec + sequence / 20));
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

await streamPhase("native-replay-forward", 42);
await streamPhase("native-replay-scrub", 12);

socket.close();
process.stdout.write("sent forward and backward-scrub validation phases at 20 Hz\n");
