# Score sheet — open sandbox sample

Standard: **M2D-SES-OSS v1.2**. Blind evaluator; identity revealed after scoring:
**A = one-shot (MOSSWILD), B = XC 0.4.4 (Cubewood)**.

## Current result — v1.3 corrected

**v1.2's 85.8 is invalid and retained only as history.** v1.3 requires real-pointer interaction
truth and blind pairwise art quality. Blind re-score: **A = one-shot MOSSWILD, B = XC 0.4.4 Cubewood.**

| Field | One-shot A | XC 0.4.4 B |
| --- | ---: | ---: |
| PES | 78.9 | 55.0 (raw 70.1; high cap) |
| ECS | 81.7 | 83.1 |
| Composite | 79.6 | 55.0 (raw 73.3; cap) |
| Experience tier | solid | prototype |
| High / medium / low | 0 / 1 / 1 | **1** / 2 / 2 |
| Art D5 | 83 (polished) | **53 (prototype)** |
| Higher | **A** | — |

B's high defect: Craft/Inventory buttons are enabled-looking but silently no-op under a normal real
click (0/10 at 90 ms, 9/10 at 10 ms); the craft list is rebuilt ~15×/s, so mousedown/up land on
different nodes. B's own selftest used `element.click()`, which missed it. A has no high defect;
its main gap is no map/coordinates (D6 50) and E/help/quest-only crafting entry, not a high defect.

## v1.2 history (superseded)

The earlier v1.2 score was **A 83.9 / B 84.8 / composite A 84.6, B 85.8**, both "polished". That
score is retained for traceability only. It over-credited a visible-but-unusable control and a
functional-but-plain art direction. Do not use it as a stop or promotion claim.

## Dimension scores (v1.3)

| Dimension | A | B |
| --- | ---: | ---: |
| D1 Core verbs/controls (10) | 90 | 78 |
| D2 World generation (16) | 80 | 82 |
| D3 Action feedback (10) | 86 | 62 |
| D4 Inventory/crafting/progression (22) | 82 | 55 |
| D5 Art/character/UI (18) | 83 | 53 |
| D6 Orientation/map (6) | 50 | 84 |
| D7 Replay/objectives/combat (8) | 82 | 74 |
| D8 Accessibility/responsive (4) | 84 | 78 |
| D9 First-run/discoverability/docs (6) | 74 | 82 |
| **PES** | 78.9 | 55.0 (cap) |
| E1 Tests (30) | 84 | 92 |
| E2 Architecture (25) | 82 | 90 |
| E3 Robustness/persistence (20) | 86 | 76 |
| E4 Performance/accessibility (15) | 84 | 82 |
| E5 Docs/tooling (10) | 82 | 84 |
| **ECS** | 81.7 | 83.1 |

## Evidence

- Blind report: [`blind-evaluation-0.4.4.md`](blind-evaluation-0.4.4.md)
- Cubewood: 79/79 tests, 21/21 browser steps; screenshots
  [`../media/xc-cubewood-day.png`](../media/xc-cubewood-day.png),
  [`../media/xc-cubewood-backdrop.png`](../media/xc-cubewood-backdrop.png)
- One-shot: 29/29 tests, browser/quest checks; [`../media/one-shot-mosswild.png`](../media/one-shot-mosswild.png)
