import type { ArenaSceneState } from "../arena";
import type { Role, Scenario } from "../app/types";

type SensorScopeProps = {
  scene: ArenaSceneState | null;
  role: Role;
  scenario: Scenario | null;
};

const LIMIT_M = 620;

function scopePoint(east: number, north: number): [number, number] {
  const radius = Math.min(1, Math.hypot(east, north) / LIMIT_M);
  const angle = Math.atan2(north, east);
  return [100 + Math.cos(angle) * radius * 83, 100 - Math.sin(angle) * radius * 83];
}

export function SensorScope({ scene, role, scenario }: SensorScopeProps) {
  const measurements = scene?.rawDetections ?? [];
  const truth = role === "analyst" ? scene?.truthEntities ?? [] : [];
  // Tracks are the operator's own picture, so both roles see them.
  const tracks = scene?.tracks ?? [];

  return (
    <section className="sensor-scope" aria-label={`${role} sensor scope`}>
      <div className="scope-heading">
        <span>SENSOR SCOPE</span>
        <strong>{role === "operator" ? "MEASUREMENTS" : "GROUND TRUTH"}</strong>
      </div>
      <svg viewBox="0 0 200 200" role="img" aria-label={`${measurements.length} detections`}>
        <defs>
          <clipPath id="scope-clip"><circle cx="100" cy="100" r="88" /></clipPath>
        </defs>
        <circle className="scope-field" cx="100" cy="100" r="88" />
        <g className="scope-grid">
          <circle cx="100" cy="100" r="29" />
          <circle cx="100" cy="100" r="58" />
          <circle cx="100" cy="100" r="87" />
          <path d="M12 100h176M100 12v176" />
          <path d="M38 38l124 124M162 38L38 162" />
        </g>
        <g clipPath="url(#scope-clip)">
          <path className="scope-sweep" d="M100 100L182 71A88 88 0 0 1 188 100Z" />
          {truth.map((entity) => {
            const [x, y] = scopePoint(entity.positionM.east, entity.positionM.north);
            return (
              <path
                className="scope-truth"
                d={`M${x} ${y - 4}l4 7h-8Z`}
                key={entity.id}
                style={{ fill: scenario?.factions.find((faction) => faction.id === entity.factionId)?.color ?? "#c6d3cb" }}
              />
            );
          })}
          {measurements.map((detection, index) => {
            const [x, y] = scopePoint(detection.positionM.east, detection.positionM.north);
            return <circle className="scope-measurement" cx={x} cy={y} r="4" key={`${detection.truthEntityId}:${index}`} />;
          })}
          {tracks.map((track) => {
            const [x, y] = scopePoint(track.positionM.east, track.positionM.north);
            return (
              <g className={`scope-track scope-track--${track.classification}`} key={track.id}>
                <rect x={x - 6} y={y - 6} width="12" height="12" />
                {track.requestId && <circle cx={x} cy={y} r="9" className="scope-track-request" />}
              </g>
            );
          })}
        </g>
        <text x="100" y="8">N</text>
        <text x="192" y="104">E</text>
      </svg>
      <div className="scope-readout">
        <span>RAW {String(measurements.length).padStart(2, "0")}</span>
        <span>TRK {String(tracks.length).padStart(2, "0")}</span>
        <span>{role === "analyst" ? `TRUTH ${String(truth.length).padStart(2, "0")}` : "TRUTH LOCKED"}</span>
      </div>
    </section>
  );
}
