# ADR 0001: Arena consumes COA authority through generated contracts

Status: accepted (fixed by `docs/CLAUDE_COA_ENGINE_OVERHAUL_PROMPT.md`, 2026-08-18)

## Context
Arena currently owns its own authoritative episode loop (`core/env.py`) and serves replay directly.
The overhaul moves authority to COA (see `coa-engine/docs/adr/0001-authority-boundary.md` and
`0002-contract-location.md`).

## Decision
Arena becomes presentation, authoring, and trainer/EXCON intent only. It consumes COA's versioned
contracts via `scripts/sync-coa-contracts.sh` (`COA_ENGINE_DIR`, default `../coa-engine`):
generated Python gRPC stubs for the Arena edge and generated TypeScript codecs for the binary
role-filtered WebSocket stream. Browsers and native clients connect only to the authenticated
Arena edge; the edge opens the backend stream to loopback-only COA. Entity IDs are `bigint` or
canonical unsigned-decimal strings in TS/JSON/DOM, never `number`. `frame-v1` remains a
compatibility adapter for the current Three.js and Dagor clients until the new stream passes
parity tests. Arena prediction/interpolation never changes COA state or evidence.

## Consequences
Arena's local episode execution survives only behind adapters during migration; the committed
`server/frontend/` bundle is rebuilt whenever `frontend-src/` changes, per repo constraints.
