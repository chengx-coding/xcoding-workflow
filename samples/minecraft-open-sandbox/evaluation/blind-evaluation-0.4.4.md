# Blind evaluation — M2D-SES-OSS v1.2

**Artifacts:** A and B, scored independently from the same standard/profile
(`STANDARD.md`, v1.2; `PROFILE-OPEN-SANDBOX.md`, v1.2).
**Identity:** not inferred; A/B labels are kept. README files and prior evaluation material were
not read. No parent/workshop content was consulted.
**Method:** source review of every JS/CSS/HTML file that matters, the artifacts' own Node test
suites, a 21-step in-page self-test where present, and independent Chromium 151 (Python Playwright)
runs that exercise the page from `file://` with real pointer and keyboard input. Evidence files are
in `blind-evidence/`; executed commands and measurements are in
`blind-evidence/executed-checks.md`.

---

## 1. Verdict

| | A | B |
| --- | --- | --- |
| **PES (75%)** | **83.9** | **84.8** |
| **ECS (25%)** | **86.8** | **88.7** |
| **Composite** | **84.6** | **85.8** |
| **Experience tier** | **polished** | **polished** (one medium persistence defect) |
| High defects | none | none (one borderline-medium save/reload rendering defect, M1) |
| Caps applied | D6 ≤ 60 (no map) → D6 55 | none |

The two results are close and split by character rather than quality: **A is the stronger
experience artifact** (atmosphere, combat, tool depth, station-gated crafting); **B is the stronger
engineering and orientation artifact** (module boundaries, tests, minimap, explicit first-run
buttons). B's one real defect is a save/reload rendering regression described in M1; it is the
single largest quality difference behind B's otherwise higher engineering score.

---

## 2. Gates

| Gate | A | B |
| --- | --- | --- |
| **G1 Offline boot** | **Pass.** `file://` boot in Chromium; all scripts/CSS are local; static scan finds no `http(s)://`, CDN, `fetch`, `XHR`, WebSocket or `@import`; no build step. | **Pass.** Same `file://` boot; no network references; no build step. |
| **G2 No fatal errors** | **Pass.** Zero `pageerror`/`console.error` on first run, play, resize, save, reload, corrupt-save boot. Fatal-error panel stays hidden. | **Pass.** Zero `pageerror`/`console.error` across the same paths. (One `Canvas2D willReadFrequently` console warning appeared only when my harness called `getImageData`, not from the page loop.) |
| **G3 Save/recovery** | **Pass.** World (including original `surface`), player, inventory, tools, clock and quest flags all restore. Corrupt save is reported to the player and a fresh world starts. | **Pass with M1.** Player, inventory, blocks, clock and quests restore; corrupt save boots a fresh world. But the loaded world loses its `surface` array, so the underground presentation degrades (M1). Corrupt saves are discarded silently (M2). |

---

## 3. First-run affordance and discoverability (v1.2 focus)

**A — immediate play, no modal.** First frame is the game itself with a prominent **Field Notes**
quest card, a **starter-controls** card, **HELP/SOUND/FULL** buttons and a visible hotbar. There is
no clickable "crafting" button anywhere:
- the starter card lists `E pack` in a key legend;
- the hotbar help line repeats `E pack`;
- **HELP** (visible button) opens a guide whose "Shape the world" table says `E — Pack & crafting`;
- **Field Notes step 2** (reached automatically after gathering the first 4 logs) says
  *"Craft a workbench — Press E. Turn logs into planks, then shape four planks into a workbench."*
  and the toast "Field note updated: Craft a workbench" appears.

Evidence: `blind-evidence/A-quest-step2.png`, `blind-evidence/A-help.png`,
`blind-evidence/A-pack-open.png`. Verdict: **not "only a passive E craft line"** — it is a visible
quest/tutorial entry that names the key and the next action, reinforced by a visible Help button.
The D4≤55 / D9≤70 passive-hint cap is therefore **not applied**, but the lack of a direct button is
recorded as a discoverability weakness (A still asks the player to press a key the first-run UI
only introduces as a legend line).

**B — one click to play, explicit buttons.** Welcome card with **Play now / Open the guide / New
world**, plus the persistent nav **Quests / Inventory / Crafting / Guide / Backdrop / Save / Menu**
and a key legend (`C crafting`). After Play now, the same nav is unblurred and the quest tracker is
open. `Crafting (C)` is a real button; clicking it opens the crafting panel. The in-page self-test
asserts all seven primary buttons are present. Verdict: **fully discoverable**; no cap.

---

## 4. Underground verification (real 3×2 dig + natural cave)

Both artifacts were tested with real pointer input, not `setBlock`, in a fresh run:

- **A:** 4-block vertical shaft removed, then a **3-wide × 2-tall** side tunnel (6 blocks). A torch
  was placed in the tunnel with the real hotbar/right-click path. Backdrop inside the removed tiles
  is dark brown/black cave tone (sampled 75–94 R), not sky, and the surface stays bright while the
  tunnel darkens. A natural cave pocket was entered at (108,45); it renders as a dark cave with
  stone faces. Evidence: `blind-evidence/A-tunnel-lit.png`, `blind-evidence/A-natural-cave.png`.
- **B:** 4-block shaft + **3×2** side tunnel removed with real pointer holds; a torch placed at
  (94,46) produced block-light level 14 and the cave texture became readable. A natural cave was
  entered at (24,55); it renders stone/coal against dark cave texture. Evidence:
  `blind-evidence/B-tunnel-lit.png`, `blind-evidence/B-natural-cave.png`.
- **B after any save/reload:** the same tunnel renders as a *flat* `#211b16` fill
  (measured pixel `[53,45,37]` before save → `[33,27,22]` after; `world.surface === undefined`
  after load). This is M1. It is dark and still readable as "underground", but the cave texture and
  the per-tile air lighting are gone. It is *not* sky/blue and the world remains playable, so I
  classify it as a **medium** persistence/presentation defect rather than the high
  "underground reveals sky/blank canvas" defect. If a reader applies "blank canvas" literally, this
  becomes a high defect and caps B at PES/composite 55 — see §9.

---

## 5. Defects

### A

| ID | Severity | Defect | Evidence |
| --- | --- | --- | --- |
| A-M1 | **Medium** | No map or minimap and no coordinates; orientation is clock/day/seed + quest prose only. This is the standard's "no spatial orientation" medium and forces D6 ≤ 60. | Pause shows seed, no map element in DOM; multi-minute sessions relied on landmarks. |
| A-L1 | Low | Corrupt-save warning leaks raw JSON parser text ("Expected property name or '}' in JSON at position 1…") instead of a friendly message. | `blind-evidence/A-corrupt.png`. |
| A-L2 | Low | At ≤600 px viewport height the bottom key-help line is hidden; controls remain in HELP. | 800×600 screenshot. |
| A-L3 | Low | No touch controls (not claimed). Reduced motion *is* honored through a global `prefers-reduced-motion` rule. | CSS scan. |

No high defect: floor is bedrock, world edges clamp (player stops at x=0.32 after holding left from
x=2.5), placement refuses player-overlap cells, save/corrupt paths boot cleanly, controls are
readable.

### B

| ID | Severity | Defect | Evidence |
| --- | --- | --- | --- |
| B-M1 | **Medium (borderline high)** | `SAVE.loadWorld` reconstructs only `{width,height,seed,data}`; `world.surface` is `undefined` after every load. Rendering then skips cave textures for air below ground and skips the per-tile air-lighting pass, so every dug tunnel/natural cave becomes a flat `#211b16` fill after a reload and torch light no longer modulates cave air. Blocks, collision, inventory, quests, minimap and saves still work. | `world.surface === undefined` after `#btn-save` + reload; tunnel pixel `[53,45,37]` → `[33,27,22]`; `blind-evidence/B-persist-before.png` vs `B-persist-after.png`. |
| B-M2 | **Medium** | A corrupt save is silently discarded: the page boots a fresh world/welcome with **no message** that the save could not be read. A player loses progress without explanation. | `blind-evidence/B-corrupt.png`; no toast/status text; contrary to A's explicit warning. |
| B-L1 | Low | A resize triggers a transient "VIEW before → after" pulse that overlays the minimap/hotbar for a few seconds at 800×600; it obscures controls while shown. | `blind-evidence/B-resp-800x600.png`. |
| B-L2 | Low | `tools/__pycache__/page_check.cpython-312.pyc` is shipped in the artifact (packaging hygiene). | Directory listing. |
| B-L3 | Low | No `prefers-reduced-motion` path and no touch controls (neither is claimed). | CSS/JS scan. |

No high defect by the standard's definition: no unsealed floor (edges clamp at x=0.31), no
collision/placement corruption, no boot failure, controls readable, no game-breaking save. B-M1 is
the judgement call; it is player-visible on the normal autosave/reload loop but does not break the
player world or block play.

**Medium count / −10 cap:** A has 1 medium, B has 2; the "three or more mediums" −10 composite cap
does not apply to either.

---

## 6. Signature coverage

| Signature | A | B |
| --- | --- | --- |
| Seeded world with more than a flat strip | **Yes.** 224×96 seeded hills, 16 caves + 4 rooms, carved spawn stair, coal/iron/gem veins, oaks/pines, campfire + torch. No biome bands, no water/sand. | **Yes.** 192×96 seeded terrain with 4 biome bands (plains/forest/desert/rocky), caves, coal/iron, sand/sandstone, trees/flowers. No water. |
| Mine/place with readable feedback | **Yes.** Outline, hover tooltip with tool requirement/refusal, break progress, particles, sound, "+1 Dirt" floaters, screen shake, tool swing, placement preview/refusal. | **Yes.** Outline, mining progress, particles/sound, refusal toast, before/after "Backdrop" ghost + pulse on every edit, placement preview/refusal. |
| Inventory/hotbar with counts or palette | **Yes.** 9-slot hotbar + tool belt + backpack with counts, durability, binding. | **Yes.** 9-slot hotbar, backpack panel with counts, "click item to bind", empty-state copy. |
| Crafting/progression loop | **Yes, deep.** 16 recipes; handcraft vs workbench station; tool tiers/durability; 8-step Field Notes chain ending in the Warden's Lantern. Executed: logs → planks → workbench → place → mine stone → stone pickaxe (tier 2). No smelting. | **Yes.** 11 recipes with gather-unlock; planks → sticks → wooden pickaxe → stone pickaxe → iron pickaxe, torch/glass. No station, no smelting. Executed to stone pickaxe. |
| Save/restore | **Yes.** Full world incl. `surface`, inventory, tools, clock, flags; corrupt fallback with warning. | **Yes with M1.** Blocks/inventory/clock/quests restore; `surface` is lost, causing the M1 visual regression. Corrupt fallback silent (M2). |
| Day/night or atmosphere | **Yes.** 5-min cycle, sky palette, sun/moon, fireflies, campfire, night enemy spawns, lighting. | **Yes.** 4-min cycle, sky palette, sun/moon/stars/clouds, lighting; cave-dark atmosphere. |
| Orientation/minimap | **No map.** Clock/day + seed in pause; no coordinates. | **Yes.** Real minimap with viewport rectangle, zoom readout and view size; seed input. |
| Objectives/exploration loop | **Yes.** 8 field notes, amberstone, hollows/combat, death/respawn, random new world. | **Yes.** 8 quests with material rewards, "Dig deep", "Find iron", "Survive the night"; no combat. |

Other coverage: **A** has sprint, coyote time/jump buffer, hollows (combat), health/death/respawn,
tool durability, three ore tiers. **B** has zoom, undo/redo, export/import save, seed input,
before/after edit history, fall damage and health. Neither has liquids or sand physics; A has no
biomes, B has no combat. These are depth/coverage gaps under D2/D4/D1/D7, not high defects.

---

## 7. PES — dimension scores

Weights from v1.2. Scores are 0–100, then weighted.

| ID | Dimension | Weight | A | A pts | B | B pts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| D1 | Core verbs and controls | 10 | **92** | 9.20 | **82** | 8.20 |
| D2 | World gen, biomes, physics | 16 | **78** | 12.48 | **86** | 13.76 |
| D3 | Mining/placement feedback | 10 | **90** | 9.00 | **84** | 8.40 |
| D4 | Inventory, crafting, progression | 22 | **84** | 18.48 | **85** | 18.70 |
| D5 | Presentation, character, UI, audio | 18 | **91** | 16.38 | **86** | 15.48 |
| D6 | Orientation and map | 6 | **55** | 3.30 | **88** | 5.28 |
| D7 | Replay, objectives, combat | 8 | **88** | 7.04 | **80** | 6.40 |
| D8 | Accessibility and responsive | 4 | **84** | 3.36 | **80** | 3.20 |
| D9 | First-run discoverability and docs | 6 | **78** | 4.68 | **90** | 5.40 |
| | **PES total** | 100 | | **83.92 → 83.9** | | **84.82 → 84.8** |

Rationale highlights:

- **D1 A 92 / B 82.** A adds sprint, coyote time, jump buffer, three tool tiers with durability,
  hollow combat, health/death/respawn and explicit refusal reasons ("Stone — needs a pickaxe");
  B has solid walk/jump/mine/place/zoom/undo but no sprint and no combat.
- **D2 A 78 / B 86.** Both have real caves, ores and non-flat seeded terrain; B adds four biomes,
  sand/sandstone and broader surface variety. A has a stronger hand-built spawn stair/camp but no
  biome or granular material variety; neither has fluids/sand physics.
- **D3 A 90 / B 84.** Both read actions without explanation; A's break progress, particles, sound,
  floaters, shake and tool swing are richer. B's before/after edit ghosts and pulse are excellent
  and partly compensate.
- **D4 A 84 / B 85.** Both have a real gather→craft→build loop with tools and quest progression.
  A has a station gate, 16 recipes, tool durability, 8-step lantern chain; B has a visible Crafting
  button, gather-unlock recipe list, 8 rewarded quests, but no station/smelting. The v1.2
  passive-hint cap was not applied to A because the first-run Field Notes entry explicitly says
  "Press E…" and Help names "Pack & crafting"; A's direct-button weakness is reflected in D9.
- **D5 A 91 / B 86.** Both are far from "plain prototype". A's parallax valley, campfire smoke,
  fireflies, animated character/tools and enemy silhouettes give the stronger first frame; B is
  clean and coherent with a good cave/minimap presentation.
- **D6 A 55 / B 88.** A has no map or coordinates (cap); B has a real minimap with viewport box and
  zoom/viewport readout.
- **D7 A 88 / B 80.** A has combat, random new worlds, help/pause and a full goal chain; B has
  seeds, new world, pause/menu, undo/redo and save export/import but no combat.
- **D8 A 84 / B 80.** Both fit 800/960/1280/1440 with no overflow, have ARIA labels on the canvas,
  hotbar and dialogs, and keyboard access. A also honors `prefers-reduced-motion` globally; B has
  no reduced-motion path. Neither ships touch controls; no mobile claim is made.
- **D9 A 78 / B 90.** A is immediately playable but leans on a key legend and quest text; B puts
  Play now and the seven core buttons in front of the player on first run.

Experience floor/cap: neither PES is below 70, so the `PES + 10` / `PES` composite floors do not
trigger.

---

## 8. ECS — dimension scores

| ID | Dimension | Weight | A | A pts | B | B pts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| E1 | Tests and verification | 30 | **88** | 26.40 | **95** | 28.50 |
| E2 | Architecture and readability | 25 | **85** | 21.25 | **92** | 23.00 |
| E3 | Robustness, persistence, security | 20 | **87** | 17.40 | **78** | 15.60 |
| E4 | Performance, accessibility, responsive | 15 | **88** | 13.20 | **86** | 12.90 |
| E5 | Documentation and tooling | 10 | **85** | 8.50 | **87** | 8.70 |
| | **ECS total** | 100 | | **86.75 → 86.8** | | **88.70 → 88.7** |

- **E1 A 88.** 29 `node:test` cases over 4 files assert real invariants: terrain determinism, caves/
  ores/bedrock, collision and walls, jump/fall, damage, time rollover, RLE save round-trip and
  malformed payload rejection, inventory/tool basics, and generated-content validity. Tools include
  a raw-CDP `browser_check.mjs`, `quest_check.mjs` and a headless `page_check.py`. No in-page
  self-test.
- **E1 B 95.** 79 tests over 12 focused files plus a 21-step in-page self-test that drives real DOM
  clicks, real pointer mining/placement, real keyboard movement, save parsing, minimap trail and
  performance budget; `browser_check.py` ships a self-test plus two-launch persistence check.
  This is the strongest verification surface in the pair.
- **E2 A 85.** Clean UMD modules (config/content/time/world/player/inventory/art/audio/render/ui/
  main), data-driven item/recipe/quest tables, testable pure modules. `main.js` (66 KB) is a large
  orchestration file; workable but the weakest boundary.
- **E2 B 92.** 22 small modules with sharp seams (physics/mining/placement/crafting/lighting/tasks/
  save/backdrop/scenes/selftest), no god file, state owned by `main`, pure rules testable in Node.
- **E3 A 87.** Versioned save with full `surface` + RLE validation and size limits, corrupt-save
  fallback with player-visible warning, bounds checks, zero `innerHTML`, zero network, safe
  `textContent`-based UI. Minor copy leak of a JSON parser message.
- **E3 B 78.** Versioned save, extensive schema validation, import/export, bounds, no network, no
  user-controlled `innerHTML`. Loses points for M1 (surface not persisted) and M2 (silent corrupt
  discard).
- **E4 A 88 / B 86.** 60 fps measured for both; no console spam; responsive at all required widths;
  ARIA labels; A honors reduced motion, B does not. B adds zoom-aware minimap/UI.
- **E5 A 85 / B 87.** Both ship reproducible checks/tools and in-game controls docs (A: Help;
  B: Guide + self-test). Both include a README, but it was not read under the identity-blind rule,
  so its content is only indirectly credited. A ships a root screenshot and CDP checker; B ships a
  broader tool suite but also a stray `__pycache__`.

---

## 9. Composite, caps and tier

```
A: 0.75 × 83.92 + 0.25 × 86.75 = 62.94 + 21.69 = 84.63  → 84.6
B: 0.75 × 84.82 + 0.25 × 88.70 = 63.62 + 22.18 = 85.80  → 85.8
```

Applied caps:

- **A:** D6 ≤ 60 without a real map → D6 = 55. No high-defect cap. PES > 70, so no composite floor.
- **B:** no high-defect cap, no D4/D6/D5 cap (Crafting is a visible button; minimap is real;
  presentation is not plain). PES > 70. The three-medium −10 cap does not apply (2 mediums).
  **Borderline:** if B-M1 is reclassified as the high "underground blank canvas" defect, then
  **PES ≤ 55, composite ≤ 55**, experience tier `prototype`. My reading is that the flat dark
  backdrop is a degraded but still-readable underground, not a sky/blank reveal, so I did not apply
  the high-defect cap. This is the single most consequential judgement in this evaluation.

Tiers (v1.2):

| Artifact | PES | D5 | D4 | Tier |
| --- | ---: | ---: | ---: | --- |
| A | 83.9 | 91 | 84 | **polished** |
| B | 84.8 | 86 | 85 | **polished** (with M1 caveat) |

Neither result is `broken`; neither is a `prototype` on the measured evidence. A's no-map medium
does not move the tier because the other dimensions carry PES above 80.

---

## 10. Comparison

- **A wins on experience**: stronger first frame and atmosphere, richer action feedback, combat and
  death/respawn, tool tiers/durability, station-gated crafting and a longer goal chain. Its
  weaknesses are a missing map/coordinates and a discoverability path that relies on a key legend
  plus the Field Notes text rather than a first-class button.
- **B wins on engineering and orientation**: exceptional verification (79 tests + 21-step in-page
  self-test), cleaner modular seams, a real minimap, visible core-system buttons, seed input and a
  distinctive before/after edit "Backdrop". Its weaknesses are the save/reload surface regression
  (M1), silent corrupt-save discard (M2), and no combat/station/smelting depth.
- **Net:** B is ahead by ~1.2 composite points; A is ahead on PES dimensions that a player feels
  most (D3/D5/D7). The choice between them is a product choice between polish/atmosphere (A) and
  robustness/verification/orientation (B), not a clear quality gap.

---

## 11. Evidence limits

- README files were **not read** (identity-blind rule); documentation was judged from in-game Help/
  Guide and tooling. README quality is therefore only indirectly represented in E5.
- Screenshots are headless Chromium; audio was not auditioned. Audio code, mute toggles and
  procedural sound paths were inspected and the mute button was exercised only structurally.
- One B torch-light-after-reload probe failed to place the torch (support/aim), so the "torch light
  no longer modulates cave air" consequence of M1 is supported by source reading plus the flat
  backdrop pixel, not by a clean lit/unlit screenshot. The surface-loss invariant itself is
  executable and directly observed.
- A's full lantern quest chain was not completed end-to-end. The chain was verified through
  logs → planks → workbench → placement → stone mining → stone pickaxe; the lantern recipe and
  final quest steps were read but not executed.
- The 3×2 dig used real pointer holds but the evaluator used the artifacts' public debug hooks for
  **positioning** (A `Mosswild.teleport`, B `commands.teleport`) in some runs to keep the player
  centered on a single tile; mining, placement, crafting, saving and UI clicks were real input.
  Natural-cave shots used teleport for reachability of the cave, not `setBlock`.
- No physical mobile/touch device test; responsive checks are viewport resizes at 800/960/1280/1440
  plus DOM-overflow inspection.
- Day/night cycles are short (A 300 s, B 240 s); observations of night vs day came from real elapsed
  play and the artifacts' own time controls.
- Browser locale/time zone: headless defaults; no locale-specific text issues were seen.
