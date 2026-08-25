import type { ArenaDecisionRequest, ArenaReplayFrame, RoeDisposition } from "../arena";

/** One decision as the branch endpoint expects it. */
export interface BranchDecision {
  request_id: string;
  disposition: RoeDisposition;
  operator_id: string;
  rationale: string;
  step: number;
}

export const DISPOSITIONS: readonly RoeDisposition[] = ["hold", "deny", "authorize"];

/**
 * Authority requests for one frame: still-open requests first, then oldest, so
 * the operator reads the queue top-down without sorting it themselves.
 */
export function decisionQueue(frame: ArenaReplayFrame | null): ArenaDecisionRequest[] {
  return [...(frame?.decisions ?? [])].sort((left, right) => {
    if (left.pending !== right.pending) return left.pending ? -1 : 1;
    if (left.step !== right.step) return left.step - right.step;
    return left.requestId < right.requestId ? -1 : left.requestId > right.requestId ? 1 : 0;
  });
}

export function pendingCount(frame: ArenaReplayFrame | null): number {
  return (frame?.decisions ?? []).filter((request) => request.pending).length;
}

/**
 * A decision is recorded at the step the operator is looking at. Every request
 * on that frame was already open, so the child run can replay the decision
 * there and still reproduce every earlier frame exactly.
 */
export function branchDecision(
  request: ArenaDecisionRequest,
  disposition: RoeDisposition,
  operatorId: string,
  step: number,
): BranchDecision {
  if (!request.pending) {
    throw new Error(`request ${request.requestId} already has a terminal disposition`);
  }
  if (step < request.step) {
    throw new Error(
      `a decision at step ${step} would predate request ${request.requestId} (step ${request.step})`,
    );
  }
  return {
    request_id: request.requestId,
    disposition,
    operator_id: operatorId,
    rationale: `Operator ${disposition} on ${request.trackId} at step ${step}`,
    step,
  };
}
