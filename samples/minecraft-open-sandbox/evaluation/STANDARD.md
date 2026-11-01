# M2D-SES-OSS v1.2 — Open Sandbox Standard

A fixed, reproducible rubric for a **simple, open Minecraft-style 2D sandbox prompt**. It evaluates
what an agent actually produced, not whether it followed a pre-written feature list.

This standard is intentionally separate from the compact-sample v1.1 rubric. Scores are not
comparable across the two samples.

## 1a. Experience-first correction (v1.1)

v1.0 under-ranked a technically present but poor experience. v1.1 changes the weighting and adds
accessibility/discoverability rules **before** re-scoring; it does not change the A/B artifacts.

- A feature counts only if a player can find and use it from the first-run UI or in-game help.
  Code/README presence without a discoverable entry point is not full credit; a primary system
  (crafting, inventory, map) that is not discoverable is at most 50% of its dimension.
- A map/minimap is a real spatial aid. Coordinates or field notes alone do not earn the top D6 band
  (D6 ≤60 without a map).
- Visual composition, character readability, animation and tool visualisation are a primary
  experience dimension, not polish. A plain prototype cannot score above 60 in D5.
- Biomes, water/sand physics, smelting/ingots and combat/mobs are coverage/depth items under D2/D4/D1;
  they are not high defects, but their absence lowers the relevant dimension.
- ECS cannot rescue a poor PES: composite is capped at PES + 10 when PES <70, and at PES when PES <60.
  The existing high-defect caps still apply.


## 1. Prompt and comparison

Both conditions receive exactly this product prompt:

> Build a playable, offline 2D sandbox game inspired by Minecraft.
>
> It must run by opening `index.html`, with no build step, external libraries, CDNs, or network
> access. Make it feel like a small Minecraft, save progress, and document the controls.

One-shot and XC start from the same seed. The XC condition may use workflow process tooling; it must
not receive extra product requirements. Evaluate anonymized A/B outputs; the evaluator must not know
the condition.

## 1b. v1.2 correction — discoverability and high-defect severity

A passive HUD key hint is not enough. A core system is discoverable only when the first-run UI has a
visible button/tutorial/quest entry that a new player can find without reading the README or guessing
a key. If crafting is reachable only by a passive `E craft` line, D4 ≤55 and D9 ≤70 even if the code
works. This rule applies to both conditions; it was added after a real user could not find Blockhaven's
crafting.

A high integrity defect cannot land at 65. v1.2 caps one high defect at **PES ≤55 / composite ≤55**;
two or more at **PES ≤45 / composite ≤45**; a blocker remains 20/30. The defect is a broken player
world, not a missing optional feature.

Report the **experience tier** separately from the composite:

- `polished`: PES ≥80, D5 ≥75, D4 ≥75;
- `solid`: PES 65–79 and D5 ≥60;
- `prototype`: PES <65 or D5 <55;
- `broken`: a blocker/high defect prevents normal play.

A high-defect artifact can be `prototype` even when its ECS is strong; engineering does not promote
the experience tier.

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

**Caps:** one high defect → PES ≤55, composite ≤55; two or more → PES ≤45, composite ≤45.
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
| D1 | Core verbs and controls | 10 | movement, jump, collision, mining, placing, camera; clear controls and refusal reasons; combat/health only if present |
| D2 | World generation, biomes and physics | 16 | seeded terrain, block variety, caves/ores/biomes/structures, water/sand behavior; a world worth exploring, not a flat strip |
| D3 | Mining and placement feedback | 10 | target/outline, break progress, particles/sound, animation, placement preview/refusal; actions read without explanation |
| D4 | Inventory, crafting and progression | 22 | counts/hotbar/backpack, **discoverable** gather→craft→build loop, recipes (grid or list), stations/tools, smelting/ingots, resource pressure, goals/progression. No fixed recipe count; no crafting/progression caps at 40; a hidden crafting entry point caps at 55 |
| D5 | Presentation, character, UI, audio | 18 | composition, character readability, movement/tool animation, readable HUD, lighting, sound/mute, atmosphere; a plain prototype ≤60 |
| D6 | Orientation and map | 6 | seed/position/time and a real minimap/map; coordinates/field notes alone ≤60 |
| D7 | Replay, objectives, combat | 8 | seed/new world, pause/help, goals/exploration loop, combat if present |
| D8 | Accessibility and responsive | 4 | keyboard/accessible labels, reduced motion, 800/960/1280 behavior, no clipping |
| D9 | First-run discoverability and docs | 6 | immediate play, visible core-system entry points, in-game help, short README; README cannot substitute for discoverability |

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

Experience floor/cap: if PES <70, composite ≤ PES + 10; if PES <60, composite ≤ PES.
High-defect caps still apply and take precedence. Report the experience tier separately.

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
