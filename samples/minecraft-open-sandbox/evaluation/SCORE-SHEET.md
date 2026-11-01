# Score sheet — open sandbox sample

Standard: **M2D-SES-OSS v1.2** (fixed before this re-score; v1.0/v1.1 retained as history). Blind
evaluator: independent; identity hidden during scoring. Reveal: **A = one-shot (MOSSWILD), B = XC
(Blockhaven)**.

## v1.2 result

| Field | One-shot A | XC B |
| --- | ---: | ---: |
| PES | **80.8** | **55.0** (raw 63.0; high cap 55) |
| ECS | **81.3** | **86.1** |
| Composite | **80.9** | **55.0** (raw 68.8; cap) |
| Experience tier | **polished** | **prototype** |
| High / medium / low | 0 / 1 / 1 | **1 / 2 / 2** |
| Higher | **A** | — |

The v1.2 correction changes two things after a real user could not find Blockhaven's crafting:

- a passive `E craft` HUD hint is **not** discoverability; D4 ≤55 and D9 ≤70 without a visible
  button/tutorial/quest entry;
- one high integrity defect caps PES/composite at **55**, not 65.

The raw dimension evidence is from the blind v1.1 pass; v1.2 applies the discoverability and
high-defect severity rules mechanically, without re-running or changing either artifact.

## Dimension scores

| Dimension | A | B |
| --- | ---: | ---: |
| D1 Core verbs/controls (10) | 90 | 78 |
| D2 World generation/physics (16) | 70 | 72 |
| D3 Action feedback (10) | 88 | 76 |
| D4 Inventory/crafting/progression (22) | 86 | **55** (64 → discoverability cap) |
| D5 Presentation/character/UI (18) | 84 | 58 |
| D6 Orientation/map (6) | 40 | 52 |
| D7 Replay/objectives/combat (8) | 86 | 50 |
| D8 Accessibility/responsive (4) | 82 | 55 |
| D9 First-run/discoverability/docs (6) | 86 | **70** (78 → cap) |
| **PES** | **80.8** | **63.0 → 55.0** |
| E1 Tests (30) | 88 | 90 |
| E2 Architecture (25) | 68 | 88 |
| E3 Robustness/persistence (20) | 84 | 90 |
| E4 Performance/accessibility (15) | 82 | 70 |
| E5 Docs/tooling (10) | 88 | 86 |
| **ECS** | **81.3** | **86.1** |

## Why the composite is not a 2–3-tier gap

The user experience gap is real and shows up in the dimensions:

- D5 visual/character/UI: **84 vs 58** (26 points);
- D4 crafting/progression: **86 vs 55** (31 points after discoverability);
- D7 objectives/combat: **86 vs 50** (36 points);
- D1 core verbs/health/combat: **90 vs 78**.

But A also has real gaps (no map: D6 40; no biomes/water/sand physics; no smelting/ingots; ECS 81.3
vs B's 86.1), and the composite weights ECS 25%. That compresses the headline to **80.9 vs 55.0**,
about 1.3 tiers by the tier labels, not 2–3 composite bands. The tier label **polished vs prototype**
is the better expression of the qualitative gap; do not force the composite to reproduce a subjective
"two or three tiers".

## Signature coverage

| Signature | A | B |
| --- | --- | --- |
| Seeded world | yes | yes |
| Mine/place feedback | strong | yes |
| Inventory/hotbar | yes, backpack | yes, 8 slots |
| Crafting/progression | **deep** (16 recipes, workbench, tiers, 8-step quest) | **shallow/hidden** (5 recipes, no station/durability/goals; only passive hint) |
| Save/restore | yes | yes |
| Day/night/atmosphere | yes, night mobs | yes |
| Orientation/map | no map | coords, no map |
| Objectives | yes | no |
| Water/sand physics | no | water/sand present, no flow/gravity |
| Smelting/ingots | no | no |
| Combat/health | yes | no |

## Defects

| ID | Severity | Artifact | Evidence | Cap |
| --- | --- | --- | --- | --- |
| H1 | high | B | Underground air shows sky/hill layer; 3×2 dig zoom; pixel (67,92,107) | PES ≤55, composite ≤55 |
| M1 | medium | A | No coordinates/map; D6 40 | — |
| M2 | medium | B | Crafting only behind passive `E craft`; real user did not find it; D4/D9 caps | D4 ≤55, D9 ≤70 |
| M3 | medium | B | Fixed 960×540 play area; black bands at 1280×800 | — |
| L1–L2 | low | A | Corrupt-save raw JSON parse leaks into copy; headless-only evidence | — |
| L3–L4 | low | B | No reduced motion/fullscreen; `window.__sandbox` left in | — |

## History

| Standard | A | B | Note |
| --- | ---: | ---: | --- |
| v1.0 | 88.8 | 65.0 | initial blind; over-credited engineering/README presence |
| v1.1 | 80.9 | 65.0 | weights/map/discoverability corrected; high cap still 65 |
| **v1.2** | **80.9** | **55.0** | passive hint not discoverable; high cap 55; tier added |

## Evidence

- v1.1 blind report: [`blind-evaluation-v1.1.md`](blind-evaluation-v1.1.md)
- v1.0 blind report: [`blind-evaluation.md`](blind-evaluation.md)
- Selected screenshots: [`../media/blind-evidence-v1.1/`](../media/blind-evidence-v1.1/)
- Tests: A 29/29, B 41/41; both page/browser checks; independent CDP probe.

## Verdict

**A is the stronger product: polished vs prototype.** The XC result is cleaner engineering and has a
functional crafting loop, but it is visually and experientially far behind, and it fails a known
high-integrity visual state. The v1.2 standard now says that clearly without pretending the composite
is a direct tier count.
