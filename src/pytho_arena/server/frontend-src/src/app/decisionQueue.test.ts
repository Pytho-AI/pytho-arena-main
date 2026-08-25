import { describe, expect, it } from "vitest";

import type { ArenaDecisionRequest, ArenaReplayFrame } from "../arena";
import { branchDecision, decisionQueue, pendingCount } from "./decisionQueue";

const request = (overrides: Partial<ArenaDecisionRequest> = {}): ArenaDecisionRequest => ({
  requestId: "roe-001",
  trackId: "track-001",
  effectorId: "blue-response",
  rationale: "track-001 closed on blue-response for 2 consecutive updates",
  step: 4,
  timeSeconds: 4,
  classification: "hostile",
  disposition: null,
  decisionId: null,
  decisionStep: null,
  pending: true,
  ...overrides,
});

const frame = (decisions: ArenaDecisionRequest[]): ArenaReplayFrame => ({
  step: 5,
  time: 5,
  truth: [],
  detections: [],
  sensors: [],
  responses: [],
  events: { intercepts: [], attacks: [] },
  decisions,
});

describe("decision queue", () => {
  it("puts open requests ahead of decided ones and keeps the oldest first", () => {
    const queue = decisionQueue(
      frame([
        request({ requestId: "roe-003", step: 6 }),
        request({ requestId: "roe-002", step: 5, pending: false, disposition: "deny" }),
        request({ requestId: "roe-001", step: 4 }),
      ]),
    );

    expect(queue.map((row) => row.requestId)).toEqual(["roe-001", "roe-003", "roe-002"]);
    expect(pendingCount(frame(queue))).toBe(2);
  });

  it("treats a replay frame with no counter-UAS data as an empty queue", () => {
    expect(decisionQueue(null)).toEqual([]);
    expect(decisionQueue(frame([]))).toEqual([]);
    expect(pendingCount(null)).toBe(0);
  });

  it("schedules a decision at the frame the operator is looking at", () => {
    expect(branchDecision(request(), "authorize", "operator-alvarez", 5)).toEqual({
      request_id: "roe-001",
      disposition: "authorize",
      operator_id: "operator-alvarez",
      rationale: "Operator authorize on track-001 at step 5",
      step: 5,
    });
  });

  it("refuses a decision that is already terminal or predates its request", () => {
    expect(() =>
      branchDecision(request({ pending: false, disposition: "authorize" }), "deny", "op", 5),
    ).toThrow(/already has a terminal disposition/);
    expect(() => branchDecision(request({ step: 6 }), "deny", "op", 5)).toThrow(/would predate/);
  });
});
