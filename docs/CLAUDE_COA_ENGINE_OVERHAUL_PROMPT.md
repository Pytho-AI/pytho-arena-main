# Claude Code goal: NPC-scale scientific simulator factory

Use this file as the controlling implementation prompt for one persistent Claude Code
`/goal` session. This is an implementation task, not an architecture-document task.

## Terminal objective

Turn these two repositories into the first production-quality slice of a server-authoritative,
NPC-scale, multi-fidelity military exercise engine and generic scenario-to-simulator service:

- `/Users/akshay/Dev/pytho/pytho-arena`: frontend, scenario authoring, trainer/EXCON intent,
  visualization, replay presentation, and optional native rendering.
- `/Users/akshay/Dev/pytho/coa-engine`: authoritative backend, world state, simulation clock,
  entity systems, physics, sensing, effects, AI, evidence, persistence, and RL stepping.

The product is bot-playable, not a multiplayer entertainment game. Autonomous NPC policies are the
normal actors. One human may enter a training-only demonstration mode to teach a bot manually and
compare that bot with RL. The optional 3D mode must have current 2026 game-quality presentation
while treating simulation behavior as scientific software. Do not claim that a model is realistic,
validated, or predictive without evidence for a stated intended use.

The terminal deliverable is a generic service that turns a reviewed source scenario into a tested,
versioned simulator bundle. Prove it with the existing aggregate MDMP planning simulator, a live
Raven air-base counter-UAS simulator, and a small synthetic ground-evacuation scenario compiled only
after the generic service is complete and without changing service code. Also deliver a 10,000-NPC
scale fixture, outer-loop RL and demonstration training, current-quality 3D mode, role-filtered
streaming, immutable replay and branching, and evidence that all gates in this file passed. Continue
across turns until the completion condition holds. Do not stop after research, a plan, schemas,
scaffolding, one repo, or a mocked demo.

## Claude Code execution

Run the session from `/Users/akshay/Dev/pytho` so Claude can access both sibling repos. That parent
directory is not the Git context for either product. Every Git command and repo-scoped review must
use `git -C pytho-arena ...`, `git -C coa-engine ...`, or an explicit repo working directory.

The controlling goal condition is intentionally short because `/goal` conditions are limited to
4,000 characters:

```text
/goal Read pytho-arena/docs/CLAUDE_COA_ENGINE_OVERHAUL_PROMPT.md in full and execute every requirement. Complete only after both repos' regression and contract tests, simulator-factory examples, deterministic replay and branch checks, Raven browser flow, trainer-capture and headless-RL checks, NPC scale/load gates, final clean-worktree verifier, and task-owned process cleanup have passed and their exact results are reported. Preserve user work. Do not push or deploy.
```

`/goal` requires an accepted workspace trust dialog and enabled hooks. Prefer Claude Code `auto`
permission mode where supported. Use `acceptEdits` as the interactive fallback. Never use
`bypassPermissions` or `--dangerously-skip-permissions` for this task. An interrupted active goal is
resumed with `claude --continue`.

## Completion condition

Complete only when all of these statements are true and the final response includes the exact
commands and result lines that prove them:

1. Both repos obey their `CLAUDE.md` and guardrail files. Their active `docs/STATE.md` sections
   describe this task, current decisions, final evidence, and remaining non-critical work.
2. COA is the only authority for truth, time, accepted commands, simulation state transitions,
   fidelity changes, model execution, scoring, snapshots, branches, and replay evidence.
3. Arena creates scenarios, sends trainer/EXCON intents, receives role-filtered projections, and
   renders or interpolates them. No Arena client can authoritatively change truth.
4. Versioned shared contracts have generated Python and TypeScript bindings, compatibility tests,
   golden fixtures, units, axes, stable IDs, and explicit schema/model version ranges.
5. The generic scenario-to-simulator service builds and registers complete, runnable MDMP-planning,
   Raven counter-UAS, and synthetic ground-evacuation bundles through one implementation path. Each
   bundle pins code, models, data, bots, assets, tests, evidence, and provenance. The third bundle is
   added after the service code is frozen and requires no service-code change.
6. A deterministic load fixture runs 100,000 total entities, 10,000 active tactical entities, and
   1,000 high-fidelity physics entities with autonomous NPC controllers, bounded memory, queues,
   and client interest sets.
7. The same accepted-intent log, desired ticks, revisions, idempotency keys, scenario seed, artifact
   pins, engine/runtime profile, and hardware class reproduce the same canonical logical state
   hashes and event IDs. Cross-hardware comparisons meet separate declared numeric tolerances.
8. The optional 3D mode uses PBR materials, terrain, lighting, shadows, atmosphere, animation,
   damage states, and effects at current game quality. The browser maintains 60 FPS for the normal
   2,000-item detailed/instanced view and remains usable for a 10,000-item instanced stress view on
   the recorded Mac profile.
9. The headless RL API uses the same world, components, systems, fidelity registry, and models as
   bot and demonstration execution. It runs with no Arena or renderer process. A trainer-input
   dataset captured through the real Arena training path trains an imitation policy and compares it
   with RL on held-out seeds. Automated test input is labeled synthetic, never human-authored.
10. Unit, property, contract, deterministic replay, branch, role-isolation, integration, load, and
    failure-path tests pass. No critical test is skipped, weakened, deleted, or converted to a
    snapshot update to get a green result.
11. All new public APIs and scientific models are documented. Every model result records source,
    version, units, assumptions, uncertainty, validity bounds, and evidence status.
12. Every LLM-generated code or procedural-asset artifact follows the generation, isolation,
    validation, approval or quarantine, hashing, activation, replay, and immutable rollback rules in
    this file. The fixed simulation tick never calls or waits for an LLM.
13. A checked-in cross-repo evidence generator runs before the final local commits. A separate
    read-only final verifier then runs from those clean commits, writes only to temporary storage,
    exercises both full repo gates and integration gates, enforces COA's changed-file coverage target
    of at least 80% against Phase 0 baseline SHAs, and checks generated-file freshness.
14. No process, browser, native viewer, test server, or listening port started by this task remains
    running. Nothing is pushed or deployed.

An unchanged, reproduced baseline failure may be reported separately only if it existed before the
first edit, is not in a changed path, and is not hidden. Fix new failures. Do not update the known
Arena golden replay fixture merely to match a different unpinned Torch build.

## Fixed user decisions

These decisions are accepted. Do not ask the user to choose them again.

### Product boundary

- Arena owns the product frontend. It includes scenario authoring, the browser UI, trainer/EXCON
  input, human-demonstration capture, role-aware presentation, replay controls, cameras, asset
  manifests, Three.js, and the optional Dagor client.
- COA owns the authoritative backend. It includes the entity model, truth, clocks, deterministic
  systems, physics, sensing, tracks and beliefs, damage, AI and tasks, effects, command validation,
  scoring, persistence, events, snapshots, branches, and RL environment execution.
- Bots and Arena training controls send the same intents. COA validates identity, policy/trainer
  role, ownership, tick, state revision, feasibility, and exercise rules. COA emits an accepted or
  rejected command event for every intent.
- Arena may interpolate and predict for display. Prediction never changes COA state or evidence.
- The two repos release independently. Contracts use explicit versions, compatibility ranges,
  generated clients, shared fixtures, and cross-repo tests.

### Scope and scale

- Start with a modular authoritative COA process. Add cell or worker process boundaries only after
  a profile proves a bottleneck and a deterministic single-process reference still exists.
- Each exercise is an isolated world with immutable runs, snapshots, replay, and child branches.
  Long-lived campaigns are later work.
- Target 100,000 total entities, 10,000 active tactical NPC entities, and 1,000 entities in the
  highest active physics fidelity. This scale is for bot populations, not human players.
- One human may enter training-only demonstration/correction mode for an authorized bot or
  formation. Do not create a general user-playable or many-human MMO mode.
- The first functional slice is the fictional Raven Gulf air-base counter-UAS exercise already in
  Arena. Extend it with soldiers, ground vehicles, sensors, drones, structures, component damage,
  human authorization, replay, and RL evaluation.
- Keep all built-in data unclassified. Use fictional composite layouts. Do not encode a current
  real facility's exact coordinates, defenses, routes, force posture, weak points, or strike paths.
- This is a simulation and training system. Do not add an operational command path to real sensors,
  effectors, vehicles, weapons, or C2 systems.

### Entity and fidelity model

- Represent terrain and large immutable visual surfaces as streamed terrain data, not one entity per
  triangle.
- Support fully static semantic objects, dynamic immovable structures, dynamic movable entities,
  transient effects/projectiles, and aggregate formations.
- Use five simulation fidelity levels: aggregate, kinematic, tactical systems, rigid-body physics,
  and domain plugin. Evidence status is separate. Call a plugin validated only for a named intended
  use with actual validation evidence.
- COA promotes and demotes fidelity using relevance, distance, interaction, human control, exercise
  rules, and available budget. Use hysteresis. Record every transition.
- A fidelity transition must preserve stable identity and each model's declared conserved state.
  There is exactly one authoritative representation at a time.
- Keep the current Python implementation language first. Benchmark before moving hot kernels to
  Rust or C++. Benchmark an ECS or physics library before adding it. Do not select Flecs, Rapier,
  Jolt, Bullet, or another engine from feature lists alone.

### Simulation and RL

- Use fixed ticks, deterministic multi-rate phases, pause, accelerated time, snapshots, replay, and
  branch-from-snapshot.
- Promise exact replay only for a pinned engine build, schema set, model set, seed set, and hardware
  class. Use tolerance-based validation across hardware classes.
- Use LLMs heavily where useful in the scenario compiler: scenario extraction, model selection,
  missing simulator code, bot behavior code, procedural asset recipes, tests, and documentation.
  Generation may run asynchronously while an exercise continues on its old pinned artifacts.
- Support configured remote model inference, read-only primary-source research, deterministic fake
  or recorded providers for tests, and an offline local-provider path. Model access may read approved
  inputs and return artifacts; it may not write to external systems or receive secrets.
- Keep every LLM call outside the authoritative tick and rollout loop. Activate a new artifact only
  after isolated checks and at an explicit paused or branched tick. Replay loads the stored artifact;
  it never calls the LLM again.
- Keep RL as an outer loop. Expose versioned create/reset/observe/step/snapshot/restore/branch/close
  and batch APIs. Do not put an RL framework inside the simulation kernel.
- Provide native vectorized headless execution and adapters for Gymnasium, PettingZoo Parallel, and
  the existing Arena training API. Do not depend on RLlib for multi-agent vectorization.
- Add human demonstration and corrective training as a second outer-loop path. Record exactly the
  observation available to the bot, the accepted intent, timing, outcome, scenario/model pins, and
  trainer/dataset provenance. Support behavior cloning and an optional DAgger-style correction loop,
  then compare imitation, RL, scripted, and MCTS bots on the same held-out evaluation set.

### Generic scenario-to-simulator service

- Accept reviewed DOCX, structured scenario data, or an existing saved scenario as input. Produce a
  self-contained `SimulatorBundle`, not loose prose or an untracked Python file. Self-contained means
  a content-addressed dependency closure whose code, models, bots, assets, schemas, data, licenses,
  and provenance can be imported into an empty registry and run offline without sibling source files.
- A bundle contains the canonical scenario, entity archetypes and initial snapshot, clock/fidelity
  profile, model/plugin set, NPC policy set, objectives/rewards, terrain/render/asset manifests,
  generated tests, model cards, source citations, assumptions, warnings, and a content manifest.
- Support aggregate planning and live entity simulation behind the same bundle contract. MDMP uses
  aggregate entities and coarse decision ticks. Counter-UAS uses tactical/physics entities and live
  3D projections.
- Reuse approved library components before generating new code or assets. Record why generation was
  needed and every prompt, model/version, input hash, output hash, tool version, and reviewer.
- Treat generated simulator code as untrusted. Build and test it only in an OS-enforced sandbox,
  container, VM, or non-executable declarative DSL with no network, a narrow read-only input set, a
  disposable output directory, CPU/memory/time limits, no inherited credentials, and no host
  subprocess access. A plain subprocess and the current AST-restricted in-process `exec` are not
  security boundaries. If no enforceable boundary is available, do not execute or activate the code.
- Treat generated procedural asset code the same way. Validate format, topology, bounds, units,
  material/PBR completeness, LODs, collision/nav proxies, license/provenance, polygon/texture budget,
  and visual output before registration.
- Use lifecycle states `draft`, `generated`, `static_checked`, `conformance_tested`,
  `scientifically_labeled`, `quarantined_preview`, `approved`, `active`, `superseded`, and `rejected`.
  Record approval kind and approver identity separately. Novel generated executable code requires an
  actual human approval record before activation. Never label a model, subagent, automated check, or
  development policy as human approval. A bundle composed only from already-approved artifacts may
  follow a recorded development-policy approval for local unclassified use. Novel artifacts may be
  exercised only in the enforced quarantined preview during this unattended run. Final Raven
  execution uses already-approved artifacts unless a real human approval record already exists.
- A generation request made during an exercise never patches the active world in place. Continue on
  the old bundle or pause. After validation, activate the new bundle at an explicit tick in a child
  branch. Replay reads the stored bundle and does not regenerate it. Rollback is another immutable
  activation event or child branch that points to the prior pinned bundle; it never edits history.

### Data, protocol, and deployment

- Use Protobuf as the canonical wire schema. Use gRPC for backend control/query and a binary
  WebSocket stream for browser/native projections. Generate Python and TypeScript bindings.
- Do not hash raw Protobuf serialization for replay identity. Define a canonical logical state hash.
- Use SI units inside COA. Use local ENU `(east, north, up)` meters with a declared WGS84 origin for
  each exercise. Use radians and scalar-first body-to-world quaternions `[w, x, y, z]`. Convert to
  Three.js axes only at the Arena boundary.
- Use OpenUSD as the preferred offline scene/asset interchange where it solves composition and
  provenance. Use 3D Tiles or another measured tiling format for large geospatial visual delivery
  only after a local prototype. Keep COA terrain semantics in a renderer-neutral manifest.
- Treat DIS and HLA as later gateways. They are not the internal state model or transport.
- Target on-premises and air-gapped Linux first, browser and optional native clients, Mac
  development, and a later GovCloud path.
- Stay unclassified now. Preserve data labels, provenance, audit, and deployment seams needed for a
  later CUI assessment. Do not claim CUI compliance.

### People and views

- Automated NPC agents are the normal actors. EXCON/instructor, blue/red control, system operator,
  observer, and analyst are exercise staff roles, not MMO player accounts.
- Human platform/formation control exists only in demonstration or correction training. It uses the
  bot's observation and intent contract and never exposes analyst truth or bypasses authority.
- Support strategic, tactical, sensor, first-person, third-person, EXCON, and replay perspectives.
- Preserve the separation among truth, physical state, measurements, fused tracks, beliefs, and
  analyst conclusions. Operators act on authorized projections, not hidden truth IDs.

## Working rules

1. Start in `/Users/akshay/Dev/pytho`. Read both repos' `CLAUDE.md`, all routed guardrail files,
   both `docs/STATE.md` files, this file, and `pytho-arena/CLAUDE_HANDOFF.md` in full before editing.
2. Run `git -C pytho-arena status --short --branch`, `git -C coa-engine status --short --branch`,
   each repo's `git log --oneline -10`, dependency manifests, and narrow baseline suites. Record
   failures before edits. Never reset, discard, or overwrite user work.
3. Keep Arena on its existing `akshay/3dsim` branch. If COA is clean on `main` and no paired feature
   branch exists, create local branch `akshay/3dsim`. If state differs, preserve it and record the
   safe branch decision. Never force a checkout over changes.
4. Use stable Claude Code subagents for bounded read-only audits, performance research, tests, and
   disjoint repo work. Give each editing agent exclusive paths. Do not let agents edit a contract
   producer and its consumer at the same time. The lead reviews every diff and runs integration
   checks itself. Do not use `/batch`; it is a poor fit for two coordinated repos and it assumes a
   PR/worktree workflow.
5. Post a short ETA after the baseline, each implementation phase, and any material plan change.
6. Update each repo's `docs/STATE.md` when the task, decision, result, blocker, or next step changes.
7. Prefer the smallest code that meets the current acceptance test. Do not add speculative services,
   extension points, flags, dependencies, or failure handling for impossible states.
8. Do not rewrite working modules blindly. First identify the behavior and tests to preserve. Port
   authority from Arena to COA in vertical slices with a compatibility adapter until migration is
   proven.
9. Add no dependency without checking installed dependencies, standard-library options, maintenance,
   license, air-gap install, deterministic behavior, binary size, and a focused benchmark.
10. Use local commits at green phase gates. Pair cross-repo commits in their messages or evidence
    manifest. Read-only primary-source research and configured model inference are allowed. Do not
    push, open a PR, deploy, alter shared infrastructure, send external writes, or expose credentials.
11. Run commands yourself. Ask the user only if work needs new authority or a choice that changes
    the data model or irreversible behavior and cannot be answered from code, tests, this prompt, or
    the accepted defaults.
12. If a gate fails, diagnose and fix it before continuing. Try at least three safe in-scope paths
    before declaring a true blocker. A blocker is not completion.
13. Add `pytho-arena/scripts/generate-coa-integration-evidence.sh` for evidence that belongs in the
    commits, then add `pytho-arena/scripts/verify-coa-integration.sh` as a read-only final check. Both
    locate COA through `COA_ENGINE_DIR`, defaulting to `../coa-engine`. Record each repo's baseline SHA
    in Phase 0 and calculate task coverage from those SHAs. Commit generated evidence, run the final
    verifier from clean commits, and let that verifier write only to a temporary directory.

## Current code to reuse

Treat this as a starting map, then verify every path against the current checkout.

### Arena

- `src/pytho_arena/scenario/models.py`: strict scenario validation, schema versioning, directional
  relationships, actor groups, sensors, responses, objectives, policy bindings, scene metadata, and
  immutable content hashes.
- `src/pytho_arena/scenario/store.py`: immutable scenario versions and atomic writes.
- `src/pytho_arena/scenario/documents.py`: bounded DOCX import, assumptions, warnings,
  fictionalization, provenance, and reverse DOCX export.
- `src/pytho_arena/simulation/contracts.py`, `compiler.py`, `scheduler.py`, and `events.py`:
  environment identity, compile boundary, fixed multi-rate scheduling, and typed events. Move the
  authoritative forms to COA; keep compatibility consumers during migration.
- `src/pytho_arena/core/env.py` and `simulation/physics.py`: deterministic batched tensor state,
  seeded randomness, normalized intent actions, kinematic 2D, point-mass 3D, and synthetic
  multirotor 6-DOF. Reuse them as COA headless kernels or reference implementations. Do not call the
  multirotor surrogate a rotor, motor, battery, contact, or War Thunder flight model.
- `simulation/beliefs.py`, `cuas.py`, `cuas_lane.py`, `server/replay.py`, `server/runs.py`, and
  `server/app.py`: truth/belief separation, opaque tracks, evidence-linked authority, typed effects,
  deterministic replay, immutable runs, and child branches.
- `env/`, `training/`, and `experiments/`: outer-loop adapters, rollout, versioned algorithm
  registry, sessions, checkpoints, REINFORCE, held seeds, policy populations, and empirical regret.
- `server/frontend-src/src/arena/`: replay types and adapter, ENU conversion, quaternion attitude,
  role projections, and the current 2,000-item guard.
- `server/frontend-src/src/scene/`: Three.js viewport, assets, instancing, terrain, effects, and
  truth-hiding render plan. `ArenaViewport.tsx` is already too large; split it by scene systems
  before adding more entity classes.
- `server/frontend-src/src/app/decisionQueue.ts`: human hold/deny/authorize workflow.
- `native/dagor-client/`: optional Metal/native renderer, 20 Hz loopback stream, ENU conversion,
  ECS overlay, resource packs, and stored 100/500/2,000-item evidence. Keep it optional and
  non-authoritative.
- `server/frontend-src/ASSET_PROVENANCE.md`: approved, hash-locked visual assets. Preserve
  provenance for every added or converted asset.

### COA

- `simulation_runner.py` and `protocol.py`: transport-independent pipeline, typed parameters, phase
  state, callbacks, cancellation, and run identity. Separate planning/MCTS jobs from the new
  real-time world service without breaking current planning behavior.
- `state.py`, `environment.py`, `rule_engine.py`, `scenario_loader.py`, and rules YAML: current
  deterministic action/state primitives, objectives, forces, legal actions, effects, terminal
  checks, and scenario loading. Keep their tested planning semantics behind adapters while entity
  truth moves to the new world model.
- `mcts.py`, `progress_mcts.py`, `coa_extractor.py`, and `coa_analysis.py`: retain MCTS as a
  high-level planner that evaluates immutable world snapshots. It must not directly mutate the
  real-time world.
- `simulation_persistence.py`, `simulation_result.py`, and run APIs in `http_server.py`: run IDs,
  saved context, immutable/superseded results, resume, and result delivery. Reuse the durable job
  lifecycle. Replace unsafe cross-version pickle as the authoritative replay format.
- `sim_generator.py`, `sim_sandbox.py`, `sim_semantics.py`, and generated-simulator tests: current
  model artifact identity, conformance, sandboxing, semantic checks, reattachment, and fallback.
  Preserve evidence. Current generated `apply_action()` governs generated rollouts, while committed
  tree transitions still call `agent.resolve_action()`; do not mistake this hybrid for a complete
  generated simulator. The final tick engine executes reviewed, pinned plugins, not fresh LLM code.
- `websocket_server.py`, `websocket_handlers.py`, and `http_server.py`: existing external service
  boundary. Preserve the current planning APIs. Add the exercise service beside them, then migrate
  clients deliberately.
- `tests/`: the existing planning, security, persistence, codegen, simulation, and provenance suite
  is a regression boundary. Do not narrow it to make the new engine pass.

### Limits the implementation must remove or contain

- Arena currently has group-centric entities, dense all-pairs sensing, one physics backend per
  scenario, binary destruction, local JSON runs, synchronous episode requests, full replay fetches,
  heuristic asset selection, and no live COA authority stream.
- Current clients have no spatial interest graph, dormancy, delta baseline, resync, or bounded
  staff/trainer command path.
- Current high-fidelity physics does not cover mixed air, ground, soldier, structure, and contact
  behavior in one world.
- Current roles are mostly operator and analyst. Current track association is one truth entity per
  track and does not cover loss or reacquisition.
- COA's current planning state is not an entity-level world. Some current simulation content is
  generated per run and must be pinned before comparison. Audit terminal reachability, objective
  mutation, risk statistics, classification fallbacks, and action parsing against current code;
  close any still-present defect that invalidates the first slice.
- `rule_engine.legal_categories()` currently restores all categories when strict feasibility leaves
  none. Audit and remove that fail-open behavior from any authoritative bot/command path.
- Current generated Python uses AST-restricted in-process execution. Preserve its tests as a legacy
  planning defense, but do not expose it to untrusted source scenarios or call it process isolation.
- Current COA WebSocket sessions are process-local and tied to remote addresses; current HTTP has no
  exercise authentication/authorization. Do not expose the new trainer/bot service until explicit
  identity, role, bounds, and origin policy tests pass.
- Protobuf deterministic serialization is not canonical across languages or schema changes. Hash
  normalized logical state, never raw wire bytes.

## Target architecture

Build a modular monolith first. Preserve clear process boundaries so profiling can justify later
partitioning.

```text
DOCX / structured scenario / EXCON generation request
                 |
                 v
scenario compiler -> isolated code/asset generators -> artifact gates/registry
                 |                                      |
                 +---------- approved SimulatorBundle --+
                                                        v
    Arena browser/native -> authenticated Arena edge -> COA loopback gRPC/stream
            ^                         |                         |
            |                         |                         v
            +---- binary role-filtered WS ---------- projection/interest service
                                                         |
              +----------------------------------+------------------+
              | authoritative COA exercise world                   |
              | command gate -> fixed phase scheduler -> ECS       |
              | terrain/spatial -> movement/physics -> sensing      |
              | tracks/beliefs -> tasks/AI -> effects/damage        |
              | objectives/scoring -> event log/snapshots           |
              +----------------------------------+------------------+
                                                 |
                     +---------------------------+----------------+
                     | replay/branch | headless RL batch | gateways |
                     +---------------------------------------------+
```

### Authoritative world and ECS

Create a versioned data-oriented ECS contract in COA. Start with a simple Python implementation
over typed component tables, NumPy, or Torch where measured. Keep system interfaces narrow so a hot
table or kernel can move to native code without changing wire contracts.

Entity IDs are unsigned 64-bit values scoped by a stable world ID. One allocator issues them
monotonically and never reuses an ID inside a world lineage. A child branch preserves every prefix
ID. Aggregation lineage and ordered spawn provenance live in separate components; never overload
the ID with parent/ordinal bits. TypeScript, JSON adapters, DOM attributes, and logs represent IDs
as `bigint` or canonical unsigned decimal strings, never JavaScript `number`. Test values above
`2^53 - 1` across Python, Protobuf, TypeScript, JSON adapters, and the DOM.

At minimum define these component groups, with schema versions and units:

- Identity: entity ID, kind, display name, source/provenance ID, lifecycle state.
- Ownership: faction, role owner, controller, command authority, protected status.
- Transform: ENU position, body quaternion, linear/angular velocity, bounds.
- Spatial: cell, mobility class, collision layer, terrain/nav footprint, dormancy.
- Render reference: asset ID, variant, damage state, animation state, LOD hints. COA never stores a
  renderer object.
- Mobility: stationary, pedestrian, ground vehicle, multirotor, fixed wing, maritime, or aggregate;
  physical parameters and active fidelity.
- Task and command: goal, ordered task graph, current task, command ID, status, timing, reason.
- Perception: sensor definition, measurement, fused track, covariance, confidence, evidence IDs,
  track age, loss, and reacquisition.
- Communications/EW: networks, links, latency, loss, bandwidth, health, emissions, and simulated
  interference effects.
- Damage/readiness: component health, functional capability, damage cause, fire/debris state,
  repair, availability, and provenance.
- Inventory/logistics: consumables, capacity, fuel/energy abstraction, resupply, and maintenance.
- Objective/scoring: ownership, progress, measures, costs, exercise outcomes, and uncertainty.
- Fidelity: current level, requested level, promotion reason, cooldown, source/target state maps,
  transition error, and model pins.

Systems read stable snapshots for a phase and enqueue mutations. Apply commands at deterministic
barriers. Define an explicit phase order. Sort queries and reductions by stable IDs where order can
change a result. Give each stochastic subsystem an isolated, derived RNG stream. Never rely on hash
map iteration, wall-clock time, global RNG, thread completion order, or client frame rate.

Use one explicit right-handed coordinate convention. World axes are ENU: `+x` east, `+y` north,
`+z` up. Body axes are `+x` forward, `+y` left, `+z` up unless a validated plugin declares and
converts another source convention. Heading zero is north and increases clockwise when viewed from
above; pitch is positive nose-up; roll is positive right-wing-down. Declare true versus grid north
in the terrain manifest. Arena's Three.js boundary maps world east/north/up to renderer axes with a
documented handedness-preserving quaternion transform; do not assign axes independently and mirror
orientation. Add golden origin, cardinal-heading, pitch, roll, quaternion round-trip, and
`frame-v1` adapter tests.

### Clocks and rates

Use integer ticks as truth. Store simulation time as a rational tick period or integer nanoseconds,
not accumulated binary floating-point time. The scheduler must support declared fixed rates for:

- rigid-body integration;
- kinematic movement;
- sensing and track fusion;
- communications and EW;
- task/behavior updates;
- effects and damage;
- objectives, logistics, and scoring;
- network projection and replay sampling.

Pause, accelerated time, single-step, snapshot, restore, and replay all use the same scheduler. A
slow client never slows or changes authority. A slow authoritative phase emits a deadline metric and
cannot silently skip work.

### Multi-fidelity rules

Implement fidelity as a simulation model choice, not visual LOD. Each domain plugin declares:

- supported entity kinds and fidelity levels;
- input and output component versions;
- units, assumptions, validity bounds, and uncertainty;
- fixed update rate and deterministic guarantees;
- promotion and demotion transforms;
- conserved or bounded quantities and permitted transition error;
- calibration data and verification status;
- compute cost estimate and health metrics.

Promotion priority combines explicit human control, sensor/effect interaction, task relevance,
distance, uncertainty, exercise rules, and available budget. Demotion uses lower thresholds and a
cooldown. Test rapid boundary movement to prove hysteresis prevents thrashing.

Promotion/demotion must preserve identity, affiliation, task, inventory, accumulated damage,
objective contribution, evidence links, and model-specific conserved state. Record before/after
hashes, model IDs, trigger, tick, and error. Observers see one entity, not both representations.

### Spatial, terrain, navigation, and visibility

- Define one renderer-neutral terrain manifest with origin, CRS, vertical datum, units, elevation,
  semantic surfaces, collision/nav products, LOS/occlusion products, material IDs, source hashes,
  classification label, and visual asset references.
- Keep high-detail visual terrain in Arena. COA loads only measured products needed for elevation,
  collision, navigation, visibility, and material response.
- Start with a deterministic uniform grid or another measured simple spatial index. Queries return
  stable sorted results. Add hierarchical cells only when the benchmark requires them.
- Build per-client interest sets from spatial cells plus role, faction, ownership, sensor/belief
  visibility, exercise permissions, update priority, and bandwidth budget.
- Implement dormancy and update-frequency tiers. Do not destroy authoritative entities merely
  because no client sees them.
- Provide pedestrian and vehicle pathing for the Raven slice. Separate route planning from motion
  control. Store navigation provenance and detect unreachable tasks.

### Physics and domain models

Support mixed models in one world. Use the current kinematic, point-mass, and multirotor kernels as
reference implementations. Add stationary structures, pedestrian movement, ground vehicles,
fixed-wing kinematics, and deterministic collision/terrain bounds needed by the first slice.

Before adding a native contact or ECS library, build the same focused benchmark for at least the
existing tensor kernel and the candidate. Record dependency version, license, air-gap packaging,
determinism, supported platforms, p50/p95 tick time, memory, serialization cost, and integration
surface. Select from measured evidence. If Python misses a mandatory target, move only the profiled
hot kernel behind the existing component/system contract.

Do not copy or claim War Thunder's full physics. Dagor remains an optional rendering client. Visual
explosions, debris, smoke, and animation must be driven by authoritative outcome events, but their
appearance is not evidence that the damage model is correct.

### NPC bots, planners, and training commands

- Use goals and hierarchical tasks for soldiers, vehicles, drones, sensors, teams, and formations.
  Tasks have prerequisites, resources, start/end ticks, success/failure reasons, and evidence.
- Implement deterministic task execution with small planners, doctrine/rule policies, or behavior
  trees as justified by each domain. Do not build a generic planner before one use case needs it.
- Separate NPC decision fidelity from physical fidelity. Most of 10,000 active NPCs use cheap
  deterministic reactive or behavior-graph policies. A measured subset may use search or learned
  policies. Do not run one live LLM agent per NPC.
- MCTS operates on immutable COA snapshots at the command/formation layer. It submits candidate
  intents through the same command gate as scripted, learned, and demonstration policies.
- RL, imitation, MCTS, and scripted policies submit intents. No policy receives a mutable world
  object. A slow external planner misses a declared decision deadline; it never stalls the tick.
- Commands carry command ID, world/branch ID, expected revision, actor/role, owned entity or task,
  desired tick, payload version, and idempotency key. Rejections state a machine-readable reason.
- Preserve the current human hold/deny/authorize path. Every simulated effect requires the exercise
  authority declared by its model and scenario.
- Demonstration mode temporarily replaces one bot policy or formation policy with a trainer input
  policy. Start, handoff, correction, and return-to-bot are recorded events. The trainer sees only
  that bot's declared observation. The recording stores requested and accepted actions separately.

### Truth, sensors, tracks, and effects

Maintain separate stores and projections for:

1. ground truth and physical state;
2. sensor measurements with noise and provenance;
3. fused tracks with covariance, confidence, age, classification evidence, loss, and reacquisition;
4. faction/role beliefs;
5. analyst conclusions and after-action annotations.

Never derive operator track IDs from truth IDs. Never expose an adversary relationship or hidden
classification in an operator projection. Test for truth leakage at schema and UI boundaries.

Extend the existing counter-UAS lane with deterministic association, gating, stale/duplicate report
handling, track split/merge rules, loss, and reacquisition. Separate effector activation, attempt,
physical/model outcome, and scored consequence. Record capacity, readiness, range eligibility,
authority, uncertainty, cost, and linked evidence.

### Structures, damage, logistics, and effects

Dynamic immovable structures need component-level damage and functional state. At minimum model
power, communications, sensor/mission function, structural envelope, fire state, debris bounds,
occlusion changes, repair state, and source event. Damage must change capability and relevant terrain
queries, not just swap a mesh.

Movable entities need readiness, mobility damage, sensor/communications damage, inventory, and
repair. Keep lethality and EW values abstract and scenario/model-card driven. Do not embed sensitive
real-world performance values in built-in fixtures.

Effects and projectiles are transient entities or events with stable source, target/track,
authorization, attempt, outcome, and causal links. Arena may create particles from them; particles
do not feed back into COA.

### Persistence, replay, and branching

Use an append-only event log and periodic versioned snapshots. Start with a local durable store that
works air-gapped and has atomic metadata updates. A simple SQLite metadata/event index plus
content-addressed snapshot/replay files is preferred unless the audit proves a smaller current
mechanism meets transaction and scale needs. Do not add Kafka, Kubernetes, or a distributed database
for the first slice.

Each run records world ID, branch ID, parent branch/tick, scenario hash, terrain hash, schema
descriptor hash, engine commit/build, model/data pins, seed manifest, commands, command decisions,
events, snapshot hashes, interpreter version, dependency-lock digest, native library versions,
compiler flags, determinism settings, CPU/GPU fingerprint, hardware profile, and intended-use label.

Canonical logical hashes sort entities by ID and components by type/version, normalize declared
units and numeric representation, and exclude presentation-only fields. Specify field order, UTF-8
normalization, byte order, integer widths, float width/encoding, negative-zero handling, and NaN/
infinity rejection or normalization. Exact hashes never use lossy quantization. Cross-hardware
tolerance reports compare physical fields separately and cannot replace the exact-hash result. A
branch must reproduce its parent prefix exactly. Parent evidence is immutable.

Remove pickle from the authoritative long-term replay contract. It may remain as a version-pinned
legacy planning cache while a migration and compatibility test exists.

### Network contract

Place canonical versioned `.proto` sources in `coa-engine/contracts/pytho/sim/v1/` and export a
content-hashed descriptor/source bundle under `coa-engine/contracts/dist/`. COA's Python 3.11
service hosts gRPC. Arena's Python 3.12 edge uses generated Python gRPC stubs under its package. The
browser uses generated TypeScript message codecs under its frontend source tree for the binary
WebSocket projection stream; it does not call gRPC directly. Add
`pytho-arena/scripts/sync-coa-contracts.sh`, located by `COA_ENGINE_DIR` with default
`../coa-engine`, to import the versioned bundle and regenerate both clients. The cross-repo verifier
fails on stale code, a hash mismatch, or incompatible descriptors. Do not hand-copy parallel types.

The control/query API must cover world lifecycle, scenario/model validation, generation-job
submit/status/cancel, artifact review/approval/activation/rollback, commands, pause/rate, snapshots,
branches, replay queries, role/ownership, health, and RL batch execution. Use deadlines, idempotency,
bounded messages, and explicit error codes.

For the first slice, browsers and native clients connect only to the Arena edge. The edge authenticates
the session and Origin, derives the exercise principal, serves the binary WebSocket, and opens a
server-authenticated backend stream to a COA service that is forced to loopback. A COA listener must
refuse a non-loopback bind in this profile. Any later non-loopback backend profile requires TLS and
mutual service authentication. Exercise-scoped role grants and entity/task ownership are resolved on
the server. Client-supplied actor, role, or owner fields are audit claims only and never grant
authority. Test the real browser handshake, bad/missing Origin, impersonation, role escalation,
revoked sessions, expired grants, cross-exercise access, backend bind refusal, and client claims that
disagree with the server principal.

Authoritative truth/snapshot/event messages and client role-projection messages are different schema
types. A projection builder is the only boundary between them. A projection contains only authorized
entity fields, tracks/beliefs, UI-safe effects, and a checksum of that authorized projection. It
never includes a truth checksum, omitted-field hash, or generic payload that lets a client infer
hidden state.

The binary WebSocket projection stream includes protocol version, world/branch, server-derived view,
sequence, authoritative tick/time, snapshot or delta ID, base snapshot ID, interest revision,
authorized entities/tracks/effects, and projection checksum. Define full snapshot, ordered delta,
ACK, resync, reconnect, compression negotiation, maximum frame, queue bound, newest-state
coalescing, and slow-client disconnect behavior. State deltas may coalesce only against the last
acknowledged base. Evidence events use a separate durable event cursor and may never be silently
coalesced or dropped. Queue overflow forces a snapshot plus event-cursor resync. Never use an
unbounded queue.

Arena's edge adapter may expose browser-friendly HTTP where needed, but it is not authoritative. It
uses generated COA clients. Preserve `frame-v1` as a compatibility adapter for the current Three.js
and Dagor clients until the new stream passes parity tests.

### Scientific model registry and VV&A

Create a model/data registry whose immutable record includes:

- stable ID, semantic version, code/data hash, owner, source, and license;
- domain, intended use, supported fidelity, inputs, outputs, units, and coordinate frame;
- assumptions, exclusions, validity bounds, known failure modes, and uncertainty model;
- calibration dataset and date, verification tests, validation evidence, sensitivity results, and
  accreditation status for a named intended use;
- deterministic class, supported hardware, performance evidence, and superseded versions.

An unvalidated model is allowed for training development if its status is visible. Results must not
silently imply accreditation. Generate machine-readable evidence plus concise model cards. Align
the evidence structure with DoDI 5000.61 and MIL-STD-3022 without claiming formal Government
accreditation.

### 3D and trainer experience

Build current-quality 3D presentation without turning the product into an entertainment game:

- strategic map, RTS/tactical command view, sensor scope, training-only first/third-person
  demonstration view, EXCON controls, and synchronized replay;
- streamed terrain, instanced entities, explicit render assets from COA components, stable object
  lifecycles, PBR materials, high-resolution terrain, time-of-day lighting, soft shadows,
  atmospheric effects, animation, damage variants, smoke/fire/debris, post-processing, and readable
  tactical overlays;
- selectable entities and tracks, tasking, command acknowledgement/rejection, role-aware panels,
  time controls, branch comparison, uncertainty, system health, and evidence links;
- operator view contains only authorized tracks/beliefs; analyst and EXCON views can reveal truth
  with clear labels;
- visual LOD and simulation fidelity are separate controls;
- Three.js remains the product renderer. The approved Dagor assets/client remain an optional native
  presentation path and must consume the same projections.
- Procedurally generated assets must arrive through the approved artifact manifest. Missing or
  rejected assets use an explicit diagnostic placeholder during development only; a final Raven
  acceptance capture may not contain debug primitives or accidental placeholders.

Split large viewport and application modules along existing scene/UI responsibilities before
adding features. Do not replace the current visual work with debug primitives. Preserve approved
assets and their hashes. Add screenshots and frame-time captures for the Raven functional run and
the 2,000/10,000-item views. Run visual regression checks plus a deliberate lead-agent review of
composition, scale, materials, lighting, animation, terrain contact, water placement, effects, UI
legibility, and camera motion. A passing frame rate does not prove visual quality.

Check in a visual acceptance rubric and the required captures. Zero high-severity findings are
allowed. The gate fails for debug placeholders, terrain intersections, objects in water without an
intentional maritime role, broken scale, missing materials, animation defects, unreadable overlays,
or camera defects. A separate visual-review subagent records findings; the lead verifies every fix.

### Scenario documents

Preserve the current document-to-scenario and scenario-to-document flow. Generalize it so an
unclassified exercise background DOCX produces:

- a draft generic `SimulatorBundle` request and COA-owned simulation manifest;
- an Arena render/asset manifest;
- extracted facts with page/section provenance;
- assumptions, warnings, unknowns, confidence, and fictionalization changes;
- an explicit approval state before execution.

The service compiles the approved request into code/model/bot/asset artifacts, runs the artifact
gates, and registers the finished bundle. The unattended goal may use an existing reviewed Raven
request or a development-policy-approved request made entirely from already-approved artifacts. It
must leave novel executable artifacts in quarantine rather than inventing human approval. Prove that
the MDMP source selects aggregate/coarse-time models and the Raven source selects
tactical/physics/live-3D models without hard-coded scenario ID branches.

Reverse export must create a background document from the canonical scenario and model manifests,
not from rendered frames. Round-trip tests must preserve stable facts while marking non-round-trip
layout or inferred fields. The original urban source is external at
`/Users/akshay/Downloads/JLC_cUAS_BackgroundData (1).docx`; use it for local acceptance if readable,
but do not silently commit the large external file. Keep the derived scenario/import report and
Raven reverse brief. Add a small synthetic checked-in DOCX for repeatable parser and round-trip
tests.

## Required implementation sequence

Work through these phases in order. A phase is complete only when its named gate passes. Continue
to the next phase in the same `/goal` session.

### Phase 0: baseline and decision record

1. Audit current branches, worktrees, dependencies, repo instructions, test commands, generated
   files, and local hardware.
2. Run narrow and full-enough baselines in both repos. Record current suite counts, known failures,
   package versions, ports, and performance baselines.
3. Trace the current Raven run from scenario to simulation to replay to browser and native frame.
4. Trace COA planning, persistence, resume, generated model, MCTS, HTTP, and WebSocket paths. Prove
   which transitions generated code does and does not control today.
5. Trace one MDMP input and the Raven/DOCX input into a proposed common `SimulatorBundle` without
   erasing their different clocks, entity resolutions, or output views.
6. Write short ADRs for authority, contract location, logical hashing, initial ECS storage, durable
   storage, and dependency/benchmark policy. Decisions in this prompt are not open ADR questions.

Record both repo baseline SHAs here. All later changed-file coverage and scope reports use those
exact SHAs, not merge bases that include or omit Arena's prior branch work.

Gate P0: no edits beyond state/ADR files until the lead can name the preserved behavior, current
failures, exact first vertical path, and every new dependency under consideration.

### Phase 1: shared contracts and compatibility harness

1. Define versioned Protobuf messages/services for IDs, units, components, commands, command
   results, models, simulator bundles, generation jobs, artifact lifecycle, bot policies,
   demonstration datasets, terrain, snapshots, deltas, tracks, events, replay, branches, roles,
   and RL.
2. Generate Python and TypeScript bindings reproducibly. Add one command that refreshes them and a
   check that fails on stale generated files.
3. Add cross-repo fixtures and tests for binary round-trip, unknown fields, version ranges, removed
   field reservation, coordinate conversion, logical hashes, and malformed/bounded input.
4. Add a `frame-v1` compatibility mapper. Prove current Raven frames still render.

Gate P1: contract lint/compatibility, codegen freshness, Python/TypeScript compile, and cross-repo
fixtures pass before authoritative state moves.

### Phase 2: COA authoritative core

1. Implement world IDs, entity IDs, typed component tables, deterministic queries, command buffer,
   explicit phase scheduler, RNG stream derivation, canonical hashes, events, snapshots, and branch
   lineage.
2. Implement entity lifecycle for static semantic objects, dynamic immovable structures, dynamic
   movable entities, transient entities, and aggregate formations.
3. Add the terrain manifest, stable spatial index, interest query primitives, and fidelity registry.
4. Add the artifact registry and immutable bundle manifest without executing generated code yet.
5. Add property and deterministic tests before porting domain behavior.

Gate P2: 100 repeated small-world runs match canonical hashes; shuffled creation/input order either
produces the declared same result or a tested rejection; snapshot/restore and branch prefix tests
pass; a 100,000-entity storage/query benchmark records time and memory.

### Phase 3: generic scenario compiler and COA kernel migration

1. Implement source ingestion, canonicalization, library resolution, isolated generation,
   static/security checks, conformance, scientific labeling, approval, registration, activation,
   supersession, and rejection for complete simulator bundles.
2. Generate procedural visual assets through isolated code and validate their geometry, material,
   LOD, collision/nav proxy, provenance, and budgets before Arena can resolve them.
3. Compile and run MDMP planning and Raven counter-UAS bundles through the same service contract.
   Freeze the service code, then compile and execute `synthetic-ground-evac-v1` from a new small
   structured source without a service-code change. Scenario-specific behavior belongs in bundle
   data/plugins, not service if-chains.
4. Port or wrap the current schedulers, kinematic/point-mass/multirotor kernels, sensing, belief,
   C-UAS authority, effects, rewards, events, replay, and branch semantics behind COA components.
5. Preserve existing scenario and policy contracts through adapters while COA becomes authority.
6. Compare the same Raven seed and command log on old and new paths. Explain and test any intended
   semantic change. Do not accept visual similarity as parity.
7. Keep COA's existing planning/MCTS routes green and move MCTS to immutable world snapshots where
   the first slice uses it.
8. Remove the current MDMP hybrid transition defect: generated MCTS rollouts and committed execution
   must use the same approved bundle transition contract, unless an ADR defines a deliberate
   abstraction boundary and parity tests prove it. Test reachable terminal conditions, objective
   mutation, nondegenerate risk statistics, classification-miss reporting, action-parser cleanup,
   and removal of the fail-open legal-category path from authority.

Gate P3: old-path regression tests pass; MDMP, Raven, and the post-freeze synthetic bundle compile
without hard-coded scenario branches; a clean empty registry imports each content-addressed closure,
verifies all dependency hashes, and runs it offline with no sibling source files; escape tests cover
filesystem writes, network, subprocess creation, credential access, CPU, memory, and time; a rejected
or quarantined artifact cannot activate; immutable activation and rollback pass replay tests;
new-path replay/event/metric fixtures pass; the generated/committed transition is unified or has the
explicit parity-tested boundary, while terminal reachability, objective mutation, degenerate risk,
classification-miss reporting, action parsing, and fail-open legality defects are closed;
pre-migration semantics are matched or each approved difference has a test and ADR.

### Phase 4: multi-fidelity mixed world

1. Add aggregate, kinematic, tactical systems, rigid-body, and domain-plugin fidelity contracts.
   Carry model evidence status separately; do not invent validation evidence.
2. Add deterministic promotion/demotion with hysteresis, budget, transition journal, and
   conservation checks.
3. Run stationary structures, pedestrians, ground vehicles, multirotors, fixed-wing kinematics,
   sensors, tracks, communications/EW, and effects in one world.
4. Implement component damage, functional state, debris/occlusion bounds, repair, readiness,
   inventory, and basic logistics needed by Raven.
5. Implement Raven soldier/vehicle pathing and unreachable-task results.

Gate P4: mixed-domain unit/property tests pass; promotion/demotion has no duplicate authority,
teleport, inventory creation, damage loss, RNG discontinuity, or thrashing; damage changes both
capability and the Arena projection.

### Phase 5: live service, roles, and replay

1. Add COA loopback gRPC control/query and projection streams, plus the authenticated Arena-edge
   role-filtered binary WebSocket used by the real browser path.
2. Add bounded per-client interest graphs, delta baselines, ACK/resync, backpressure, reconnect, and
   command idempotency with a separate durable evidence-event cursor.
3. Add the Arena edge adapter and generated client. Make COA the source for live Raven state.
4. Add EXCON, blue, red, operator, controller, observer, analyst, and automated roles with tests for
   authenticated principals, server-derived grants/ownership, revocation, origin policy, and truth
   isolation. Human entity control is enabled only for a demonstration/correction session.
5. Persist events/snapshots and expose pause, time scale, replay scrub, branch, and comparison.

Gate P5: eight simulated staff/trainer clients maintain bounded queues; duplicate and stale commands
are rejected or deduplicated; reconnect/resync converges; the actual browser-to-Arena-edge handshake
enforces authentication and Origin; COA refuses a non-loopback bind; unauthorized views and commands
fail; a parent and child replay share an exact prefix and the parent bytes remain unchanged.

### Phase 6: Raven product slice and Arena presentation

1. Upgrade Raven from a local replay scene to a live COA-backed exercise.
2. Include terrain/infrastructure, destructible buildings, soldiers, vehicles, sensors, protected
   traffic, multiple UAS behaviors, fused tracks, a human decision queue, one typed RF-jammer
   mission-effect surrogate, component outcomes, tasks, objectives, and AAR scoring.
3. Preserve the current air-base art, aircraft, UAS, sensor, ship, tower, effects, terrain, lighting,
   and native assets. Replace name heuristics with explicit render components.
4. Add strategic/tactical/sensor/EXCON/replay views plus training-only first/third-person
   demonstration and correction views with clear recording state.
5. Split `ArenaViewport.tsx` and `App.tsx` into tested modules where the audit identifies current
   responsibilities. Use persistent pools and incremental updates instead of clearing layers each
   frame.
6. Prove document import, recorded approval state, bundle compilation, execution, replay, branch, and
   reverse DOCX in one flow. Prove a procedural asset produced by generated code passes the asset
   gates and renders in the enforced quarantined preview with no authority role. Do not use that
   novel asset in the final Raven run without an existing real human approval record.

Gate P6: a browser test drives the functional scenario through detection, track change, authority,
effect, damage/task consequence, replay scrub, and child branch; operator output contains no hidden
truth; screenshots and console/network/frame-time evidence are saved; the checked-in visual rubric
has zero high-severity defects after independent visual review.

### Phase 7: RL outer loop and experiment evidence

1. Implement native headless single and vector batch APIs using COA worlds and model pins.
2. Add Gymnasium and PettingZoo Parallel adapters plus compatibility for existing Arena training
   sessions/checkpoints where the contracts match.
3. Add Arena demonstration capture, dataset validation, behavior-cloning training, policy
   checkpointing, and a correction session where a trainer temporarily takes over a learned bot.
   Drive the real capture UI with automated browser input for acceptance and label the resulting
   fixture `synthetic_trainer_input`. Reserve `human_demonstration` provenance for actual human input.
4. Test scripted, demonstration/imitation, MCTS, and RL intent producers through the same command
   gate and observation contract.
5. Add held-out seeds, deterministic reset/restore, separate terminated/truncated flags,
   checkpoint compatibility, population evaluation, uncertainty, and provenance.

Gate P7: headless training smoke and deterministic evaluation run without Arena; trainer-input and RL
paths replay the same accepted-intent log with identical desired ticks, revisions, and idempotency
keys and produce matching authoritative hashes; vector workers do not share RNG or mutable state; a
recorded synthetic trainer-input fixture captured through the real UI trains a bot; imitation, RL,
scripted, and MCTS bots are compared on identical held-out seeds with no truth leakage. Do not claim
the automated fixture was authored by a human.

### Phase 8: scale, failure tests, review, and cleanup

1. Create a deterministic Raven-derived load fixture with 100,000 total, 10,000 active tactical,
   and 1,000 rigid-body/high-fidelity entities. Keep the functional Raven scenario readable; the load
   fixture exists to test NPC scale, not to clutter the functional exercise.
2. Profile entity tables, spatial queries, systems, serialization, WebSocket deltas, Arena update,
   rendering, snapshots, and RL batches. Fix measured hot paths. Move a kernel to native code only
   if the profile and focused candidate benchmark require it.
3. Run malformed-input, disconnect, slow-client, duplicate-command, stale-revision, corrupt
   snapshot, incompatible-model, unavailable-asset, and partial-store failure tests.
4. Run deterministic, full regression, contract, browser, native-if-touched, load, and a bounded
   soak test. Scan logs for warnings, errors, queue growth, leaked truth, and nondeterminism.
5. Run explicit simplicity, code-review, and security-review agents against each repo's own diff and
   Git context. Fix confirmed findings and rerun affected gates. The lead then reviews both diffs and
   their integration itself. Do not rely on nested slash commands from inside the active response.
6. Rebuild generated artifacts from source. Remove task-created temporary files. Before starting a
   process, record its PID and any preexisting listener on its intended port. Stop only task-owned
   PIDs. Verify task-owned listeners closed without killing or claiming a preexisting process.
7. Run the checked-in evidence generator, inspect and commit its task-owned artifacts, and verify both
   worktrees are clean. Then run the separate read-only cross-repo verifier from those commits. It
   writes only to a temporary directory and must leave both worktrees clean. Do not push or deploy.

Gate P8: every completion statement at the top of this file has fresh evidence. The final report
lists commits, changed files, tests, performance, known limitations, screenshots, model status, and
open non-critical work without claiming more than was measured.

## Performance and load gates

Detect and record the exact hardware, OS, Python, Node, browser, compiler, Torch, and GPU used. Keep
benchmarks deterministic and versioned. The named scale fixture is `raven-bot-10k-v1`: 600 simulated
seconds after a 30-second warm-up, fixed seed set, 100,000 total entities, 10,000 active NPCs, 1,000
high-fidelity entities, declared bot policy tiers and decision rates, five-second snapshots, a
2,000-item normal projection, and the fixed command/event script checked into the fixture. The
browser run uses a 1440x900 foreground tab at device-pixel ratio 1 unless the hardware profile names
another fixed viewport. Freeze the fixture manifest and hash before optimization; changing it starts
a new named benchmark version. Report p50, p95, p99, maximum, memory, entity/fidelity/policy mix,
every tick and decision rate, missed bot decision deadlines, duration, seeds, snapshot interval,
projection size, and build type.

Use these first targets unless a stricter contract already exists:

- COA fixed tick: 20 Hz with 10,000 active tactical and 1,000 high-fidelity entities; authoritative
  p95 tick at or below 50 ms for a 10-minute local run, no skipped authoritative phase, no unbounded
  queue, and total process memory below 8 GiB.
- COA total world: 100,000 entities with 90,000 dormant, aggregate, or low-rate entities; stable
  memory after warm-up and no O(total world) work in a per-client projection.
- Staff/trainer connections: eight simulated local clients with at most one active demonstration
  controller; accepted/rejected command response p95 below 100 ms; projection latency p95 below
  150 ms; reconnect/snapshot/event-cursor resync completes within 2 seconds on localhost.
- Arena normal view: 2,000 visible entities/tracks/effects at 60 FPS p95 frame at or below 16.7 ms
  after warm-up, with no console or WebGL error.
- Arena stress view: 10,000 instanced visible items remains interactive at 30 FPS p95 frame at or
  below 33.3 ms. Detail may reduce; truth and selection must remain correct.
- Replay: scrub to any indexed snapshot in under 250 ms locally, then converge deltas without a
  state mismatch.
- Determinism: 100 identical short runs produce one logical hash sequence. Promotion/demotion error
  stays within each model's declared tolerance.
- RL: record headless steps/second for 1, 8, and 32 worlds and show scaling. Do not assert a speedup
  without the old and new result on the same hardware and scenario.

If a target fails, keep the result, profile it, fix the limiting path, and rerun. Do not relax a
target silently. If the hardware cannot support a target, add a second explicit hardware profile and
keep the original result visible; do not call the gate passed without evidence on its named profile.

## Test matrix

Add focused tests rather than one giant end-to-end test.

- Schema: codegen freshness, compatibility, reserved fields, malformed lengths, version ranges,
  units, axes, quaternion, unknown-field behavior, and cross-language fixtures.
- ECS: lifecycle, stable IDs, table moves, query order, command buffer, snapshot, restore, hash, and
  branch lineage.
- Scheduler: phase order, rates, pause, acceleration, single-step, deadlines, RNG isolation, and
  thread/order determinism.
- Fidelity: every promotion/demotion pair, conservation, hysteresis, budget, failure rollback, and
  event evidence.
- Terrain/spatial: elevation, collision, navigation, LOS/occlusion, cell boundary, stable query
  order, dormancy, and interest filters.
- Domains: stationary/destroyable structures, soldiers, vehicles, air entities, sensing, tracks,
  communications/EW, effects, readiness, repair, inventory, tasks, and objectives.
- Authority: role, ownership, idempotency, revision, timing, protected traffic, hold/deny/authorize,
  authentication, server-derived grants, revocation, impersonation, activation/attempt/outcome, and
  all rejection reasons.
- Information separation: truth never appears in operator/trainer schemas, IDs, client-accessible
  logs, browser console/network captures, DOM, native frames, screenshots, projection checksums, or
  command payloads. Access-controlled COA evidence may contain clearly labeled truth.
- Generation: source canonicalization, library reuse, prompt/provenance capture, deterministic
  fake/recorded and offline providers, OS-enforced isolation, filesystem/network/subprocess/credential
  escape checks, resource limits, code and procedural-asset validation, lifecycle gates, truthful
  approval kinds, quarantine, rejected activation, content hashes, empty-registry offline dependency
  closure, child-branch activation, immutable rollback and failed rollback, replay without LLM calls,
  and MDMP/Raven/post-freeze synthetic bundle generation through one service path.
- Persistence: atomic write, crash/reopen, corrupt input, snapshot migration, immutable parent,
  exact prefix, deterministic child, and model/schema mismatch.
- Network: real browser-to-edge authentication and Origin, COA loopback bind enforcement, ordered
  deltas, missing base, projection checksum, evidence cursor, resync, reconnect, slow consumer,
  bounded queue, oversized frame, invalid command, eight-client load, and clean shutdown.
- RL/imitation: reset seeds, independent batches, terminated/truncated, snapshot/restore, adapter
  compliance, observation parity, demonstration integrity, behavior cloning, correction handoff,
  policy isolation, checkpoint compatibility, and accepted-intent-log parity.
- Arena: generated client mapping, incremental scene updates, pooling, selection, camera/view roles,
  replay, branch, uncertainty, damage variants, explicit assets, frame limits, visual snapshots, and
  the checked-in zero-high-severity visual acceptance rubric.
- Documents: bounded parsing, provenance, fictionalization, approval, import/export, and semantic
  round trip.
- Scientific evidence: missing units/source/bounds/status rejects a model; calibrated and
  unvalidated labels render correctly; reports pin every model/data version.

Use property tests for invariants and deterministic fixtures for wire/replay identity. Use real
services on localhost for the final functional and load gates. Mocks may isolate unit tests; they do
not satisfy the terminal integration gate.

## Required artifacts

Keep these artifacts concise and checked in unless they are too large, in which case check in a
manifest with hashes and exact reproduction commands:

- architecture decision records and the current component/system/fidelity registry;
- Protobuf sources, generated binding procedure, descriptor hash, and cross-repo fixtures;
- generic scenario-compiler service, immutable MDMP, Raven, and post-freeze synthetic simulator
  bundles, content-addressed dependency closures, artifact registry, generated-code isolation profile,
  and procedural-asset validation reports;
- Raven functional scenario and the separate 10k/100k load fixture;
- model cards and VV&A evidence templates for every executed model;
- deterministic replay, branch, and load reports;
- hardware profiles and raw benchmark summaries;
- one `synthetic_trainer_input` dataset captured through the real Arena training UI, imitation
  checkpoint, RL checkpoint, and held-out comparison report; never label it human-authored;
- browser screenshots for strategic, tactical, sensor, platform, EXCON, damage/effect, replay, and
  2,000/10,000-item views;
- the visual acceptance rubric and independent review findings with zero open high-severity items;
- final test matrix with exact commands and results;
- a short operator/developer runbook that starts COA then Arena from the parent workspace and stops
  both cleanly.

Do not check in credentials, machine secrets, classified data, large package downloads, caches,
node modules, Python environments, browser profiles, or proprietary game packages.

## Research basis

Use primary sources and verify current versions before adding a standard or dependency:

- Claude Code [`/goal`](https://code.claude.com/docs/en/goal),
  [commands](https://code.claude.com/docs/en/commands),
  [subagents](https://code.claude.com/docs/en/subagents), and
  [permission modes](https://code.claude.com/docs/en/permission-modes).
- [gRPC core concepts](https://grpc.io/docs/what-is-grpc/core-concepts/) and
  [Protocol Buffers compatibility](https://protobuf.dev/programming-guides/proto3/).
- Protocol Buffers warns that
  [deterministic serialization is not canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/).
- [RFC 6455 WebSocket Protocol](https://www.rfc-editor.org/rfc/rfc6455).
- [Flecs deterministic system ordering and staging](https://www.flecs.dev/flecs/md_docs_2Systems.html)
  as a scheduling benchmark, not a preselected dependency.
- [Unreal Replication Graph](https://dev.epicgames.com/documentation/en-us/unreal-engine/replication-graph-in-unreal-engine)
  and [World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine)
  as interest/streaming patterns, not runtime dependencies.
- [OpenUSD scene composition](https://openusd.org/release/intro.html) and the
  [OGC 3D Tiles specification](https://docs.ogc.org/cs/22-025r4/22-025r4.pdf).
- [Gymnasium environment API](https://gymnasium.farama.org/api/env/),
  [Gymnasium vector API](https://gymnasium.farama.org/api/vector/), and
  [PettingZoo Parallel API](https://pettingzoo.farama.org/api/parallel/).
- Current RLlib documentation states that
  [multi-agent environments are not yet vectorizable](https://docs.ray.io/en/latest/rllib/multi-agent-envs.html).
- [IEEE 1516-2025 HLA](https://standards.ieee.org/ieee/1516/6687/) and
  [IEEE 1730-2022 DSEEP](https://standards.ieee.org/ieee/1730/10715/) for later federation work.
  IEEE 1278.1-2012 DIS is inactive-reserved while its revision is open; pin a partner-approved
  profile before implementing a gateway.
- [DoDI 5000.61 (2024)](https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/500061p.pdf)
  and [MIL-STD-3022](https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=275961) for
  lifecycle VV&A and evidence structure.
- [NASA-STD-7009B](https://standards.nasa.gov/node/263) for supporting model credibility,
  sensitivity, uncertainty, and acceptance practices. It does not replace DoD accreditation.

## Final response contract

Do not end with a progress summary. End only after the completion condition passes or a true
external blocker remains after three documented alternatives.

The final response must contain:

1. the delivered functional behavior in plain language;
2. paired repo branches and local commit IDs;
3. a table of each completion claim, exact command, exact result line, and whether it ran after the
   last relevant edit;
4. scale and performance results tied to hardware profiles;
5. deterministic replay and branch hashes;
6. model/VV&A status and limits, with no unsupported realism claim;
7. links to screenshots, evidence, contracts, runbook, and main changed modules;
8. every remaining issue classified as critical or non-critical, with critical issues preventing
   completion;
9. confirmation that no push or deployment occurred and all task-started processes and ports are
   closed.

Begin now. Read first, establish the baseline, use subagents with clear ownership, then implement
through every green gate without waiting for another user prompt.
