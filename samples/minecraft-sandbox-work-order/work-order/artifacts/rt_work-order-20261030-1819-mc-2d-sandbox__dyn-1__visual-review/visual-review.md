---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__visual-review"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Independent visual review — M2D-SES v1.1

## Scope

Independent review of the rendered page and implementation before the result document. The review
read `goal.md`, `analysis.md`, `solution.md`, both implementation records and all three verification
artifacts, inspected the 960x600, day, night, paused and 1280x800 screenshots, and drove the real page
through the M2D-SES v1.1 journeys J1–J8. It is a read-only review: no product file was changed.

Method limitation recorded: no second agent is available in this environment, so this is a structured
adversarial pass by the work-order owner in a separate review role, not a different reviewer. The
M2D-SES v1.1 standard and the 2D profile were read only at this review stage, after implementation and
verification; they were not used as implementation input. The one-shot baseline and prior sample
results were not read, preserving the run's isolation.

## Evidence

### Journey log

| Journey | Probe | Observed |
| --- | --- | --- |
| J1 First launch/controls | `file://` load, status, hint line, console | ready marker green at distance 0, controls hint complete, no console error or exception in the probe report |
| J2 Movement/collision | held A/D at both edges, jump/land physics tests | movement works, camera clamps, player stays inside; physics suite proves walls, ceilings and no tunnelling |
| J3 Mine/place/hotbar | real mouse press/hold, journey checks | target readout, particles, toast, sound and counts work; **block breaks instantly on mousedown with no hold/progress state** (holding 70 ms already removed it) |
| J4 Underground/world floor | review probe: dug a 23-row shaft at x=5, teleported down, inspected background, mined the floor | underground background reads dark, not sky; **rows 62–63 are ordinary stone and were mined away; the player stood at y=64 with no floor** (`j4-floor-gone.png`) |
| J5 Persistence/recovery | reload, corrupt-save injection, storage failure | edit → reload restores blocks/counts/position; corrupt save recovers with a notice; storage failure path covered by tests |
| J6 Window/motion/audio/pause | 960x600, 800x600, 1280x800; emulated reduced motion; mute toggle; pause | no overflow at any size; 18/3/1 stat visibility at narrow widths; reduced-motion CSS applies; mute persists; pause overlay covers and freezes |
| J7 Time/atmosphere | day/night screenshots and clock | sky changes from bright day to star/moon night; foreground stays readable; HUD clock changes |
| J8 Free discovery | underground trip, building, palette | immediate break is satisfying but reads as instant, the palette covers the centre of the bottom row when standing on the floor, and there is no spatial aid beyond coordinates |

### Defect ledger

| ID | Severity | Confidence | Evidence | Impact | Closure |
| --- | --- | --- | --- | --- | --- |
| D1 | **High** | high | Review probe J4: `mine(5,62)` and `mine(5,63)` returned ok; screenshot `j4-floor-gone.png` shows the player at y=64 over a removed floor | The world is not sealed: the bottom can be mined away, so world integrity is broken and the player can stand outside the last row | Make the bottom rows unbreakable, refuse the mine with a visible reason, add a machine-checkable invariant test and a browser J4 probe that attempts the floor and asserts the block is unchanged |
| D2 | **Medium** | high | Review probe J3: block already air 70 ms after mousedown; snapshot exposes no mining/progress state; no tool/character animation while breaking | Mining lacks the hold/progress/crack feedback the profile requires; the action reads as an instant teleport of state | Add a short break-progress state with a growing crack overlay and a pickaxe/arm swing; test progress advancement/cancel and prove it in the browser |
| D3 | **Medium** | high | `document.querySelectorAll('#minimap,.minimap,[data-minimap]')` returned 0; HUD has only the target text | A 128x64 world with underground navigation has no map/spatial aid, only coordinates and seed | Add a compact minimap showing the surface profile, player position and viewport, updated live; test its model and prove it in the browser |
| D4 | Low | medium | Hotbar top is 451 px while the bottom row sits at 508–540 px; the centre columns are covered | The palette hides the centre of the floor row while standing on it; an unobstructed side column exists and was used for the J4 integrity check | Record as a known overlay limitation; no blocking fix required |
| D5 | Low | medium | No save-state indicator; only the restore/failure toasts | The player cannot tell when an autosave happened | Optional polish; recorded, not required |
| O1 | Observation | high | One surface family (grass plateau/hills with a dune patch), no ores/biome-specific content | Domain D2/D3 depth, not an integrity defect | Domain score only; no closure required |
| O2 | Observation | high | No crafting/survival/mobs/weather | Explicit profile non-goals for this compact sample | None |

### Scores (as found, before remediation)

PES domains (0–5, weight): D1 4 (12), D2 2 (12), D3 2 (10), D4 2 (12), D5 4 (10), D6 2 (10),
D7 4 (8), D8 3 (8), D9 2 (8), D10 4 (10).

PES = (12×4 + 12×2 + 10×2 + 12×2 + 10×4 + 10×2 + 8×4 + 8×3 + 8×2 + 10×4) / 100 × 20 = **57.6**.

ECS domains (0–5, weight): E1 4 (25), E2 4 (25), E3 4 (20), E4 4 (15), E5 4 (15).

ECS = (25×4 + 25×4 + 20×4 + 15×4 + 15×4) / 100 × 20 = **80.0**.

Caps: one high defect → PES ≤ 60 and composite ≤ 65. PES 57.6 is already below the cap.

Composite before caps = 0.75 × 57.6 + 0.25 × 80.0 = **63.2**; with the high-defect cap (≤65) it stays
**63.2**.

Gate: G1 boot/offline pass; G2 no fatal errors pass (0 exceptions, 0 console errors in the journey
report); G3 save/load/recovery pass. No blocker.

Coverage: not enumerated against the v1.0 86-criterion table; the standard treats it as a diagnostic
that cannot raise PES, and the run stayed isolated from prior reference material. Recorded as a
review limitation. Extras: none claimed; no harmful additions found.

### Required findings

1. **D1 (high)** — seal the world floor: unbreakable bottom rows, explicit refusal on a mine attempt,
   machine-checkable invariant test (mine attempt fails, block unchanged), and browser J4 proof.
2. **D2 (medium)** — hold-mine feedback: break-progress state with a crack overlay and a tool/character
   swing, tested and browser-proven.
3. **D3 (medium)** — spatial aid: a minimap with surface profile, player dot and viewport, tested and
   browser-proven.

## Findings

- The core experience is coherent and visually distinctive, but the review cannot accept the result as
  delivered: the broken world floor is a high-severity integrity defect, and the missing break-progress
  feedback and spatial aid are required experience findings.
- The engineering surface is strong (modular, tested, robust, documented); the defect is
  player-visible integrity, not architecture.
- The underground background, collision/placement safety, persistence/recovery and offline boot all
  hold under direct probing.

## Conclusion

Review result before remediation: **PES 57.6 / ECS 80.0 / composite 63.2 (high-defect cap), gate pass,
1 high + 2 medium + 2 low defects**. The work order must not close on this state. Three required
findings are handed to remediation, which must add machine-checkable closure tests and re-run the
browser journeys; a recheck will re-score the fixed state.

Next hypothesis for the workflow: the create-scope integrity set should name a sealed world floor and
an underground/background journey as a default obligation, and the default verify stage should run a
J4-style dig-to-floor probe rather than relying on surface screenshots.
