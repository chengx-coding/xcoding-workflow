---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__verify-journeys"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Verification — stateful journeys and visible states (feature scope)

## Scope

Executed the automated browser journey probe against the real page at 960x600, then mapped the
executed evidence to every must and should capability, to journeys J1–J11 and to integrity invariants
I1–I5, including the visible-state obligations at materially different visual states.

## Evidence

### Command and outcome

```console
cd C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project
node tools/journey_check.js --out <workbench>/tmp/journeys

ok: true
checks: 58
failed: []
```

Report: `<workbench>/tmp/journeys/journey-report.json`. Screenshots (SHA-256 in full in the report):

| File | SHA-256 |
| --- | --- |
| `mine-before.png` | `8E8A413BDE472E4C5B92880125F32CF74C4094A341DC786720F0233A01F1BE0F` |
| `mine-after.png` | `8FB073FB4B3D9739D24F09684AC3E5FE9835DC0A4FB1098753F41F3532394EAA` |
| `paused.png` | `36FE38EAD83858B5E62611DF3364C7E86AB79753852567B931CE5BF67C0BB567` |
| `day.png` | `D19C3D38B5C14B3F30C7EC8AE82338A1A1048180C07FF1DA2E8E593B0688CBB7` |
| `night.png` | `0C6170E6DE2EAA24BAFFD6E683403958DEF36F1F829D160458405378D5AB683F` |
| `final-960x600.png` | `DE4E69EEFD2556E210E9090FC46BF6F6789829AB6F89A2708027B2129BD9EE97` |
| `wide-1280x800.png` | `B8A2591D9AE629655271EEB2CF00AF577E3B354B400DE01159626070D251F5B9` |

### Journey evidence (58 executed checks)

| Journey | Executed result |
| --- | --- |
| J1 mine | block (13,41) becomes air; grass 16→17; `+1 grass` toast; the same tile's pixel changes by RGB distance > 40 and becomes background-blue (the removed content's visible replacement) |
| J2 place | planks occupy (14,40); count 12→11; `Placed planks` toast; the cell pixel is visibly the new block |
| J3 refuse occupied | pixel unchanged (<6 distance); `That spot is not empty` visible in a toast element over an unchanged world |
| J4 refuse player | player cell stays air and shows `You are standing there` |
| J5 refuse no inventory | leaves count 0 → `No leaves left` and the cell stays air |
| J6 reload | mined/placed blocks, counts and player position survive a real reload; restore notice visible |
| J7 corrupt save | corrupt payload injected before the next document's scripts; page stays `ready`, regenerates a fresh world and shows the unreadable-save notice |
| J8 pause | overlay covers >800x400 with backdrop blur; clock frozen for 700 ms; resume hides the overlay and time advances |
| J9 day/night | two 960x600 screenshots, sky pixels differ materially, HUD clock `12:00 day` vs `00:01 night`, foreground block still drawn and readable at night |
| J10 boundary | camera clamps to x=0 and x=128*32−960; player stays inside both edges |
| J11 hotbar | key 5 selects slot 5, wheel advances, exactly one selected slot, wheel wraps back |
| Extra | coordinates track the player (`20, 41`); mute and unmute persist; reduced-motion media query + CSS applied; numeric seed 4242 regenerates a different terrain; error status turns red and reload recovers; 1280-wide layout with no overflow |

### Capability mapping

| # | Capability | Executed evidence |
| --- | --- | --- |
| C1 | Deterministic seeded terrain | seed 1337 world shown; seed 4242 regeneration produces a different terrain checksum; determinism proven by terrain tests |
| C2 | Movement, gravity, jump, collision | held A/D movement in the boundary journey; reload restores player position; physics unit tests (10) |
| C3 | Mining within reach | J1 check |
| C4 | Placement and refusal explanation | J2, J3, J4, J5 checks |
| C5 | Hotbar ≥4 types, number keys, visible selection | 9 slots, key 5, wheel, single selected class |
| C6 | Camera follows and clamps | J10 camera clamp values |
| C7 | Save/load restored on load | J6 checks |
| C8 | Readable page, hint, offline | boot hint/overflow checks; page check static contract |
| C9 | README | document review |
| C10 | Status marker contract | ready at boot; red error; reload returns ready |
| C11 | Tests and seed preservation | verify-tests node: 104/104, seed file unchanged |
| C12 | No external resources | page check static scan (no network reference) |
| C13 | Screenshot + independent review | screenshots above; review node |
| C14 | Lifecycle recorded | runtime stages + validated documents |
| C15 | Per-block inventory counts | mine/place count checks; all slot counts rendered |
| C16 | 52 tests including seed | 104 tests |
| C17 | Reduced motion | emulated media query matches; computed slot transition < 0.001 s |
| C18 | Wheel selection | wheel advance and wrap checks |
| C19 | 1280-wide scaling | layout/canvas 1280, no overflow, hotbar inside |
| C20 | Audio and mute | mute/unmute control persists; generated-oscillator chain proven by audio unit tests (headless audio is muted) |
| C21 | Numeric seed entry | seed 4242 regenerates and shows `New world` |
| C22 | Pause | J8 checks |
| C23 | Eighth hotbar block | nine palette blocks including glass (slot 8) |
| C24 | Day/night | J9 two-state checks |
| C25 | Nine-slot hotbar | 9 palette slots |
| C26 | Coordinates | HUD `20, 41` after teleport |
| N1–N5 | Sourced non-goals | verified absent: no network, no build, no commit, no report, no multiplayer |

### Integrity invariants

- **I1** placement never overwrites: occupied and player-overlap refusals leave the world unchanged
  (checks 20–24), and placement only succeeds into air.
- **I2** player never intersects a solid tile: proven by the physics suite (walls, ceilings, 1000
  tiles/s tunnelling) — recorded as unit-level rather than a browser AABB assertion.
- **I3** save round-trip or safe fallback: J6/J7 checks.
- **I4** camera never leaves the world: J10 clamp values.
- **I5** selected index/counts stay valid: wheel wrap, empty-slot zero, inventory never negative in
  the inventory suite.

### Gaps

- Headless Chrome runs with `--mute-audio`, so mute behaviour and the generated oscillator chain are
  verified through the control's persisted state plus the audio unit tests; audible output is not
  machine-verified. Recorded gap.
- I2 is verified at unit level, not by reading a live browser AABB. Recorded gap.
- A reduced-motion frame is not captured as a screenshot; the media query match and computed
  transition duration are asserted in the browser.

## Findings

- Every must capability has executed evidence; every should capability has executed or unit evidence
  with its limitation recorded.
- The visible-state obligations are met: removal shows the background at the same anchor, refusals
  leave the world unchanged under a visible explanation, pause occludes and freezes, and day/night are
  two materially different visual states with a readable foreground.

## Conclusion

Feature verification passes with no failed check. The recorded gaps are limitations of audible and
unit-level assertions, not acceptance failures.
