import { describe, expect, it } from "vitest";

import { multiFactionAirDefenseScene } from "../arena";

describe("default scene manifest", () => {
  it("keeps each default group on an explicit asset and altitude", () => {
    expect(multiFactionAirDefenseScene.groups).toEqual({
      "red-strike": { assetId: "uav_orion", altitudeM: 120 },
      "neutral-traffic": { assetId: "mq_1l_usa", altitudeM: 90 },
    });
    expect(multiFactionAirDefenseScene.sensor.assetId).toBe("range_watch_tower");
    expect(multiFactionAirDefenseScene.response.assetId).toBe("nasams_fcs");
  });
});
