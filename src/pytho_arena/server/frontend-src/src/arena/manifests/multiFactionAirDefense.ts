import type { ArenaSceneManifest } from "../types";

// The 100 x 100 abstract Arena world becomes a one-kilometer ENU scene.
// The manifest owns presentation choices; the simulation contract stays unchanged.
export const multiFactionAirDefenseScene: ArenaSceneManifest = {
  metersPerWorldUnit: 10,
  originWorld: [50, 50],
  groups: {
    "red-strike": { assetId: "uav_orion", altitudeM: 120 },
    "neutral-traffic": { assetId: "mq_1l_usa", altitudeM: 90 },
  },
  sensor: { assetId: "range_watch_tower", altitudeM: 0 },
  response: { assetId: "nasams_fcs", altitudeM: 0 },
};
