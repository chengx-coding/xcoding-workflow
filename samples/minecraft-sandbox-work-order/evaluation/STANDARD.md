# M2D-SES v1.1 — Experience-First 2D Sandbox Evaluation Standard

**Status:** current fixed sample-evaluation standard. **Supersedes:** M2D-SES v1.0
([`STANDARD-v1.0.md`](STANDARD-v1.0.md), retained for the 0.3.3–0.3.6 scores).
**Scope:** the Minecraft-style 2D sandbox sample, and any future sample compared against its
reference set.

## 1. Why v1.1 exists

v1.0 was a systems/engineering-completeness rubric. It allowed a build with more tests, responsive
layout and counted inventory to outscore a build with a richer world, minimap, underground backdrop,
bedrock floor and stronger mining feedback. A player-visible defect such as "the world has no floor"
could not outweigh 124 passing tests. The score was internally consistent but not a good answer to
"which game is better to play".

v1.1 changes the primary question from **"how much is implemented?"** to **"what does a player
actually experience, and what is visibly broken?"** Engineering remains first-class, but it is a
**flexible secondary score** plus a **small minimum gate**, not a set of additional gates that can
either dominate the product or make every run fail.

The **composite headline** is 75% Player Experience + 25% Engineering/Code Quality. Both scores are
reported separately; a high player-visible defect caps the experience score and the composite.

## 2. Core principles

1. **Experience is the primary score.** The **Player Experience Score (PES)** is 75% of the
   composite.
2. **Engineering is a flexible score, not a pile of gates.** The **Engineering & Code Quality
   Score (ECS)** is 25% of the composite. It rewards meaningful tests, architecture, readability,
   robustness, performance, accessibility and documentation. Test count is not a score.
3. **Only hard safety is a gate.** Boot/offline, no fatal errors, and save/load/recovery are
   pass/fail. Everything else is scored, not gated, to avoid a brittle all-or-nothing run.
4. **Defects cap the experience.** A missing world floor, a void/background hole, broken collision/
   placement or data loss is a defect, not a missing optional feature. High defects cap PES and the
   composite.
5. **Journeys, not first frames.** The evaluator must actually play the critical journeys,
   especially underground, before scoring.
6. **Discovery is part of evaluation.** The evaluator records issues outside the rubric; recurring
   classes become criteria in the next standard version.
7. **No single metric is the goal.** Coverage, test count and feature count are diagnostics; PES,
   ECS and the capped composite are the reported triage.

## 3. Mandatory player journeys

Run these against the artifact itself, in a real browser, at 960x600 (plus 800x600 and 1280x800 for
J6). Record actions, expected/observed behavior, screenshots at meaningful states, and defect IDs.
Code/tests are supporting evidence, not a substitute for the journey.

| ID | Journey | Required probes |
| --- | --- | --- |
| J1 | First launch and controls | `file://` boot, status, visible controls/help, no console error |
| J2 | Movement and collision | walk, jump, land, wall/ceiling, world edges, no tunnelling/stuck |
| J3 | Mine, place, hotbar | hold-mine feedback, target outline, crack/particles/audio, placement/refusal, selection, counts |
| J4 | Underground and world floor | dig down, remove adjacent underground blocks, inspect the exposed background, reach the bottom, try to mine the floor; record whether the world is sealed and whether voids show sky/blank |
| J5 | Persistence and recovery | edit, reload, corrupt/invalid save, offline, storage unavailable |
| J6 | Window, motion, audio, pause | 960/800/1280, reduced motion, mute/unmute, pause/help, focus/keys |
| J7 | Time and atmosphere | day/night transition, lighting, stars/sun/moon, ambience |
| J8 | Free discovery | 10–15 minutes of play; record unexpected issues, delights and confusing states |

J4 is mandatory and cannot be replaced by a first-frame screenshot. J3 must observe the animation
and feedback, not just the final block removal. J8 is the anti-checklist pass: it is where issues
outside the rubric are found.

**Reproducible evidence.** Prefer a scripted browser/input probe for J2–J7 and keep the script under
the evaluation workbench. A first-frame screenshot is not evidence for an underground/background or
interaction claim. If the evaluator cannot drive input, it must say so, mark the journey unverified
and not award a pass; "not tested" is not a pass.

## 4. Player Experience Score (PES)

Ten weighted domains, each scored 0–5 using the experience anchors below.

| Domain | Weight | What it measures |
| --- | ---: | --- |
| D1 Core loop, controls and feel | 12 | Boot/offline, movement, jump, collision, camera, pause/help, input feel |
| D2 World integrity and underground | 12 | Seed/strata/caves, **solid floor/bedrock**, **underground background**, ores, flora, bounds |
| D3 Biomes and environment variety | 10 | ≥3 biomes, biome-specific content, water/fluids, weather/light, structures |
| D4 Interaction feedback and game feel | 12 | Target/ghost, break progress, **character/tool mining animation**, particles/audio, placement feedback, camera impact, inventory feedback |
| D5 Player, character, art and readability | 10 | Character silhouette/animation, palette, textures, composition, lighting/depth, UI typography |
| D6 HUD, navigation and orientation | 10 | Essential status, **minimap/map**, objectives/field notes, target readout, help, save/error status |
| D7 Atmosphere, audio and time | 8 | Day/night, sky/lighting, ambience, weather, particles, biome mood |
| D8 Inventory, progression and economy | 8 | Hotbar, counts/stacks, tools/durability, crafting, resource loop, containers, progression |
| D9 Content depth, extras and innovation | 8 | Block/mob/content variety, survival/combat/redstone/structures where in scope, delight, replay |
| D10 Replay, accessibility and performance | 10 | Responsive 960/800/1280, reduced motion, audio accessibility, frame stability, replay/seed |

**PES = Σ(domain weight × domain score) / 100 × 20**, before defect caps.

**ECS = Σ(engineering domain weight × domain score) / 100 × 20.**

**Composite = 0.75 × PES after caps + 0.25 × ECS**, then capped at 65 for any high defect and 30 for
any blocker. The two scores are always reported separately; the composite is a triage headline, not
a substitute for the experience judgement.

### Experience anchors

| Score | Meaning |
| ---: | --- |
| 0 | Absent or unusable. |
| 1 | A stub, label or static hint; no real experience. |
| 2 | Minimal: one case works, but the experience is visibly incomplete or fragile. |
| 3 | Functional: the user can complete the activity with understandable feedback. |
| 4 | Polished: robust, readable, cohesive, with satisfying feedback. |
| 5 | Exceptional for a 2D sandbox: deep, integrated, delightful, and consistent at the edges. |

A domain score is a judgement over its probes, not a count of features. For example, D2 is not 5
merely because terrain exists: the player must be able to reach the bottom, the world must have a
sealed floor, and underground voids must read as underground.

## 5. Engineering and Code Quality Score (ECS)

ECS is a flexible 0-100 score, 25% of the composite. It exists because a one-shot sample cannot
measure XC's long-term maintenance ability directly, while code quality is a real side of that
ability. It is scored, not gated, so a single imperfect dimension does not fail the run.

| Domain | Weight | What it measures |
| --- | ---: | --- |
| E1 Test quality | 25 | Tests exercise critical invariants, negative/edge cases and recovery, not just count; a green test that does not assert the requirement is a flaw |
| E2 Architecture and readability | 25 | Module boundaries, cohesion, naming, data flow, absence of god-files, maintainable structure |
| E3 Persistence, robustness and security | 20 | Versioned save, corruption/fallback, offline behavior, error handling, no unsafe injection/storage |
| E4 Performance, accessibility and responsiveness | 15 | Frame stability, resize/Dpr, reduced motion, labels/focus, no unbounded work |
| E5 Documentation and tooling | 15 | README/controls, reproducible checks, clear setup, useful verification artifacts |

**ECS = Σ(domain weight × domain score) / 100 × 20**, using the same 0–5 anchors as PES but judged on
engineering quality. Test count is evidence, not a score: 124 shallow tests can score below 20
meaningful ones. A test named after a requirement that only checks a proxy is a test-quality defect.

## 6. Defect ledger and caps

Record every observed defect in the journey log. Severity is about player impact, not implementation
effort.

| Severity | Definition | Examples |
| --- | --- | --- |
| **Blocker** | Cannot play, save, boot or recover | blank page, fatal console error, no offline boot, unrecoverable save corruption |
| **High** | Breaks world integrity or a core verb | **no bedrock/world floor**, **underground void shows sky/blank**, mining/placing through the player, collision escape, data loss, severe rendering corruption |
| **Medium** | A visible, repeated experience weakness | weak/absent mining animation, no minimap/orientation, crowded HUD, art inconsistency, jank, no reduced motion/pause |
| **Low** | Polish or isolated cosmetic issue | typo, tiny alignment, one-off particle |

Caps after PES:

- any **blocker**: PES ≤ 20 and composite ≤ 30;
- any **high** defect: PES ≤ 60, composite ≤ 65;
- **two or more high** defects: PES ≤ 50;
- **three or more medium** defects: PES ≤ 85 (unless a high/blocker cap is lower).

ECS is not capped by a PES defect: the engineering score can remain high. The composite cap is what
prevents strong engineering from fully offsetting a broken player-visible state.

A missing optional feature is not automatically a defect. It lowers the relevant domain. A high
defect is a broken or contradictory player-visible state, not "the reference has this feature".
The profile in [`PROFILE-2D-SANDBOX.md`](PROFILE-2D-SANDBOX.md) decides which expected capabilities
are integrity requirements (floor/background) versus optional depth.

## 7. Minimum engineering gate

Only hard safety/correctness is pass/fail. This deliberately keeps the gate small; tests,
performance, accessibility and responsiveness are scored in ECS rather than gated.

| Gate | Evidence |
| --- | --- |
| G1 Boot and offline | `file://` load, no external network, status ready |
| G2 No fatal errors | browser console clean during J1–J7 |
| G3 Save/load/recovery | edit → reload, corrupt save, storage blocked |

If a gate fails, apply the blocker/high cap as appropriate. A build with 124 passing tests and a
broken world floor still has a high defect and a capped PES/composite; a build with 17 passing tests
and a sound experience can score higher. Test quality, not test count, is scored in E1.

## 8. Coverage and extras

- **Coverage** uses the v1.0 86-criterion table as a **diagnostic**: report `present/86` and the
  missing classes. It never raises PES, never offsets a defect, and is not the headline.
- **Extras** are separate: bonus +1..+5 per genuine delight/clarity/accessibility gain (cap +10),
  penalty −1..−5 for a harmful addition (cap −10), controversial items 0 with both sides recorded.
  Extras do not excuse a high defect or a failed gate.
- The evaluation reports `PES | ECS | composite | gate | high/medium defects | coverage | extras`;
  the headline is the **capped composite**, with PES and ECS visible separately. Tests and
  responsiveness are ECS/experience inputs, never a way to outscore a richer, intact game.

## 9. Scoring procedure

1. Read the task and profile; identify the expected player experience.
2. Run J1–J8; capture state screenshots and notes.
3. Record the defect ledger with severity and evidence.
4. Score the ten PES domains; do not score engineering as a PES domain.
5. Score the five ECS domains; test count is evidence, not a score.
6. Apply PES caps and the composite cap; compute the composite.
7. Run the **minimum** engineering gate; record only G1–G3.
8. Report coverage from v1.0 as a diagnostic.
9. Record extras/penalties/controversies separately.
10. Write `rubric_gaps` (issues outside this standard) and a **next hypothesis** for the workflow.
11. Compare with the reference set: baseline, pre-correction, 0.3.6 standard, E3 reference, and the
    previous standard sample.

## 10. Self-evolution protocol

The standard is a discovery engine, not a fixed checklist:

- every evaluation must include a **discovery log** from J8 and any journey anomaly;
- if a new issue class appears, add it to `rubric_gaps` with severity and a proposed criterion;
- if it recurs in two runs, add the criterion to the next M2D-SES version and re-score the reference
  set;
- never delete a prior version or score; v1.0 and v1.1 scores are not directly comparable;
- the next sample iteration should use the highest-severity defect and the next hypothesis as its
  quality target, not a single total score.

This is how the evaluation supports automated self-iteration: it produces a **ranked, capped,
evidence-backed defect ledger** that the workflow can act on, rather than a single number that can
be gamed by tests.

**Defect-to-test closure.** For every high defect, the next hypothesis must add a machine-checkable
check of the real invariant, not a test named after the requirement. For example, a bedrock check
must assert that the floor block is unbreakable/present and that a mine attempt fails — not merely
that the bottom row `isSolid()`. A green proxy test is an E1 test-quality flaw, not evidence that the
defect is fixed.

## 11. 2D sandbox profile

The profile in [`PROFILE-2D-SANDBOX.md`](PROFILE-2D-SANDBOX.md) defines the expected player
experience for this sample: world floor, underground backdrop, mining feedback, orientation/minimap,
character/scene art, biomes/ores, inventory/economy, day/night/audio, responsive/accessibility. It
separates **integrity requirements** (high defects if broken) from **should-have depth** (domain
scores). It is not a feature-count checklist and does not require every Minecraft system.

## 12. Limits

- This is a human judgement rubric, not a precision instrument; scores are evidence-anchored.
- One run and one evaluator can miss issues; J8 and independent review reduce that risk.
- The standard is intentionally stricter on player-visible integrity than v1.0; a v1.1 score is not
  comparable to a v1.0 score.
- No multiplayer, long-session or acoustic validation is implied; record those as untested.
- The sample profile is scoped to the compact sandbox prompt; absent crafting/survival/redstone is a
  coverage/profile decision, not automatically a high defect.
