# Counter-UAS product roadmap

## Scope and safety

Pytho Arena should become a mission-training system for counter-UAS crews, instructors,
and analysts. It should train the full decision loop: detect, track, identify, decide,
act, and review. It should feel like a modern game, but score actions against declared
training objectives rather than reward spectacle.

All built-in scenarios must remain unclassified fictional composites. They may use broad
public patterns such as an air base, port, or urban event site. They must not copy current
coordinates, defense layouts, readiness, routes, force posture, weak points, or strike
paths. Public product claims below are design inputs, not independent test results or
performance certifications.

## What public systems and exercises teach us

| Public example | What its public material emphasizes | Lesson for Arena |
| --- | --- | --- |
| [Army Green Sands](https://www.army.mil/article/274387/green_sands_the_evolution_of_counter_uas_training) | Crews practice identifying, classifying, and engaging threats through repeated, theater-relevant scenarios with C2 and system-of-systems simulation. | Train the crew decision loop, not only drone flight or a weapon view. Support repeatable runs and team roles. |
| [Army National Training Center C-UAS study](https://www.army.mil/article/288207/counter_unmanned_aerial_systems_c_uas_training_and_implementation_at_the_national_training_center) | Manual engagement adjudication is slow and misses events. The study calls out the training gap caused by limited instrumentation. | Record every sensor report, operator decision, effect, and outcome. Adjudicate in simulation time and make the evidence reviewable. |
| [NATO JPOW 2025](https://www.ncia.nato.int/newsroom/news/ncia-strengthens-allies-counter-drone-defence-training) | The exercise connects C-UAS with broader air defense and uses Distributed Interactive Simulation and hardware-in-the-loop. | Keep Arena interfaces open. Add federation and hardware connections only after the internal contracts are stable. |
| [NATO TIE 2026](https://www.ncia.nato.int/newsroom/news/allies-and-industry-test-the-latest-counterdrone-technology-during-nato-exercise) and [LCI-X](https://www.act.nato.int/activities/lci-x/) | Many sensors, effectors, and C2 applications must interoperate; connected cells must scale beyond one site. | Treat sensors and effectors as replaceable plugins. Test multi-cell coordination and degraded links. |
| [DedroneTracker.AI](https://www.dedrone.com/products/drone-detection-software) | The product presents a fused air picture, works with several sensor types, ranks alerts, and retains forensic records. | Make tracks, confidence, evidence, and alert priority the main operator objects. Keep truth out of the operator view. |
| [DroneSentry-C2](https://www.droneshield.com/products-software) | The public design joins RF, radar, and optical data, shows site and sensor health, supports edge and enterprise views, and exports after-action data. | Model readiness and health, not just nominal coverage. Use one operator workflow from one site to several sites. |
| [Anduril Lattice C-UAS](https://www.anduril.com/news/anduril-selected-for-u-s-army-s-integrated-battle-command-system-maneuver-program) | A shared C2 layer joins sensors and effectors and helps one operator manage several threats. | Build a decision queue with clear automation boundaries. Measure operator load as threat count rises. |
| [MACE UAS operations](https://www.bssim.com/uas/) | The simulator models contested links and spectrum effects, supports first-person controls and table-top planning, and allows configurable threat missions. | Offer role-specific views over one simulation. Add deterministic link degradation and instructor-authored variation. |
| [Horizon Guardian](https://www.appliedvirtual.net/horizon-guardian) and [Operator XR Interceptor](https://operatorxr.com/counterdrone) | Portable trainers combine configurable threats, signal and environment effects, team practice, and replay from several viewpoints. | Make short drills easy to launch. Save camera, decision, and score timelines for review from operator, threat, and analyst views. |

Two policy points affect the design. [DoD Directive 3000.09](https://www.defense.gov/News/Releases/Release/Article/3278076/dod-announces-update-to-dod-directive-300009-autonomy-in-weapon-systems/)
requires appropriate levels of human judgment over the use of force and clear operator
feedback. [GAO's counter-drone technology review](https://www.gao.gov/assets/gao-22-105705.pdf)
also notes false detections, limited mitigation range, interference, and safety risks.
Arena therefore needs an explicit authority gate, visible system limits, protected
traffic, and scored consequences for bad decisions.

## Fit with the current repository

Arena already has the boundaries needed for this plan:

- `scenario/models.py` stores versioned factions, relationships, actor groups, sensors,
  responses, objectives, rewards, policy bindings, simulation rates, and 3D scene data.
- `scenario/documents.py` imports a background brief into a reviewed fictional scenario
  and exports the saved scenario back to a DOCX brief.
- `core/env.py` owns the batched deterministic state transition. Policies submit
  normalized commands and cannot write state directly.
- `simulation/physics.py` supports fast 2D, point-mass 3D, and a multirotor 6-DOF
  surrogate behind a versioned state contract.
- `simulation/cuas.py` provides the first typed sensor-report and deterministic fused-track
  contract. `simulation/events.py` has event names for fusion, authority, effector use,
  intercepts, and attacks.
- `training/` has an algorithm registry, immutable environment contracts, isolated jobs,
  checkpoints, and a REINFORCE baseline. `experiments/` can compare policy populations.
- `server/replay.py` records truth, measurements, events, and metrics. The browser has
  separate operator and analyst views with replay scrubbing.
- `live/messages.py` and the shadow-mode live API define transport-neutral track messages.
  Shadow mode does not issue external commands.
- The Three.js client and Dagor overlay consume the same `frame-v1` display contract at
  20 Hz and cap a frame at 2,000 visible items.

The main gap is not another renderer. It is a connected track-to-decision model that uses
these boundaries end to end.

## Ranked features

### P0 — one useful training lane

Build these in order. Each item must preserve deterministic replay and operator-truth
separation.

1. **Track-centered detect-to-identify workflow.** Turn raw sensor measurements into
   persistent tracks with age, confidence, covariance, classification, source reports,
   and loss/reacquisition state. The operator acts on tracks, not truth entities.
2. **Human authority gate.** Add `hold`, `deny`, and `authorize` decisions with operator,
   reason, simulation time, authority scope, and expiry. No simulated effect may occur
   without a valid decision. Keep automation at recommendation level in this phase.
3. **One typed effector.** Replace the generic response in the first lane with one
   abstract, non-parameterized response type. Track range eligibility, readiness,
   capacity, assignment, result, and cost. Add more types only after the event contract
   and AAR are stable.
4. **Decision queue and workload.** Rank tracks by scenario-declared risk. Show why each
   item is ranked, what evidence supports it, and which friendly or protected traffic is
   nearby. Track acknowledgements, stale decisions, and queue depth.
5. **Threat variation.** Add deterministic red behaviors such as direct transit,
   loiter, decoy, split group, link loss, and route change. Keep all routes synthetic.
   Hold out seeds and behavior combinations from training runs.
6. **Evidence-grade AAR.** Replay the operator picture beside analyst truth. Mark first
   detection, classification changes, authority requests, decisions, assignments,
   effects, false alarms, protected-traffic risk, and objective outcomes. Allow a branch
   from any decision point with the same pre-branch state.

### P1 — crew and instructor product

1. **Instructor/EXCON console.** Schedule or inject synthetic contacts, sensor faults,
   weather changes, link loss, false alarms, and protected traffic. Record every inject.
2. **Team roles and communications.** Add sensor operator, battle captain, authority,
   and analyst seats. Support handoff, acknowledgement, shared annotations, and recorded
   text or push-to-talk event metadata.
3. **EW and datalink degradation.** Execute the existing communication-component data.
   Model deterministic latency, packet loss, range, terrain masking, interference, and
   recovery without publishing real system parameters.
4. **Readiness and logistics.** Add sensor warm-up, calibration, faults, duty cycle,
   effector inventory, reload or recharge time, maintenance state, and cost per attempt.
5. **Mastery progression.** Use short drills, clear objectives, hidden analyst truth,
   increasing contact density, repeat-until-mastered gates, and unit-owned scorecards.
   Do not use a global leaderboard for operational training data.
6. **Counterfactual review.** Re-run a saved decision point with another assignment or
   authority decision. Report outcome deltas and uncertainty rather than declaring one
   answer universally correct.
7. **Role-specific controls.** Support a table-top command view, sensor view, optional
   first-person drone view, and common game controllers where they match the training
   task. All views must read the same authoritative state.

### P2 — connected test and evaluation

1. **DIS/HLA federation.** Map Arena entities, tracks, effects, time control, and exercise
   ownership to a versioned gateway. Keep the current engine usable without a federation.
2. **Hardware- and software-in-the-loop.** Add adapters for approved training devices and
   C2 test systems. Require explicit `simulation`, `shadow`, and `test` modes. Do not add
   a live-use command path to the training server.
3. **Multi-cell and multi-site exercises.** Join several fictional sites with separate
   operators, local sensor pictures, cross-cueing, link limits, and an enterprise view.
4. **Validated fidelity plugins.** Add radar, EO/IR, RF, propagation, weather, terrain,
   fixed-wing, and detailed multirotor models only with declared validity ranges and
   reference cases.
5. **Adversarial policy curriculum.** Train red and blue policies against populations,
   evaluate on held-out seeds and behaviors, and report exploitability and failure cases.
   Never score a policy only against the opponent used during training.
6. **Scenario factory with review gates.** Extend DOCX import with reusable fictional
   templates, asset checks, coverage checks, difficulty estimates, and human approval.
   Preserve the reverse DOCX export and source-to-scenario assumptions.

## First vertical slice: Track-to-decision drill

Use the existing fictional Raven air-base scene. Create a short scenario with a small
mixed set of hostile, friendly, protected, and unknown tracks. The layout, routes, system
locations, and performance values remain synthetic.

The slice has one loop:

1. Existing scenario sensors emit noisy `SensorTrackReport` records.
2. The fusion service associates reports to one persistent `FusedTrack` and retains the
   evidence IDs.
3. A deterministic classifier recommends `unknown`, `friendly`, `suspect`, or `hostile`
   and explains the recommendation with scenario-visible evidence.
4. The operator chooses `hold`, `deny`, or `authorize` from the operator view.
5. One typed response accepts only a current authorization and eligible track.
6. The engine writes fusion, authority, assignment, result, and outcome events into the
   same replay used by the browser and native client.
7. The AAR shows the operator picture first, then reveals analyst truth and score causes.

This slice uses the existing simulation clock, event model, replay store, operator/analyst
split, scene, and `frame-v1`. It does not need DIS, hardware, a second effector type, or a
new rendering engine.

## Acceptance criteria for the first slice

| Area | Pass condition |
| --- | --- |
| Determinism | Three runs with the same scenario hash, seed, and action log produce the same fused tracks, event order, terminal state, score, and replay digest on CPU. |
| Track evidence | Every fused track references at least one source report. Duplicate reports, mixed track IDs, non-finite values, and out-of-order stale updates are rejected or recorded as explicit drops. |
| Operator separation | Automated UI tests prove that operator payloads and screens contain no truth-only position, faction, status, or analyst label. Analyst mode still shows the corresponding truth. |
| Human authority | Tests attempt every effect path without authorization, after denial, after expiry, and against protected traffic. All four paths produce no effect and record the reason. |
| Decision audit | Every authority request has exactly one current disposition. Every effector attempt links to the track, decision, response, operator or policy, simulation time, and outcome. |
| Workload | The UI remains usable with 100 simultaneous tracks: queue sorting, acknowledgement, filtering, and one decision all update within 100 ms on the reference Mac. |
| Display scale | Browser and native views sustain 60 FPS while receiving 2,000-item `frame-v1` snapshots at 20 Hz on the reference Mac. No decision event is dropped during replay scrub. |
| AAR | Scrubbing backward and forward reconstructs the same operator picture and decision state. Branching once from a saved decision preserves all pre-branch event IDs and gives the branch a new run ID. |
| Scoring | The AAR reports time to first detection, time to classification, time to decision, correct and incorrect classifications, effects attempted, protected-traffic effects, objective damage, resource cost, and peak queue depth. |
| Scenario documents | Importing the approved fictional background brief creates the lane with an assumptions report. Exporting that saved version produces a brief that identifies every synthetic transformation and review warning. |
| Training evaluation | Any learned policy is evaluated on at least 30 held-out seeds and every declared red behavior. The report includes mean, spread, worst case, and failures, not only training return. |
| Regression gate | Unit tests cover fusion, authority, effector eligibility, event linkage, and scoring. API tests cover scenario save, run, replay, and rejected commands. Frontend tests cover operator-truth separation and the decision queue. |

## Product score, not just simulation score

A strong release must improve crew learning and instructor work. Track these measures per
version:

- median setup time from selecting a scenario to starting the first run;
- percentage of a run that can be explained from recorded evidence;
- operator decision accuracy and median decision time by difficulty band;
- protected-traffic effects and authority violations, both with a target of zero;
- learning gain between first and third attempts on the same skill;
- retention on a different held-out scenario after at least seven days;
- instructor time needed to build, run, and review one lane;
- performance at 100, 500, and 2,000 displayed items;
- replay digest stability and scenario/checkpoint contract compatibility.

The release gate is not a visual demo alone. It is a repeatable drill, a clear operator
decision, a complete evidence chain, a useful AAR, and a held-out evaluation.
