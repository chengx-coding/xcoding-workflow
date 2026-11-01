# M2D-SES-OSS v1.0 — Open Sandbox Standard

A fixed, reproducible rubric for a **simple, open Minecraft-style 2D sandbox prompt**. It evaluates
what an agent actually produced, not whether it followed a pre-written feature list.

This standard is intentionally separate from the compact-sample v1.1 rubric. Scores are not
comparable across the two samples.

## 1. Prompt and comparison

Both conditions receive exactly this product prompt:

> Build a playable, offline 2D sandbox game inspired by Minecraft.
>
> It must run by opening `index.html`, with no build step, external libraries, CDNs, or network
> access. Make it feel like a small Minecraft, save progress, and document the controls.

One-shot and XC start from the same seed. The XC condition may use workflow process tooling; it must
not receive extra product requirements. Evaluate anonymized A/B outputs; the evaluator must not know
the condition.

## 2. Gates and defect caps

Hard gates:

- **G1 Offline boot:** opens from `file://`, no network/external assets, no build.
- **G2 No fatal errors:** no uncaught boot/runtime error; page renders.
- **G3 Save/recovery:** progress saves/restores, or a documented reason it cannot; a corrupt save
  does not fatally break the page.

High defects (player-visible broken core):

- unsealed world floor / player can leave the world;
- underground removal reveals sky/blank canvas (no underground read);
- collision/placement can trap/corrupt the player;
- save destroys a valid world or prevents boot;
- controls are unreadable or the game cannot be played.

**Caps:** one high defect → PES ≤60, composite ≤65; two or more → PES ≤50, composite ≤60.
A blocker (game unplayable / no offline boot) → PES ≤20, composite ≤30.

Medium defects: missing break/place feedback, no spatial orientation, no visible selected hotbar,
weak first frame, no mobile/responsive behavior where claimed. Medium defects lower dimension scores;
three or more apply a −10 composite cap.

Low defects: polish, copy, minor layout. Record but do not cap.

**Crafting/progression is not a high defect when absent.** It is a domain/signature gap scored in D4.
Do not treat a deliberate compact scope as an integrity failure; do not excuse it from the experience
score either.

## 3. PES — player experience score (75%)

Score each dimension 0–100, then take the weighted sum.

| ID | Dimension | Weight | What earns the score |
| --- | --- | ---: | --- |
| D1 | Core verbs and controls | 12 | movement, jump, collision, mining, placing, camera; clear controls and refusal reasons |
| D2 | World generation and exploration | 14 | seeded terrain, block variety, caves/ores/biomes/structures; a world worth exploring, not a flat strip |
| D3 | Mining and placement feedback | 12 | target/outline, break progress, particles/sound, animation, placement preview/refusal; actions read without explanation |
| D4 | Inventory, crafting and progression | 20 | counts/hotbar, gather→craft→build loop, recipes (grid or list), stations/tools, resource pressure, goals/progression. No fixed recipe count; absence of any crafting/progression caps D4 at 50 |
| D5 | Presentation, UI, audio, atmosphere | 12 | coherent visual identity, readable HUD, day/night/lighting, sound/mute, composition; not a debug canvas |
| D6 | Orientation and status | 6 | seed/position/time, minimap or equivalent spatial aid, clear feedback |
| D7 | Replay, objectives and world controls | 6 | seed/new world, pause/help, lightweight goals or exploration loop |
| D8 | Accessibility, responsive and polish | 6 | keyboard/accessible labels, reduced motion, 800/960/1280 behavior, no clipping/overlap |
| D9 | First-run and documentation | 12 | immediate playability, visible controls, short README/architecture, no external docs needed |

D4 is the **signature dimension**. A Minecraft-like result need not implement every Minecraft system,
but a gather→craft→build loop is the genre's defining progression. A recipe list is acceptable; a
crafting grid is not required. If the agent explicitly decides not to implement it, record the
reason and score the lower band; do not rewrite the prompt to make the omission disappear.

## 4. ECS — engineering/code score (25%)

| ID | Dimension | Weight | What earns the score |
| --- | --- | ---: | --- |
| E1 | Tests and verification | 30 | tests assert real invariants (terrain determinism, collision, placement, save/recovery, crafting if present), not only smoke; executed browser evidence |
| E2 | Architecture and readability | 25 | coherent modules, no god file, clear data/state boundaries, readable code |
| E3 | Robustness, persistence, security | 20 | save/version/corrupt fallback, bounds/limits, no unsafe HTML/network, deterministic errors |
| E4 | Performance, accessibility, responsive | 15 | stable frame loop, no leaks/console spam, accessible labels, required widths |
| E5 | Documentation and tooling | 10 | README controls/architecture, reproducible checks/tools |

ECS does not require a framework, package manager, build step or a specific file layout. Tests may be
Node, browser or scripted checks; count is evidence, not score.

## 5. Composite and reporting

`composite = 0.75 × PES + 0.25 × ECS`

Report:

- each PES/ECS dimension score and the weighted totals;
- high/medium/low defects with evidence;
- gates G1–G3;
- signature coverage: crafting/progression present or absent, with depth;
- executed evidence (browser/screenshot/test commands);
- caps applied;
- A/B identity only after both are scored.

## 6. Evidence bar

A first frame, code reading or narrative is not evidence for a journey. Execute the page and record
before/after for mining, placing, save/reload, and any crafting journey present. A high defect closes
only with an executable invariant or a recorded user-accepted risk. Static checks and tests are
evidence for ECS, not for PES.

## 7. Scope

No Minecraft system is pre-declared a non-goal. The evaluator scores what is present and records what
is absent. Survival, mobs, redstone, fluids, weather and structures are **depth/coverage** choices,
not required for a valid small sandbox; but their absence cannot be hidden by a high score in
unrelated polish.

## 8. Fairness

- Same prompt, same seed, isolated workspaces.
- XC may use workflow tooling, not extra product requirements.
- The evaluator is blind to condition and does not read the other output before scoring.
- Do not tune the rubric after seeing either result.
- Report evidence limits and any unexecuted checks; do not award a pass for unexecuted evidence.
