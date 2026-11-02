# Score sheet — open sandbox sample

Standard: **M2D-SES-OSS v1.2**. Blind evaluator; identity revealed after scoring:
**A = one-shot (MOSSWILD), B = XC 0.4.4 (Cubewood)**.

## Current result — 0.4.4 stop sample

| Field | One-shot A | XC 0.4.4 B |
| --- | ---: | ---: |
| PES | 83.9 | **84.8** |
| ECS | 86.8 | **88.7** |
| Composite | 84.6 | **85.8** |
| Experience tier | polished | **polished** |
| High / medium / low | 0 / 1 / 1 | 0 / 2 / 2 |
| Higher | — | **B** |

B wins by 1.2 composite and is higher on both PES and ECS. No high defect was applied. B's medium
M1 is a persistence defect: `world.surface` is not restored after reload, so caves/tunnels render
flat after a save; the evaluator classified it medium/borderline high because the world remains
playable. If it were reclassified high, B would cap at PES/composite 55 and would not stop.

## Dimension scores (0.4.4)

| Dimension | A | B |
| --- | ---: | ---: |
| D1 Core verbs/controls (10) | 92 | 82 |
| D2 World generation (16) | 78 | 86 |
| D3 Action feedback (10) | 90 | 84 |
| D4 Inventory/crafting/progression (22) | 84 | 85 |
| D5 Presentation/character/UI (18) | 91 | 86 |
| D6 Orientation/map (6) | 55 | 88 |
| D7 Replay/objectives/combat (8) | 88 | 80 |
| D8 Accessibility/responsive (4) | 84 | 80 |
| D9 First-run/discoverability/docs (6) | 78 | 90 |
| **PES** | 83.9 | **84.8** |
| E1 Tests (30) | 88 | 95 |
| E2 Architecture (25) | 85 | 92 |
| E3 Robustness/persistence (20) | 87 | 78 |
| E4 Performance/accessibility (15) | 88 | 86 |
| E5 Docs/tooling (10) | 85 | 87 |
| **ECS** | 86.8 | **88.7** |

## Defects

| ID | Severity | Artifact | Evidence |
| --- | --- | --- | --- |
| A-M1 | medium | A | no map/coordinates; D6 55 |
| A-L1 | low | A | corrupt-save copy leaks raw JSON parser text |
| B-M1 | medium (borderline high) | B | `world.surface` not persisted; dug caves flatten after reload |
| B-M2 | medium | B | corrupt save silently starts a new world, no warning |
| B-L1/L2 | low | B | HUD clock inconsistency; no reduced motion |

## History

| Version | PES | ECS | Composite | Tier | Note |
| --- | ---: | ---: | ---: | --- | --- |
| one-shot | 83.9 | 86.8 | 84.6 | polished | fixed reference |
| XC 0.4.2 | 66.1 | 86.1 | 71.1 | prototype | H1 fixed; hidden crafting |
| XC 0.4.3 | 66.1 | 86.1 | 71.1 | prototype | Blockfall, H1 fixed |
| **XC 0.4.4** | **84.8** | **88.7** | **85.8** | polished | first-run + backdrop + persistence caveat |

## Evidence

- Blind report: [`blind-evaluation-0.4.4.md`](blind-evaluation-0.4.4.md)
- Cubewood: 79/79 tests, 21/21 browser steps; screenshots
  [`../media/xc-cubewood-day.png`](../media/xc-cubewood-day.png),
  [`../media/xc-cubewood-backdrop.png`](../media/xc-cubewood-backdrop.png)
- One-shot: 29/29 tests, browser/quest checks; [`../media/one-shot-mosswild.png`](../media/one-shot-mosswild.png)
