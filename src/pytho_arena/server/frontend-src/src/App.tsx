import { useCallback, useEffect, useMemo, useState } from "react";

import { adaptArenaReplayFrame } from "./arena";
import type { ArenaDecisionRequest, ArenaSceneState, RoeDisposition } from "./arena";
import { api } from "./app/api";
import { DISPOSITIONS, branchDecision, decisionQueue, pendingCount } from "./app/decisionQueue";
import { playbackStartFrame } from "./app/playback";
import type {
  DisruptionSpec,
  Health,
  Notice,
  PolicyBinding,
  Replay,
  Role,
  RunSummary,
  Scenario,
  ScenarioListItem,
  ScenarioRecord,
  TrainingAlgorithm,
  TrainingAlgorithmsResponse,
  TrainingStatus,
} from "./app/types";
import { SensorScope } from "./components/SensorScope";
import { FrameV1Publisher, type NativeLinkStatus } from "./native/framePublisher";
import { ArenaViewport } from "./scene/ArenaViewport";
import { resolveSceneManifest } from "./scene/sceneManifest";

const POLICY_OPTIONS: Record<string, string[]> = {
  movement: ["transit", "direct", "probe", "coordinated"],
  sensing: ["sweep", "track", "coverage"],
};

// One seat in this slice. A decision is attributed to this operator in the
// child run's evidence, so it must be recorded, not inferred at review time.
const OPERATOR_ID = "operator-console";

const TRAINING_POLL_MS = 900;

type ImportReport = {
  source_filename: string;
  source_sha256: string;
  matched_sections: string[];
  sensor_modalities: string[];
  asset_resolution: Array<{ source_category: string; scene_asset: string; status: string }>;
  safety_transformations: string[];
  assumptions: string[];
  warnings: string[];
};

function defaultAlgorithmParameters(
  algorithm: TrainingAlgorithm,
): Record<string, boolean | number | string> {
  return Object.fromEntries(algorithm.parameters.map((parameter) => [parameter.id, parameter.default]));
}

function bindingLabel(binding: PolicyBinding): string {
  return binding.name ?? binding.id;
}

// Slider percentages compile to typed specs; zero sliders add nothing so the
// request stays byte-compatible with pre-disruption clients.
function buildDisruptions(comms: number, sensor: number, effector: number): DisruptionSpec[] {
  const specs: DisruptionSpec[] = [];
  if (comms > 0) specs.push({ kind: "communications", drop_probability: comms / 100 });
  if (sensor > 0) specs.push({ kind: "sensor", detection_probability_multiplier: 1 - sensor / 100 });
  if (effector > 0) specs.push({ kind: "effector", effectiveness_multiplier: 1 - effector / 100 });
  return specs;
}

function disruptionLabel(summary: RunSummary): string {
  const parts: string[] = [];
  for (const spec of summary.disruptions ?? []) {
    if (spec.kind === "communications") {
      parts.push(`comms ${Math.round(spec.drop_probability * 100)}%`);
    } else if (spec.kind === "sensor") {
      const detection = 1 - (spec.detection_probability_multiplier ?? 1);
      // A spec degrading only range/noise has no single percentage to show.
      parts.push(detection > 0 ? `sensors ${Math.round(detection * 100)}%` : "sensors degraded");
    } else {
      const effectiveness = 1 - (spec.effectiveness_multiplier ?? 1);
      parts.push(
        effectiveness > 0 ? `effectors ${Math.round(effectiveness * 100)}%` : "effectors degraded",
      );
    }
  }
  return parts.length ? parts.join(" · ") : "nominal";
}

function parseScenario(source: string): Scenario {
  try {
    return JSON.parse(source) as Scenario;
  } catch (error) {
    throw new Error(`Invalid scenario JSON: ${(error as Error).message}`);
  }
}

function percent(value: number | undefined): string {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function AppMetric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric-line"><dt>{label}</dt><dd>{value}</dd></div>;
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [record, setRecord] = useState<ScenarioRecord | null>(null);
  const [editor, setEditor] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [seed, setSeed] = useState(7);
  const [device, setDevice] = useState("cpu");
  const [communicationDisruption, setCommunicationDisruption] = useState(0);
  const [sensorDisruption, setSensorDisruption] = useState(0);
  const [effectorDisruption, setEffectorDisruption] = useState(0);
  const [trainingCommsDisruption, setTrainingCommsDisruption] = useState(0);
  const [trainingSensorDisruption, setTrainingSensorDisruption] = useState(0);
  const [trainingEffectorDisruption, setTrainingEffectorDisruption] = useState(0);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [role, setRole] = useState<Role>("operator");
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(250);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>({ kind: "neutral", text: "Loading mission library." });
  const [fps, setFps] = useState(0);
  const [nativeStatus, setNativeStatus] = useState<NativeLinkStatus>("offline");
  const [nativeError, setNativeError] = useState("");
  const [publisher, setPublisher] = useState<FrameV1Publisher | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);
  const [trainings, setTrainings] = useState<TrainingStatus[]>([]);
  const [trainingAlgorithms, setTrainingAlgorithms] = useState<TrainingAlgorithm[]>([]);
  const [algorithmId, setAlgorithmId] = useState("reinforce");
  const [algorithmParameters, setAlgorithmParameters] = useState<Record<string, boolean | number | string>>({});
  const [trainingBindings, setTrainingBindings] = useState<string[]>([]);
  const [iterations, setIterations] = useState(60);
  const [batchSize, setBatchSize] = useState(64);
  const [learningRate, setLearningRate] = useState(0.003);
  const [trainDevice, setTrainDevice] = useState<"auto" | "cpu" | "cuda" | "mps">("auto");
  const [importReport, setImportReport] = useState<ImportReport | null>(null);

  const useRecord = useCallback((next: ScenarioRecord) => {
    setRecord(next);
    setEditor(JSON.stringify(next.scenario, null, 2));
    setSeed(next.scenario.seed);
    setCommunicationDisruption(0);
    setSensorDisruption(0);
    setEffectorDisruption(0);
    setOverrides(Object.fromEntries(next.scenario.policy_bindings.map((binding) => [
      binding.id,
      binding.policy_id,
    ])));
    setTrainingBindings(next.scenario.policy_bindings.filter((binding) => binding.trainable).map((binding) => binding.id));
    setReplay(null);
    setFrameIndex(0);
    setPlaying(false);
  }, []);

  const loadScenario = useCallback(async (scenarioId: string) => {
    const next = await api<ScenarioRecord>(`/api/scenarios/${scenarioId}`);
    useRecord(next);
    setImportReport(null);
    setNotice({ kind: "success", text: `Loaded ${next.scenario.name}.` });
  }, [useRecord]);

  const importDocument = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setNotice({ kind: "neutral", text: "Reading document and resolving scene assets." });
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api<{ record: ScenarioRecord; report: ImportReport }>(
        "/api/scenarios/import-document",
        { method: "POST", body },
      );
      useRecord(result.record);
      setImportReport(result.report);
      const list = await api<{ scenarios: ScenarioListItem[] }>("/api/scenarios");
      setScenarios(list.scenarios);
      setNotice({
        kind: "success",
        text: `Imported ${result.report.matched_sections.length} brief sections · ${result.report.asset_resolution.length} asset categories resolved.`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let live = true;
    Promise.all([
      api<Health>("/api/health"),
      api<{ scenarios: ScenarioListItem[] }>("/api/scenarios"),
      api<TrainingAlgorithmsResponse>("/api/training-algorithms"),
    ]).then(async ([healthResult, list, algorithmResult]) => {
      if (!live) return;
      setHealth(healthResult);
      setScenarios(list.scenarios);
      setTrainingAlgorithms(algorithmResult.algorithms);
      const initialAlgorithm = algorithmResult.algorithms.find(
        (algorithm) => algorithm.id === algorithmResult.defaultAlgorithmId,
      ) ?? algorithmResult.algorithms[0];
      if (!initialAlgorithm) throw new Error("No training algorithms are registered.");
      setAlgorithmId(initialAlgorithm.id);
      setAlgorithmParameters(defaultAlgorithmParameters(initialAlgorithm));
      const first = list.scenarios.find((item) => item.scenarioId === "strait-sentinel-airbase")
        ?? list.scenarios[0];
      if (!first) throw new Error("No scenarios are available.");
      await loadScenario(first.scenarioId);
    }).catch((error) => {
      if (live) setNotice({ kind: "error", text: (error as Error).message });
    });
    return () => { live = false; };
  }, [loadScenario]);

  const loadTrainings = useCallback(async () => {
    try {
      const body = await api<{ trainings: TrainingStatus[] }>("/api/trainings");
      setTrainings(body.trainings);
    } catch {
      setTrainings([]);
    }
  }, []);

  useEffect(() => { void loadTrainings(); }, [loadTrainings]);

  // Poll only while this scenario has a job in flight; stop as soon as none do.
  const hasRunningTraining = trainings.some((training) => training.status === "running");
  useEffect(() => {
    if (!hasRunningTraining) return;
    const timer = window.setInterval(() => { void loadTrainings(); }, TRAINING_POLL_MS);
    return () => window.clearInterval(timer);
  }, [hasRunningTraining, loadTrainings]);

  useEffect(() => {
    const next = new FrameV1Publisher((url) => new WebSocket(url), setNativeStatus, setNativeError);
    next.start();
    setPublisher(next);
    return () => next.stop();
  }, []);

  useEffect(() => {
    if (!playing || !replay) return;
    const timer = window.setInterval(() => {
      setFrameIndex((current) => {
        if (current >= replay.frames.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, speedMs);
    return () => window.clearInterval(timer);
  }, [playing, replay, speedMs]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(target.tagName)) return;
      if (event.code === "Space" && replay) {
        event.preventDefault();
        if (playing) setPlaying(false);
        else {
          setFrameIndex((value) => playbackStartFrame(value, replay.frames.length - 1));
          setPlaying(true);
        }
      }
      if (event.code === "ArrowRight" && replay) {
        setPlaying(false);
        setFrameIndex((value) => Math.min(replay.frames.length - 1, value + 1));
      }
      if (event.code === "ArrowLeft") {
        setPlaying(false);
        setFrameIndex((value) => Math.max(0, value - 1));
      }
      if (event.code === "KeyF" && role === "analyst" && selectedEntityId) {
        setFocusNonce((value) => value + 1);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [playing, replay, role, selectedEntityId]);

  const frame = replay?.frames[frameIndex] ?? null;
  const sceneResult = useMemo<{ state: ArenaSceneState | null; error: string | null }>(() => {
    if (!frame || !replay) return { state: null, error: null };
    try {
      return { state: adaptArenaReplayFrame(frame, resolveSceneManifest(replay.scenario)), error: null };
    } catch (error) {
      return { state: null, error: (error as Error).message };
    }
  }, [frame, replay]);

  useEffect(() => {
    if (publisher && replay && sceneResult.state) {
      publisher.setFrame(replay.summary.run_id, sceneResult.state, true);
    }
  }, [publisher, replay, sceneResult.state]);

  const validate = async () => {
    setBusy(true);
    try {
      const result = await api<{ steps: number; entities: number; factions: number; policyBindings: number }>(
        "/api/scenarios/validate",
        { method: "POST", body: JSON.stringify(parseScenario(editor)) },
      );
      setNotice({
        kind: "success",
        text: `Valid · ${result.steps} ticks · ${result.entities} entities · ${result.factions} factions.`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      const next = await api<ScenarioRecord>("/api/scenarios", {
        method: "POST",
        body: JSON.stringify(parseScenario(editor)),
      });
      useRecord(next);
      const list = await api<{ scenarios: ScenarioListItem[] }>("/api/scenarios");
      setScenarios(list.scenarios);
      setNotice({ kind: "success", text: `Saved immutable version ${next.scenario.version}.` });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    if (!record) return;
    setBusy(true);
    setPlaying(false);
    setNotice({ kind: "neutral", text: "Running deterministic policy simulation." });
    try {
      const summary = await api<RunSummary>("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          scenario_id: record.scenario.scenario_id,
          scenario_version: record.scenario.version,
          policy_overrides: overrides,
          seed,
          device,
          disruptions: buildDisruptions(communicationDisruption, sensorDisruption, effectorDisruption),
        }),
      });
      const nextReplay = await api<Replay>(`/api/runs/${summary.run_id}/replay`);
      setReplay(nextReplay);
      setFrameIndex(0);
      setSelectedEntityId(nextReplay.frames[0]?.truth[0]?.id ?? null);
      setNotice({
        kind: "success",
        text: `Run complete · ${nextReplay.frames.length} replay frames · ${summary.device}.`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  // A decision never edits this run. It re-runs the same scenario, seed, and
  // policies with the decision scheduled at the frame on screen, and the server
  // proves every earlier frame still matches before saving the child run.
  const decide = async (request: ArenaDecisionRequest, disposition: RoeDisposition) => {
    if (!replay || !frame) return;
    setBusy(true);
    setPlaying(false);
    setNotice({ kind: "neutral", text: `Branching on ${request.requestId}: ${disposition}.` });
    try {
      const decision = branchDecision(request, disposition, OPERATOR_ID, frame.step);
      const summary = await api<RunSummary>(`/api/runs/${replay.summary.run_id}/branches`, {
        method: "POST",
        body: JSON.stringify({ decisions: [decision] }),
      });
      const childReplay = await api<Replay>(`/api/runs/${summary.run_id}/replay`);
      const decisionFrame = Math.min(decision.step, childReplay.frames.length - 1);
      setReplay(childReplay);
      setFrameIndex(decisionFrame);
      setNotice({
        kind: "success",
        text: `Child run ${summary.run_id.slice(0, 8)} · ${disposition} on ${request.trackId} at step ${decision.step}.`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };

  // A checkpoint only loads when scenario identity, version, and content hash all match.
  const scenarioTrainings = useMemo(() => trainings.filter((training) => record
    && training.scenario_id === record.scenario.scenario_id
    && training.scenario_version === record.scenario.version
    && training.scenario_hash === record.content_hash), [trainings, record]);
  const activeTraining = scenarioTrainings.find((training) => training.status === "running") ?? null;
  const checkpointsFor = useCallback(
    (bindingId: string) => scenarioTrainings.filter(
      (training) => training.status === "completed" && training.binding_ids.includes(bindingId),
    ),
    [scenarioTrainings],
  );
  const selectedAlgorithm = useMemo(
    () => trainingAlgorithms.find((algorithm) => algorithm.id === algorithmId) ?? null,
    [algorithmId, trainingAlgorithms],
  );

  const selectAlgorithm = (nextId: string) => {
    const algorithm = trainingAlgorithms.find((item) => item.id === nextId);
    if (!algorithm) return;
    setAlgorithmId(algorithm.id);
    setAlgorithmParameters(defaultAlgorithmParameters(algorithm));
  };

  const startTraining = async () => {
    if (!record) return;
    if (!trainingBindings.length) {
      setNotice({ kind: "error", text: "Select at least one trainable binding." });
      return;
    }
    try {
      const status = await api<TrainingStatus>("/api/trainings", {
        method: "POST",
        body: JSON.stringify({
          scenario_id: record.scenario.scenario_id,
          scenario_version: record.scenario.version,
          config: {
            binding_ids: trainingBindings,
            algorithm_id: algorithmId,
            algorithm_parameters: algorithmParameters,
            iterations,
            batch_size: batchSize,
            learning_rate: learningRate,
            seed,
            device: trainDevice,
            disruptions: buildDisruptions(
              trainingCommsDisruption,
              trainingSensorDisruption,
              trainingEffectorDisruption,
            ),
          },
        }),
      });
      setTrainings((current) => [...current.filter((item) => item.training_id !== status.training_id), status]);
      setNotice({ kind: "neutral", text: `Training ${status.training_id.slice(0, 8)} started.` });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  };

  const cancelTraining = async () => {
    if (!activeTraining) return;
    try {
      await api<TrainingStatus>(`/api/trainings/${activeTraining.training_id}/cancel`, { method: "POST" });
      await loadTrainings();
      setNotice({ kind: "neutral", text: `Training ${activeTraining.training_id.slice(0, 8)} cancelled.` });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  };

  const scenario = replay?.scenario ?? record?.scenario ?? null;
  const metrics = replay?.summary.metrics;
  const activeTruth = frame?.truth.filter((entity) => entity.active).length ?? 0;
  const events = frame ? frame.events.intercepts.length + frame.events.attacks.length : 0;
  const onFps = useCallback((value: number) => setFps(value), []);
  const truthIds = frame?.truth.map((entity) => entity.id) ?? [];
  const selectedIndex = selectedEntityId ? truthIds.indexOf(selectedEntityId) : -1;
  const selectAdjacent = (offset: number) => {
    if (!truthIds.length) return;
    const current = selectedIndex < 0 ? 0 : selectedIndex;
    setSelectedEntityId(truthIds[(current + offset + truthIds.length) % truthIds.length]);
  };
  const focusRequest = useMemo(
    () => selectedEntityId ? { id: selectedEntityId, nonce: focusNonce } : null,
    [focusNonce, selectedEntityId],
  );
  const queue = useMemo(() => decisionQueue(frame), [frame]);
  const pending = pendingCount(frame);
  const eventMarks = useMemo(() => {
    if (!replay || replay.frames.length < 2) return [];
    return replay.frames.flatMap((item, index) => [
      ...item.events.intercepts.map((_event, eventIndex) => ({
        key: `i:${index}:${eventIndex}`,
        left: `${(index / (replay.frames.length - 1)) * 100}%`,
        kind: "intercept",
      })),
      ...item.events.attacks.map((event, eventIndex) => ({
        key: `a:${index}:${eventIndex}`,
        left: `${(index / (replay.frames.length - 1)) * 100}%`,
        kind: event.succeeded ? "attack" : "attempt",
      })),
      ...(item.decisions ?? [])
        .filter((request) => request.decisionStep === item.step)
        .map((request) => ({
          key: `d:${index}:${request.requestId}`,
          left: `${(index / (replay.frames.length - 1)) * 100}%`,
          kind: "decision",
        })),
    ]);
  }, [replay]);

  const togglePlayback = () => {
    if (!replay) return;
    if (playing) setPlaying(false);
    else {
      setFrameIndex((value) => playbackStartFrame(value, replay.frames.length - 1));
      setPlaying(true);
    }
  };

  return (
    <div className="arena-shell" data-role={role}>
      <header className="system-strip">
        <div className="wordmark">
          <span className="wordmark-mark">P</span>
          <div><strong>PYTHO ARENA</strong><span>COUNTER-UAS MISSION LAB</span></div>
        </div>
        <div className="system-readouts">
          <span><i className={`status-lamp ${health ? "is-live" : ""}`} />{health ? "SYSTEM READY" : "CONNECTING"}</span>
          <span>ENGINE {health?.version ?? "—"}</span>
          <span>{health?.defaultDevice.toUpperCase() ?? "—"}</span>
          <span>{fps ? `${fps.toFixed(0)} FPS` : "FPS —"}</span>
        </div>
        <div className="role-switch" role="group" aria-label="Replay visibility">
          <button className={role === "operator" ? "is-active" : ""} aria-pressed={role === "operator"} onClick={() => setRole("operator")}>OPERATOR</button>
          <button className={role === "analyst" ? "is-active" : ""} aria-pressed={role === "analyst"} onClick={() => setRole("analyst")}>ANALYST TRUTH</button>
        </div>
      </header>

      <main className="mission-layout">
        <aside className="mission-rail" aria-label="Mission controls">
          <div className="rail-heading"><span>MISSION</span><strong>CONFIGURATION</strong></div>
          <label className="field-label" htmlFor="scenario-select">Scenario</label>
          <select
            id="scenario-select"
            value={record?.scenario.scenario_id ?? ""}
            onChange={(event) => loadScenario(event.target.value)}
            disabled={busy}
          >
            {scenarios.map((item) => <option value={item.scenarioId} key={`${item.scenarioId}:${item.version}`}>{item.name}</option>)}
          </select>
          <div className="scenario-title">
            <strong>{record?.scenario.name ?? "Loading"}</strong>
            <span>{record ? `V${record.scenario.version} · ${record.content_hash.slice(0, 8)}` : "—"}</span>
            <p>{record?.scenario.description}</p>
          </div>

          <section className="document-tools" aria-label="Scenario document tools">
            <div className="document-actions">
              <label className={busy ? "is-disabled" : ""}>
                IMPORT DOCX
                <input
                  type="file"
                  accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  disabled={busy}
                  onChange={(event) => {
                    void importDocument(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
              <a
                className={!record ? "is-disabled" : ""}
                aria-disabled={!record}
                href={record ? `/api/scenarios/${record.scenario.scenario_id}/background-document?version=${record.scenario.version}` : undefined}
              >
                EXPORT BRIEF
              </a>
            </div>
            {importReport && (
              <details className="import-report">
                <summary>IMPORT REVIEW · {importReport.source_sha256.slice(0, 8)}</summary>
                <div>
                  <strong>{importReport.source_filename}</strong>
                  <span>{importReport.matched_sections.length} sections</span>
                  <span>{importReport.sensor_modalities.length} sensor modalities</span>
                  <span>{importReport.asset_resolution.length} asset groups resolved</span>
                </div>
                <p>{importReport.safety_transformations[0]}</p>
                <p>{importReport.warnings[importReport.warnings.length - 1]}</p>
              </details>
            )}
          </section>

          <div className="roster" aria-label="Scenario force roster">
            {record?.scenario.actor_groups.map((group) => (
              <div key={group.id}>
                <span>{group.id.replaceAll("-", " ")}</span>
                <strong>{String(group.count).padStart(2, "0")}</strong>
              </div>
            ))}
          </div>

          <section className="rail-section">
            <div className="section-label"><span>POLICY BINDINGS</span><i>{record?.scenario.policy_bindings.length ?? 0}</i></div>
            <div className="policy-list">
              {record?.scenario.policy_bindings.map((binding) => (
                <label key={binding.id}>
                  <span>{bindingLabel(binding)}<small>{binding.trainable ? "TRAINABLE" : "FIXED"}</small></span>
                  <select
                    aria-label={`${bindingLabel(binding)} policy`}
                    value={overrides[binding.id] ?? binding.policy_id}
                    onChange={(event) => setOverrides((value) => ({ ...value, [binding.id]: event.target.value }))}
                  >
                    {[...new Set([binding.policy_id, ...(POLICY_OPTIONS[binding.role] ?? [])])].map((policy) => (
                      <option value={policy} key={policy}>{policy}</option>
                    ))}
                    {checkpointsFor(binding.id).map((training) => (
                      <option value={`checkpoint:${training.training_id}`} key={training.training_id}>
                        checkpoint {training.training_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          </section>

          <div className="run-fields">
            <label><span>SEED</span><input type="number" min="0" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
            <label><span>DEVICE</span><select value={device} onChange={(event) => setDevice(event.target.value)}>
              <option value="cpu">CPU</option><option value="auto">AUTO</option><option value="mps">MPS</option><option value="cuda">CUDA</option>
            </select></label>
          </div>
          <div className="disruption-control" role="group" aria-label="Degraded conditions">
            <span><b>DEGRADED CONDITIONS</b></span>
            <label>
              <span>COMMS<output>{communicationDisruption}%</output></span>
              <input
                aria-label="Communications disruption percentage"
                type="range"
                min="0"
                max="100"
                step="5"
                value={communicationDisruption}
                disabled={busy}
                onChange={(event) => setCommunicationDisruption(Number(event.target.value))}
              />
            </label>
            <label>
              <span>SENSORS<output>{sensorDisruption}%</output></span>
              <input
                aria-label="Sensor disruption percentage"
                type="range"
                min="0"
                max="100"
                step="5"
                value={sensorDisruption}
                disabled={busy}
                onChange={(event) => setSensorDisruption(Number(event.target.value))}
              />
            </label>
            <label>
              <span>EFFECTORS<output>{effectorDisruption}%</output></span>
              <input
                aria-label="Effector disruption percentage"
                type="range"
                min="0"
                max="100"
                step="5"
                value={effectorDisruption}
                disabled={busy}
                onChange={(event) => setEffectorDisruption(Number(event.target.value))}
              />
            </label>
            <small>Degrades the defending network: report delivery, sensor detection, response effectiveness</small>
          </div>
          <button className="run-command" onClick={run} disabled={!record || busy}>{busy ? "WORKING" : "RUN SCENARIO"}</button>
          <div className={`notice notice--${notice.kind}`} role="status">{notice.text}</div>

          <section className="rail-section training-panel">
            <div className="section-label">
              <span>RL TRAINING</span>
              <i>{activeTraining
                ? `${activeTraining.config.algorithm_id.toUpperCase()} ${activeTraining.iterations_done}/${activeTraining.config.iterations}`
                : "IDLE"}</i>
            </div>
            <label className="training-algorithm">
              <span>ALGORITHM</span>
              <select
                aria-label="Training algorithm"
                value={algorithmId}
                disabled={Boolean(activeTraining)}
                onChange={(event) => selectAlgorithm(event.target.value)}
              >
                {trainingAlgorithms.map((algorithm) => (
                  <option value={algorithm.id} key={algorithm.id}>{algorithm.name}</option>
                ))}
              </select>
            </label>
            {selectedAlgorithm && (
              <div className="training-algorithm-summary">
                <span>{selectedAlgorithm.family.toUpperCase()} · {selectedAlgorithm.on_policy ? "ON-POLICY" : "OFF-POLICY"}</span>
                <p>{selectedAlgorithm.description}</p>
              </div>
            )}
            <div className="training-bindings">
              {record?.scenario.policy_bindings.filter((binding) => binding.trainable).map((binding) => (
                <label key={binding.id}>
                  <input
                    type="checkbox"
                    checked={trainingBindings.includes(binding.id)}
                    disabled={Boolean(activeTraining)}
                    onChange={(event) => setTrainingBindings((current) => event.target.checked
                      ? [...current, binding.id]
                      : current.filter((id) => id !== binding.id))}
                  />
                  <span>{bindingLabel(binding)}</span>
                </label>
              ))}
              {!record?.scenario.policy_bindings.some((binding) => binding.trainable)
                && <p className="locked-copy">This scenario declares no trainable bindings.</p>}
            </div>
            <div className="training-fields">
              <label><span>ITERATIONS</span><input type="number" min="1" max="5000" value={iterations} onChange={(event) => setIterations(Number(event.target.value))} /></label>
              <label><span>BATCH</span><input type="number" min="1" max="4096" value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} /></label>
              <label><span>LEARNING RATE</span><input type="number" min="0.00001" max="1" step="0.0005" value={learningRate} onChange={(event) => setLearningRate(Number(event.target.value))} /></label>
              <label><span>TRAIN DEVICE</span><select value={trainDevice} onChange={(event) => setTrainDevice(event.target.value as typeof trainDevice)}>
                <option value="auto">AUTO</option><option value="cpu">CPU</option><option value="cuda">CUDA</option><option value="mps">MPS</option>
              </select></label>
              <label title="Fraction of defending-network sensor reports dropped during training rollouts">
                <span>COMMS DISRUPTION {trainingCommsDisruption}%</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={trainingCommsDisruption}
                  disabled={Boolean(activeTraining)}
                  onChange={(event) => setTrainingCommsDisruption(Number(event.target.value))}
                />
              </label>
              <label title="Sensor detection-probability degradation during training rollouts">
                <span>SENSOR DISRUPTION {trainingSensorDisruption}%</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={trainingSensorDisruption}
                  disabled={Boolean(activeTraining)}
                  onChange={(event) => setTrainingSensorDisruption(Number(event.target.value))}
                />
              </label>
              <label title="Response effectiveness degradation during training rollouts">
                <span>EFFECTOR DISRUPTION {trainingEffectorDisruption}%</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={trainingEffectorDisruption}
                  disabled={Boolean(activeTraining)}
                  onChange={(event) => setTrainingEffectorDisruption(Number(event.target.value))}
                />
              </label>
            </div>
            {selectedAlgorithm && selectedAlgorithm.parameters.length > 0 && (
              <div className="training-fields training-parameters">
                {selectedAlgorithm.parameters.map((parameter) => (
                  <label key={parameter.id} title={parameter.description}>
                    <span>{parameter.label.toUpperCase()}</span>
                    {parameter.kind === "boolean" ? (
                      <select
                        value={String(algorithmParameters[parameter.id] ?? parameter.default)}
                        disabled={Boolean(activeTraining)}
                        onChange={(event) => setAlgorithmParameters((current) => ({
                          ...current,
                          [parameter.id]: event.target.value === "true",
                        }))}
                      >
                        <option value="true">ENABLED</option>
                        <option value="false">DISABLED</option>
                      </select>
                    ) : (
                      <input
                        type="number"
                        min={parameter.minimum ?? undefined}
                        max={parameter.maximum ?? undefined}
                        step={parameter.step ?? (parameter.kind === "integer" ? 1 : "any")}
                        value={Number(algorithmParameters[parameter.id] ?? parameter.default)}
                        disabled={Boolean(activeTraining)}
                        onChange={(event) => setAlgorithmParameters((current) => ({
                          ...current,
                          [parameter.id]: parameter.kind === "integer"
                            ? Number.parseInt(event.target.value, 10)
                            : Number(event.target.value),
                        }))}
                      />
                    )}
                  </label>
                ))}
              </div>
            )}
            <div className="training-actions">
              <button onClick={cancelTraining} disabled={!activeTraining}>CANCEL</button>
              <button onClick={startTraining} disabled={!record || Boolean(activeTraining) || !trainingBindings.length}>
                {activeTraining ? "TRAINING" : "START TRAINING"}
              </button>
            </div>
            {scenarioTrainings.length > 0 && (
              <div className="training-history">
                {[...scenarioTrainings].reverse().slice(0, 6).map((training) => (
                  <a href={`/trainings/${training.training_id}`} key={training.training_id} target="_blank" rel="noreferrer">
                    <code>{training.training_id.slice(0, 8)}</code>
                    <span>{training.config.algorithm_id.toUpperCase()} · {training.binding_ids.length} binding{training.binding_ids.length === 1 ? "" : "s"}</span>
                    <i className={`training-state training-state--${training.status}`}>
                      {training.status} {training.iterations_done}/{training.config.iterations} ↗
                    </i>
                  </a>
                ))}
              </div>
            )}
          </section>

          <details className="scenario-source">
            <summary>SCENARIO SOURCE</summary>
            <textarea aria-label="Versioned scenario JSON" spellCheck={false} value={editor} onChange={(event) => setEditor(event.target.value)} />
            <div><button onClick={validate} disabled={busy}>VALIDATE</button><button onClick={save} disabled={busy}>SAVE NEW VERSION</button></div>
          </details>
        </aside>

        <section className="mission-stage">
          <ArenaViewport
            sceneState={sceneResult.state}
            scenario={scenario}
            role={role}
            onFps={onFps}
            selectedEntityId={selectedEntityId}
            focusRequest={focusRequest}
          />
          <div className="stage-heading">
            <span>LIVE REPLAY / {role.toUpperCase()}</span>
            <strong>{scenario?.name ?? "Awaiting mission"}</strong>
          </div>
          <div className="north-index" aria-hidden="true"><span>N</span><i /></div>
          <SensorScope scene={sceneResult.state} role={role} scenario={scenario} />
          {!replay && <div className="empty-command"><span>NO RUN LOADED</span><strong>Run the scenario to generate replay evidence.</strong></div>}
          {sceneResult.error && <div className="scene-error">3D VIEW UNAVAILABLE · {sceneResult.error}</div>}
          <div className="viewport-key">
            {scenario?.factions.map((faction) => (
              <span key={faction.id}><i style={{ background: faction.color }} />{faction.name.toUpperCase()}</span>
            ))}
            <span><i className="key-detection" />RAW DETECTION</span>
          </div>
        </section>

        <aside className="inspector" aria-label="Replay inspector">
          <div className="rail-heading"><span>RUN EVIDENCE</span><strong>{role === "operator" ? "SENSOR VIEW" : "ANALYST VIEW"}</strong></div>
          <section className="clock-block">
            <span>MISSION TIME</span>
            <strong>T+{Math.round(frame?.time ?? 0).toString().padStart(3, "0")}<small>S</small></strong>
            <div><span>STEP {frame?.step ?? 0}</span><span>{playing ? "PLAYING" : "HOLD"}</span></div>
          </section>

          <section className="inspector-section">
            <div className="section-label"><span>CURRENT FRAME</span><i>{events ? "EVENT" : "NOMINAL"}</i></div>
            <dl className="metric-table">
              <AppMetric label="Raw detections" value={frame?.detections.length ?? 0} />
              <AppMetric label="Fused tracks" value={frame?.tracks?.length ?? 0} />
              <AppMetric label="Defense events" value={frame?.events.intercepts.length ?? 0} />
              <AppMetric label="Attack events" value={frame?.events.attacks.length ?? 0} />
              <AppMetric label="Active truth" value={role === "analyst" ? activeTruth : "LOCKED"} />
            </dl>
          </section>

          {queue.length > 0 && (
            <section className="inspector-section authority-queue">
              <div className="section-label"><span>AUTHORITY QUEUE</span><i>{pending} PENDING</i></div>
              {queue.map((request) => (
                <div className={`authority-row authority-row--${request.classification}`} key={request.requestId}>
                  <div className="authority-head">
                    <strong>{request.trackId}</strong>
                    <span>{request.classification.toUpperCase()}</span>
                    <em>{request.disposition ? request.disposition.toUpperCase() : "PENDING"}</em>
                  </div>
                  <p className="authority-why">{request.rationale}</p>
                  <div className="authority-meta">
                    <span>{request.effectorId}</span>
                    <span>OPENED T+{request.timeSeconds}S · STEP {request.step}</span>
                  </div>
                  {request.pending ? (
                    <div className="authority-actions">
                      {DISPOSITIONS.map((disposition) => (
                        <button
                          key={disposition}
                          className={`authority-action authority-action--${disposition}`}
                          disabled={busy || !frame || frame.step < request.step}
                          onClick={() => decide(request, disposition)}
                        >
                          {disposition.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="authority-meta">
                      <span>{request.decisionId}</span>
                      <span>DECIDED AT STEP {request.decisionStep}</span>
                    </div>
                  )}
                </div>
              ))}
              <p className="authority-note">
                A decision starts an immutable child run from this frame. The run on screen is never changed.
              </p>
            </section>
          )}

          {role === "analyst" && truthIds.length > 0 && (
            <section className="inspector-section entity-focus">
              <div className="section-label"><span>ENTITY FOCUS</span><i>{selectedIndex + 1}/{truthIds.length}</i></div>
              <select value={selectedEntityId ?? ""} onChange={(event) => setSelectedEntityId(event.target.value)} aria-label="Analyst truth entity">
                {truthIds.map((id) => <option value={id} key={id}>{id}</option>)}
              </select>
              <div>
                <button onClick={() => selectAdjacent(-1)} aria-label="Previous entity">PREV</button>
                <button onClick={() => setFocusNonce((value) => value + 1)}>FOCUS</button>
                <button onClick={() => selectAdjacent(1)} aria-label="Next entity">NEXT</button>
              </div>
            </section>
          )}

          <section className="inspector-section">
            <div className="section-label"><span>RUN METRICS</span><i>{role === "analyst" ? "TRUTH" : "WITHHELD"}</i></div>
            {role === "analyst" && metrics ? (
              <dl className="metric-table metric-table--large">
                <AppMetric label="Detection rate" value={percent(metrics.detection_rate)} />
                <AppMetric label="Defense rate" value={percent(metrics.defense_rate)} />
                <AppMetric label="Ever detected" value={`${metrics.ever_detected}/${metrics.opponent_entities}`} />
                <AppMetric label="Intercepted" value={metrics.defense_intercepts} />
                <AppMetric label="Attack success" value={`${metrics.attack_successes}/${metrics.attack_attempts}`} />
                <AppMetric label="Attack attempts" value={metrics.attack_attempts} />
                <AppMetric label="Background active" value={`${metrics.background_active_at_end}/${metrics.background_entities}`} />
                <AppMetric label="Protected intercepts" value={metrics.protected_intercepts} />
              </dl>
            ) : <p className="locked-copy">Switch to Analyst Truth to inspect scored outcomes and undetected entities.</p>}
          </section>

          {role === "analyst" && metrics?.counter_uas && (
            <section className="inspector-section">
              <div className="section-label"><span>DECISION SCORECARD</span><i>TRUTH</i></div>
              <dl className="metric-table metric-table--large">
                <AppMetric label="Requests opened" value={metrics.counter_uas.requests_opened} />
                <AppMetric label="Decisions recorded" value={metrics.counter_uas.decisions_recorded} />
                <AppMetric label="Effects activated" value={`${metrics.counter_uas.effects_activated}/${metrics.counter_uas.effects_attempted}`} />
                <AppMetric label="Effects defeated" value={metrics.counter_uas.effects_defeated} />
                <AppMetric label="Authority violations" value={metrics.counter_uas.authority_violations} />
                <AppMetric label="Protected traffic effects" value={metrics.counter_uas.protected_traffic_effects} />
                <AppMetric label="First detection" value={metrics.counter_uas.first_detection_seconds === null ? "—" : `T+${metrics.counter_uas.first_detection_seconds}s`} />
                <AppMetric label="First hostile call" value={metrics.counter_uas.first_hostile_classification_seconds === null ? "—" : `T+${metrics.counter_uas.first_hostile_classification_seconds}s`} />
                <AppMetric label="Decision latency" value={metrics.counter_uas.mean_decision_latency_seconds === null ? "—" : `${metrics.counter_uas.mean_decision_latency_seconds}s`} />
                <AppMetric label="Hostile calls right/wrong" value={`${metrics.counter_uas.hostile_classifications_correct}/${metrics.counter_uas.hostile_classifications_incorrect}`} />
                <AppMetric label="Peak queue depth" value={metrics.counter_uas.peak_pending_requests} />
                <AppMetric label="Open at end" value={metrics.counter_uas.pending_requests_at_end} />
              </dl>
            </section>
          )}

          {role === "analyst" && replay && (
            <section className="inspector-section outcomes">
              <div className="section-label"><span>FACTION OUTCOMES</span><i>{Object.keys(metrics?.factions ?? {}).length}</i></div>
              {replay.scenario.factions.map((faction) => {
                const result = metrics?.factions[faction.id];
                if (!result) return null;
                return (
                  <div className="outcome-line" key={faction.id} style={{ "--faction": faction.color } as React.CSSProperties}>
                    <strong>{faction.name}</strong>
                    <span>{result.active_at_end}/{result.entities} ACTIVE</span>
                    <span>{result.ever_detected} DET · {result.intercepted} INT</span>
                    <span>{result.attack_successes}/{result.attack_attempts} ATK</span>
                  </div>
                );
              })}
            </section>
          )}

          <section className="run-identity">
            <span>RUN ID</span><code>{replay?.summary.run_id ?? "not assigned"}</code>
            <span>PARENT RUN</span><code>{replay?.summary.parent_run_id ?? "none · this is a baseline run"}</code>
            <span>SCENARIO HASH</span><code>{replay?.summary.scenario_hash.slice(0, 18) ?? "—"}</code>
            <span>RUN CONFIG</span><code>{replay ? `seed ${replay.summary.seed} · ${replay.summary.device} · ${replay.summary.steps} steps · degraded: ${disruptionLabel(replay.summary)} · v${replay.summary.scenario_version}` : "—"}</code>
            <span>POLICIES</span><code>{replay ? Object.entries(replay.summary.policies).map(([id, policy]) => `${id}:${policy}`).join(" · ") : "—"}</code>
            <span>ANALYST/NATIVE EXPORT</span><code>127.0.0.1:46000 · {nativeStatus}{nativeError ? ` · ${nativeError}` : ""}</code>
          </section>
        </aside>
      </main>

      <footer className="replay-strip">
        <button className="play-control" onClick={togglePlayback} disabled={!replay} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "Ⅱ" : "▶"}</button>
        <div className="timeline-label"><span>REPLAY</span><strong>{frameIndex.toString().padStart(3, "0")} / {Math.max(0, (replay?.frames.length ?? 1) - 1).toString().padStart(3, "0")}</strong></div>
        <div className="timeline-wrap">
          <input
            className="timeline"
            aria-label="Replay frame"
            type="range"
            min="0"
            max={Math.max(0, (replay?.frames.length ?? 1) - 1)}
            value={frameIndex}
            disabled={!replay}
            onChange={(event) => { setPlaying(false); setFrameIndex(Number(event.target.value)); }}
          />
          <div className="timeline-events" aria-hidden="true">
            {eventMarks.map((mark) => <i className={`event-mark event-mark--${mark.kind}`} style={{ left: mark.left }} key={mark.key} />)}
          </div>
        </div>
        <select aria-label="Replay speed" value={speedMs} onChange={(event) => setSpeedMs(Number(event.target.value))}>
          <option value="500">0.5×</option><option value="250">1×</option><option value="100">2.5×</option><option value="50">5×</option>
        </select>
        <span className="key-help">SPACE PLAY · ← → STEP · DRAG TO SCRUB</span>
      </footer>
    </div>
  );
}
