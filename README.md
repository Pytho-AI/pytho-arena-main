# Pytho Arena

A deterministic, GPU-friendly, multi-domain environment for wargaming, policy
training, and empirical-game evaluation. The default scenario demonstrates:

`movement → sensing → response → objective attack → outcome`

Red, Blue, and Neutral are data in a scenario rather than hard-coded engine roles.
Factions declare relationships, actor groups, resources, reward weights, and policy
bindings. This keeps the same execution and evidence contracts usable for aircraft,
uncrewed systems, ground vehicles, maritime platforms, background traffic, and other
domains.

## Quick start

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./scripts/run-arena.sh
```

Open <http://127.0.0.1:8096/>.

The browser opens on the unclassified fictional Strait Sentinel — Raven Air Base
Defense scenario. Its public-source and safety basis is in
[`docs/SCENARIO_BASIS.md`](docs/SCENARIO_BASIS.md).

For training or headless use, the core install (`pip install -e .`) needs only
PyTorch and Pydantic; the FastAPI server is the `server` extra
(`pip install -e '.[server]'`).

## Docker

```bash
docker compose up --build
```

Open <http://127.0.0.1:8096/>. Override the host port with `PYTHO_ARENA_PORT`.

Without compose:

```bash
docker build -t pytho-arena:local .
docker run --rm -p 8096:8096 -v arena-data:/data pytho-arena:local
```

Notes:

- The image installs **CPU-only** PyTorch wheels (~960MB image). For an NVIDIA
  host, build with a CUDA index and run with `--gpus all`:
  `docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124 -t pytho-arena:cuda .`
- The browser bundle is rebuilt from `frontend-src/` inside the image, so the
  container never depends on the committed `server/frontend/` tree being current.
  `npm run build` includes `tsc --noEmit`, so a type error fails the image build.
- Scenarios and replays live in the `arena-data` volume at `/data/arena`
  (`PYTHO_ARENA_DATA_DIR`), kept separate from the host's gitignored `var/`.
  Saved scenario versions are immutable once seeded — to pick up
  `scenario/library/*.json` edits, recreate the volume:
  `docker compose down -v`.
- The container runs as non-root (uid 10001) and exposes a healthcheck on
  `/api/health`.

## Architecture

The package is layered by dependency direction. One compiled contract serves
wargaming, training, population evaluation, replay, and live adapters:

```text
scenario ← simulation ← core ← policies ← env ← training ← server
```

```text
src/pytho_arena/
├── scenario/     Versioned data, platform components, objectives, registry
├── simulation/   Compiler, contracts, clocks, physics, events, objectives
├── core/         Batched tensor kernel driven by external actions
├── policies/     Scripted and learned policy implementations
├── env/          Rollouts and multi-agent adapters
├── training/     Algorithm registry, RL backends, isolated jobs, checkpoints
├── experiments/  Population matchups and empirical regret
├── live/         Canonical track messages and shadow-mode adapters
└── server/       FastAPI, replay evidence, run/training/live APIs
```

The engine never chooses actions, and actions never write state directly.
`BatchedScenarioEnv.step(actions)` takes normalized *commands* keyed by
policy-binding id — unit-ball direction vectors `[batch, k, D]` for movement
(`D=2` or `3` according to the compiled physics contract)
bindings, desired headings `[batch, k]` for sensing bindings — and an actuator
stage owned by the engine turns commands into state: validate (reject
non-finite), project onto declared capabilities (speed, sensor slew rate), then
integrate. No controller — scripted, trained, human, or remote — can exceed
scenario physics, and command saturation is surfaced per step in
`StepOutput.info`. Two test families pin the contract: a golden-fixture test
(same inputs, bit-for-bit same world) and adversarial invariant tests (no
inputs break the world).

The automatic `/api/runs` executor resolves scripted policies and compatible
checkpoints. Human and remote implementations drive the public `step(actions)`
contract through an external session/adapter; they are not silently substituted by
the baseline policy registry.

## Current capabilities

- Strict schema `2.0` scenario JSON with immutable saved versions
- Curated scenario library packaged under `pytho_arena.scenario` (data, not code),
  seeded into the registry at startup; override it with `PYTHO_ARENA_SCENARIO_DIR`
- DOCX background-brief import that produces a scenario, typed 3D scene blueprint,
  asset-resolution report, assumptions, and review warnings
- Reverse DOCX export for any saved scenario, using the same background-brief contract
- Scenario-defined factions and directional `ally`, `opponent`, `neutral`,
  `protected`, and `unknown` relationships
- Actor groups, sensors, responses, objectives, and policy-to-resource bindings
- Scenario-declared reward weights (`rewards`), so the training objective is data
- Faction-scoped `reward_terms` for attack, defense, survival, and transit objectives
- Composable mobility and communications component contracts independent of platform names
- A physics registry with `kinematic_2d`, bounded `point_mass_3d`, and external backends
- Deterministic multi-rate policy, physics, sensing, and effects clocks
- External action stepping: `step(actions)` keyed by binding id, with a
  validate → project → integrate actuator stage enforcing declared capabilities
  (speed, optional sensor `slew_rate_dps`) and reporting saturation counters
- Policy registry resolving bindings to scripted baselines or trained
  checkpoints (`checkpoint:<training_id>`)
- Discoverable RL training algorithms behind one validated job contract;
  REINFORCE is the first built-in backend and retains its batch baseline,
  entropy exploration, deterministic execution, and GPU-friendly rollouts
- Descriptor-driven browser training controls and `GET /api/training-algorithms`,
  so each new backend can declare its capabilities and hyperparameters without
  changing scenario or checkpoint contracts
- PettingZoo-parallel-style multi-agent adapter (`ParallelArenaEnv`)
- Dense PyTorch state shaped `[batch, entity, feature]`
- CPU, CUDA, and Apple MPS device selection
- Deterministic seeded runs and persisted replay evidence
- Run-level degraded conditions: typed `disruptions` on runs and training jobs
  degrade communications (delivered reports), sensors (detection, range, noise),
  or effectors (effectiveness, launch reliability) per faction, deterministically,
  without touching scenario hashes or checkpoint contracts
- Faction-attributed belief observations, track age/confidence, metrics, and rewards,
  separate from analyst truth
- Relationship-aware responses: only declared opponents are eligible, while
  protected neutral traffic remains in the same world and replay
- A counter-UAS decision lane: fused tracks with evidence report IDs and opaque track
  ids, deterministic classification from measured kinematics plus cooperative
  identification, an authority queue, and one typed RF-jammer effector that stays closed
  until a recorded human decision authorizes it
- Immutable decision branching: an operator's hold, deny, or authorize starts a child run
  that reproduces the parent frame-for-frame up to the decision and never edits the parent
- Operator view, analyst truth, timeline, events, aggregate metrics, and per-faction
  outcomes
- A React and Three.js mission viewport rendering replay over a fictional Gulf air
  base with an approved F-16 LOD, camera presets, a sensor scope, terminal-event
  effects, entity focus, and scrubbing; it degrades to instanced convex geometry at
  scale and to procedural geometry only when an asset fails to load
- Browser-launched RL training with live job status and checkpoint selection
- FastAPI contracts for scenario management and simulation runs
- Hash-locked scenario and action/observation contracts for trained checkpoints
- Isolated process training workers (`PYTHO_ARENA_TRAINING_WORKER=thread` for debugging)
- Canonical replay events, shadow-mode live tracks, and population evaluation manifests

The default stays on the fast 2D fidelity level. Scenarios can select the integrated
3D point-mass backend or register a higher-fidelity external backend without changing
policy, evidence, or API boundaries. Aerodynamic, terrain, maritime, and specialized
communications models remain plugins rather than assumptions in the kernel.
`trainable` bindings identify the controllers the selected RL algorithm replaces; checkpoints
load only when their immutable scenario and environment contracts match.

## Scenario model

```text
Scenario
├── simulation             physics backend and subsystem clock rates
├── visualization          environment and static 3D scene assets
├── factions[]             identity, category, objectives, display metadata
├── relationships[]        directional rules between factions
├── evaluation_faction_id  viewpoint for aggregate opponent/protection metrics
├── protected_zones[]      objectives and geometry
├── actor_groups[]         entities, mission, domain-neutral components, target
├── sensors[]              observation resources owned by factions
├── responses[]            abstract response resources owned by factions
├── rewards                per-event reward weights (scenario data)
├── reward_terms[]         faction-specific event objectives
└── policy_bindings[]      controller → faction → groups/sensors (+ display name)
```

Every actor group has exactly one movement binding and every sensor has exactly one
sensing binding. Any faction can own either type. A binding can be marked `trainable`
or fixed independently, so self-play can swap Red and Blue checkpoints while neutral
traffic stays scripted—or neutral behavior can become trainable in another experiment.
A binding may carry an optional display `name` (the default scenario ships
"Red drone swarm", "Blue sensor net", "Neutral air traffic"); the UI shows it
everywhere and falls back to the binding id when absent.

Relationships are directional. For example, the default scenario declares Red as an
opponent from Blue's perspective and Neutral as protected. The response engine uses
that relationship rather than a faction name when deciding eligibility.
Aggregate detection and defense metrics use `evaluation_faction_id`; when it is
omitted, they use the union of all declared opponent and protected relationships.

## Scenario documents

The mission rail accepts a `.docx` background brief with the same semantic sections
as the JLC example: background, scope, coordination, protected assets, threat,
sensors, responses, coverage views, and references. Import creates an immutable
scenario version and returns a review report. The report lists matched sections,
resolved assets, assumptions, warnings, and every safety transformation.

Images and maps are not treated as spatial truth. If a brief names a real site, the
importer retains broad environment and asset categories but replaces boundaries,
coordinates, marked vulnerable points, sensor positions, response positions, patrol
zones, and approach geometry with a fictional layout. A human reviewer still owns
approval of the imported scenario.

The **EXPORT BRIEF** action generates a `.docx` from the selected saved version. The
same paths are available headlessly:

```bash
PYTHONPATH=src .venv/bin/python scripts/scenario_documents.py import brief.docx \
  --scenario-out scenario.json --report-out import-report.json

PYTHONPATH=src .venv/bin/python scripts/scenario_documents.py export scenario.json \
  --output background-data.docx --hero-image scene.png
```

## Repository layout

```text
src/pytho_arena/       Scenario, simulation, core, policies, training, experiments, live
  scenario/library/    Packaged curated scenario JSON library
  server/frontend-src/ Vite, React, and Three.js frontend source
  server/frontend/     Packaged browser build and local 3D assets
native/dagor-client/   Dagor viewer overlay, converted packs, tests, and evidence
tests/                 Determinism, golden-fixture, validation, and API tests
scripts/run-arena.sh   Local launcher
var/                   Ignored runtime scenarios and replays
```

## API

```text
GET  /api/health
GET  /api/capabilities
GET  /api/training-algorithms
GET  /api/scenarios
GET  /api/scenarios/{scenario_id}?version=N
POST /api/scenarios/validate
POST /api/scenarios
POST /api/scenarios/import-document
GET  /api/scenarios/{scenario_id}/background-document?version=N
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/replay
POST /api/runs/{parent_run_id}/branches
POST /api/trainings
GET  /api/trainings
GET  /api/trainings/{training_id}
POST /api/trainings/{training_id}/cancel
POST /api/live/tracks
GET  /api/live/tracks/latest
```

A run selects policies by binding ID rather than by side. A policy id is either
a scripted baseline or a trained checkpoint:

```json
{
  "scenario_id": "multi-faction-air-defense",
  "scenario_version": 1,
  "policy_overrides": {
    "red-movement": "checkpoint:1f0f4a2e-…",
    "blue-sensing": "track",
    "neutral-movement": "transit"
  },
  "seed": 7,
  "device": "cpu",
  "disruptions": [
    {"kind": "communications", "drop_probability": 0.5},
    {"kind": "sensor", "detection_probability_multiplier": 0.7},
    {"kind": "effector", "reliability": 0.9}
  ]
}
```

Disruptions are counterfactual run inputs, never scenario truth: `communications`
drops delivered sensor reports while analyst truth still records what sensors saw,
`sensor` degrades what sensors physically see, and `effector` degrades response
effectiveness and launch reliability. `faction_ids` scopes a spec; omitted, it
targets the defending network (the `evaluation_faction_id`, else every faction
declaring opponent or protected relationships). Branches inherit the parent's
disruptions, replays record them, and `StepOutput.info` reports
`dropped_report_count` and `launch_failure_count` alongside saturation counters.

### Counter-UAS authority gate and decision branches

A response that declares an `effector` block is authority-gated: the engine applies its
effect only against entities a recorded human decision authorized for that effects tick.
Responses without the block keep their legacy always-on behavior, and because
`content_hash()` excludes `None` fields, existing scenario hashes are unchanged.

```json
{
  "id": "response-alpha",
  "faction_id": "defense",
  "position": [58.0, 42.0],
  "engagement_range": 34.0,
  "effector": { "kind": "rf_jammer", "available_uses": 2, "authority_valid_for_seconds": 45.0 }
}
```

Running such a scenario records an operator picture alongside analyst truth: each frame
gains `tracks` (fused, opaquely identified, built from measurements) and `decisions` (the
authority queue), and `metrics.counter_uas` scores the lane. Nothing fires until a
decision authorizes it.

An operator decides by branching, never by editing a run:

```json
POST /api/runs/{parent_run_id}/branches
{
  "decisions": [
    {
      "request_id": "roe-001",
      "disposition": "authorize",
      "operator_id": "operator-console",
      "rationale": "Inbound track correlated on the flight line",
      "step": 14
    }
  ]
}
```

The server re-runs the parent's exact scenario, seed, device, and policies with the
decision scheduled at that step, proves every frame before it is byte-identical to the
parent, and saves a child run carrying `parent_run_id`. The parent is never modified.
Dispositions are `hold` (deferrable), `deny`, and `authorize` (both terminal); one
authorization permits exactly one activation, and the engine — not the effector — reports
whether the effect defeated the track.

## Generalized RL training

The mission rail's **RL training** panel discovers registered algorithms from the
server. Select an algorithm, configure its declared hyperparameters, tick the
trainable bindings, and set common job controls such as iterations, batch size,
learning rate, and device. The panel polls while a job is in flight, showing
completed iterations against the target and offering cancellation; the recent-job
list identifies the algorithm and links each run to its details page. Every job —
running or past — has a details page at
`/trainings/{training_id}` with full return and loss charts that grow live
while it trains. When a job completes, its checkpoint appears as a
`checkpoint:<training_id>` option in the run policy selectors (for the exact
immutable scenario hash it was trained on), so a trained Red can immediately fly
against scripted (or trained) Blue in a deterministic replay. The same job is
available headlessly:

```bash
curl -X POST http://127.0.0.1:8096/api/trainings \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id": "multi-faction-air-defense",
       "config": {"algorithm_id": "reinforce",
                  "algorithm_parameters": {"gamma": 0.99, "entropy_coef": 0.01},
                  "iterations": 200, "batch_size": 256, "device": "auto"}}'
```

Or drive the trainer directly in Python:

```python
from pytho_arena import (
    CheckpointStore,
    TrainingConfig,
    default_scenario,
    environment_contract,
    train,
)

scenario = default_scenario()
contract = environment_contract(scenario)
result = train(
    scenario,
    TrainingConfig(
        algorithm_id="reinforce",
        algorithm_parameters={"gamma": 0.99, "entropy_coef": 0.01},
        iterations=200,
        batch_size=256,
    ),
)
CheckpointStore("var/arena/trainings").save(
    "my-checkpoint",
    {
        "training_id": "my-checkpoint",
        "scenario_id": result.scenario_id,
        "scenario_hash": scenario.content_hash(),
        "environment_contract_hash": contract.content_hash(),
    },
    result.policies,
)
```

`TrainingConfig` separates common execution fields from an `algorithm_id` and
`algorithm_parameters`. The registry validates those parameters with the selected
backend, resolves defaults before launching a worker, and records the normalized
configuration in job and checkpoint metadata. Older requests containing top-level
`gamma` and `entropy_coef` are migrated to the REINFORCE parameter block.

REINFORCE remains the default and regression baseline. Each trainable binding gets
its own actor (a small MLP over its faction belief observations, shared across the
entities or sensors it commands) and optimizes its faction's scenario-declared
reward with discounted returns, a normalized batch baseline, and an entropy bonus.
Everything the engine enforces for scripted policies holds for learned ones:
commands are validated and projected onto declared capabilities. Training runs are
deterministic for a given seed, reject non-finite updates, and run in isolated worker
processes by default.

New backends implement `TrainingAlgorithm`, publish a `TrainingAlgorithmDescriptor`
and parameter model, then register with `register_training_algorithm(...)`. They
receive the same scenario, selected bindings, callbacks, cancellation signal, and
immutable scenario hash as REINFORCE. The public `train(...)` function remains the
stable dispatch facade.

## Physics and fidelity

`step_seconds` remains the policy interval. The scheduler holds an action across
integral physics substeps and independently gates sensing and effects:

```json
{
  "simulation": {
    "physics_backend": "point_mass_3d",
    "physics_step_seconds": 0.1,
    "sensor_interval_seconds": 1.0,
    "effects_interval_seconds": 1.0
  }
}
```

Actor groups add mobility limits, initial altitude, communications limits, domain
labels, and tags through `components`. Physics backend API version 2 advances a
`PhysicsState` and returns a `PhysicsState`; external backends declare
`api_version = PHYSICS_BACKEND_API_VERSION` before registration. The kernel
continues to own command validation and capability enforcement.

Legacy worlds use scenario-local distance units. A force-based backend must convert
through `world.meters_per_unit`; the browser uses the same value for scene scale.
Leaving it absent preserves the existing visual scale fallback. Mobility is
executable today; communications fields are versioned contract data for the next
network-system plugin.

## Population experiments and live data

`ExperimentManifest.for_scenario(...)` pins scenario and environment hashes,
populations, and evaluation seeds. `evaluate_population(...)` runs the Cartesian
matchups and `empirical_regret(...)` summarizes best-response gaps.

`POST /api/live/tracks` accepts canonical `TrackUpdate` batches in shadow mode.
`ReplayTrackAdapter` emits the same messages from deterministic replay, so ingestion
can be developed before connecting an external feed. Shadow mode never issues
external commands.

## Development

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/pytest -q -ra
cd src/pytho_arena/server/frontend-src
npm ci
npm test
npm run build
```

The browser build uses the Arena replay as its source of truth. The default scene
manifest converts abstract world units to meters and maps each actor group to a local
asset. Operator mode shows raw sensor measurements. Analyst mode adds replay truth.
At 100 or more truth entities, the renderer switches to instanced low-cost convex
geometry derived from the loaded approved OBJ assets. Procedural geometry is used only
when an asset fails to load.
The browser also publishes the current replay frame at 20 Hz to the loopback frame-v1
relay at `ws://127.0.0.1:46000/`. The UI reports the link as offline, connecting,
linked, or error without implying that a native viewer is attached.

Start the checked-in loopback relay from the frontend source directory with
`npm run relay`. It binds only to `127.0.0.1:46000`. The publisher sends the current
full frame on reconnect and skips sends while the socket is above its buffer high-water mark.

The native Dagor client consumes that same loopback contract. Build, restore, resource,
and performance evidence is recorded in [`docs/DAGOR_CLIENT.md`](docs/DAGOR_CLIENT.md).

The mission rail launches and cancels RL training against `/api/trainings`, and a
completed job appears as a `checkpoint:<training_id>` policy on every binding it
trained, offered only when scenario id, version, and content hash all match. The
per-job curve page at `/trainings/{training_id}` stays a standalone document served
from `frontend-src/public/`, so the Vite build copies it rather than deleting it —
`build.emptyOutDir` clears `server/frontend/` on every run. It keeps its own
`training.css` because `styles.css` is now the React bundle's stylesheet.

The interactive demo defaults to CPU because a single episode is too small to
amortize accelerator dispatch. Batched evaluation can use `auto`, `cuda`, or `mps`
while keeping simulation state on the selected device.

### Driving the engine directly

The wargaming server and a trainer share one loop — observe, act, step:

```python
from pytho_arena import BatchedScenarioEnv, build_policies, default_scenario
from pytho_arena.env.rollout import episode

env = BatchedScenarioEnv(default_scenario(), batch_size=256, device="auto")
policies = build_policies(env, {"red-movement": "coordinated", "blue-sensing": "coverage"})
for output in episode(env, policies):
    ...  # output.observations / rewards / terminated / info, per faction
```

For multi-agent training, `ParallelArenaEnv` exposes the same engine through a
PettingZoo-parallel-style contract with one agent per policy binding:

```python
from pytho_arena.env import ParallelArenaEnv

arena = ParallelArenaEnv(default_scenario(), batch_size=256, device="auto")
observations, infos = arena.reset()
# arena.trainable_agents -> ["red-movement", "blue-sensing"]
observations, rewards, terminations, truncations, infos = arena.step(actions)
```

The generalized trainer (`pytho_arena.training`) dispatches this loop through a
registered algorithm. The built-in REINFORCE backend samples actions from
per-binding actors, accumulates faction rewards, and applies Monte Carlo policy
gradient updates. Alternating self-play schedulers can sit above population manifests;
formal gap assignment and specialized domain backends consume the same event and
contract interfaces without modifying the policy loop.
