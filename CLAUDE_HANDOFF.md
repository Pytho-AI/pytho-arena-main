# Claude handoff: Pytho Arena 3D simulation

Date: 2026-08-17

Repository: `/Users/akshay/Dev/pytho/pytho-arena`

Branch: `akshay/3dsim`

## Read order

1. Read `CLAUDE.md`. It contains mandatory repository procedures.
2. Read `docs/STATE.md`. It is the short current-state ledger.
3. Read this file in full.
4. Run `git status --short --branch` before editing anything.
5. Do not reset, abort a merge, discard, or rewrite local changes.

## User intent and constraints

The user is building an unclassified counter-drone simulation and training product for
an Army Phase 2 effort. The product should combine a game-quality 3D experience with
deterministic simulation, RL, scenario generation from DOCX, reverse DOCX export, and
evidence-grade replay.

User constraints that still apply:

- Run commands yourself. Do not ask the user to run commands that you can run.
- Use subagents for independent work.
- Keep all scenarios and data unclassified.
- Use fictional composite layouts. Do not encode current real-site coordinates,
  defenses, routes, force posture, weak points, or strike paths.
- Do not claim that the public Dagor source contains War Thunder's complete aircraft
  flight model. It does not.
- Close `dngSceneViewer` and local test services after using them.
- Give periodic ETA updates during long work.
- Do not push unless the user asks.

## One-sentence state

The 3D/Dagor/document, RL, physics, replay, roadmap, and C-UAS contract work is locally
committed. The C-UAS contract commit is explicit WIP that must be reviewed before a
product claim.

## Git topology after the RL merge

- RL merge commit: `b8242df4adef9951c419aad141f4a081be8f56ea`
- Physics/C-UAS handoff commit: `b9ab2b0` (`WIP: hand off drone physics and C-UAS
  contracts`)
- Merge parents: `2e0b92fb4ce61342225a0d6ece84b8bbe2e0bd99` and
  `7b9ef48222171fdc1274070bd2e369ad767a1515`
- `origin/main` at the last fetch: `7b9ef48222171fdc1274070bd2e369ad767a1515`
- `origin/akshay/3dsim`: `ba37605`
- The local branch was three commits ahead of `origin/akshay/3dsim` after the merge.
- The merge is finished. There is no `MERGE_HEAD` and no unresolved conflict entry.

The WIP handoff commit contains:

- physics state API v2, metric scale, and the multirotor 6-DOF surrogate;
- 3D replay and viewport attitude;
- the counter-UAS roadmap and this handoff;
- the C-UAS contract WIP and tests.

The worktree was clean before the final handoff-note commit. Confirm it before
continuing:

```bash
git diff --stat
git status --short --branch
```

## RL absorption audit

The latest RL commit is `7b9ef48 feat: generalize RL training framework`.

The audit found:

- all 26 paths changed by `7b9ef48` are represented in the conflict-free merge index;
- all `training/algorithms/*`, `training/contracts.py`, `training/registry.py`,
  `training/session.py`, `training/trainer.py`, `server/trainings.py`, and
  `tests/test_training.py` blobs match `origin/main`;
- `App.tsx`, frontend types, `server/app.py`, README, and package metadata differ only
  where the RL work was combined with the branch's 3D and DOCX features;
- the algorithm registry, parameter UI, `/api/training-algorithms`, legacy parameter
  migration, deterministic training, and checkpoint policies are present;
- merge commit `b8242df` now places `7b9ef48` in branch ancestry.

## Committed base already on the branch

Commit `2e0b92f Add document-driven 3D scenarios and Dagor client` contains the prior
large delivery:

- fictional Raven Gulf air-base and JLC coastal-urban scenes;
- DOCX scenario import and reverse background-document export;
- Three.js Arena viewport, approved/provenance-tracked assets, terrain, explosions,
  operator and analyst replay views;
- frame-v1 loopback publishing at 20 Hz;
- Dagor East District package, overlay, resource packs, Metal validation, and stored
  100/500/2,000-entity evidence;
- saved screenshots and evidence under `docs/evidence/20260810/`;
- Dagor notes and commands in `docs/DAGOR_CLIENT.md`;
- scenario basis and fictionalization rules in `docs/SCENARIO_BASIS.md`.

Do not repeat those tasks unless a current test or user request requires it.

## Physics WIP

Primary files:

- `src/pytho_arena/simulation/physics.py`
- `src/pytho_arena/core/env.py`
- `src/pytho_arena/scenario/models.py`
- `tests/test_physics.py`
- `tests/test_generalization.py`
- `README.md`

Current design:

- `PhysicsState` owns batched positions, velocities, scalar-first body-to-world
  `[w, x, y, z]` quaternions, and body angular velocity in rad/s.
- `PHYSICS_BACKEND_API_VERSION = 2`; legacy external backends are rejected during
  registration with a migration error.
- Existing `kinematic_2d` and `point_mass_3d` behavior is preserved.
- `WorldSpec.meters_per_unit` is optional. Old scenarios omit it and retain old content
  hashes. Force-based SI backends require it.
- `multirotor_6dof` is a deterministic thrust-vectored rigid-body surrogate with
  gravity, limited tilt/thrust/torque, inertia, quaternion integration, fixed substeps,
  active masks, and bounded-world handling.
- The model is not a rotor, motor, battery, propeller, ground-effect, damage, or War
  Thunder flight model.
- It is currently scenario-wide and requires all actor groups to use the air domain.
  It does not yet support mixed multirotor, fixed-wing, ground, and maritime dynamics
  in one scenario.

Recorded CPU medians on this Mac for 50 substeps were 7.87/11.71/26.62 ms for
100/500/2,000 bodies. Re-run the benchmark before making a release claim.

Longer-term decision: keep Pytho tensor physics authoritative for headless RL. Keep
Dagor as a renderer/native client. Benchmark Rapier before adding it as a contact core.
Use JSBSim as a fixed-wing validation reference, not as an unexamined runtime choice.

## Replay and viewport attitude WIP

Primary files:

- `src/pytho_arena/server/replay.py`
- `src/pytho_arena/server/frontend-src/src/arena/types.ts`
- `src/pytho_arena/server/frontend-src/src/arena/replayAdapter.ts`
- `src/pytho_arena/server/frontend-src/src/arena/replayAdapter.test.ts`
- `src/pytho_arena/server/frontend-src/src/scene/ArenaViewport.tsx`
- `src/pytho_arena/server/frontend-src/src/scene/ArenaViewport.test.ts`
- `src/pytho_arena/server/frontend-src/src/scene/sceneManifest.ts`

Behavior:

- Only `multirotor_6dof` replay truth adds `orientationWxyz`; legacy replay frames do
  not gain the key.
- A three-component arena position maps to ENU east/up/north. Legacy 2D frames retain
  manifest altitude and velocity-derived heading.
- The adapter converts the physics quaternion to heading, pitch, and roll.
- The viewport applies heading clockwise from north, pitch nose-up, and roll
  right-wing-down to both detailed and instanced assets.
- Asset `baseYaw` is applied in model-local space after body attitude.
- Native frame-v1 already carries ENU attitude, so no wire-version bump was needed.

The generated frontend was rebuilt after these source edits with `npm run build`.

## Counter-UAS research and roadmap

Read `docs/COUNTER_UAS_ROADMAP.md`. It contains 13 direct public sources, product and
exercise comparisons, P0/P1/P2 priorities, a first vertical slice, and measurable gates.

The recommended first product slice is:

1. persistent fused tracks with evidence IDs;
2. human hold/deny/authorize decisions;
3. one typed RF-jammer mission-effect surrogate;
4. immutable child-run branching from an operator decision;
5. operator-picture versus analyst-truth AAR and scoring.

## C-UAS contracts: repaired and integrated (2026-08-17)

Primary files:

- `src/pytho_arena/simulation/cuas.py`
- `src/pytho_arena/simulation/cuas_lane.py`
- `src/pytho_arena/simulation/events.py`
- `tests/test_cuas.py`, `tests/test_cuas_lane.py`

All eleven audit findings below are closed. Each line names the resolution:

1. An effect timestamped before its approving decision -> `engage()` raises.
2. One approval authorizing multiple uses -> `blocked_authorization_spent` after the
   first activation.
3. Stale reports overwriting a newer track -> dropped and recorded as `track_drop`.
4. Fusion accepting mixed simulation times -> `fuse_track` requires one `(step, time)`.
5. `EFFECT_APPLIED` without an engine outcome -> renamed `effect_activated`; the engine
   reports the result through `record_outcome` as a separate `effect_outcome` event.
6. Missing hold, expiry, stable IDs, evidence pinning -> `RoeDisposition`,
   `valid_for_seconds`, a deterministic `event_id` in every event's attributes, and a
   pinned track snapshot per request.
7. Engagement reading the latest mutable track -> the authorization pins the evidence the
   operator judged, geometry uses the current estimate, and `authorized_offset_m` records
   the difference. Pinned geometry was tried first and rejected: an authorization aimed at
   a frozen position can never reach a moving track.
8. `decision_id` uniqueness -> enforced across all requests.
9. Mixed attribute casing -> all event attributes are snake_case.
10. Undeclared axes -> `COORDINATE_FRAME = "scene_local_enu_m"`, `(east, north, up)`.
11. Cumulative `replay_evidence()` -> `replay_evidence(since=cursor)` plus `event_count`.

The typed effector is now wired end to end: `ResponseSpec.effector` gates
`_apply_responses`, `CounterDroneLane` drives the cell from engine sensing,
`recorded_cuas_rollout` records the operator picture and decision queue per frame, and
`POST /api/runs/{parent_run_id}/branches` saves an immutable child run.

## Recommended integration design

Use an immutable decision-branch workflow. Do not add a live persistent session engine
inside this slice.

1. A baseline typed-C-UAS run records fused-track snapshots and pending ROE requests.
   Typed effectors default closed. Untyped legacy responses stay byte-for-byte unchanged.
2. The operator scrubs to a pending request and submits hold, deny, or authorize.
3. `POST /api/runs/{parent_run_id}/branches` loads the immutable parent configuration,
   schedules the decision, reruns the same scenario/seed/policies, verifies the exact
   pre-decision replay prefix, and saves a child run with a new run ID.
4. The UI loads the child replay. The parent run is never mutated.
5. Keep response decisions outside `Policy.act` for this slice so existing RL action
   keys and shapes do not change.

Likely seams:

- optional typed-effector data on `ResponseSpec`, with `None` defaults to preserve old
  hashes;
- one-effects-tick authorization mask in `_apply_responses` for typed responses only;
- a separate `recorded_cuas_rollout` path so legacy replay digests stay unchanged;
- branch provenance in `server/runs.py` and a branch endpoint in `server/app.py`;
- track and decision types in the replay adapter and frame-v1 publisher;
- pending-decision controls in the operator inspector in `App.tsx`;
- operator track display without analyst truth leakage;
- total native item guard for entities + tracks + effects, not entities alone.

This integration was estimated at 500–650 production lines and 250–350 test lines
across 10–12 source/test files. A real pause/resume multi-user live session is a separate
design with locking, reconnect, recovery, and much larger scope.

## Current verification evidence

Commands were run from the repository unless another directory is shown.

- `.venv/bin/ruff format --check .` -> `76 files already formatted`
- `.venv/bin/ruff check .` -> `All checks passed!`
- `.venv/bin/pytest -ra -k 'not scripted_rollout_reproduces_golden_fixture_exactly'`
  -> `86 passed, 1 deselected, 1 warning in 3.40s`
- `.venv/bin/pytest -v tests/test_training.py`
  -> `8 passed, 1 warning in 2.03s`
- focused physics/generalization/simulation/C-UAS tests -> exit 0, 63 test dots
- from `src/pytho_arena/server/frontend-src`: `npm test`
  -> `Tests  33 passed (33)`
- from that directory: `npx tsc --noEmit` -> exit 0
- from that directory: `npm run build` -> `built in 752ms`
- `/api/training-algorithms` ASGI probe -> HTTP 200 with REINFORCE, `gamma`, and
  `entropy_coef` descriptors
- `git diff --cached --check` -> exit 0
- local commits created: `b8242df` for the RL merge and `b9ab2b0` for the explicit
  physics/C-UAS WIP handoff

The full Python suite has exactly one known failure:

```text
FAILED tests/test_golden_rollout.py::test_scripted_rollout_reproduces_golden_fixture_exactly
expected e34418d558362e7dddc81da7c212e93fbdcfe7695b31446f9b20b5d45ca762d6
actual   3c5325ae746af38f3fde1afe19c1e5637b84dc3fd8ff82ffe6ec27a8bf299ba2
```

This failure also occurs on `origin/main` in this environment because Torch is not
pinned and the local Torch 2.13.0 changes one spawn value by 1/128. Do not regenerate
the digest or loosen the assertion without explicit user approval.

Other open verification notes:

- Torch warns that optional NumPy is not installed. Tests still pass.
- Vite warns that `app.js` is 856.88 kB after minification. Browser load acceptance is
  stored separately, but code splitting remains open work.
- No push has been performed.

## Safe continuation sequence

1. Confirm the branch state and read the latest local commit messages.
2. Repair `simulation/cuas.py` invariants and tests before integration.
3. Implement the immutable child-run slice in small gates: contracts, environment gate,
   replay/API branch, frontend decision UI, then native item guard.
4. After every frontend source edit, run `npm run build` from `frontend-src`.
5. Run focused tests after each gate, then the full verification protocol in
   `docs/guardrails/VERIFY.md`.
6. Update `docs/STATE.md` as decisions, failures, and milestones occur.
7. Do not push until the user explicitly asks.

## Service cleanup

Expected local ports are Arena `8096`, frame relay `46000`, and browser QA `9232`.
`lsof` showed no listeners on those ports during handoff. Process enumeration was
restricted in the sandbox, so verify `dngSceneViewer` through the process/UI tools before
claiming process-level cleanup on another machine.
