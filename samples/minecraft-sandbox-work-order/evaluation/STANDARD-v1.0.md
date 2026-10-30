# M2D-SES v1.0 — Minecraft-like 2D Sandbox Evaluation Standard

> **Historical v1.0.** Superseded by [`STANDARD.md`](STANDARD.md) / [`SCORE-SHEET.md`](SCORE-SHEET.md) (v1.1). Retained for the 0.3.3–0.3.6 scores and provenance.

> **Fixed sample evaluation standard (v1.0).** Every sample run is scored with this rubric. Changes require a deliberate revision, a new version number and a new score sheet; completed score sheets are retained as history.

A detailed, reproducible rubric for evaluating 2D sandbox games that aim at the Minecraft fantasy.
It separates **coverage** (which Minecraft systems exist), **depth/quality** (how well the present
systems work), **core demo playability**, and **extras/innovation/controversy**. It is deliberately
stricter than a normal game jam rubric: a small demo can score well on execution while still scoring
low on Minecraft completeness.

Research snapshot: 2026-10-29. External references are used as domain background, not as
instructions.

## 1. Research basis

The rubric's system inventory is grounded in the Minecraft Wiki and related references:

- [Minecraft](https://minecraft.wiki/w/Minecraft) — game modes, mobs, multiplayer, the sandbox frame.
- [Crafting](https://minecraft.wiki/w/Crafting) — 2×2 inventory grid, 3×3 crafting table, shaped/
  shapeless/fixed recipes, recipe book, automated crafter.
- [Inventory](https://minecraft.wiki/w/Inventory) — hotbar, 27 storage slots, armor/offhand, stacks,
  containers, recipe book.
- [Health](https://minecraft.wiki/w/Health) — hearts, damage, regeneration, death.
- [Hunger](https://minecraft.wiki/w/Hunger) — hunger/saturation, eating, sprinting, starvation.
- [Mob](https://minecraft.wiki/w/Mob) — passive/hostile/neutral mobs, spawning, AI, drops, breeding.
- [Biome](https://minecraft.wiki/w/Biome) — 60+ Overworld biomes, climate/vegetation/mob variation.
- [Water](https://minecraft.wiki/w/Water) — source blocks, flow distance/speed, fluid interactions.
- [Sand](https://minecraft.wiki/w/Sand) — gravity-affected blocks, falling behavior.
- [Redstone mechanics](https://minecraft.wiki/w/Redstone_mechanics) — power, conductivity, ticks,
  components, circuits, automation.
- [Daylight cycle](https://minecraft.wiki/w/Daylight_cycle) — 20-minute day, sun/moon/stars, light.

Known systems not separately fetched but covered by the overview and standard Minecraft knowledge:
weather, structures, farming, trading, enchanting, brewing, bosses, dimensions, multiplayer/PvP.

## 2. 2D adaptation

The target is a 2D browser sandbox, not a 3D clone. Criteria are scored on a **2D-equivalent** basis:

- 3D-only geometry (e.g., 3D redstone dust orientation, 3D mob pathfinding) is adapted to 2D
  equivalents; absence of 3D alone is not penalized.
- A system can be simplified but must preserve its **decision space**: e.g., a 2D crafting grid can
  be 2×2/3×3 or a recipe list, but it must consume inputs, produce outputs, and support progression.
- A decorative hint (a "water" texture that does not flow) scores at most 1-2, not as a working
  fluid.
- Visuals and audio are judged as presentation, not as substitutes for missing mechanics.

## 3. Tiers

- **T0 — demo core:** must exist for the artifact to be playable: boot/offline, seeded terrain and
  strata, movement, jump/gravity/collision, camera, mining, placing, hotbar, save/load.
- **T1 — expected sandbox:** block variety, inventory/counts, simple recipes, terrain/atmosphere
  variety, health/damage, basic feedback/help, tests.
- **T2 — Minecraft systems:** crafting table/tiers, tools/durability, hunger/armor/hazards,
  mobs/combat, fluids/gravity blocks, weather, redstone basics, minimap/map, containers, structures/
  ores.
- **T3 — advanced:** redstone logic/automation, enchanting/brewing, boss/stronghold encounters,
  complex mob AI, farming/trading, multiplayer/PvP, seasons/temperature.

## 4. Score anchors

Each criterion is scored 0-5:

| Score | Meaning |
| ---: | --- |
| 0 | Absent; no code, UI or behavior. |
| 1 | Cosmetic/stub: a label, texture, static prop or a non-functional hint. |
| 2 | Minimal functional: one basic case works, shallow or fragile. |
| 3 | Functional with reasonable breadth: multiple cases, understandable rules, some feedback. |
| 4 | Deep/polished: robust edge cases, good feedback, integrated with other systems. |
| 5 | Minecraft-grade for a 2D adaptation: broad, systemic, testable, and delightful. |

For **coverage**, count a criterion as present only at score ≥2. Coverage is the **unweighted share
of all 86 criteria** that are present: `present count / 86`. For **depth**, average only the present
criteria (score ≥2); absent criteria do not inflate depth.

## 5. Domain weights

| Domain | Weight | Why |
| --- | ---: | --- |
| D1 Core loop and controls | 10 | The game must be playable at all |
| D2 World generation and biomes | 10 | The Minecraft world is the first differentiator |
| D3 Terrain physics, fluids, weather | 8 | Sand/water/weather are signature systemic behaviors |
| D4 Blocks, mining, building | 10 | The core verb pair |
| D5 Inventory and items | 8 | Carrying, stacking and using items |
| D6 Crafting and progression | 8 | Minecraft's progression spine |
| D7 Survival: health, hunger, death | 7 | Survival mode's pressure |
| D8 Mobs and combat | 7 | The world's living challenge |
| D9 Redstone and automation | 6 | Minecraft's engineering ceiling |
| D10 Day/night, weather, atmosphere | 6 | Time and ambience |
| D11 UI/UX, audio, accessibility | 10 | The interface through which everything is read |
| D12 Persistence, engineering, tests | 10 | A browser sandbox must be reliable |
| **Total** | **100** | |

Within a domain, criteria are averaged; criteria marked **C** (critical) count double. Domain score
is 0-5. Overall base score = Σ(domain weight × domain score) / 100, then ×20 for a 0-100 scale.

**Core demo index.** Record a separate **T0/T1 sub-score** (0-5) for each domain, using only that
domain's T0/T1 criteria. The core demo index is the weighted average of those sub-scores over the
domains that contain at least one T0/T1 criterion, renormalized to those domains' weights. D3 and D9
contain only T2/T3 criteria and are excluded from the core subset. Record the sub-scores in the score
sheet so the index is reproducible.

**Coverage.** Record per-domain `present / total` criterion counts. Coverage is the sum of present
criteria divided by 86. Do not weight coverage by domain weight; it is a breadth count.

## 6. Criteria

### D1 Core loop and controls (10)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| C1 | Boots and runs from `file://`, no server/build | T0 | C | Open page, status marker, no console error |
| C2 | Horizontal movement with acceleration/friction | T0 | C | Input changes player x, animation |
| C3 | Gravity, jump, solid collision on both axes | T0 | C | Fall, jump, wall/floor/ceiling cases |
| C4 | Camera follows and clamps to world bounds | T0 | 1 | Camera target/bounds |
| C5 | Mining a block within reach | T0 | C | Target, break, drop, range rejection |
| C6 | Placing a block in a valid cell | T0 | C | Occupancy/support/player rules |
| C7 | Input breadth: keyboard/mouse/wheel, remap or clear hints | T1 | 1 | Controls help, keys |
| C8 | Pause/help/tutorial and recoverable state | T1 | 1 | Pause/help overlay, resume |

### D2 World generation and biomes (10)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| W1 | Deterministic seed → same world | T0 | C | Seed input, repeat generation |
| W2 | Layered terrain with grass/dirt/stone/bedrock | T0 | C | Column strata, invariants |
| W3 | Trees/flora/decorations | T1 | 1 | Trees, flowers, grass |
| W4 | Caves/overhangs/underground volume | T1 | 1 | Cave generation, enclosed spaces |
| W5 | Biome variety with distinct terrain/vegetation | T2 | 1 | ≥3 biomes, biome-specific content |
| W6 | Ores/minerals with distribution | T2 | 1 | Coal/iron/etc. in stone |
| W7 | Structures/landmarks (villages, ruins, etc.) | T2 | 1 | Generated set pieces |
| W8 | World size, bounds and spawn logic | T1 | 1 | Finite/infinite boundary, spawn safety |

### D3 Terrain physics, fluids, weather (8)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| P1 | Sand/gravel gravity and stacking | T2 | 1 | Falling block updates |
| P2 | Water source/flow and level | T2 | 1 | Source, spread, flow distance |
| P3 | Fluid interactions (water+lava, currents) | T3 | 1 | Obsidian/stone, push/drag |
| P4 | Rain/snow/thunder or weather state | T2 | 1 | Weather cycle, visuals, effects |
| P5 | Light propagation and darkness | T2 | 1 | Sky/block light, caves |
| P6 | Fire/spread or other environmental hazard | T3 | 1 | Ignition, spread, extinguish |

### D4 Blocks, mining, building (10)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| B1 | Block variety with distinct identities | T1 | 1 | ≥6 materials, icons, names |
| B2 | Hardness/tool requirements/mining time | T2 | 1 | Tool-specific speed, drops |
| B3 | Break progress, particles, sound | T1 | 1 | Cracks, particles, audio |
| B4 | Placement validity, support, occupancy, player overlap | T0 | C | Rejection feedback |
| B5 | Block entities (chest, furnace, door, sign) | T2 | 1 | Stateful blocks, GUIs |
| B6 | Building at meaningful scale (multi-block structures) | T1 | 1 | Build, undo/redo, persistence |
| B7 | Drops/inventory integration | T1 | 1 | Mined item enters inventory |

### D5 Inventory and items (8)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| I1 | Hotbar selection and visible selected state | T0 | C | Keys/wheel, highlight |
| I2 | Inventory grid or equivalent storage | T1 | 1 | Slots, open/close, move items |
| I3 | Stacks/counts and capacity | T1 | 1 | Counts, stack limits |
| I4 | Tools/durability/equipment | T2 | 1 | Tool items, wear, armor |
| I5 | Item use/equip/offhand | T2 | 1 | Consume, place, equip |
| I6 | Containers/chests/shared storage | T2 | 1 | Transfer between inventories |
| I7 | Drop/pickup and item entities | T2 | 1 | World item, collect |

### D6 Crafting and progression (8)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| K1 | Crafting UI/grid or recipe interface | T1 | 1 | Inputs → output |
| K2 | Recipe set with shaped/shapeless logic | T2 | 1 | ≥5 useful recipes |
| K3 | Crafting table / tiered station | T2 | 1 | Place/use station |
| K4 | Smelting/furnace/cooking | T2 | 1 | Fuel, input, output, time |
| K5 | Tool tiers and progression gates | T2 | 1 | Wood→stone→iron etc. |
| K6 | Progression chain (resources → tools → capability) | T2 | 1 | Clear next-step loop |
| K7 | Automated crafting/processing | T3 | 1 | Crafter/hopper-like |

### D7 Survival: health, hunger, death (7)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| S1 | Health/damage and feedback | T1 | C | Hearts, hurt, heal |
| S2 | Hunger/saturation/eating | T2 | 1 | Food, hunger bar, sprint gate |
| S3 | Death/respawn and consequences | T1 | 1 | Death screen, respawn |
| S4 | Armor/defense | T2 | 1 | Equip, damage reduction |
| S5 | Potions/enchanting/status effects | T3 | 1 | Brewing/enchanting/effects |
| S6 | Hazards: fall, drown, fire, lava | T2 | 1 | Environmental damage |
| S7 | Difficulty/status effects/regeneration rules | T3 | 1 | Difficulty-dependent behavior |

### D8 Mobs and combat (7)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| M1 | Passive/ambient mobs | T1 | 1 | Animals, birds, fish |
| M2 | Hostile mobs and spawning rules | T2 | 1 | Light/biome/time spawning |
| M3 | Mob AI/pathfinding | T2 | 1 | Wander, chase, avoid |
| M4 | Melee/ranged combat and knockback | T2 | 1 | Attack, cooldown, damage |
| M5 | Drops/breeding/taming | T2 | 1 | Loot, feed, follow |
| M6 | Boss/stronghold encounters | T3 | 1 | Boss AI, arena |
| M7 | Multiplayer/PvP | T3 | 1 | Shared world/opponents |

### D9 Redstone and automation (6)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| R1 | Power source and wire transmission | T2 | 1 | Signal strength, distance |
| R2 | Logic gates/comparators/repeaters | T3 | 1 | AND/OR/NOT, delay |
| R3 | Actuators: piston, door, lamp, dispenser | T2 | 1 | Signal → state change |
| R4 | Sensors: pressure plate, button, observer | T3 | 1 | Input events |
| R5 | Automated farm/sorter/machine | T3 | 1 | Multi-component build |
| R6 | Tick/timing semantics | T3 | 1 | Delays, pulses, order |

### D10 Day/night, weather, atmosphere (6)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| L1 | Daylight cycle with time state | T1 | C | Clock, sun/moon movement |
| L2 | Sky/light/ambient change | T1 | 1 | Stars, colors, light |
| L3 | Weather cycle | T2 | 1 | Rain/snow/thunder |
| L4 | Seasons/temperature | T3 | 1 | Seasonal biome change |
| L5 | Ambient particles/audio | T1 | 1 | Fireflies, birds, wind |
| L6 | Biome-specific ambience | T2 | 1 | Desert vs forest mood |

### D11 UI/UX, audio, accessibility (10)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| U1 | Distinct visual identity/art direction | T1 | C | Coherent palette, typography |
| U2 | HUD information hierarchy | T1 | C | Seed, position, time, biome, status |
| U3 | Minimap/map or spatial aid | T2 | 1 | World overview, viewport |
| U4 | Feedback/readability of actions | T1 | C | Toasts, outlines, hit/blocked |
| U5 | Menus/dialogs/tutorial | T1 | 1 | Help, new world, settings |
| U6 | Audio/soundscape and mute | T1 | 1 | Generated audio, volume |
| U7 | Responsive/full-window layout | T1 | C | 960/800/1440 no collision |
| U8 | Accessibility/reduced motion/keyboard | T2 | 1 | Reduced motion, focus, labels |
| U9 | Performance/DPR/canvas stability | T2 | 1 | Frame time, resize, DPR |

### D12 Persistence, engineering, tests (10)

| ID | Criterion | Tier | Wt | 2D evidence |
| --- | --- | --- | ---: | --- |
| E1 | Save/load of world and player | T0 | C | Reload restores state |
| E2 | Versioning/corruption safety/fallback | T1 | 1 | Bad payload handled |
| E3 | Offline/no external network | T0 | C | No CDN/fonts/fetch |
| E4 | Automated tests and coverage | T1 | 1 | Logic tests, meaningful cases |
| E5 | Architecture/modularity | T1 | 1 | Separation, readable code |
| E6 | Determinism/seed invariants | T2 | 1 | Reproducible generation |
| E7 | Performance/memory and no leaks | T2 | 1 | Long run, particles |
| E8 | Error handling/security | T1 | 1 | No XSS, safe storage, status error |

## 7. Extras, innovation, controversy

The rubric cannot enumerate every good or bad idea. Evaluate extras separately:

| Class | Definition | Score |
| --- | --- | --- |
| **Bonus** | A feature/integration not required by the rubric that adds fun, clarity, accessibility or depth without harming core use | +1 to +5 per item, capped +10 |
| **Penalty** | An extra that harms usability, performance, clarity or correctness (e.g., clutter, collisions, noisy effects, misleading UI) | −1 to −5 per item, capped −10 |
| **Controversial** | A design that some users will love and others dislike (e.g., permanent minimap/field-notes HUD, unlimited creative palette vs counted survival economy, autosave) | 0, recorded with both sides; may inform the penalty if it causes a concrete defect |

Extras are reported separately from the base score; a sensitivity line may show `base + extras`.
They must never be used to excuse a missing T0/T1 criterion.

## 8. Evaluation procedure

1. Read the prompt and both READMEs; confirm the artifact is the claimed build.
2. Capture 960×600 and 800×600 screenshots; inspect with an image tool.
3. Run the project's tests and page check; record results.
4. Inspect the code for each domain; mark criteria 0-5 with evidence.
5. Score each artifact independently; use a blind pass where possible.
6. Compute domain scores, base score, per-domain T0/T1 sub-scores (core demo index), and per-domain
   present/total counts (coverage/depth).
7. List extras, penalties and controversies separately.
8. Record the completed score sheet, including the per-domain sub-scores and present/total counts, in
   the sample's evaluation history; never delete prior results.
9. State limits: one run, static screenshots, no human play, no multiplayer.

## 9. Limits

- The rubric is Minecraft-inspired, not a claim that every 2D demo must implement all 60+ Minecraft
  biomes or 3D redstone.
- Scores are judgements anchored in evidence, not a precision measurement.
- Absence of a system is not a bug by itself; it is a coverage gap. A small demo can be excellent
  within T0/T1 while scoring low on T2/T3.
- The rubric is versioned; changes must be recorded and previous evaluations remain comparable.
