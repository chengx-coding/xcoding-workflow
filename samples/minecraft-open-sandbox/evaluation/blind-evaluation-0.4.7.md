# Blind Evaluation — M2D-SES-OSS v1.3

**Scope:** two anonymized artifacts, **A** and **B**, scored against `STANDARD.md` v1.3 and
`PROFILE-OPEN-SANDBOX.md` v1.3. The evaluator remained blind: no mapping, prior evaluation,
work-order context, or identity-bearing documentation was read. Only the two artifact trees, the
two rubric files, and the evaluation tooling were used. The report intentionally makes no
condition/identity inference.

**Artifacts (product names as delivered):** A = *Mosswild*; B = *Emberdeep*. Both are offline 2D
sandbox games that open from `index.html`.

**Environment:** Windows, headless Chromium via Playwright 1.62, viewport 1280×800 (desktop),
page served from `file://` with the browser context **offline**, device pixel ratio 1. Every
actuation reported as a pointer event was a real CDP mouse event at the control's rendered
position; keyboard actions were real key events. State was read from the page's own exposed game
objects after the fact, not used to synthesize clicks.

**Companion evidence:** screenshots in `blind-eval-shots/` (relative to this file), raw harness
outputs in `../../tmp/eval-047/` (`A3-eval.json`, `A-mining10-eval.json`, `B5-eval.json`,
`*-run.log`).

---

## 1. Headline

| | **A** | **B** |
|---|---:|---:|
| PES (75%) | **82.4** | **78.8** |
| ECS (25%) | **82.2** | **88.2** |
| **Composite** | **82.4** | **81.1** |
| Experience tier | **polished** | **prototype** (D5 < 55) |
| Art tier (pairwise) | **polished** (89) | **prototype** (51) |
| G1 offline boot | pass | pass |
| G2 no fatal errors | pass | pass |
| G3 save/recovery | pass | pass |
| High defects | none | none |
| Medium defects | 1 | 1 |
| Caps applied | none | none |

A wins the composite by **1.3 points**. The margin is narrow and is dominated by the D5 art
difference; B is the stronger engineering artifact and the better-oriented game. The v1.3
pairwise-art rule is satisfied: A is clearly more polished, the D5 gap is **38 points (≥ 15)**,
and B is not called polished.

---

## 2. Gates

**G1 — offline boot.** Both pages opened from `file://` in an offline context. No `http(s)` or
protocol-relative resources were requested or referenced; `performance` resource list contained no
external entries. A canvases at 1280×800 (fills viewport); B at 1152×648 (letterboxed, see D5/D8).
No build step, package manager, or network dependency was used. **Pass / pass.**

**G2 — no fatal errors.** Zero page errors and zero console errors across boot, play, mining,
crafting, save/reload, corrupt-save boot, and viewport changes for both candidates. The fatal-error
region stays hidden in both; status markers reach `ready`. Producer page checks also pass for both.
**Pass / pass.**

**G3 — save/recovery.** A: versioned save (`v: 1`), manual pause save, autosave; reload resumed the
same world (`loadedFromSave: true`) with quest 08/08, all flags, inventory, health, position and
clock intact. B: versioned+validated save; reload produced a title with **CONTINUE** and a summary
(Day 1 · 34 blocks mined · 1m 25s), and continuing restored stage 8, all eight completed stages,
inventory and world. A corrupt payload injected before app scripts read it produced, in A, a clear
toast (“The old save could not be read. A new world begins…”) and a fresh world; in B, a title with
**ENTER WORLD** and “The saved meadow could not be read. A fresh one awaits.” Neither page failed to
boot. **Pass / pass.**

---

## 3. Interaction truth (v1.3)

### 3.1 Real-pointer mining trials

| Check | A | B |
|---|---|---|
| Trials executed | 10 | 10 |
| Blocks actually removed | **10/10** | **10/10** |
| pointerdown target == pointerup target | yes (`canvas#game`) | yes (`canvas#game`) |
| Minimum hold (client-side `timeStamp` delta) | **1905.8 ms** | **707.0 ms** |
| Hold ≥ 90 ms | yes, every trial | yes, every trial |
| Synthetic `element.click()` on canvas | **did not mine** (1→1) | **did not mine** (2→2) |

A's focused 10-trial run (`A-mining10-eval.json`) verified the hovered tile before each press; A's
camera applies a mouse look-ahead, so the harness settled the camera before pressing (a human sees
the highlight move with the cursor and clicks it; this is presentation, not a control defect). A's
own browser check independently reports 10/10 (900 ms holds).

### 3.2 Enabled-looking no-op audit

Every visible primary control was exercised with a real pointer at its rendered position, and the
effect was read back:

- **A:** HELP (opened guide), SOUND (aria-pressed true→false, label SOUND→MUTED), quest collapse,
  tutorial dismiss, hotbar slot 1↔2 selection, pack open via `E`, recipe CRAFT buttons, backpack
  bind chip, pause → **Save now**, **Resume**, **Keep wandering** (done state), close buttons.
- **B:** title **Enter world**, title **Controls**, HUD `?` help, hotbar slot click, `E` inventory,
  recipe **Craft** buttons, inventory slot move, pause **Save now** / **Resume** / **Controls** /
  **Mute**, **Quit to title**, victory **Keep building**, title **Continue**.

No control was found that looked enabled, accepted a real press, and silently did nothing. The only
presses that produce no action are the intentionally **disabled** craft buttons; both artifacts mark
them visibly disabled with a reason (below). **No high-severity interaction defect in either.**

### 3.3 Crafting with insufficient materials (must explain what is missing)

**A.** With no stone/sticks and no workbench, `stone_pickaxe` renders disabled, label `BENCH`,
title “Place a workbench near you to unlock this recipe.”, and visible missing chips
**“Stone 0/3”, “Stick 0/2”, “needs a placed workbench nearby”**; the bench status reads “No
workbench nearby”. A real press on the disabled button landed pointerdown/up on
`button.craft-button` (same target, 155 ms) and produced **no click event, no inventory change, no
toast**. This meets the rule's “visibly disabled with a reason” branch. Handcraft recipes behave
the same way with their own missing counts (e.g. `Oak Log 0/1`).

**B.** With no wood, all 15 recipe rows are `LOCKED`, each input shows its count in red, and the
button title states the reason (“Missing materials” or “Needs a nearby workbench”). A real press on
the locked `planks` button landed on `button.btn` (same target, 155 ms), produced **no click event,
no count change, no toast**. Same rule branch.

### 3.4 Crafting with sufficient materials (must produce output and update counts)

**A (real UI clicks, real gathered logs):** 4 oak logs gathered by holding LMB on a trunk →
`planks` ×4 consumed 4 logs (→16 planks) → `workbench` (→10 planks, 1 workbench) → `sticks`
(→8 planks, 4 sticks). Counts and recipe rows refreshed after each click; toasts confirmed “Crafted
Workbench.” / “Field note updated”.

**B (real UI clicks, real gathered wood):** 4 oak logs → `planks` ×4 (→16 planks) → `workbench`
(→1) → `sticks` (→4); counts updated. Placed workbench: **stage 2**. Then wooden pickaxe (stage 3),
3×2 stone dig (6 stone), stone pickaxe (stage 4), torch (stage 5), furnace + 3 smelts + iron pickaxe
(stage 6), 3 ember ore mined (stage 7), 3 shards + bricks + beacon crafted and placed → **stage 8,
victory overlay visible**. Every craft button was clicked at its rendered position after scrolling
it into view; every placement used a real right-button press.

---

## 4. Underground 3×2 dig

Both candidates were teleported to a natural stone pocket, then six exposed stone tiles in a
3-wide × 2-high wall were removed with real pointer holds.

- **A:** all six tiles 3 → 0 (`[92,55]…[94,56]`), with the pickaxe selected (tier 1, then tier 2).
  Screenshot `A-underground-dig.png`: the removed pocket shows the **cave backdrop**, ore glints and
  stone texture; no sky or blank canvas, player remains on the floor. **No high defect.**
- **B:** all six tiles 3 → 0 (`[49,97]…[51,98]`) after the wooden pickaxe was crafted. Screenshot
  `B-underground-dig.png`: the opening reads as a dark tunnel with the cave backdrop and a small
  pickaxe highlight; no sky. **No high defect.**

Both candidates also rendered night scenes (A: star/moon sky, lantern/campfire pools; B: night HUD,
one hollow spawned) and both keep a sealed world floor (A bedrock layer, B solid bottom row; B's
test suite asserts it).

---

## 5. Save / reload

- **A:** pause → **Save now** (real press; “Saved · just now”) → reload → auto-resume in the same
  world with **quest 08/08**, `lanternPlaced`, inventory, health, clock and workbench-near state
  intact (`loadedFromSave: true`). Corrupt payload → fresh world with explanatory toast, no fatal.
- **B:** pause → **Save now** → reload → title **CONTINUE** with saved summary → continue → stage 8,
  all eight completed stages, inventory and world restored; **Save now** shows `Saved · just now`.
  Corrupt payload → fresh-world title and explanatory toast, no fatal.

---

## 6. Map / orientation

- **A:** **no minimap and no coordinates/position readout.** HUD exposes clock/day, help, sound,
  fullscreen, field notes and hotbar; the seed appears only in the pause panel. D6 is therefore
  capped at 60 and scored at **40**.
- **B:** a real minimap (`228×136` canvas, pixel variance 1604, not blank), live
  **`X 33 · Y 91`** coordinates, and a depth band label (`Surface`, `Shallow caves`, `Ember band`).
  D6 **88**.

---

## 7. Responsive / accessibility checks

| Width | A | B |
|---|---|---|
| 800×800 | canvas 800×800, no overflow, no clipped HUD | canvas 800×450 (scaled), no overflow |
| 960×800 | 960×800, no overflow | 960×540, no overflow |
| 1280×800 | 1280×800, no overflow | fixed 1152×648 at x=64 (black bars), no overflow |

A fills the viewport at all required widths; B preserves a fixed 24-column view and letterboxes at
1280. Both expose aria labels/roles (canvas label, hotbar `role="toolbar"`, status/toast live
regions, labelled buttons) and keyboard control. A additionally has fullscreen and sprint; B has a
quit-to-title flow. Neither was tested on touch/mobile.

---

## 8. PES scores

| ID | Dimension | Weight | A | B | Why |
|---|---|---:|---:|---:|---|
| D1 | Core verbs and controls | 10 | **90** | **86** | A: walk/jump/sprint, AABB collision, mine/place with tool tiers, tool durability, combat, hearts, death/respawn, fullscreen, clear refusal text. B: same core minus sprint/fullscreen, with hold-jump, tool-tier gating and “out of reach/needs a pickaxe” refusals. |
| D2 | World generation, biomes, physics | 16 | **77** | **83** | A: fBm hills, caves, three ore depths, varied trees, spawn stair/camp light; no biome/water/sand. B: ridge/detail terrain, caves, coal/iron/ember bands, desert sand band, larger 360×140 world; no fluids. |
| D3 | Mining/placement feedback | 10 | **86** | **80** | A: hover outline, target tooltip, break progress, particles, material sounds, placement preview/refusal, swing animation. B: target brackets/crack overlay, particles, refusal toasts, progress, but less explicit placement preview. |
| D4 | Inventory, crafting, progression | 22 | **84** | **87** | A: 16 recipes, workbench station, tool tiers/durability, 8-step field-note chain to the Lantern, bind-to-hotbar; no furnace/smelting. B: 15 recipes, workbench + furnace stations, smelting ingots, stone bricks, 36-slot grid with move/merge, 8-stage journey to the Beacon; discoverable from title cards/journey/controls. |
| D5 | Presentation, character, UI, audio | 18 | **89** | **51** | Pairwise art table below. A is a layered, cohesive pixel presentation; B is a plain prototype. Audio exists in both (procedural WebAudio, mute) but was not audible in headless. |
| D6 | Orientation and map | 6 | **40** | **88** | A has neither map nor coordinates (seed only in pause). B has a working minimap, coordinates and depth labels. |
| D7 | Replay, objectives, combat | 8 | **86** | **84** | A: 8-step quest with narrative field notes, night hollows, health/death/respawn, new-world confirm, celebration. B: 8-stage journey tracker, night hollows, death/respawn, new world, quit-to-title, victory screen. |
| D8 | Accessibility and responsive | 4 | **86** | **82** | A: viewport-filling responsive canvas, labelled controls, fullscreen, live regions. B: fixed-aspect scaling/letterbox, labelled controls, live regions. Both keyboard-playable. |
| D9 | First-run discoverability and docs | 6 | **88** | **88** | A: immediate play, tutorial card, prominent Field Notes, help panel, short README. B: one-click title, three first-run control cards, Controls panel, journey tracker, README. Both name `E` as the crafting entry; neither has a clickable Craft button, so the entry is tutorial/quest text rather than a button. Because it is a first-run tutorial/quest panel rather than a passive HUD key line, the v1.2 55/70 caps were **not** applied; reading it more strictly would cap both equally and would not change the ordering. |

**PES (A)** = 0.10·90 + 0.16·77 + 0.10·86 + 0.22·84 + 0.18·89 + 0.06·40 + 0.08·86 + 0.04·86 + 0.06·88 = **82.4**
**PES (B)** = 0.10·86 + 0.16·83 + 0.10·80 + 0.22·87 + 0.18·51 + 0.06·88 + 0.08·84 + 0.04·82 + 0.06·88 = **78.8**

No PES floor/cap applies (both PES > 70); no high defect exists; neither candidate has three or
more medium defects.

---

## 9. D5 — blind pairwise art

Matched states: surface day at 1280×800, inventory/crafting, underground after the 3×2 dig, and
night. Screenshots: `A-day.png` / `B-day.png`, `A-crafted.png` / `B-crafted.png`,
`A-underground-dig.png` / `B-underground-dig.png`, `A-night.png` / `B-night.png`,
`A-completion.png` / `B-victory.png`.

| Sub-score | Max | A | B | Evidence |
|---|---:|---:|---:|---|
| Composition | 5 | **4.5** | **2.0** | A: layered parallax mountains, horizon, foreground flowers/tufts, balanced panels. B: large empty sky, tiny character, flat ground band, letterboxed canvas. |
| Character readability / animation | 5 | **4.5** | **2.0** | A: hat/face/tool silhouette readable at 1280; walk bob, leg lift, arm/tool swing, air pose. B: one-tile body, simple walk; readable only when close. |
| Asset detail | 3 | **2.6** | **1.5** | A: procedural textures per block, tree/leaf variation, ores, flowers, glows. B: flat block textures, simple trees, minimal scene props. |
| UI / typography coherence | 3 | **2.7** | **2.2** | A: cohesive pixel-paper HUD, field-notes card, hearts, hotbar readout, toasts/tooltips. B: clean dark panels and readable type, but generic and spatially loose. |
| Atmosphere / lighting | 2 | **1.7** | **1.5** | A: sky palettes, sun/moon, torch/lantern pools, campfire, particles. B: day/night tint, torch glow, cave darkness; weaker depth. |
| **Total / 18** | 18 | **16.0** | **9.2** | |
| **D5 scaled** | 100 | **89** | **51** | |
| **Art tier** | | **polished** | **prototype** | |

A is clearly more polished; the gap is **38 points**, satisfying the v1.3 “at least 15” rule, and B
is not described as polished anywhere. `A-completion.png` (Lantern end modal over a lit valley) and
`A-night.png` are the strongest evidence; `B-victory.png` is clean but plain, and `B-day.png` shows
the composition weakness directly.

---

## 10. ECS scores

| ID | Dimension | Weight | A | B | Why |
|---|---|---:|---:|---:|---|
| E1 | Tests and verification | 30 | **82** | **90** | A: 29 Node tests (determinism, spawn, terrain, block access, serialization, content) plus CDP browser check and full quest check; all executed green. B: 80 Node tests across worldgen, blocks, light, player, inventory, crafting, progression, mobs, save; plus CDP browser check (10 pointer trials, negative control, save/reload) and page check; all green. |
| E2 | Architecture and readability | 25 | **72** | **86** | A: clear UMD modules (world/player/inventory/art/render/ui/audio), but `main.js` is ~2,230 lines and holds loop, input, mining, enemies, saves and quest wiring; `ui.js` ~950 lines. B: 15 focused modules, `main.js` ~1,150 lines, clear save/input/light/mobs/progression boundaries. |
| E3 | Robustness, persistence, security | 20 | **88** | **90** | Both: versioned, validated saves, corrupt fallback with a message, bounded world access, no network/unsafe HTML, deterministic test of malformed payloads. B adds explicit schema/version validation and save-error reporting; A has a fatal-error surface and storage-unavailable path. |
| E4 | Performance, accessibility, responsive | 15 | **88** | **86** | Both run stable loops with no console spam. A fills 800/960/1280 without clipping; B scales but letterboxes at 1280. Both expose aria roles/labels and keyboard control. |
| E5 | Documentation and tooling | 10 | **88** | **88** | A: thorough README, controls, architecture table, three reproducible checks. B: thorough README, controls, layout table, two checks. Both documented commands executed successfully. |

**ECS (A)** = 0.30·82 + 0.25·72 + 0.20·88 + 0.15·88 + 0.10·88 = **82.2**
**ECS (B)** = 0.30·90 + 0.25·86 + 0.20·90 + 0.15·86 + 0.10·88 = **88.2**

---

## 11. Composite

`composite = 0.75 × PES + 0.25 × ECS`

- **A:** 0.75 × 82.4 + 0.25 × 82.2 = **82.4**
- **B:** 0.75 × 78.8 + 0.25 × 88.2 = **81.1**

**Caps:** none. No high defects, no blocker, PES > 70 for both, and neither has three medium defects.
**Experience tier:** A **polished** (PES ≥ 80, D5 ≥ 75, D4 ≥ 75). B **prototype** under the v1.3
tier rule because D5 = 51 < 55, even though its gameplay and engineering are complete; this is an
art/experience tier, not an integrity judgement.

---

## 12. Signature coverage

| Signature | A | B |
|---|---|---|
| Seeded world larger than a flat strip | Yes — 224×96, fBm hills, caves, three ore depths, trees, spawn stair/camp | Yes — 360×140, ridge/detail terrain, caves, coal/iron/ember bands, desert band, trees |
| Mine/place with readable feedback | Yes — hover outline, tooltip, progress, particles, sound, refusal text | Yes — target brackets, crack overlay, particles, refusal toasts |
| Inventory/hotbar with counts | Yes — 9-slot hotbar + backpack, counts, selected tool readout | Yes — 9 hotbar + 36 slots, counts, move/merge |
| Crafting/progression loop | Yes — 16 recipes, workbench station, tool tiers/durability, 8-step Lantern quest; no smelting | Yes — 15 recipes, workbench + furnace, smelting/ingots/bricks, 8-stage Beacon journey |
| Save/restore | Yes — versioned save, autosave, manual save, resumed world | Yes — versioned/validated save, autosave, title Continue |
| Day/night or atmosphere | Yes — 5-min cycle, palettes, sun/moon, lighting | Yes — day/night cycle, night hollows, torch light |
| Orientation/minimap | **No** — no map, no coordinates | Yes — real minimap, coordinates, depth labels |
| Objectives/exploration loop | Yes — Field Notes with 8 steps and completion modal | Yes — Journey tracker with 8 stages and victory modal |
| Combat | Yes — night Hollows, swords, health/death/respawn | Yes — night hollows, swords, health/death/respawn |

Both signature loops were **completed end-to-end**: A reached the Warden's Lantern (quest 08/08,
`lanternCrafted`/`lanternPlaced`); B reached the Ember Beacon (stage 8, all eight stages, victory
overlay). Both persisted the completed state across reload.

---

## 13. Defects

### A
- **Medium A-M1 — no spatial orientation.** No minimap and no coordinates/position readout
  (`A3-eval.json → orientation.hasMinimap=false, hasCoords=false`; HUD body text has only clock/day,
  controls, field notes, hotbar; seed is pause-only). D6 = 40.
- **Low A-L1 — HUD occlusion.** The Field Notes card and first-morning tutorial card cover a
  noticeable part of the 1280×800 playfield; the tutorial is dismissible.
- **Low A-L2 — unexecuted checks.** Audio and fullscreen were not verifiable in headless; they are
  code-read only.
- No high defects. Underground dig, placement, save/reload and completion all held.

### B
- **Medium B-M1 — weak in-game first frame / composition.** Surface scene is dominated by empty
  sky, the character is one tile tall, and the fixed 1152×648 canvas is letterboxed at 1280×800.
  This is the D5 evidence, not an integrity failure.
- **Low B-L1 — seed not displayed.** The save summary shows day/blocks/playtime but not the seed,
  so players cannot record/share it.
- **Low B-L2 — no sprint and no fullscreen** (scope choice), lowering D1/D8 slightly.
- No high defects. 3×2 dig, placement, save/reload, furnace/ember/beacon chain and completion all held.

Neither artifact has a high defect; both medium counts are 1, so the “three or more medium → −10”
composite cap does not apply.

---

## 14. Executed evidence

All commands were run from each artifact root; raw output kept in `../../tmp/eval-047/`.

**Node tests**
- A: `node --test "tests/**/*.test.js"` → **29 pass, 0 fail**.
- B: `node --test "tests/**/*.test.js"` → **80 pass, 0 fail**.

**Producer checks**
- A: `python tools/page_check.py` → ok (no external refs, canvas colour buckets 229);
  `node tools/browser_check.mjs` → ok (10/10 pointer, min hold 351 ms, save/reload, night, combat);
  `node tools/quest_check.mjs` → ok (full quest to 08/08, death, pause).
- B: `python tools/page_check.py` → ok (buckets 142); `node tools/browser_check.js` → ok
  (first-run title, 10/10 pointer, min hold 351 ms, synthetic click negative control, placement,
  save/reload, crafting via UI, night threat, inventory screen).

**Independent Playwright harness (this evaluation)**
- A: 10/10 real-pointer mining at 1906 ms minimum, same target, `element.click()` negative control
  did not mine; crafting insufficient/sufficient; 4 logs gathered; workbench crafted/placed; 3×2
  stone dig 6/6; stone pickaxe; 3 coal + 3 iron mined; Lantern crafted/placed → **08/08**; save/
  reload; corrupt-save boot; 800/960/1280 responsive.
- B: 10/10 real-pointer mining at 707 ms minimum, same target, negative control did not mine;
  crafting insufficient/sufficient; 4 wood gathered; workbench placed; wooden pickaxe; 3×2 stone dig
  6/6; stone pickaxe; torch placed; furnace + 3 smelts + iron pickaxe; 3 ember ore mined; shards +
  bricks + beacon crafted/placed → **stage 8**; save/reload; corrupt-save boot; 800/960/1280
  responsive; minimap/coordinates.

---

## 15. Comparison and conclusion

**A** is the experience-first artifact: strong composition, readable character and animation,
cohesive HUD/typography, atmospheric lighting, immediate play, and a complete 8-step Lantern
progression with a polished completion modal. Its weaknesses are the missing map/coordinates and a
less system-complete world/crafting set (no furnace/smelting, no biome band).

**B** is the engineering-first artifact: cleaner module boundaries, far more automated tests, a real
minimap with coordinates/depth, a larger world with a desert band and an ember layer, and a deeper
station chain (workbench + furnace, smelting, ingots, bricks, Beacon). Its weakness is presentation:
plain pixel art, a sparse surface composition, a small character, and a letterboxed fixed canvas.

Under v1.3's 75% PES weighting and its explicit art emphasis, **A edges B on composite, 82.4 to
81.1**. The margin is inside one art sub-score step: if B's D5 were scored at the top of the
“plain prototype” band (60) rather than 51, the composites would be effectively tied, and B would
lead on a stricter engineering/orientation weighting. The defensible conclusion is:

- **A wins the experience/composite comparison**, driven by D5 (89 vs 51) and small D1/D3/D7 edges.
- **B wins engineering (88.2 vs 82.2), orientation (88 vs 40), world breadth and station depth.**
- **Neither artifact is broken.** Both pass G1–G3 with no high defects, both complete their
  signature loop, both save/reload, and both disable unavailable recipes with visible reasons rather
  than offering an enabled-looking no-op.

---

## 16. Evidence limits

- Audio (procedural WebAudio) was not audible in headless; mute/toggle state was exercised, but sound
  quality is code-read only.
- Fullscreen cannot be meaningfully verified headless; A's FULL button was not exercised beyond its
  presence.
- No touch/mobile testing; only 800/960/1280 desktop widths.
- Late-game material provisioning was instrumented to keep runtime reasonable: A's coal/iron blocks
  were placed into an underground air pocket with the page's world data and then **mined with real
  pointer presses**; B's cobble/coal/iron ore/ingots were granted through the page's own test hook for
  the furnace/ember/beacon chain, while every craft/placement remained a real pointer action. Early
  loops (logs/wood → planks → workbench → wooden/stone tools → first dig/torch) were gathered/mined
  with real pointer holds in both.
- A's night sample at 2.5 s after setting 22:00 showed 0 enemies (spawn timer); the producer's check
  at ~5 s showed 1 enemy and combat damage 7 → 5.6. B's independent night sample showed 1 hollow and
  night state true.
- One evaluator; art sub-scores are a documented judgement with the matched screenshots supplied.
- Identity was not inferred or revealed; the report deliberately uses only blind labels A and B.
