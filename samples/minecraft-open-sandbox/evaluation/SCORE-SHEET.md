# Score sheet — open sandbox sample

Standard: **M2D-SES-OSS v1.0** (fixed before the runs). Blind evaluator: independent; identity hidden.
Identity revealed after scoring: **A = one-shot (MOSSWILD), B = XC (Blockhaven)**.

## Result

| Field | One-shot A | XC B |
| --- | ---: | ---: |
| PES | **89.4** | **60.0** (raw 76.8) |
| ECS | **87.0** | **88.3** |
| Composite | **88.8** | **65.0** (raw 79.7) |
| High / medium / low | 0 / 0 / 3 | **1 / 1 / 3** |
| Caps | none | H1: PES ≤60, composite ≤65 |
| Gates G1–G3 | pass | pass |
| Higher | **A (one-shot)** | — |

The XC result has the higher ECS (88.3 vs 87.0) but loses on PES because of one high integrity
defect: underground air is transparent to the sky/sun/clouds layer.

## Dimension scores

| Dimension | A | B |
| --- | ---: | ---: |
| D1 Core verbs/controls (12) | 92 | 82 |
| D2 World generation (14) | 84 | 80 |
| D3 Action feedback (12) | 90 | 80 |
| D4 Inventory/crafting/progression (20) | **93** | 64 |
| D5 Presentation/audio (12) | 91 | 76 |
| D6 Orientation (6) | 76 | 82 |
| D7 Replay/objectives (6) | 90 | 68 |
| D8 Accessibility/responsive (6) | 88 | 74 |
| D9 First-run/docs (12) | 92 | 90 |
| **PES weighted** | **89.4** | **76.8 → 60.0** |
| E1 Tests (30) | 92 | 90 |
| E2 Architecture (25) | 76 | 90 |
| E3 Robustness/persistence (20) | 90 | 90 |
| E4 Performance/accessibility (15) | 86 | 80 |
| E5 Docs/tooling (10) | 95 | 88 |
| **ECS weighted** | **87.0** | **88.3** |

## Signature coverage

| Signature | A | B |
| --- | --- | --- |
| Seeded world | yes | yes |
| Mine/place feedback | strong | yes |
| Inventory/hotbar | yes | yes |
| Crafting/progression | **deep** (16 recipes, workbench, tiers, 8-step quest) | **shallow** (5 recipes, no station/durability/goals) |
| Save/restore | yes | yes |
| Day/night/atmosphere | yes, with night mobs | yes |
| Orientation | partial (no minimap) | partial (no minimap; X/Y) |
| Objectives | yes | no |

## Defects

| ID | Severity | Artifact | Evidence | Cap |
| --- | --- | --- | --- | --- |
| H1 | high | B | Underground air shows sky/sun/clouds; pixel check at light 0 follows sky time | PES ≤60, composite ≤65 |
| M1 | medium | B | Occupied-tile placement refusal is silent; no placement ghost | dimension |
| L1 | low | B | Fixed 960×540 page leaves black bands at 1280 | — |
| L2 | low | B | Canvas not focusable/roleless; no reduced-motion rule | — |
| L3 | low | B | No objectives/progression goal in the delivered experience | — |
| L1–L3 | low | A | No minimap/coordinates; large `main.js`; headless-only evidence | — |

## Evidence

- `node --test`: A 29/29, B 41/41.
- `page_check.py`: both ok, no static problems, exact ready marker, non-blank canvas.
- A browser + full quest check; B browser check 16/16; independent Playwright probe for both.
- Blind report: [`blind-evaluation.md`](blind-evaluation.md); screenshots in
  [`../media/blind-evidence/`](../media/blind-evidence/).

## Verdict

**One-shot A wins 88.8 to 65.0.** The XC condition produced cleaner engineering and a real
crafting loop, but failed a known high-integrity visual state. The sample exposes that the workflow
does not automatically prevent this defect; it does not support a claim that XC is globally better.
