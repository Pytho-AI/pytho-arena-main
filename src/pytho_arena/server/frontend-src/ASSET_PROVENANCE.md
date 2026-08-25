# Arena visual asset provenance

These approved local files were copied from `pytho-drone-range/public/assets`. They
were extracted read-only from the local War Thunder installation under the project's
approved asset workflow. No packed game file is included here.

| File | Purpose | SHA-256 |
| --- | --- | --- |
| `public/assets/gulf_arid_terrain_albedo.jpg` | Arid range terrain albedo | `5a72a46d301f2d12c8e7ea7ff07cbcf39a8fb8aa9e67623373d2a862e3f50416` |
| `public/assets/explosion_vfx.png` | Terminal-event fire plate | `be667819c54bb30d5ecc1cfd94f9718336714149de8def375e3d7006bab0660a` |
| `public/assets/explosion_smoke_vfx.png` | Terminal-event smoke plate | `74c57e023d26dbde125f045506ff87ea657d8504d3b61e6b8ca0e019c7e9bce5` |
| `public/assets/orion_ucav.obj` | Detailed Orion UCAV mesh | `8805ea860edc47aa2f08df28b035245910afeb2d1409e50377e57f3cf5597f5a` |
| `public/assets/orion_ucav.mtl` | Orion material map | `bd5862de2cbff214783e3f33927068f9d66fcec56e0a89e5debb188324bd2cc3` |
| `public/assets/orion_ucav_albedo.png` | Orion albedo | `fb3705c7bf886b83ed3d68f2929d5e494dd8b16bf42554c0ae109b4adce43479` |
| `public/assets/mq_1l_usa_lod2.obj` | Detailed MQ-1 mesh | `7d700d507d7dc55ec82711aa203db8039db2bef8e66f484d2de02d2c0aac9a40` |
| `public/assets/mq_1l_usa_lod2.mtl` | MQ-1 material map | `29a7746fe6d4e577e365c579e1f85ce9342b0c915addb9bf5ad6bffd79cbb4ea` |
| `public/assets/mq_1l_usa_albedo.png` | MQ-1 albedo | `4edff2dabefcca946075def5c4a4aee956384da67b9419c5126c26b63b887353` |
| `public/assets/liberty_cargo_ship.obj` | Detailed cargo ship mesh | `620716cc3ea856cc14cdec8879d1f1813aa1b7fbd803fe47b1acbf2399b69c99` |
| `public/assets/liberty_cargo_ship.mtl` | Cargo ship material map | `4048c9dbe33a509c6b90e8f42df7123a1e79380d0b4362e17eb93438f6f9f8c9` |
| `public/assets/liberty_cargo_ship_albedo.png` | Cargo ship albedo | `ecb075f6c684446769899936034aedfbde7be6e9f951b72ba0a9176662590cf2` |
| `public/assets/nasams_fcs_vehicle.obj` | Detailed response vehicle mesh | `4992f1454b72260e3d8dc02a6fd4f658d94e6c323a0d3cf8df82d611768b4403` |
| `public/assets/range_watch_tower.obj` | Detailed sensor tower mesh | `645f2ffc045cf855eb2d085ead9cbce8297c19cf258c3e01d93919172b1bf2ce` |
| `public/assets/f_16c_block_50_lod2.obj` | Parked F-16C LOD2 source mesh; runtime hides external stores | `04486d2c30f62cebc043fcc4bb6693699533a7277549002d0cbbffa568b8a6fa` |

Detailed OBJ geometry is used for the normal scenario size. Convex low-cost geometry
derived from each loaded OBJ is used with `InstancedMesh` at 100 or more truth
entities. Procedural geometry is only the load-failure fallback.

## Mesh extraction chain

- `uav_orion`: `ussr_orion.grp`, pack SHA-256 `6cd67a94479eea69514fd8f2e95db15dfe2b066eb8ec2ab44a3c48dda2749474`, LOD 2.
- `mq_1l_usa`: `usa_mq_1.grp`, pack SHA-256 `251ae2de6a8e50aea12e05f85fe2a48a0537108a0925845cd83e3cccd9a06d2e`, LOD 2.
- `cargo_ship_liberty`: `usa_cargo_ship_liberty.grp`, pack SHA-256 `ac0dbd04b71b9f7576c349ce4c40b5603bbfe674f883b01ffb216b90b04cd1ef`, LOD 2.
- `nasams_fcs`: `se_nasams_fcs.grp`, pack SHA-256 `33c121eb9fe4525515c6a5728ef7a8a87d17ac40155dc2037287c381714edaff`, LOD 2.
- `range_watch_tower`: `units.grp`, pack SHA-256 `e049f4ac97bc64f262ccb94950910c2f5bb3ed8b811d6bfef955c33b8fb4d5ea`, LOD 0.
- `f_16c_block_50`: `usa_f_16.grp`, resource `f_16c_block_50`, LOD 2. Arena
  renders the airframe, canopy, control surfaces, hook, wheels, and landing gear,
  and hides external stores, pylons, pods, flares, and the exhaust-flame groups.

Gaijin `dumpGrp-dev` from toolkit release `fea0a2b3ae5acdb25e088e57a8fb1f77d5ba3e1d`
inspected the resource tables. Dagor Engine commit
`caaa956346c5f0172bc36afad4192f65d5999700` provided the format reference. Dagor
Asset Explorer commit `1f0d1e04ded04bf9b28e8d5be93cb79714f505d3` decoded geometry and skeleton
transforms. `unoodle` from oozextract commit
`320dc3aeb7214c114b5475ae02d89dc2f5738df6` decoded Oodle-compressed geometry.
Pillow 11.3.0 converted decoded DDS textures to PNG without resizing or color edits.

## Synthetic image prompts

Terrain:

> Create a tileable top-down material texture for an arid Persian Gulf coastal island. Natural limestone, compact sand, small gravel, pale salt crust, dark weathered rock flecks, and sparse dry scrub. No water and no shoreline. Photorealistic game-terrain albedo, orthographic, evenly distributed, flat diffuse light, and no buildings, roads, vehicles, aircraft, people, text, watermark, border, or perspective distortion.

Fire:

> Create a square realistic aerial interception explosion VFX plate on a perfectly uniform pure black (#000000) background. Compact irregular orange fireball with a small white-hot center, dark charcoal smoke rising above it, a few small glowing fragments. No checkerboard, no transparency preview, no rings, no circular shockwave, no HUD, no aircraft, no ground, no sky, no text. Keep generous pure-black padding to every edge. Centered military simulation billboard texture, 1024x1024 PNG.

Smoke:

> Create a square realistic dark aircraft-fire smoke plume VFX plate on a perfectly uniform pure black (#000000) background. Thick irregular charcoal and black smoke with softer gray edges, rising and curling upward from a compact source. A tiny trace of dull ember orange only at the bottom, no open flame and no bright center. No checkerboard, no transparency preview, no rings, no circular shockwave, no HUD, no aircraft, no ground, no sky, no text. Keep generous pure-black padding to every edge. Centered military simulation billboard texture, 1024x1024 PNG.
