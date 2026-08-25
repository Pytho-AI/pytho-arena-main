# ADR 0002: Renderer strategy — Three.js tactical/fallback, UE 5.8 high-fidelity client

Status: accepted (user amendment, 2026-08-18)

## Context
The required high-fidelity target is the perceptual quality of
`docs/evidence/20260818/proposal/06-notional-200-agent-airbase-swarm.png` (Image 6). Expanding
Three.js alone is not an accepted path to that target. COA Engine stays authoritative; RL stays
headless; Arena React remains the product frontend.

## Decision
- Three.js remains in Arena as the lightweight tactical/fallback renderer.
- A renderer-neutral **RenderProjection** boundary is the only input any renderer consumes:
  the role-filtered projection stream defined in
  `coa-engine/contracts/pytho/sim/v1/projection.proto` (ProjectionFrame et al.). Renderers get
  authorized entities/tracks/effects with velocities for interpolation; no renderer receives
  truth-side messages or holds authoritative simulation logic.
- An **Unreal Engine 5.8 presentation client** is the high-fidelity renderer. It consumes the same
  Arena-edge projection stream, interpolates 20 Hz state to 60 Hz, supports replay and trainer
  input, and contains no authoritative logic. Native execution first; browser embedding via Pixel
  Streaming is the planned delivery for the product UI.
- Unreal is NOT downloaded or built during the current backend goal. Before the 3D implementation
  phase (Phase 6) this repo must have: this ADR current, the contract seam verified against a real
  stream, render/asset manifests extended for UE-class assets (PBR material sets, LODs, provenance),
  and a named graphics hardware profile.
- A separate graphics vertical-slice goal owns the UE client, with measurable gates: 1440p at
  60 FPS, 200 simultaneous agents, the checked-in visual-quality rubric, asset provenance for every
  imported asset, and captures from the implemented renderer.
- Image-6 parity may only be claimed from a capture of the implemented renderer — never from
  concept art or Three.js screenshots.

## Consequences
The Dagor client remains an optional native path; the projection contract gains no
renderer-specific fields; Phase 6 in the current goal targets the Three.js tactical renderer's
gates, while Image-6-parity work moves to the graphics vertical-slice goal.
