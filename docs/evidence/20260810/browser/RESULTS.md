# Browser acceptance — 2026-08-10

## Environment

- macOS, Chrome 151.0.7922.76, headless Metal ANGLE (`--use-angle=metal`)
- Arena `akshay/3dsim`, local server `127.0.0.1:8096`
- WebGL renderer string: `WebKit WebGL`
- Viewport: 1440 × 1000

## Raven scenario

- Scenario: `strait-sentinel-airbase` version 1
- Run: `b9908301-b99f-4381-930d-85646522ce32`
- Replay: 151 frames
- First detection frame: 1
- First event frame: 34
- Frame 34: 2 defense events, 0 attack events
- Scrub sequence: frame 34 → frame 0 → frame 34
- Final observed rate: 120 FPS
- Browser exceptions: 0
- Scene errors: 0

## Entity load

Temporary five-frame scenarios exercised the analyst truth path and the same
instanced meshes used by replay.

| Entities | Active truth | Entity selector | Observed FPS | JS heap | Result |
| ---: | ---: | ---: | ---: | ---: | :--- |
| 100 | 100 | 100 | 120 | 52,215,000 B | PASS |
| 500 | 500 | 500 | 120 | 27,264,320 B | PASS |
| 2,000 | 2,000 | 2,000 | 120 | 42,850,052 B | PASS |

All three loads reported no browser exception and no scene error. FPS is a
headless-Chrome observation, not a guarantee for every display or GPU.

## Visual evidence

- `arena-airbase-flightline.png`: real F-16 LOD, shelters, hangars, apron, and camera controls.
- `arena-airbase-live-operator.png`: live sensor-view replay at the first detection frame.
- `arena-airbase-event-fire.png`: frame-34 fireball and pressure ring.
- `arena-airbase-event-smoke.png`: persistent layered smoke after the flash.
- `arena-airbase-2000-entities.png`: 2,000 analyst-truth entities and UI counters.

The `../showcase/` directory contains current captures from the final browser build:

- `jlc-coastal-urban-overview.png`: imported document scenario, typed assets, tracks, and analyst UI.
- `jlc-coastal-urban-harbor.png`: fictional harbor and installation camera.
- `raven-flightline-command.png`: Raven operator command and flightline view.
- `raven-active-intercept.png`: frame-34 intercept effects and outcome evidence.
- `raven-impact-smoke.png`: persistent layered smoke after the intercept flash.

## Build and unit checks

- `npm test -- --run`: 27/27 passed.
- `npm run build`: passed.
- Vite warning: generated `app.js` is larger than 500 kB; this is tracked as a
  delivery-size warning and did not affect the acceptance rate.
