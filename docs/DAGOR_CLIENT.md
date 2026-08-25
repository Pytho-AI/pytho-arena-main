# Arena Dagor native client status

Date: 2026-08-10
Dagor source revision: `6c117dc00c29866ea3e7f51838a686f0374099f7`

Repository location: `native/dagor-client/`. This is the Arena-owned copy of the validated native client and its Pytho-owned resource packs. Pack artifacts live under `native/dagor-client/assets/packs`; ignored daBuild scratch output uses `assets/build` and `assets/cache`. The 2.46 GB East District archive, extracted engine tree, native test binaries, and runtime logs remain outside the repository.

## Current result

The official East District package and stock arm64 viewer work on this Mac. The stock viewer selected Apple M4 Pro through Metal and rendered the supplied East District scene.

The Pytho source viewer builds with its daScript overlay AOT-compiled into the arm64 executable. It mounts the official Pytho resource pack, connects to a relay at `127.0.0.1:46000`, and applies complete `frame-v1` snapshots at 20 Hz.

The native run completed 100, 500, and 2,000 entity phases. The on-screen Metal counter showed 106.6, 107.6, and 106.9 FPS respectively. The runtime log created all five Pytho DAG resources and accepted the final frame in each phase. The completed load portion contained no synchronous ECS creation errors, grid-holder errors, Dagor error-level messages, or crashes.

The replay run advanced simulation time from 42.00 to 45.95 seconds, switched to a new run ID, and restarted at 12.00 seconds through 15.95 seconds. It created the two heading cases, two watch towers 100 meters apart, one track, and one response effect. The replay run completed without error-level messages or a crash.

No Dagor viewer or validation producer was left running after validation. The original loopback relay was parent-owned and was not stopped by the native client work.

Arena server/frontend publication is not wired by this directory. A runtime producer must publish the documented `frame-v1` contract to the loopback relay. The copied validation streamers test that boundary without changing Arena application code.

## Artifacts and evidence

| Item | Value |
| --- | --- |
| Official archive | `/private/tmp/pytho-dagor-20260810/east_district-dagor.p1.tar.gz` |
| Archive size | `2,463,450,557` bytes |
| Archive SHA-256 | `641e5797d4b3af639b9d794892b95aafabad81f629f2f3180506ba22f8245416` |
| Extracted official viewer | `/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer` |
| Pinned source | `/private/tmp/pytho-dagor-20260810/dagor-engine` |
| Packaged custom app | `/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer/PythoDngSceneViewer.app` |
| Packaged arm64 binary SHA-256 | `21f9d505bd0c4b557c43ae1d7544ef59547e63096e9bca21ca51c4a098834d23` |
| Packed scripts SHA-256 | `2d93e4d3d6b8fc49f58206afa6b6dd0b3d7d036881fac6f6baf800e18fcfef1a` |
| Entity-load log | `/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer/.log/dng_scene_viewer-dev-2026.08.10-09.22.47/debug` |
| Clean replay log | `/private/tmp/pytho-dagor-20260810/east-extract/samples/dngSceneViewer/viewer/.log/dng_scene_viewer-dev-2026.08.10-09.27.31/debug` |
| Persistent evidence | `native/dagor-client/evidence/20260810/` |

The two final runtime logs record:

- `[METAL_INIT] selected device Apple M4 Pro`
- `SYSINFO_GPU_API: "Metal"`
- `load_vromfs_dump <content/pytho/res/grp_hdr.vromfs.bin>`
- `loading res pkg: content/pytho/res/`
- all five Pytho templates created with their expected `riExtra` resources in the entity-load run
- the overlay's track and response-effect templates created
- forward and backward-scrub phases applied at 20 Hz

The final package removes `options no_aot`; generated `pytho_frame_overlay_das_AOT.cpp` contains `apply_frame_root` and `pytho_frame_client_es`, and the final binary linked successfully.

The official archive URL was:

```text
https://dagorenginedata.cdn.gaijin.net/rel-fea0a2b3ae5acdb25e088e57a8fb1f77d5ba3e1d/east_district-dagor.p1.tar.gz
```

## Production transport

```text
Arena frame-v1 producer
  -> Node relay bound only to 127.0.0.1:46000
  -> one complete frame-v1 JSON text message at 20 Hz
  -> Dagor nonblocking WebSocket client
  -> newest pending snapshot
  -> daScript ECS upsert and stale-entity removal
```

Rules:

- Maximum message size: 8 MiB.
- Maximum truth entities: 2,000.
- Maximum combined visible entities, tracks, and successful effects: 2,000.
- A changed `runId` starts a replay baseline or branch.
- `sequence` increases within a run; equal or lower values are dropped.
- An absent entity ID is removed on the next accepted full snapshot.
- Replay playback publishes at 20 Hz. A scrub sends the selected full frame.
- Dagor receives display snapshots. Simulation, sensor, fusion, and response logic stay in TypeScript.

The C++ client implements a loopback-only, nonblocking RFC 6455 connection. It reconnects after one second and keeps a single latest-message slot, so rendering does not drain a stale queue.

## Coordinates and ECS

Wire positions are local ENU meters:

```text
Dagor X = east
Dagor Y = up
Dagor Z = north
```

Heading zero points along Dagor `+Z`. Heading 90 points along `+X`. Positive pitch raises the nose. Positive roll lowers the right wing. The native unit test covers these axes and a 100-meter scale change.

The overlay contains templates for:

- fixed-wing and multirotor UAS
- NASAMS ground response assets
- sensors and watch towers
- tracks
- ships
- response and penetration effects

The East District sample pack exposes environmental effects rather than a full weapon-effect library. The current response effect uses `envir_sparks_burst_big_cmps_fx`; a successful attack uses `fire_spot_1m_nosmoke_cmps_fx`. The response resource loaded and created in the native replay run. It is not a weapon-grade explosion, and no such result is claimed.

## Official asset conversion

Blender 4.2.20 LTS used official dag4blend 2.5.0. Official `daBuild-dev` revision 1.38 from the pinned Dagor commit produced the final resource packs.

The five real DAG outputs are:

| DAG | SHA-256 |
| --- | --- |
| `uav_orion.lod00.dag` | `cae90a195068a9f81f07153b46a1951bc621215bd378f7ef7f940d38f41c3514` |
| `nasams_fcs.lod00.dag` | `01e4785ea97e2d84c7636f5c800c229d05301250118b934bcc29cae0ddd26d2a` |
| `range_watch_tower.lod00.dag` | `b234e42893541a064f55844f510ee386d44f5bba3b7e84424cb0e7c426191487` |
| `mq_1l_usa.lod00.dag` | `a7b19f454de82751fea0aece894d882522f5e8bbdca522c14a621f96eb77b106` |
| `cargo_ship_liberty.lod00.dag` | `7dd89f5d98aadc14f6890cc97982222b10539f66d5f0aaa9d8a2bb9dca022872` |

The official pack outputs are:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `pytho_assets.grp` | 416,947 | `c5425b37bf4307f13787ad84ba2b824f708f77aaec0d4769a0d4239bec011c4f` |
| `pytho_assets.dxp.bin` | 815,024 | `50b655c1972d0ab000b827c4f0234d1dad1593227831887ce126241d53d5ea31` |
| `grp_hdr.vromfs.bin` | 538 | `e2405851bd89cdfe352358024bcd26c7fb88285e88fb7ff300af1df4e03d26b9` |

The pipeline is implemented by [`../native/dagor-client/tools/export_pytho_dags.py`](../native/dagor-client/tools/export_pytho_dags.py), [`../native/dagor-client/tools/build_pytho_assets.sh`](../native/dagor-client/tools/build_pytho_assets.sh), and [`../native/dagor-client/tools/stage_pytho_viewer.sh`](../native/dagor-client/tools/stage_pytho_viewer.sh).

## Source build

The build uses the pinned arm64 Jam tool and a Command Line Tools shim with macOS SDK 15.4. Sound is disabled for the source build because the official source checkout does not include the commercial FMOD SDK.

```sh
cd /private/tmp/pytho-dagor-20260810/dagor-engine/samples/dngSceneViewer/prog/_aot
env _DEVTOOL=/private/tmp/pytho-dagor-20260810/dagor-devtools \
  /private/tmp/pytho-dagor-20260810/dagor-jam-arm64/jam -sPlatformArch=arm64 -sHaveSound=no -j13

cd /private/tmp/pytho-dagor-20260810/dagor-engine/samples/dngSceneViewer/prog
env _DEVTOOL=/private/tmp/pytho-dagor-20260810/dagor-devtools \
  /private/tmp/pytho-dagor-20260810/dagor-jam-arm64/jam -sNeedDasAotCompile=yes \
  -sPlatformArch=arm64 -sHaveSound=no -sFmodStudio=none -j13
```

The final link printed `SUCCESSFULLY built dng_scene_viewer-dev`. Jam returned status 1 because one bundle-copy target failed after the executable and AOT output were produced; the executable was copied into the separately packaged app and ad-hoc signed. This is recorded rather than reported as a clean all-target build.

## Measured non-render results

The parser, invalid-version check, ship case, ENU heading, and 100-meter scale tests pass. A 100-frame benchmark measured contract validation only:

| Entities | Bytes per frame | Validated frames per second |
| ---: | ---: | ---: |
| 100 | 20,144 | 3,810.3 |
| 500 | 101,050 | 827.5 |
| 2,000 | 406,806 | 224.1 |

These values exceed the 20 Hz publisher rate. They do not establish ECS time, GPU time, or display FPS.

## Native render validation

| Phase | Accepted final frame | On-screen Metal FPS | Result |
| ---: | --- | ---: | --- |
| 100 entities | sequence 99 at 4.95 s | 106.6 | Passed |
| 500 entities | sequence 199 at 9.95 s | 107.6 | Passed |
| 2,000 entities | sequence 239 at 11.95 s | 106.9 | Passed |

Periodic frame counters in the runtime log imply 104.8–107.5 rendered frames per second during these phases. The screenshots show the East District scene and FPS counter. The stress-test grid was placed 600 meters north to keep large ship resources from surrounding the default camera, so these screenshots do not visibly prove the individual asset headings.

The runtime log does prove pack and model creation. It records `uav_orion`, `mq_1l_usa`, `nasams_fcs`, `range_watch_tower`, and `cargo_ship_liberty` as `riExtra` resources. The replay scenario records the two aircraft at the requested ENU positions and the two towers at east -50 and +50 meters. Heading math and the 100-meter conversion pass the native transform test.

The first runtime iterations exposed two integration defects. `createEntitySync` was invalid for render-resource entities, so the overlay now uses deferred `createEntity`. Destroying a `rendinst` called the sample's loot-grid callback even though this viewer has no loot grid, so Pytho render instances set `ri_extra__isBeingReplaced` during replacement. The clean runs contain neither error.

After successful validation, pressing F12 entered the stock DaEditor path and crashed in Metal debug-line rendering at `CachedDebugLinesData::flushLines`. A fresh run repeated the replay test without F12 and completed cleanly. The F12 editor path remains unsupported in this build.

The archive restore and resource-staging helper is `native/dagor-client/tools/restore_east_district.sh`. It verifies the exact archive SHA-256 before extraction. Full evidence and pass/fail screenshot labels are in `native/dagor-client/evidence/20260810/RESULTS.md`.

The checked-in packs do not require Blender or daBuild at runtime. Rebuilding them requires external Blender 4.2, dag4blend 2.5.0, and `daBuild-dev`; those tools are intentionally not copied into Arena. Their default `/private/tmp` paths are configurable through `PYTHO_BLENDER_BIN`, `PYTHO_DAG4BLEND_DIR`, and `PYTHO_DABUILD_BIN`.

## Remaining gates

| Gate | State |
| --- | --- |
| Stock East District Metal rendering | Passed |
| Official `.dag`, `.grp`, `.dxp.bin`, and group header | Passed |
| Custom source build and AOT generation | Passed, with one post-link bundle-copy failure noted above |
| Pytho pack mount | Passed in the native runs |
| Live full-frame relay connection and 20 Hz apply | Passed |
| Replay branch/scrub | Passed in clean native run |
| ENU position and 100-meter scale | Passed in runtime log and native test |
| Heading conversion | Passed by native test; fixed-camera visual proof remains open |
| Environmental response effect | Resource load passed; weapon-grade explosion remains open |
| 100, 500, and 2,000 entities at 60 FPS | Passed at 106.6, 107.6, and 106.9 FPS |
| Free-camera/F12 editor path | Failed in stock Metal debug-line renderer; do not use |
