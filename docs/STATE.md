## Goal
Execute `docs/CLAUDE_COA_ENGINE_OVERHAUL_PROMPT.md` in full: NPC-scale simulator factory across
pytho-arena (frontend) and coa-engine (authoritative backend), Phases 0-8, all gates green with
exact evidence. Preserve user work. Do not push or deploy.

## Now
SHIPPED 2026-08-18. Arena main = 39850f1 (merge of akshay/3dsim); branch pushed at 9d8bcda. The
user explicitly reversed the standing "do not push or deploy" constraint mid-session.
Arena has no deploy pipeline of its own in this repo; only coa-engine deployed (EC2 staging,
healthy at https://stagingapi.pytho.ai/coa-api/api/health).
Arena work resumes at Phase 5.3 (authenticated edge + role-filtered binary WS) and Phase 6.
NOTE: `contracts-import/dist/` was being swallowed by the blanket `dist/` gitignore rule — now
un-ignored, matching the same fix in coa-engine.

## Next
1. (COA) Phase 2 ECS core -> Phase 3 simulator factory.
2. Arena Phase 5: authenticated edge, role-filtered binary WS using src/contracts codecs.
3. Phases 2-8 per the canonical prompt, each ending at its named gate.
4. BEFORE Phase 6 (user amendment 2026-08-18): update renderer ADR, verify the RenderProjection
   seam, extend render/asset manifests for the UE 5.8 client, define the named graphics hardware
   profile, and author the separate graphics vertical-slice goal with its measurable gates.

## Constraints
"run it yourself. dont ask me to run commands that you can execute yourself moving forward"
"yes all unclassified"
"close the scene viewer when you are done using it"
"please dont do mediocre work. pay attention to detail"
"give me an eta of the full completion periodically"
"don't digress away from the work"
"don't stop until it is done"
"i want a one shot implementation"
"no mediocre or buggy work at the end of the turn"
"the MMO is for NPC bots. we are not creating user playable game"
"i do want an option to add a user player"
"the user player mode is for training only. the user can train their own bot manually that way vs RL"
"Preserve user work. Do not push or deploy." (from the active /goal, 2026-08-18)
"Do not attempt to reach this target solely by expanding Three.js." (user, 2026-08-18)
"Do not derail the current backend goal by downloading or building Unreal immediately." (user, 2026-08-18)
"Do not claim Image 6 parity from concept art or Three.js screenshots. Only a capture from the
implemented renderer can pass that gate." (user, 2026-08-18)
Use fictional composite layouts; do not copy exact current coordinates, defenses, routes, force posture, weak points, or strike paths.
Pytho Arena is the frontend; COA Engine is the authoritative backend; RL stays outside the simulation loop.
Do not push unless the user asks.

## Decisions
DECISION (2026-08-18, user): this session targets the full Phase 0-8 scope, not a subset.
DECISION (2026-08-18, user): scenario-compiler acceptance runs call the real Claude API (key file
`~/Downloads/anthropic-key.txt`, read into the environment at call time, never committed, printed,
or logged); all checked-in tests use deterministic fake/recorded providers.
DECISION (2026-08-18, user): the generated-code isolation boundary is OCI containers via
colima + docker CLI (installed 2026-08-18; docker server 29.5.2).
DECISION (2026-08-18, user): fully unattended run — novel generated executable artifacts stay in
enforced quarantine with review packets; final Raven execution composes already-approved artifacts.
DECISION (2026-08-18): COA had uncommitted docs on `main`; created local `akshay/3dsim` from
`51e5ad7` carrying them, per the safe-branch rule. Nothing reset or discarded.
DECISION (2026-08-18, user amendment): high-fidelity visual target is the perceptual quality of
docs/evidence/20260818/proposal/06-notional-200-agent-airbase-swarm.png. Three.js becomes the
lightweight tactical/fallback renderer; a UE 5.8 presentation client (native + Pixel Streaming
embed) consumes the same role-filtered projection stream via a renderer-neutral RenderProjection
boundary, interpolates 20 Hz -> 60 Hz, supports replay and trainer input, holds no authoritative
logic. Unreal work is deferred to a separate graphics vertical-slice goal defined before Phase 6
(renderer ADR update, contract seam, render/asset manifest extension, named hardware profile,
gates: 1440p/60 FPS, 200 agents, visual quality, asset provenance, capture-only parity claims).
See docs/adr/0002-renderer-strategy.md.
Keep Dagor East District as the native engine test harness; Arena remains the product interface.
Treat document images and maps as semantic references, never spatial truth.
Generate real-site imports as fictional layouts and require human approval.
Do not update or weaken the golden-rollout fixture; its digest changes across unpinned Torch builds.
Use `pip wheel --no-deps --no-build-isolation` because the local `build/` directory shadows the optional `build` CLI module.
Keep Dagor as the rendering client; keep authoritative batched physics in Pytho so RL remains headless and tensorized.
Benchmark Rapier before adding it as a contact kernel; do not make the dependency decision from feature lists alone.
Store legacy state in scenario units; SI physics backends require an explicit `world.meters_per_unit` conversion.
Name the first model `multirotor_6dof`, but describe it as a synthetic thrust-vectored surrogate, not a rotor or War Thunder flight model.
Use immutable child runs for operator ROE decisions; preserve the parent evidence and the existing RL action tensor contract.
A typed effector is declared by `ResponseSpec.effector`; absent (`None`) it keeps legacy always-on behavior and the existing content hash.
Counter-UAS event attributes are snake_case to match the `SimulationEvent` envelope; frame-level dicts stay lowerCamelCase, as `replay.frame()` already was.
One replay frame carries one coordinate contract — scenario world units. Metric lane values are rescaled on the way into a frame; only `*_m`/`*M` names are meters.
Pin the authorization evidence, but aim the effect at the current track estimate: geometry from a frozen position can never reach a moving track. Record `authorized_offset_m` instead.
The lane holds an authorization until the track is inside the firing envelope, so one recorded attempt means one trigger pull rather than one tick.
Track ids are opaque and assigned in first-detection order (`track-001`), never derived from entity ids, so the operator picture cannot leak truth identity.
Classification uses scenario-declared protected relationships as cooperative identification (the IFF equivalent) and measured kinematics for everything else; the opponent relationship is never read.
Mirror the das render-count guard in TypeScript: visible entities + tracks + successful effects share one 2,000-item budget.
Use one persistent Claude Code `/goal` session with measurable implementation gates; do not treat one-shot as one unreviewed commit.
Keep Arena presentation-only and move authoritative world state, simulation, fidelity, evidence, and RL stepping to COA Engine.
Audit and reuse the current code before replacing it; benchmark before selecting a native ECS or physics dependency.
Treat MMO scale as autonomous NPC scale, not a many-human game; one optional human uses the same intent/authority path as a bot.
Limit human control to demonstration/correction training; record the bot-visible observation and intent stream for imitation learning and comparison with RL.
Generate simulator code and procedural asset recipes asynchronously during scenario compilation or explicit paused injects; the fixed tick runs only tested, hashed, pinned artifacts.
Make scenario-to-simulator a generic service whose outputs include MDMP planning and counter-UAS simulator bundles.

## Facts
Phase 0 baseline SHAs (2026-08-18): pytho-arena `c88756f` on `akshay/3dsim`; coa-engine `51e5ad7`
on new local `akshay/3dsim`. All changed-file coverage uses these SHAs.
Phase 0 trace (2026-08-18), verified file:line. Chain: POST /api/runs app.py:215 -> env ctor
compiles (env.py:73 -> compiler.py:22-36, contracts.py:35-59, scheduler.py:17-29) -> rollout
dispatch app.py:236-240 (recorded_cuas_rollout when a typed effector exists, replay.py:275-276) ->
episode loop replay.py:340-352 -> RunStore.save runs.py:61-76 (immutable var/arena/runs/<uuid>.json)
-> GET /api/runs/{id}/replay app.py:372 -> adaptArenaReplayFrame replayAdapter.ts:145 ->
ArenaViewport.tsx:1818. Branch endpoint app.py:257-320 verifies byte-identical pre-decision prefix
(replay.py:279-296) and 409s on divergence.
RNG is stateless SplitMix64 keyed (seed, step, channel) — rng.py:20-52; channels: spawn 1-2,
detection 10, measurement 11+, response 30, attack 40 (env.py:432-836). No global RNG.
Raven scenario = scenario/library/strait-sentinel-airbase.json (kinematic_2d, step 1.0s,
150 steps, environment gulf_airbase); JLC urban = jlc-urban-counter-uas.json
(document-85fe0ad9d371, coastal_urban). multirotor_6dof/orientationWxyz never fires for Raven —
only scenarios opting in via simulation.physics_backend.
Browser asset choice is a name/mission regex heuristic at sceneManifest.ts:18-28 (Phase 6 replaces
with explicit render components). frame-v1 conversion is browser-side: sceneStateToFrameV1
replayAdapter.ts:272-341. 2,000-item guard copies: replayAdapter.ts:19/27+312-333, both
frame-v1.schema.json maxItems:25/30, loopbackFrameServer.mjs:73, frame_receiver.mm:99-101.
Scenario compile contract: EnvironmentContract (contracts.py:17) pins scenario_hash,
physics_backend, dims, OBSERVATION "faction-belief-v1" / ACTION "normalized-command-v2".
Checkpoint load re-validates scenario_id+hash+contract hash (training/checkpoints.py:81-99).
Baseline suites (2026-08-18): arena `.venv/bin/pytest` -> `1 failed, 122 passed` (the known golden
torch mismatch only); coa `.venv/bin/python -m pytest -q` -> `1086 passed in 84.32s`; vendored gbc
(from coa-engine/gbc, gbc's own venv) -> `543 passed, 2 skipped` (one load-order flake
`test_psa_live_service.py::test_live_server_recompute_workbench`: failed once under 4-suite
parallel load, passed 3/3 isolated and on full rerun — pre-existing, untouched); frontend
`npm test` -> `Tests 41 passed (41)`; `npx tsc --noEmit` -> exit 0.
Arena pytest note: `addopts = "-q"` already applies -q; passing `-q` again (-qq) suppresses the
final count line. Run bare `.venv/bin/pytest`.
Hardware profile (2026-08-18): Apple M4 Pro, 12 cores, 24 GiB RAM, macOS 26.5.2; Node v25.9.0;
both repo venvs Python 3.12.13 (COA production container is python:3.11-slim).
Contract toolchain: no protoc/buf/grpcio/protobuf installed in either venv yet;
`@bufbuild/protobuf` 2.14.0 reachable on npm; grpcio-tools bundles protoc for Python.
Sandbox runtime: colima VM (4 CPU / 8 GiB) + docker CLI, server 29.5.2, context `colima`.
Repository: `/Users/akshay/Dev/pytho/pytho-arena`; branch `akshay/3dsim`.
Canonical cross-repo prompt: `/Users/akshay/Dev/pytho/pytho-arena/docs/CLAUDE_COA_ENGINE_OVERHAUL_PROMPT.md`.
COA integration pointer: `/Users/akshay/Dev/pytho/coa-engine/docs/CLAUDE_ARENA_INTEGRATION.md`.
RL merge commit: `b8242df`, with parents `2e0b92f` and `7b9ef48`; no unresolved merge entries remain.
Physics/C-UAS handoff commit: `b9ab2b0`; it is explicitly WIP and was not pushed.
Current source/package version: `0.5.0`; Python 3.12.13; Torch 2.13.0.
Source DOCX SHA-256: `85fe0ad9d3711b85eaebb07273a859b0c6d78797a7c0d60589eee181c917bcb8`.
Reverse DOCX SHA-256: `e02812ad6f279a7daf886662970bdb5fd26c1c9099664291869f0cd988bb4a2a`.
Final wheel: `/private/tmp/pytho-arena-wheel-release.mTYdIo/pytho_arena-0.4.0-py3-none-any.whl`; SHA-256 `dafd602c4da8d1d32c907fac5f16ee77513c27c06e64b6395de7829c082e29f9`.
Current environment: Python 3.12.13, Torch 2.13.0, Pytho Arena 0.4.0.
`core/env.py` map: `StepOutput` 33-38; `BatchedScenarioEnv` 41-; `__init__` 61-91; `_compile` 93-211;
`_compile_relationships` 237-268; `_compile_sensors` 270-343; `_compile_responses` 344-421;
`reset` 430-547; `_observations` 549-570; `_gather_actions` 584-635; `step` 637-708;
`_apply_sensing` 710-743; `authorize_effect` 759-777; `_apply_responses` 778-826; `_apply_attacks` 828-841.
The shipped counter-UAS lane scenario is `document-85fe0ad9d371` (`library/jlc-urban-counter-uas.json`);
both of its responses declare an `rf_jammer` effector with a 45 s authority window.
`ensure_library()` only seeds scenarios that do not exist yet, so an existing `var/` keeps its v1 —
use a fresh `PYTHO_ARENA_DATA_DIR` to pick up the typed effector.

## Done
Claude implementation prompt — RESULT: the 1,072-line canonical prompt defines the two-repo
authority split, generic three-scenario simulator factory, deterministic NPC engine, multi-fidelity
state, training-only demonstration/imitation path, RL outer loop, 2026-quality 3D rubric, generated
artifact quarantine/approval rules, staged implementation gates, load targets, and exact evidence.
Prompt validation — RESULT: 22 required semantic patterns, all 9 phases and gates, the 471-character
`/goal`, exact pointer/command synchronization, external DOCX presence, zero trailing whitespace,
and both repo diff checks passed.
Independent review — RESULT: three repo/architecture audits plus a final adversarial prompt review
were applied. The final pass closed approval deadlock, OS-enforced generated-code isolation,
three-scenario factory proof, offline bundle closure, immutable rollback, WebSocket topology, MDMP
transition parity, synthetic trainer-input labeling, verifier recursion, and visual acceptance gaps.
Document import — RESULT: the nine source sections create a reviewed coastal-urban scenario with 14 actors and 30 typed static assets.
Reverse document — RESULT: the Raven brief renders as three clean US Letter pages with named headings, two input tables, a scene figure, references, and traceability.
Arena integration — RESULT: mission-rail DOCX import/export, environment switching, urban/coastal terrain, procedural quadcopters, harbor assets, and Raven graphics are packaged.
Browser acceptance — RESULT: Raven replay/effects and 100/500/2,000 entity loads reached 120 FPS with no browser or scene errors.
Native Dagor gate — RESULT: packed resources, 20 Hz frame-v1 stream, replay scrub, ENU/heading/scale, and 100/500/2,000 entities passed; stored FPS is 106.6/107.6/106.9.
Package gate — RESULT: the rebuilt wheel contains both scenarios, frontend bundle, F-16, and Raven brief image; installed-wheel smoke passed.
Cleanup — RESULT: ports 8096/46000/9232 are closed; dngSceneViewer, Chrome QA, relay, Arena server, and Pages are stopped.
RL merge gate — RESULT: upstream algorithm registry and UI are combined with document import; 56 focused Python tests, 32 direct tests, 27 frontend tests, TypeScript, and production build passed.
Physics contract gate — RESULT: explicit pose/twist state, API version rejection, optional metric scale, legacy hash preservation, and shared render scale passed 9 Python and 5 frontend tests plus TypeScript.
Multirotor gate — RESULT: 27 physics/generalization tests passed; CPU medians for 100/500/2,000 bodies at 50 substeps were 7.87/11.71/26.62 ms.
Replay attitude gate — RESULT: multirotor replay carries 3D position, velocity, and body-to-world quaternion data; the browser converts it to heading, pitch, and roll; instanced and detailed models passed 15 focused scene tests and TypeScript.
Current verification — RESULT: 86 Python tests passed with the one known golden test deselected; 33 frontend tests, TypeScript, Ruff, and the production build passed.
RL absorption — RESULT: local merge commit `b8242df` contains the latest `origin/main` RL framework; it was not pushed.
Claude handoff — RESULT: `CLAUDE_HANDOFF.md` records the workstreams, Git topology, evidence, known C-UAS defects, and exact continuation sequence.
C-UAS contract repair — RESULT: all 11 audited defects are closed and `tests/test_cuas.py` grew from 4 to 22 tests covering mixed timestamps, stale and replayed reports, decision ordering, hold/deny/authorize, one-authorization-one-activation, expiry, pinned evidence, stable event ids, and engine-reported outcome.
Engine authority gate — RESULT: `ResponseSpec.effector` makes a response authority-gated; `authorize_effect` opens one entity for one effects tick; the untouched golden digest proves legacy replay output is byte-identical.
Counter-UAS lane — RESULT: `simulation/cuas_lane.py` turns measurements into opaque tracks, classifies them, opens requests, replays scheduled decisions, fires inside the envelope, and records the engine's outcome; 14 lane tests pass.
Immutable branch — RESULT: `POST /api/runs/{parent}/branches` re-runs the parent's exact inputs, verifies the pre-decision prefix, and saves a child run; the live API confirmed the parent is unchanged and frames 0-9 plus their event ids are identical.
Operator decision UI — RESULT: the inspector's authority queue, fused-track counts, decision timeline marks, scope track symbols, 3D track markers, and analyst decision scorecard render in the browser; 41 frontend tests and TypeScript pass.
Native item guard — RESULT: `sceneStateToFrameV1` now counts visible entities + tracks + successful effects against one 2,000-item budget, mirroring `pytho_frame_overlay.das`, and both frame-v1 schemas bound `tracks`.

## Open items
The full Python suite has one known golden mismatch: expected `e34418d558362e7dddc81da7c212e93fbdcfe7695b31446f9b20b5d45ca762d6`, actual `3c5325ae746af38f3fde1afe19c1e5637b84dc3fd8ff82ffe6ec27a8bf299ba2`. The other 64 tests pass; the fixture is intentionally unchanged.
Vite reports the existing bundle-size warning for the 854 kB Three.js application bundle. Browser load acceptance is recorded separately.
The lane associates one track per detected entity. Real association, track loss, and reacquisition (roadmap P0.1) are not implemented, so track count equals detected-entity count.
Decision latency is measured from request open to decision, not from an operator's first look; there is no per-seat workload model yet.
The branch endpoint runs the child episode synchronously inside the request, like `POST /api/runs`. A 150-step lane run takes roughly a second on CPU; a longer scenario will need a job.
`authorized_offset_m` is recorded but never gates an engagement; whether a large offset should force re-confirmation is an open product question.

## Failed attempts
ATTEMPT 1 [L1]: the first semantic validator searched for `Pytho Arena.*frontend`, but the prompt
uses the repo name `pytho-arena`; corrected the check to exact required phrases and reran it green.
ATTEMPT 1 [L1]: `.venv/bin/python -m build --wheel` -> local `build/` shadows the optional build CLI; use `pip wheel --no-deps --no-build-isolation`.
ATTEMPT 2 [L1]: pack audit referenced a nonexistent `pack_manifest.sha256`; recorded byte counts and SHA-256 values match `docs/DAGOR_CLIENT.md`.
ATTEMPT 3 [L1]: `comments_extract.py` without `--out` -> corrected invocation wrote a zero-comment report.
ATTEMPT 4 [L3]: `.venv/bin/pip install -e . --no-deps` -> build isolation attempted a blocked network fetch for `setuptools>=69`; use the installed build toolchain with `--no-build-isolation`.
ATTEMPT 5 [L4]: refreshed the editable install to `0.5.0` with `--no-build-isolation` -> test processes still resolved `importlib.metadata.version("pytho-arena")` as `0.4.0`; inspect duplicate metadata on `sys.path` before another install.
ATTEMPT 1 [L1]: handoff API probe used inline `async def` -> Python rejected the compound statement after a semicolon with `SyntaxError`; use a temporary script file for the probe.
