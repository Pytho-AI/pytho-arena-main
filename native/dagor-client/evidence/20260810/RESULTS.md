# Native Dagor validation — 2026-08-10

## Result

The patched arm64 `dngSceneViewer` loaded East District through Metal, mounted the Pytho resource pack, accepted `frame-v1` snapshots at 20 Hz, and completed the 100, 500, and 2,000 entity runs. The completed load portion contained no synchronous ECS creation errors, grid-holder errors, Dagor error-level messages, or crashes.

| Check | Result | Evidence |
| --- | --- | --- |
| Metal renderer | Passed | Apple M4 Pro and Metal are recorded in the runtime log; `00-east-district-metal-baseline.jpeg` shows 90.1 FPS |
| 100 entities | Passed | Frames 0–99 accepted; `08-native-fixed-100.jpeg` shows 106.6 FPS |
| 500 entities | Passed | Frames 0–199 accepted; `11-native-replacement-500.jpeg` shows 107.6 FPS |
| 2,000 entities | Passed | Frames 0–239 accepted; `12-native-replacement-2000.jpeg` shows 106.9 FPS |
| Five Pytho DAG assets | Passed | Runtime log creates Orion, MQ-1, NASAMS FCS, watch tower, and Liberty ship `riExtra` resources from `pytho_assets.grp` |
| Replay branch/scrub | Passed | The clean replay run advances from 42.00 to 45.95 seconds, changes `runId`, then restarts at 12.00 and advances to 15.95 seconds |
| ENU position and 100 m separation | Passed | Runtime ECS positions match the scenario; the native transform test also passes |
| Heading conversion | Passed by native transform test | The runtime accepted headings 0 and 90, but the assets are not visible in the fixed-camera screenshots |
| Response effect resource | Passed for loading | `envir_sparks_burst_big_cmps_fx` loaded and created; this is not a weapon-grade explosion |

## Runtime excerpts

Load and asset creation:

```text
[PYTHO] frame=0 time=0 entities=100 tracks=0
ECS 65993: created <pytho_uas_orion> at (-70.000,55.000,530.000)
riExtra[407] uav_orion
ECS 65994: created <pytho_uas_mq1> at (-56.000,63.000,530.000)
riExtra[408] mq_1l_usa
ECS 65995: created <pytho_response_nasams> at (-42.000,1.000,530.000)
riExtra[409] nasams_fcs
ECS 65996: created <pytho_sensor_tower> at (-28.000,1.000,530.000)
riExtra[410] range_watch_tower
ECS 65997: created <pytho_ship_liberty> at (-14.000,1.000,530.000)
riExtra[411] cargo_ship_liberty
[PYTHO] frame=99 time=4.95 entities=100 tracks=0
[PYTHO] frame=199 time=9.95 entities=500 tracks=0
[PYTHO] frame=239 time=11.95 entities=2000 tracks=0
```

Replay and effect:

```text
[PYTHO] frame=0 time=42 entities=5 tracks=1
ECS 65993: created <pytho_uas_orion> at (-12.000,18.000,45.000)
ECS 65994: created <pytho_uas_mq1> at (12.000,18.000,45.000)
ECS 65995: created <pytho_sensor_tower> at (-50.000,1.000,80.000)
ECS 65996: created <pytho_sensor_tower> at (50.000,1.000,80.000)
_FX_ fx: loading: envir_sparks_burst_big_cmps_fx
ECS 65999: created <pytho_response_effect> at (0.000,8.000,38.000)
[PYTHO] frame=79 time=45.95 entities=5 tracks=1
[PYTHO] frame=0 time=12 entities=5 tracks=1
[PYTHO] frame=79 time=15.95 entities=5 tracks=1
```

The replay run contained zero matches for `sync creation of entity`, `Invalid grid type loot`, `[E]`, and `signal 11`.

## Automated checks

- `make test`: frame parser, ship fixture, invalid schema, ENU heading, and 100-meter transform passed.
- `npm run test`: 49 tests passed in 7 files. The sandboxed copy skipped its live bind case.
- `npm run test:native-loopback` outside the network sandbox: the live 127.0.0.1 producer/subscriber test passed.
- `npm run build`: TypeScript and Vite production build passed.
- `make benchmark`: 3,810.3, 827.5, and 224.1 validated frames per second for 100, 500, and 2,000 entity payloads.
- `codesign --verify --deep --strict`: the packaged custom app passed.

## Screenshot classification

Pass evidence:

- `00-east-district-metal-baseline.jpeg`
- `08-native-fixed-100.jpeg`
- `11-native-replacement-500.jpeg`
- `12-native-replacement-2000.jpeg`
- `14-native-replay-scrub.jpeg`

Debug evidence, not pass evidence:

- `01-native-load-100.jpeg` through `03-native-clean-100.jpeg`: synchronous creation and early placement defects
- `05-native-async-100.jpeg` and `06-native-async-500.jpeg`: async creation test before teardown was fixed
- `09-native-fixed-500.jpeg`: grid-holder teardown error remained
- `10-final-baseline.jpeg`: console overlay was open
- `13-native-geometry-forward.jpeg`: clean render, but scenario models were occluded

The fixed camera shows East District and the Metal FPS counter. It does not visibly prove individual model heading or scale. Runtime positions plus the native transform test are the evidence for those checks.

## Known debug-editor crash

After the successful load and replay validation, pressing F12 entered the stock DaEditor path and crashed in Metal debug-line rendering at `CachedDebugLinesData::flushLines`. This happened after the validation frames completed. A fresh viewer run repeated the replay test without F12 and completed with no error-level messages or crash. Do not use the F12 editor path in this build.

## SHA-256

```text
28a44d618bd507e078075cd9b9277eff3d4e8d2ec600fe1f2ac463ed14203bda  00-east-district-metal-baseline.jpeg
4a0e4d337984143af7d35a43e06db0a3e58ec16631e652e1adcd79ba7f5dedaa  08-native-fixed-100.jpeg
358f7390a1280c010b0247f0ad42ed4f20a1e01d234f2e4c9a9668de14cfd4a1  11-native-replacement-500.jpeg
ff1bdbf14a85de6b402fe7f8fdbb5c9a45ac218a3e5c36cef50ff32d7cbcd6d0  12-native-replacement-2000.jpeg
9e9feb20b060f12ef4c1e7f748fbfc62862de866ca24a89477d7dcf7d658e94a  14-native-replay-scrub.jpeg
```
