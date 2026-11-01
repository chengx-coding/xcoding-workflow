# Blind evaluation 鈥?M2D-SES-OSS v1.0

**Standard:** M2D-SES-OSS v1.0 (fixed) 路 **Profile:** open 2D sandbox 路 **Artifacts:** A and B
**Condition identity:** not inspected and not revealed. No parent directory, `.xcoding` mapping, or identity file was read.
**Date:** 2026-11-01 路 **Evaluator:** independent blind pass

Both artifacts are playable offline pages. Neither is unplayable and no evidence check was blocked.
A is the higher-scoring artifact after the fixed gates and caps.

## 1. Verdict and score summary

| Field | Artifact A | Artifact B |
| --- | --- | --- |
| Artifact path | `tmp\blind\A` | `tmp\blind\B` |
| Tests executed | `node --test` 29/29 pass | `node --test` 41/41 pass |
| Browser evidence | page check, browser check, full quest check | page check, browser check, independent probe |
| High / medium / low defects | 0 / 0 / 3 | **1 / 1 / 3** |
| PES (75%) | **89.4** | **60.0** (raw 76.8; high-defect cap) |
| ECS (25%) | **87.0** | **88.3** |
| Composite | **88.8** | **65.0** (raw 79.7; high-defect cap) |
| Caps applied | none | H1: PES 鈮?0, composite 鈮?5 |
| Gate result | G1/G2/G3 pass | G1/G2/G3 pass |
| Higher result | **A** | 鈥?|

`composite = 0.75 脳 PES + 0.25 脳 ECS`.

A is a clean, feature-rich sandbox with the strongest progression/signature coverage.
B is a clean, well-structured narrow sandbox whose core presentation is broken underground:
all underground air is transparent to the full-screen sky layer. That is the standard's listed
high defect "underground removal reveals sky/blank canvas", so B's PES and composite are capped.

## 2. Gates

| Gate | A | B | Evidence |
| --- | --- | --- | --- |
| G1 Offline boot (`file://`, no build/CDN/network) | PASS | PASS | `python tools/page_check.py`: static problems `[]`; probe recorded only `file://` requests and `remote_requests: []`; B browser check `no-network` 30 requests / 0 remote. |
| G2 No fatal errors / renders | PASS | PASS | Both page checks `ok: true`, status marker exactly `(46,204,113)`, non-blank canvas; browser checks `errors: []`; probes `pageerrors: []` and no console errors. |
| G3 Save/recovery | PASS | PASS | A: saved/reloaded placed block `9` and planks 3; corrupt save showed warning and booted a fresh world. B: browser check `reload-persistence` restored seed, planks and placed block 11; corrupt save showed warning, status ready, fresh world. |

No blocker: both pages boot and remain playable. B's H1 is a high defect, not a boot blocker.

## 3. PES 鈥?dimension scores

| ID | Dimension | Weight | A | B | Evidence |
| --- | --- | ---: | ---: | ---: | --- |
| D1 | Core verbs and controls | 12 | 92 | 82 | A: walk/sprint/jump, AABB collision, mine/place, attack, health/death/respawn, camera, tooltips/refusals; all exercised. B: walk/jump/swim, collision, mine/place, reach/tool refusals, camera; no sprint/attack/health. Controls are documented in both. |
| D2 | World generation and exploration | 14 | 84 | 80 | A: 224脳96, 1,966 underground air tiles at seed 12345, 3 ores (208 coal / 142 iron / 35 amberstone), 73 logs, 2 tree styles, camp, stair, 2 bedrock rows. B: 192脳96, 1,961 underground air, coal/crystal, trees, sand, lakes/water, surface shafts; deterministic per seed. A has more structures/ore variety; B has water/sand variety. |
| D3 | Mining and placement feedback | 12 | 90 | 80 | A: target outline, block tooltip, crack progress, particles, floating pickup text, screen shake, audio, placement ghost, explicit refusal reasons, tool-tier reasons. B: target outline, crack marks, particles, audio, save flash, reach/tool toasts; no placement ghost and occupied-tile refusal is silent (M1). |
| D4 | Inventory, crafting and progression | 20 | 93 | 64 | See 搂7. A: 16 recipes, workbench station, 3脳3 tool tiers, durability, ore tiers, 8-step quest + lantern. B: 5 recipes, no station, 2 pickaxes, no durability/goals. Both have a real gather鈫抍raft鈫抌uild loop, so the "absence caps D4 at 50" rule does **not** apply. |
| D5 | Presentation, UI, audio, atmosphere | 12 | 91 | 76 | A: coherent Mosswild identity, parallax, lighting, stars, campfire glow, flowers, birds, day/night, synthesized audio/mute. B: coherent but plain pixel style, day/night, clouds, water, torches, synthesized audio; fixed 960脳540 page at 1280 leaves large black bands (L1). |
| D6 | Orientation and status | 6 | 76 | 82 | A: clock/day/phase, field-notes objective, landmarks, seed/day/stats in pause; no minimap and no on-screen coordinates. B: clock/day/phase, X/Y position in HUD, seed in pause; no minimap. B has the better position readout; A has stronger objective orientation. |
| D7 | Replay, objectives and world controls | 6 | 90 | 68 | A: 8-step field-notes quest, completion overlay, stats, pause/help/fullscreen, confirmed new world. B: pause/help, confirmed new world, day/night cycle; no objectives or progression goal. |
| D8 | Accessibility, responsive and polish | 6 | 88 | 74 | A: canvas `tabindex` + descriptive `aria-label`, named buttons/hotbar/hearts/quest, `:focus-visible`, `prefers-reduced-motion` media rule; 800/960/1280 no overflow or clipping. B: named hotbar/buttons, dialog roles, `:focus-visible`; no reduced-motion rule, canvas not focusable/roleless, no focus trap; 800/960/1280 no overflow but fixed 960 layout. |
| D9 | First-run and documentation | 12 | 92 | 90 | A: immediate play, starter tutorial card, quest card, in-game help, README with controls/architecture/verification. B: immediate play, HUD control hint, onboarding toast, help overlay, thorough README incl. deliberate scope. |

**Weighted PES**

| | A | B |
| --- | ---: | ---: |
| D1 | 11.04 | 9.84 |
| D2 | 11.76 | 11.20 |
| D3 | 10.80 | 9.60 |
| D4 | 18.60 | 12.80 |
| D5 | 10.92 | 9.12 |
| D6 | 4.56 | 4.92 |
| D7 | 5.40 | 4.08 |
| D8 | 5.28 | 4.44 |
| D9 | 11.04 | 10.80 |
| **PES** | **89.4** | **76.8 鈫?60.0 (cap)** |

## 4. ECS 鈥?dimension scores

| ID | Dimension | Weight | A | B | Evidence |
| --- | --- | ---: | ---: | ---: | --- |
| E1 | Tests and verification | 30 | 92 | 90 | A: 29 Node tests on terrain determinism, bounds, save round-trip/malformed RLE, inventory/tool tiers/durability, quests, collision, fall damage, clock, enemies; plus interactive browser check and full quest check. B: 41 Node tests on worldgen anchors/seed contract, caves/ores/water, collision/coyote/swim/respawn, mining/gating, crafting costs/atomicity, lighting, save validation/corruption/storage failures; plus 16-step browser check. Both assert real invariants, not smoke only. |
| E2 | Architecture and readability | 25 | 76 | 90 | A: coherent UMD modules with clear responsibilities, but `main.js` is 2,106 lines and owns loop/input/quest/save/enemies; `art.js` 995 and `ui.js` 887 lines. B: 14 focused modules (largest `main.js` 594), clean data/state boundaries, no god file. |
| E3 | Robustness, persistence, security | 20 | 90 | 90 | A: versioned save (`v:1`), world RLE decode with dimension/length/block-id validation, inventory sanitize (legal keys/counts/tiers/durability), safe respawn/clamp, corrupt-save fallback, storage failure toast. B: versioned save, RLE and snapshot validation (version, dimensions, player position, inventory counts, time bounds), corrupt-save fallback, storage probe/memory fallback, save error reporting. No game network use in either. |
| E4 | Performance, accessibility, responsive | 15 | 86 | 80 | Both use fixed-step loops with iteration caps and particle culling, no console spam, no leaks observed. A has stronger labels, focus-visible and reduced-motion support; B's accessibility is thinner (canvas not focusable, no reduced motion) and its app is fixed at 960 px. |
| E5 | Documentation and tooling | 10 | 95 | 88 | A: README (controls, files, save behavior, verification), `browser_check.mjs`, `quest_check.mjs`, page check. B: README (controls, systems, deliberate scope, layout, verification), `browser_check.mjs`, page check. A ships one more journey-level tool. `tools/page_check.py` is byte-identical in both (SHA256 `3131B3鈥); treated as provided evaluation tooling, not author credit. |

**Weighted ECS**

| | A | B |
| --- | ---: | ---: |
| E1 | 27.60 | 27.00 |
| E2 | 19.00 | 22.50 |
| E3 | 18.00 | 18.00 |
| E4 | 12.90 | 12.00 |
| E5 | 9.50 | 8.80 |
| **ECS** | **87.0** | **88.3** |

## 5. Composite

| | A | B |
| --- | ---: | ---: |
| PES | 89.4 | 60.0 |
| ECS | 87.0 | 88.3 |
| `0.75路PES + 0.25路ECS` | **88.8** | **65.0** |
| Raw before cap | 88.8 | 79.7 |
| Caps | none | PES 鈮?0 and composite 鈮?5 (one high defect) |

## 6. Signature coverage

| Signature | A | B |
| --- | --- | --- |
| Seeded world beyond a flat strip | **Yes.** 224脳96, hills 36鈥?8, caves, 3 ore types, oak/pine, camp, spawn stair, 2 bedrock rows. | **Yes.** 192脳96, rolling surface, caves and surface shafts, coal/crystal, trees, sand and lakes; deterministic. |
| Mine/place with readable feedback | **Yes, strong.** Outline, crack progress, particles, pickup floaters, shake, audio, placement ghost, refusal/tool text. | **Yes.** Outline, crack marks, particles, audio; no placement ghost, silent occupied refusal. |
| Inventory/hotbar with counts or palette | **Yes.** 9 slots, counts, selected readout, durability bar, backpack binding, tool belt. | **Yes.** 8 slots, counts, selected border, accessible labels, pause inventory summary. |
| Crafting/progression loop | **Yes, deep.** 16 recipes; workbench station; 3 tool types 脳 3 tiers; durability; ore-tier gates; 8-step quest ending Warden's Lantern. | **Yes, shallow.** 5 recipes; no station; wooden鈫抯tone pickaxe; crystal gate; no durability, no goals. |
| Save/restore | **Yes.** Autosave/manual/hidden/unload; verified placed block and inventory; corrupt fallback. | **Yes.** Autosave/manual/hidden/unload; verified placed block and inventory; corrupt fallback. |
| Day/night or atmosphere | **Yes.** 5-minute cycle, stars, lighting, campfire, night mobs, audio. | **Yes.** 4-minute cycle, sky/clouds/stars, water, torches/crystal light, audio. |
| Orientation/minimap | **Partial.** Clock/day, field notes, landmarks, seed; no minimap or coordinates. | **Partial.** X/Y, clock/day, seed; no minimap. |
| Objectives/exploration loop | **Yes.** 8-step quest with progress, completion overlay, continued play. | **No objectives.** Exploration/creative loop only. |

## 7. Crafting/progression audit (D4)

### A 鈥?present, deep

- **Recipes:** 16 (`content.js`): planks, sticks, workbench, torches, 9 tool recipes across pickaxe/axe/sword at wooden/stone/iron tiers, stone bricks, campfire, Warden's Lantern.
- **Station:** 12 recipes require a placed workbench in reach; the pack shows `No workbench nearby` / `Workbench in reach` and disables station recipes.
- **Inputs/outputs:** real consumption (`canAfford`/`removeItem`) and outputs (blocks, tools with tier and durability, quest flag). Tool upgrades replace the old tier; tools wear with use and disappear when broken.
- **Loop:** gather logs 鈫?planks 鈫?sticks 鈫?workbench 鈫?place 鈫?wooden tools 鈫?stone pickaxe 鈫?mine stone/coal 鈫?iron pickaxe 鈫?iron/coal/torch 鈫?lantern 鈫?place 鈫?quest completion. Ore tiers gate iron (stone pickaxe) and amberstone (iron pickaxe).
- **Pressure/goals:** 8-step field-notes quest, ore thresholds, tool durability, night enemies, death/respawn.
- **Executed:** the full quest check advanced all eight field-note stages and reached the completion overlay through UI actions, including workbench placement, stone-pickaxe crafting, lantern crafting, lantern placement, pause, death/respawn, help and new world (`ok: true`, errors `[]`). Early wood/workbench/planks flow is real input; late stone/ore resources and the eight-stone/ore statistics were staged by the test harness, not all gathered in one continuous unassisted run (evidence limit). Independent probe additionally mined a log, crafted planks, placed planks, saved/reloaded.
- **D4 = 93.**

### B 鈥?present, shallow-to-moderate

- **Recipes:** 5 (`config.js`): 1 wood 鈫?4 planks; 2 planks 鈫?4 sticks; 1 stick + 1 coal 鈫?4 torches; 3 planks + 2 sticks 鈫?wooden pickaxe; 3 stone + 2 sticks 鈫?stone pickaxe.
- **Station:** none; crafting is available anywhere with `E`.
- **Inputs/outputs:** atomic cost check, `remove` then `add`; unique pickaxes cannot be duplicated; wrong materials do not partially consume. Tools do not wear out.
- **Loop:** wood 鈫?planks 鈫?sticks 鈫?wooden pickaxe 鈫?mine stone/coal 鈫?stone pickaxe 鈫?crystal; crystal is a light source and the deepest resource. No objective or progression tracker.
- **Pressure/goals:** tier gates only (stone/coal need wooden pickaxe; crystal needs stone pickaxe); no durability, hunger, mobs, station, quest, or completion goal.
- **Executed:** real mouse mining produced wood 1; real `E` panel produced planks 4; independent UI chain produced sticks 4, wooden pickaxe 1 and stone pickaxe 1 with exact material consumption; real placement produced block 11 and consumed one plank; browser check independently mined a tree, crafted planks and placed planks. Stone/coal for the deeper recipes were staged (evidence limit).
- **Crafting is present, so the D4 absence cap does not apply; depth is honestly narrow. D4 = 64.**

## 8. Defects and caps

### Artifact A

| ID | Severity | Defect | Evidence | Cap |
| --- | --- | --- | --- | --- |
| L1 | Low | No minimap or on-screen coordinate readout; orientation relies on landmarks, clock and field notes. | `A-01-first-1280.png`, pause panel source; no coordinate element in `index.html`/`ui.js`. | none |
| L2 | Low | No touch/mobile control layout. | Desktop-only design; README recommends mouse/keyboard and does not claim mobile. | none |
| L3 | Low | At 800 px the field-notes card covers part of the play area and the tutorial card is suppressed. | `A-02-800.png`; measured topbar/quest/hotbar within viewport, no overflow. | none |

No high or medium defects were found. A's world floor is sealed (2 bedrock rows, out-of-bounds collision),
underground air renders a cave backdrop (`drawCaveBackground`, `A-08-underground.png`), placement refuses
player-overlapping/unsupported cells, and corrupt saves recover with a warning (`A-10-corrupt.png`).

### Artifact B

| ID | Severity | Defect | Evidence | Cap |
| --- | --- | --- | --- | --- |
| **H1** | **High** | **Underground air renders the sky, sun/clouds and parallax hills instead of an underground backdrop.** `renderFrame` draws the full-screen sky and parallax first, `drawTiles` skips air, and `drawDarkness` only dims the result; there is no cave background. | `B-12-underground-before.png`, `B-13-underground-after-mine.png` (Y 92; sky and clouds visible behind the cave), `B-09-underground.png`, `B-15-cave-noon.png` vs `B-16-cave-midnight.png`. Executable check: in a light-0 cave the air pixel (132,91) was RGB 9/16/23 at noon and 4/11/18 at midnight, while adjacent stone (128,90) stayed 22/27/35 both times. Code: `js/render.js` lines 532鈥?40 and `drawTiles` air `continue`. | **PES 鈮?0; composite 鈮?5** |
| M1 | Medium | Placement has no ghost/preview, and right-clicking an occupied/invalid tile is silent (no reason). Successful placement does have particles, sound and a save flash. | `B-08-placed.png` (rejected target: no block placed, no feedback), `B-14-placed.png` (valid target: block 11 placed, one plank consumed); `js/main.js` `tryPlace` returns silently for occupied cells. | lowers D3/D8; no extra cap |
| L1 | Low | At 1280 the app stays 960脳540 and leaves large black bands; no full-viewport composition. | `B-01-first-1280.png`, `B-02-800.png`; measured canvas 960脳540 at 1280脳800, scroll size 1280脳800. | none |
| L2 | Low | No `prefers-reduced-motion` handling. | No matching media rule in `css/style.css`; A has one. | none |
| L3 | Low | Canvas is not focusable and has no role; overlays do not trap focus. | Canvas has `aria-label` but `tabindex`/`role` are absent; buttons are named and focus-visible styling exists. | none |

One high defect applies the one-high cap; only one medium is recorded, so the three-medium 鈭?0 cap does
**not** apply. B remains playable and passes all hard gates; the cap is for the broken underground read,
not for unplayability.

## 9. Executed evidence

All commands were run against the artifacts; no artifact or sample was edited.

### Node suites

```text
# Artifact A
node --test "tests/**/*.test.js"
tests 29  suites 0  pass 29  fail 0  duration_ms 210.17

# Artifact B
node --test "tests/**/*.test.js"
tests 41  suites 0  pass 41  fail 0  duration_ms 250.30
```

A's tests cover deterministic terrain, spawn safety, caves/ore content, bounds, RLE save round-trip and
malformed payloads, inventory/tool gating/durability, quest progression, collision, fall damage and clock.
B's tests cover the seed anchor, worldgen dimensions/caves/ores/water, collision/coyote/swim/respawn,
mining gating/reach, atomic crafting, lighting/skylight, save validation/corruption/storage failure and RLE.

### Static + headless render checks

Chrome/Edge were not at the usual install paths, so the Playwright Chromium 1234 executable was passed
explicitly. The check itself is the provided `tools/page_check.py` (identical in A and B).

```text
python tools/page_check.py --chrome "...\ms-playwright\chromium-1234\chrome-win64\chrome.exe" \
  --screenshot artifacts/blind-evidence/A-page-check.png
A: ok true; static problems []; status marker (46,204,113) distance 0.0; 223 canvas colour buckets.

python tools/page_check.py --chrome "...\ms-playwright\chromium-1234\chrome-win64\chrome.exe" \
  --screenshot artifacts/blind-evidence/B-page-check.png
B: ok true; static problems []; status marker (46,204,113) distance 0.0; 156 canvas colour buckets.
```

The Python wrapper printed a GBK `UnicodeDecodeError` while reading Chrome's stderr; the checks still
returned exit 0 and `"ok": true`. This is an environment console-decoding issue, not a page failure.

### A interactive browser check and full quest check

A's checks write into `artifacts/`, so they were executed on a byte-identical mirror at `tmp\eval-run\A`
(copied from A; `js/main.js` SHA256 `4F1DA104BD1C3386E6D8FFD381130CD8A9FD560EFBD8145C4C672B489AB8D894`
on both). This kept A unchanged.

```text
CHROME_PATH=... node tools/browser_check.mjs
ok true; errors []; initial seed 763254589; HP 20; move x 112.5 -> 114.98;
mine target (116,41) block 2 -> 0, dirt 1; pack 16 recipes / 3 bindables;
night 22:24, 1 enemy; combat 7 -> 5.6 HP;
save/reload restored x, dirt, stone 7, HP 15, pickaxe tier 2, durability 123,
stonePickaxeCrafted true, stoneMined 8, marker block 9, night state.
Screenshots: A-browser-check-day.png, A-browser-check-pack.png, A-browser-check-night.png.

node tools/quest_check.mjs
ok true; errors [];
prepare logs -> planks -> workbench craft -> place (nearBench true) ->
stone pickaxe -> lantern craft -> lantern place -> completion overlay ("The wild remembers."),
then pause, death ("You fell."), respawn HP 20, help, new world.
Screenshots: A-quest-workbench.png, A-quest-complete.png, A-quest-pause.png,
A-quest-death.png, A-quest-help.png, A-quest-final.png.
```

### B interactive browser check

```text
node tools/browser_check.mjs --chrome "...\chrome.exe" \
  --screenshots artifacts/blind-evidence/B-browser
ok true; 16/16 steps; consoleErrors []; 30 network requests / 0 remote.
boot 192脳96, 8 slots; jump rise 1.85 / landed 61; move 96.5 -> 99.65;
mine tree (100,60) wood 1; craft planks 4; place block 11, planks 3;
help 10 rows; pause save; reload seed/items/placed block restored;
day/night brightness 123.6 -> 19.7; responsive pointer mapping at 1280;
audio mute; new world seed 653486344; console-clean.
Screenshots: B-browser/01-boot-day.png, 02-pause.png, 03-day.png, 04-night.png.
```

### Independent Playwright probe (both artifacts)

`tmp\eval-run\probe.py`, run with Chromium headless at 1280脳800, then 960/800 widths.

```text
A: seed 1199138123; no console errors; no page errors; remote requests [].
   real mine: log block 7 -> 0 at (118,39), log 1; real craft: planks 4;
   real placement: planks block 9 at (111,39), planks 3;
   save/reload: block 9 and planks 3 restored;
   corrupt save: mode playing, fatal hidden, status ready, warning toast, fresh 21,504-tile world.
   layouts: 800/960/1280 scroll == viewport, no overflow; 14 visible buttons, 0 unnamed;
   canvas aria-label present and tabindex 0.
B: seed 1204420611; no console errors; no page errors; remote requests [].
   real mine: wood block 4 -> 0 at (100,59), wood 1; real craft: planks 4;
   UI chain: sticks (planks 6, sticks 4), wooden pickaxe (planks 3, sticks 2, tool 1),
   stone pickaxe (stone 0, sticks 0, tool 1);
   real placement: planks block 11, planks 4 (B-14);
   corrupt save: ready, status ready, warning toast, fresh 18,432-tile world.
   layouts: 800/960/1280 scroll == viewport, no overflow; 8 visible buttons, 0 unnamed;
   canvas aria-label present, no tabindex/role.
```

The probe also produced the underground invariant in 搂8: an executable pixel sample showing the
light-0 cave air changes with sky time while adjacent stone does not.

### World/content census (seed 12345)

```text
A: 224脳96; 1,966 underground air; coal 208, iron 142, amberstone 35, logs 73,
   leaves 260, bedrock 448; 16 recipes; 8 quest steps; 3 tool types 脳 3 tiers; no water block.
B: 192脳96; 1,961 underground air; coal 123, crystal 32, wood 101, sand 60, water 18;
   5 recipes; 2 tool items; 8 hotbar slots.
Both: generation deterministic for the same seed.
```

## 10. Screenshot index

Paths are relative to this report (`artifacts/`).

| Purpose | A | B |
| --- | --- | --- |
| First frame 1280脳800 | `blind-evidence/A-01-first-1280.png` | `blind-evidence/B-01-first-1280.png` |
| 800 px layout | `blind-evidence/A-02-800.png` | `blind-evidence/B-02-800.png` |
| 960 px layout | `blind-evidence/A-03-960.png` | `blind-evidence/B-03-960.png` |
| Mining in progress | `blind-evidence/A-04-mining.png` | `blind-evidence/B-04-mining.png` |
| After mining | `blind-evidence/A-05-mined.png` | `blind-evidence/B-05-mined.png` |
| Pack/crafting | `blind-evidence/A-06-pack.png` | `blind-evidence/B-06-craft.png` (deep chain: `B-07-craft-deep.png`) |
| Placement | `blind-evidence/A-07-placed.png` | `blind-evidence/B-14-placed.png` (invalid-target case: `B-08-placed.png`) |
| Underground | `blind-evidence/A-08-underground.png` (stone cave backdrop) | `blind-evidence/B-09-underground.png`, `B-12-underground-before.png`, `B-13-underground-after-mine.png`, `B-15-cave-noon.png`, `B-16-cave-midnight.png` (sky visible) |
| Save/reload | `blind-evidence/A-09-reloaded.png` | `blind-evidence/B-10-reloaded.png` |
| Corrupt-save recovery | `blind-evidence/A-10-corrupt.png` | `blind-evidence/B-11-corrupt.png` |
| Page check | `blind-evidence/A-page-check.png` | `blind-evidence/B-page-check.png` |
| Browser check | `blind-evidence/A-browser-check-day.png`, `A-browser-check-pack.png`, `A-browser-check-night.png` | `blind-evidence/B-browser/01-boot-day.png`, `02-pause.png`, `03-day.png`, `04-night.png` |
| A quest journey | `blind-evidence/A-quest-workbench.png`, `A-quest-complete.png`, `A-quest-pause.png`, `A-quest-death.png`, `A-quest-help.png`, `A-quest-final.png` | 鈥?|

![A first frame](blind-evidence/A-01-first-1280.png)

![A dark cave: stone backdrop, no sky](blind-evidence/A-08-underground.png)

![B underground at Y 92: sky and clouds behind the cave](blind-evidence/B-12-underground-before.png)

![B cave at noon: sky strip visible underground](blind-evidence/B-15-cave-noon.png)

## 11. Evidence limits

1. **A's browser checks ran on a byte-identical mirror.** A's `browser_check.mjs` and `quest_check.mjs`
   write into `artifacts/`; running them in place would edit A. A was copied to `tmp\eval-run\A`
   (33 files, 5,301,305 bytes; `js/main.js` hash equal) and the checks ran there. A itself was not modified.
2. **B was run in place but its screenshots were redirected** to `artifacts/blind-evidence/`; no B files
   were written.
3. **Headless Chromium, not desktop Chrome/Edge.** Chrome/Edge were absent from standard paths; the
   Playwright Chromium 1234 build was used. GPU/audio output is not representative of a desktop session.
4. **Late crafting materials were staged.** A's full quest check injects stone/sticks and late resources;
   B's deeper recipe chain injects wood/planks/stone. The early loop in both is real input: A mined a log
   and crafted planks; B mined wood, crafted planks and placed a plank block. A's completion journey and
   B's five-recipe chain are UI-driven but not one continuous unassisted gather.
5. **B's high defect was positioned by teleport.** The player was placed in a light-0 cave to capture the
   read; a real stone block was then mined in the same cave (`B-13`). The renderer cause is static code
   (`drawSky` 鈫?`drawTiles` skips air 鈫?`drawDarkness`), so the defect is not an artifact of the teleport.
6. **A's corrupt-save test required init-script injection** because A rewrites its save on `pagehide`.
   The corrupt payload was set in the new document before `main.js` ran; recovery and warning were
   observed. B's corrupt test used the same approach.
7. **Audio was muted/headless.** Mute toggle was exercised; actual sound quality was not audibly judged.
8. **No touch/mobile test.** Neither artifact claims a mobile control scheme; D8 was assessed at 800/960/1280
   desktop widths.
9. **`tools/page_check.py` is identical in both artifacts** (same SHA256). It is treated as provided
   evaluation tooling, not as evidence that either author wrote it. Both also ship their own
   `browser_check.mjs`; A additionally ships `quest_check.mjs`.
10. **Condition identity was not inspected.** No mapping, parent-directory scan, `.xcoding` identity file,
    or condition label was read. Report labels are A/B only.

## 12. Residual risk

- **B:** the high defect is presentation-layer only, but it is player-visible in the core mining loop
  (dig down, see sky) and is exactly the standard's listed high defect. It cannot be waived as polish.
  A fix would be an underground backdrop pass (draw a cave/stone layer for air below the surface before
  the darkness overlay). Until then B's PES is capped at 60.
- **A:** no high-integrity risk found. Residual risks are scope/polish: no minimap or coordinate readout,
  no touch controls, and a 2,106-line `main.js` that makes future changes harder. The full quest was
  validated through UI actions with staged late materials, so a completely unassisted end-to-end quest
  run remains an untested convenience path, not an integrity risk.
- **Shared:** headless-only visual and audio validation; a real desktop browser may differ in font
  rendering and audio behavior. Both artifacts' own checks and this evaluation agree on the core loop.

**Final: A 88.8 / B 65.0. A is higher. Condition identity withheld.**

