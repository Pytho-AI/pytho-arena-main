import type { ArenaReplayFrame, Point2 } from "../arena";

export type Role = "operator" | "analyst";

export interface Faction {
  id: string;
  name: string;
  category: "strategic" | "background";
  color: string;
  objectives: string[];
}

export interface PolicyBinding {
  id: string;
  faction_id: string;
  role: "movement" | "sensing";
  policy_id: string;
  trainable: boolean;
  /** Optional display label; the UI falls back to `id` when absent. */
  name?: string;
  implementation?: string;
}

/** One run-level ability degradation. `faction_ids: null` targets the defending network. */
export interface CommunicationsDisruption {
  kind: "communications";
  drop_probability: number;
  faction_ids?: string[] | null;
}

export interface SensorDisruption {
  kind: "sensor";
  detection_probability_multiplier?: number;
  range_multiplier?: number;
  noise_multiplier?: number;
  faction_ids?: string[] | null;
}

export interface EffectorDisruption {
  kind: "effector";
  effectiveness_multiplier?: number;
  reliability?: number;
  faction_ids?: string[] | null;
}

export type DisruptionSpec = CommunicationsDisruption | SensorDisruption | EffectorDisruption;

export interface TrainingConfig {
  binding_ids: string[] | null;
  algorithm_id: string;
  algorithm_parameters: Record<string, boolean | number | string>;
  iterations: number;
  batch_size: number;
  learning_rate: number;
  seed: number;
  device: "auto" | "cpu" | "cuda" | "mps";
  /** Typed ability degradations applied to every training rollout. */
  disruptions?: DisruptionSpec[];
}

export interface TrainingAlgorithmParameter {
  id: string;
  label: string;
  description: string;
  kind: "number" | "integer" | "boolean";
  default: boolean | number | string;
  minimum: number | null;
  maximum: number | null;
  step: number | null;
}

export interface TrainingAlgorithm {
  id: string;
  name: string;
  family: string;
  description: string;
  on_policy: boolean;
  supports_multi_agent: boolean;
  supports_continuous_actions: boolean;
  supports_discrete_actions: boolean;
  supports_recurrent: boolean;
  supports_centralized_critic: boolean;
  loss_description: string;
  parameters: TrainingAlgorithmParameter[];
}

export interface TrainingAlgorithmsResponse {
  defaultAlgorithmId: string;
  algorithms: TrainingAlgorithm[];
}

export type TrainingState = "running" | "completed" | "failed" | "cancelled";

export interface TrainingStatus {
  training_id: string;
  scenario_id: string;
  scenario_version: number;
  scenario_hash: string;
  binding_ids: string[];
  status: TrainingState;
  config: TrainingConfig;
  device: string | null;
  iterations_done: number;
  history: Array<Record<string, unknown>>;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export type ScenarioEnvironment = "gulf_airbase" | "coastal_urban";

export type ScenarioStaticAssetKind =
  | "warehouse"
  | "mixed_block"
  | "office_block"
  | "storage_tank"
  | "marina_pier"
  | "cargo_stack"
  | "utility_tower"
  | "fence_segment"
  | "gatehouse"
  | "sensor_tower"
  | "response_vehicle"
  | "patrol_boat";

export interface ScenarioStaticAssetPlacement {
  id: string;
  kind: ScenarioStaticAssetKind;
  /** Scene-local ENU meters: [east, north]. */
  position: Point2;
  heading_degrees?: number;
  scale?: number;
}

export interface ScenarioVisualization {
  environment: ScenarioEnvironment;
  static_assets?: ScenarioStaticAssetPlacement[];
}

export interface Scenario {
  scenario_id: string;
  version: number;
  name: string;
  description: string;
  seed: number;
  duration_seconds: number;
  step_seconds: number;
  world: {
    width: number;
    height: number;
    vertical_extent: number;
    meters_per_unit?: number;
  };
  factions: Faction[];
  actor_groups: Array<{
    id: string;
    faction_id: string;
    count: number;
    mission: string;
  }>;
  sensors: Array<{ id: string }>;
  responses: Array<{ id: string }>;
  protected_zones: Array<{ id: string; center: Point2; radius: number }>;
  policy_bindings: PolicyBinding[];
  visualization?: ScenarioVisualization;
  [key: string]: unknown;
}

export interface ScenarioRecord {
  scenario: Scenario;
  content_hash: string;
  created_at: string;
}

export interface ScenarioListItem {
  scenarioId: string;
  version: number;
  name: string;
  contentHash: string;
  createdAt: string;
}

export interface RunMetrics {
  detection_rate: number;
  defense_rate: number;
  ever_detected: number;
  opponent_entities: number;
  defense_intercepts: number;
  attack_attempts: number;
  attack_successes: number;
  background_active_at_end: number;
  background_entities: number;
  protected_intercepts: number;
  factions: Record<
    string,
    {
      entities: number;
      active_at_end: number;
      ever_detected: number;
      intercepted: number;
      attack_attempts: number;
      attack_successes: number;
    }
  >;
  /** Present only for runs of a scenario that declares a typed effector. */
  counter_uas?: CounterUasMetrics;
}

export interface CounterUasMetrics {
  tracks_held: number;
  requests_opened: number;
  decisions_recorded: number;
  pending_requests_at_end: number;
  peak_pending_requests: number;
  effects_attempted: number;
  effects_activated: number;
  effects_defeated: number;
  protected_traffic_effects: number;
  authority_violations: number;
  first_detection_seconds: number | null;
  first_hostile_classification_seconds: number | null;
  mean_decision_latency_seconds: number | null;
  hostile_classifications_correct: number;
  hostile_classifications_incorrect: number;
}

export interface BranchDecisionRecord {
  request_id: string;
  disposition: "hold" | "deny" | "authorize";
  operator_id: string;
  rationale: string;
  step: number;
}

export interface RunSummary {
  run_id: string;
  scenario_id: string;
  scenario_version: number;
  scenario_hash: string;
  seed: number;
  policies: Record<string, string>;
  device: string;
  /** Typed ability degradations this run executed under. */
  disruptions?: DisruptionSpec[];
  steps: number;
  metrics: RunMetrics;
  /** Absent on runs saved before decision branching existed. */
  parent_run_id?: string | null;
  branch_decisions?: BranchDecisionRecord[];
}

export interface Replay {
  summary: RunSummary;
  scenario: Scenario;
  frames: ArenaReplayFrame[];
}

export interface Health {
  status: string;
  version: string;
  torch: string;
  defaultDevice: string;
  cuda: boolean;
  mps: boolean;
}

export type Notice = { kind: "neutral" | "success" | "error"; text: string };
