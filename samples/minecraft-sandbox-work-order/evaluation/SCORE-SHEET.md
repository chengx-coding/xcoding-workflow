# M2D-SES v1.1 — score sheet

Use with [`STANDARD.md`](STANDARD.md) and [`PROFILE-2D-SANDBOX.md`](PROFILE-2D-SANDBOX.md). Run the
J1–J8 journeys first; a first-frame screenshot alone is not a score.

## Formula

- **PES /100** = Σ(PES domain weight × domain score) / 100 × 20, before defect caps.
- **ECS /100** = Σ(engineering domain weight × domain score) / 100 × 20.
- **Composite /100** = 0.75 × PES after caps + 0.25 × ECS, then capped at 65 for any high defect and
  30 for any blocker.
- **PES defect caps** = 20 for any blocker, 60 for one high, 50 for two or more high, 85 for three or
  more medium.
- **Minimum engineering gate** = G1–G3 only; pass/fail, no points.
- **Coverage** = v1.0 86-criterion diagnostic; not part of PES/ECS/composite.
- **Extras** = separate bonus/penalty/controversy; does not excuse a defect or gate failure.

PES, ECS and composite are reported separately. The composite is the headline; PES is the experience
judgment; ECS is the flexible engineering/code-quality judgment.

## v1.0 reference scores (historical; not comparable)

| Artifact | v1.0 Base | v1.0 Core | v1.0 Coverage | v1.0 Extras |
| --- | ---: | ---: | ---: | ---: |
| One-shot baseline | 39 | 44 | 31% | 38 |
| 0.3.3 pre-correction | 60 | 65 | 50% | 61 |
| 0.3.3 standard | 55 | 61 | 47% | 58 |
| 0.3.4 standard | 55 | 61 | 47% | 59 |
| 0.3.5 standard | 55 | 62 | 47% | 59 |
| 0.3.6 standard | 62 | 70 | 49% | 67 |
| E3 / Verdant Hollow (reference) | 56 | 67 | 47% | 60 |

These are retained for provenance only. v1.1 changes the question and the weights; do not compare a
v1.1 PES/ECS with a v1.0 base.

## v1.1 consolidated reference set

| Artifact | PES | PES cap | ECS | Composite | Gate | High / medium | Coverage | Extras |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 0.3.3 pre-correction | 70.4 | 70.4 | 74.0 | **71.3** | pass | 0 / 4 | 43/86 | +2 |
| E3 / Verdant Hollow | **71.2** | 71.2 | 65.5 | **69.8** | pass | 0 / 3 | 40/86 | +2 |
| 0.3.3 standard | 57.6 | 57.6 | 81.0 | **63.5** | pass | **1 / 2** | 40/86 | — |
| 0.3.6 standard | 60.0 | 50.0 | 92.5 | **60.6** | pass | **2 / 2** | 42/86 | +2 |
| one-shot baseline | 55.8 | 55.8 | 38.0 | **51.4** | pass | 0 / 3 | 27/86* | — |

\* Baseline coverage is a legacy v1.0 diagnostic count; it is not a v1.1 experience score.

**0.3.4 and 0.3.5 are not re-evaluated under v1.1**: their complete artifacts are not retained. Their
v1.0 historical scores remain 55/61/47% and 55/62/47%; no v1.1 score is fabricated from screenshots.

Consolidated verdict:

- **pre-correction is #1 on the composite (71.3)** and **E3 is #1 on PES (71.2)**; they are within
  the rubric's resolution (tie on experience).
- **0.3.3 standard is #3 (63.5)**; it has one high defect (no bedrock/floor), but strong ECS (81.0)
  keeps it above 0.3.6.
- **0.3.6 is #4 (60.6)** despite having the **highest ECS (92.5)**. Its 124 tests and strong
  architecture are credited; they cannot offset the two high world-integrity defects.
- **The one-shot baseline is last on composite (51.4)** because its ECS is 38.0 (no tests/README/
  tools), but its PES (55.8) is **above 0.3.6's 50.0**: it has a sealed floor and underground
  backdrop, unlike 0.3.6. This is the experience-first inversion.
- Coverage is not a ranking metric: 0.3.6 (42/86) has more coverage than E3 (40/86) but a lower
  experience score.
- The high-defect cap is not the only reason 0.3.6 loses: its raw PES (60.0) is already behind pre,
  E3 and 0.3.3 standard before the cap.

### ECS detail

| Artifact | E1 Test quality | E2 Architecture | E3 Persistence | E4 Perf/a11y | E5 Docs/tooling | ECS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.3.6 | 3.5 | 5 | 5 | 5 | 5 | 92.5 |
| pre-correction | 4 | 4 | 4 | 2 | 4 | 74.0 |
| E3 | 3 | 3 | 4 | 2.5 | 4 | 65.5 |

0.3.3 standard ECS is **81.0** (33 tests, 6 modules, README/checks; weaker accessibility/
responsiveness and no bedrock test); baseline ECS is **38.0** (no tests, README or tools, but clean
single-file code). Full breakdown is in the v1.1 consolidated evaluation.

0.3.6's E1 is 3.5, not 5: the suite is large but includes a green test named "the bedrock floor is
solid" that only checks `isSolid()` on a build with no bedrock. Test count is not test quality.

## Journey log

| ID | Journey | Result | Evidence / screenshot | Defect IDs |
| --- | --- | --- | --- | --- |
| J1 | First launch and controls | | | |
| J2 | Movement and collision | | | |
| J3 | Mine, place, hotbar | | | |
| J4 | Underground and world floor | | | |
| J5 | Persistence and recovery | | | |
| J6 | Window, motion, audio, pause | | | |
| J7 | Time and atmosphere | | | |
| J8 | Free discovery | | | |

Pilot J4: 0.3.6 fails (no bedrock, underground sky); pre and E3 pass (bedrock + cave backdrop).

## PES domains

| Domain | Weight | Score 0–5 | Evidence | Defects/notes |
| --- | ---: | ---: | --- | --- |
| D1 Core loop, controls and feel | 12 | | | |
| D2 World integrity and underground | 12 | | | |
| D3 Biomes and environment variety | 10 | | | |
| D4 Interaction feedback and game feel | 12 | | | |
| D5 Player, character, art and readability | 10 | | | |
| D6 HUD, navigation and orientation | 10 | | | |
| D7 Atmosphere, audio and time | 8 | | | |
| D8 Inventory, progression and economy | 8 | | | |
| D9 Content depth, extras and innovation | 8 | | | |
| D10 Replay, accessibility and performance | 10 | | | |
| **PES raw** | **100** | | | |

## ECS domains

| Domain | Weight | Score 0–5 | Evidence |
| --- | ---: | ---: | --- |
| E1 Test quality | 25 | | Tests assert invariants, edge cases and recovery; count only as evidence |
| E2 Architecture and readability | 25 | | Boundaries, cohesion, naming, maintainability |
| E3 Persistence, robustness and security | 20 | | Versioning, corruption/fallback, offline, errors |
| E4 Performance, accessibility and responsiveness | 15 | | Frame stability, resize/Dpr, reduced motion, labels |
| E5 Documentation and tooling | 15 | | README, controls, reproducible checks, useful evidence |
| **ECS** | **100** | | |

## Defect ledger

| ID | Severity | Journey | Observation | Evidence | Cap effect |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

Pilot defects:

| ID | Artifact | Severity | Observation |
| --- | --- | --- | --- |
| H1 | 0.3.6 | high | No bedrock/world floor; bottom stone is mineable |
| H2 | 0.3.6 | high | Underground voids show sky/blank; no cave backdrop |
| H3 | 0.3.3 standard | high | No bedrock/world floor; bottom rows are ordinary stone |
| M1 | 0.3.6 | medium | No minimap/orientation; D6 3 |
| M2 | 0.3.6 | medium | Mining animation is a small arm jitter/tool nub |
| M3 | 0.3.3 standard | medium | No minimap; weak mining animation |
| M4 | baseline | medium | No audio, pause or minimap; 800px hotbar clip (0 high defects; J4 passes) |
| — | pre/E3 | pass | Both have bedrock and a cave backdrop; no high defects |

Art/character quality is a **D5 domain score**, not a defect (0.3.6, pre, E3 all score D5 4;
0.3.3 standard 3.5; baseline 4). The score sheet's earlier art-as-medium row was inconsistent and is
removed. HUD occlusion at the world bottom is a J4 usability medium; use an unobstructed position
before claiming the floor test.

## Minimum engineering gate

| Gate | Pass/fail | Evidence |
| --- | --- | --- |
| G1 Boot and offline | | |
| G2 No fatal errors | | |
| G3 Save/load/recovery | | |

Tests, performance, accessibility and responsiveness are ECS, not gates.

## Coverage diagnostic (v1.0 criteria)

- Present/86:
- Missing classes:
- Coverage never raises PES/ECS and never offsets a defect.

## Extras

| Class | Item | Score | Why |
| --- | --- | ---: | --- |
| Bonus | | | |
| Penalty | | | |
| Controversial | | 0 | |

## Output

- PES raw:
- PES after defect caps:
- ECS:
- **Composite after caps:**
- Minimum gate:
- High / medium defects:
- Coverage:
- Extras / sensitivity:
- Best on: (experience / engineering / coverage / composite)
- `rubric_gaps` (new issues outside the standard):
- Next hypothesis for the workflow:

## Policy

- Compare with the one-shot baseline, pre-correction, 0.3.6 standard, E3 reference, and the previous
  standard sample. Label E3 as a reference condition, not a standard sample.
- A high defect is a broken player-visible state, not a missing optional feature. Missing
  crafting/survival/redstone is a profile/coverage decision.
- Engineering quality is a real 25% score, not a pile of gates. The only gates are G1–G3; tests,
  architecture, performance, accessibility and docs are scored in ECS.
- Engineering cannot fully offset a high experience defect: PES caps and the composite cap apply.
- The standard is versioned; v1.0 and v1.1 scores are not directly comparable.
