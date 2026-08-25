# Arena native Dagor client

This directory contains Arena's copy of the Pytho `frame-v1` boundary, Dagor source overlay, official converted resources, and asset build pipeline for `dngSceneViewer`.

## Status

| Gate | State |
| --- | --- |
| Official East District archive | Passed; 2,463,450,557 bytes, SHA-256 `641e5797d4b3af639b9d794892b95aafabad81f629f2f3180506ba22f8245416` |
| Stock arm64 viewer on Apple M4 Pro Metal | Passed; East District rendered at 104.5 FPS after ten minutes |
| Five official dag4blend exports | Passed |
| Official daBuild `.grp`, `.dxp.bin`, and group header | Passed |
| Pytho source viewer build | Passed; arm64 executable with AOT-compiled overlay |
| Pytho resource-pack and five DAG model loads | Passed in runtime log |
| Loopback connection to `127.0.0.1:46000` | Passed; complete frames applied at 20 Hz |
| Replay branch/scrub | Passed in a clean native run |
| Native 100/500/2,000 entity render and 60 FPS | Passed at 106.6/107.6/106.9 FPS |

The response effect loads the sample's environmental sparks resource. It is not a weapon-grade explosion. Heading conversion passes the native transform test, but the fixed-camera screenshots do not show the model headings. The stock F12 DaEditor path crashes in Metal debug-line rendering and is not used.

## Transport

```text
Arena frame-v1 producer -> loopback relay at 127.0.0.1:46000 -> Dagor WebSocket client
```

The publisher sends one complete `frame-v1` JSON text message at 20 Hz. The limit is 8 MiB. The client keeps the newest unconsumed snapshot, drops stale sequence numbers, and caps the combined visible entity, track, and successful-effect count at 2,000.

This directory does not change Arena server or frontend wiring. The Arena runtime must publish the documented contract to the loopback relay; the included validation streamers can exercise the native boundary independently.

The overlay defines ECS templates for UAS, ground response assets, sensors, tracks, ships, and effects. Wire positions are ENU meters: Dagor `X=east`, `Y=up`, and `Z=north`. Heading zero points along `+Z`; heading 90 points along `+X`.

## Verification

```sh
make test
make benchmark
make assets
make stage-assets
```

Restore the exact East District archive and stage the existing Pytho packs with:

```sh
native/dagor-client/tools/restore_east_district.sh
```

`make assets` checks approved Arena frontend asset hashes, runs Blender with official dag4blend 2.5.0, then runs official `daBuild-dev`. daBuild uses ignored `assets/build` and `assets/cache` scratch directories, then promotes these non-empty artifacts:

- `assets/packs/pytho_assets.grp`
- `assets/packs/pytho_assets.dxp.bin`
- `assets/packs/grp_hdr.vromfs.bin`

`make stage-assets` places only those Pytho-owned outputs in the extracted viewer's `content/pytho/res` directory. The source overlay patch mounts that folder.

The checked-in packs can be staged without rebuilding them. Regeneration requires external Blender 4.2, dag4blend 2.5.0, and `daBuild-dev`; they are not vendored here. Set `PYTHO_BLENDER_BIN`, `PYTHO_DAG4BLEND_DIR`, and `PYTHO_DABUILD_BIN` when those tools are not installed at the defaults in `tools/build_pytho_assets.sh`. The default shader path matches the restore helper's `/private/tmp/pytho-dagor-20260810` layout.

The native parser harness uses Foundation only. It does not read or change the War Thunder installation.

See [`../../docs/DAGOR_CLIENT.md`](../../docs/DAGOR_CLIENT.md) for paths, hashes, build commands, runtime evidence, and remaining gates. Screenshot classifications and runtime excerpts are in [`evidence/20260810/RESULTS.md`](evidence/20260810/RESULTS.md).
