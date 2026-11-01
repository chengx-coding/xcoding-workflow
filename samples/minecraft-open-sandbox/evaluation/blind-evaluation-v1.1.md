# M2D-SES-OSS v1.1 — Blind re-score of A and B

**Standard:** `M2D-SES-OSS v1.1` (`STANDARD.md`) + `PROFILE-OPEN-SANDBOX.md` v1.1
**Prompt under test:** the fixed open 2D sandbox prompt (no feature list, no non-goal list)
**Artifacts:** `A` and `B` (identities hidden; condition not inferred)
**Evaluated:** 2026-11-01 22:23–22:47 (+08:00), headless Chrome 1280×800, `file://` origin

| | PES (75%) | ECS (25%) | Raw composite | Caps applied | **Final composite** |
| --- | ---: | ---: | ---: | --- | ---: |
| **A** | 80.8 | 81.3 | 80.9 | none | **80.9** |
| **B** | 65.4 → **60.0** | 86.1 | 70.6 | **one high defect** (PES ≤60, composite ≤65) | **65.0** |

A is the stronger player experience by a wide margin; B is the stronger engineering artifact.
Both boot, render, save/restore and survive a corrupt save. A carries no confirmed high defect;
**B has one confirmed high defect** — dug ground exposes the sky/parallax layer instead of an
underground read (§3).

---

## 0. Blind protocol

Read: this standard, the open-sandbox profile, and the two artifact directories' own files.
Not read: any parent/sibling directory, `.xcoding` configuration or mapping files, the public
sample README, the prior v1.0 evaluation or score sheet, or anything naming a condition. No mapping
file, work-order narrative or score sheet was opened before scoring both artifacts.

Process traces inside the artifacts (e.g. a README sentence that attributes a scope decision to an
upstream analysis; a JS debug namespace named after the game) were treated as ordinary product
content. They were not used to infer condition and are not reported as evidence.

All checks below were executed by an independent DevTools-Protocol harness, not by the artifacts'
own verification scripts, so that neither artifact grades itself.

---

## 1. Executed evidence

Raw records: `blind-v1.1-evidence/A/facts*.json`, `blind-v1.1-evidence/B/facts*.json`.
Screenshots: `blind-v1.1-evidence/A/*.png`, `blind-v1.1-evidence/B/*.png`.

| Check | How executed | A | B |
| --- | --- | --- | --- |
| G1 offline boot | `Page.navigate` to the artifact's `index.html`; captured every `Network.requestWillBeSent` | booted, 14 requests, all `file://` | booted, 15 requests, all `file://` |
| G2 fatal errors | `Runtime.exceptionThrown`, `consoleAPICalled(error)`, `Log.entryAdded` across every harness session | 0 errors | 0 errors |
| Unit suites | `node --test tests/*.test.js` | **29/29 pass** (4 suites) | **41/41 pass** (9 suites) |
| First frame | screenshot at ready +1.2 s | `01-first-frame.png` | `01-first-frame.png` |
| Target readout | hover a tree, read the target element | `"Oak Log LMB mine"` + outline + crack overlay | outline + crack overlay; **no target text readout** |
| Mining journey | hold LMB on a trunk, read hotbar/quest before and after | quest `logs 0/4 → 1/4`, slot `Oak Log ×1` | slot `Wood ×1 → ×2` |
| Placement journey | select the mined block's slot, right-click above ground | dirt placed, slot `×1 → empty` (`42-after-place.png`); torch placed earlier `×3 → ×2` | dirt placed, slot `×1 → empty` (`40-place-check.png`) |
| Placement refusal | right-click with nothing placeable / no support | `"Cannot place Torch needs a nearby solid block"` | `"No block selected in the hotbar."` |
| Crafting journey | `E`, read panel, click first enabled recipe | `Oak Log 1/1 → Oak Planks ×4` executed (`craftPanelAfter`) | `Wood 2/1 → Planks ×4` executed |
| Save / reload | pause, reload, compare HUD | torch ×3, log ×4, planks ×2 and quest `1/4` identical after reload | hotbar identical, toast `"Welcome back. Your world was restored."` |
| Corrupt save | leave page → poison `localStorage` → return | boots `ready`, `"The old save could not be read. A new world begins."` | boots `ready`, `"The old save could not be read; a fresh world was created."` |
| Day/night | real-time wait, screenshots at dusk/night | `20:07` and `23:59` night; moon, stars, campfire light pool, **3 hollows visible** | `Dusk`, `Night`; stars, moon, darkened sky/water |
| Underground read | dig a 4-block shaft, then a 3×2 room; screenshot and sample pixels | 4-deep shaft and 3×2 room both show a dark textured hollow backdrop; no sky bleed (`30-deep-shaft.png`, `50-wide-dig.png`) | 4-deep shaft and 3×2 room both expose the **sky/hill background**; the hill silhouette is visible continuing through the hole (`50-wide-dig.png`, `zoom-wide-dig.png`) |
| Responsive | 800×600, 960×540, 1280×800 | fills each viewport, no clipping, help/footer adapt | scales down; at 1280×800 the canvas stays 960×540 inside black bands |
| Help / pause | `H`, `Esc` | full control guide + goal prose; pause with stats/seed | control list + progression note; pause with seed/size |

Not executed (evidence limits in §9): the artifacts' own `browser_check`/`quest_check`/`page_check`
tools, a full end-to-end quest completion by hand, combat resolution, a walk to the world border,
touch/mobile devices, audible audio, and long-run performance.

---

## 2. Gates

| Gate | A | B |
| --- | --- | --- |
| **G1** offline boot from `file://`, no network/build | **Pass** — 14 local requests only | **Pass** — 15 local requests only |
| **G2** no fatal error, page renders | **Pass** — 0 exceptions/console errors across all harness sessions | **Pass** — 0 across all harness sessions |
| **G3** save/recovery | **Pass** — reload restores inventory, quest, world; corrupt save falls back to a fresh world with a message | **Pass** — reload restores world/inventory; corrupt save falls back with a friendly message |

---

## 3. Defects

### A

| Severity | Defect | Evidence |
| --- | --- | --- |
| High | none confirmed | floor = bedrock rows, x clamped to world bounds (`player.js:242`), unit invariants for bounds; 4-deep shaft and 3×2 dig keep a dark hollow read (`zoom-wide-dig.png`); no save/boot failure; controls readable |
| Medium | **No spatial orientation beyond time/seed** — no coordinates and no map; the player cannot state where they are | HUD shows clock/day only; seed appears only in pause; `facts2.pauseText` |
| Low | Save-recovery message leaks a raw JSON parser string to the player | `"…(Expected ',' or '}' after property value in JSON at position…"` in `facts3.corrupt.body` |

### B

| Severity | Defect | Evidence |
| --- | --- | --- |
| **High** | **Underground removal reveals the sky/background layer — no underground read.** A 3×2 excavation shows the distant hill silhouette and sky continuing through the hole; a 4-deep shaft is a flat slate strip | `50-wide-dig.png` + `zoom-wide-dig.png` (hill edge visible through the dug cells); `30-deep-shaft.png`; dug-cell pixels sample to background colours (e.g. `(67,92,107)`), not a rock layer |
| Medium | **Weak framing at common desktop sizes** — the play area is capped at 960×540 and centred in black; at 1280×800 the game occupies ~60% width / 67% height, and large black bands dominate the first frame | `01-first-frame.png`, `11-1280x800.png`; `css/style.css:28` (`width: min(960px, 100vw)`), canvas never upscales |
| Low | No reduced-motion support, no fullscreen, single 620 px breakpoint | `style.css` has one `@media`, no `prefers-reduced-motion` |
| Low | Debug surface left on `window.__sandbox` in the shipped page | `main.js:609` |

Medium count: A = 1, B = 1 → the "three or more mediums apply −10 composite" rule is **not** triggered
for either artifact.

### The confirmed high defect in B (investigated, not assumed)

This was the decisive check of this re-score. A single 1-block test was not enough: the first pit
looked like an ambiguous dark tile, so both artifacts were put through the same 3×2 room excavation.

- B's dug cells show the **background hill and sky**, not a ground material. The zoom
  (`zoom-wide-dig.png`) shows the hill silhouette edge continuing straight through the hole, and the
  dug-cell pixels sample to background colours rather than a rock layer.
- A's identical 3×2 excavation (`zoom-wide-dig.png` under A) shows a dark, speckled hollow backdrop
  with no sky bleed, so A does not share the defect.

The standard lists this exact failure ("underground removal reveals sky/blank canvas") as a high
defect, and it is player-visible on the core mining verb from the first minute. The caps therefore
apply to B: **PES ≤60, composite ≤65**.

---

## 4. PES — player experience (75%)

### A — Mosswild-style valley sandbox

| ID | Dimension | Wt | Score | Weighted | Basis |
| --- | --- | ---: | ---: | ---: | --- |
| D1 | Core verbs & controls | 10 | 90 | 900 | walk/sprint/jump (coyote + buffer), mine, place, 1–9/wheel, health+hearts, fall damage, death→respawn, sword combat; refusals named in words (`"Cannot place Torch needs a nearby solid block"`); every control listed in the in-game guide |
| D2 | Worldgen, biomes, physics | 16 | 70 | 1120 | seeded 224×96, hills, caves, spawn stair, camp/torch landmarks, 3 ore tiers, trees, sealed bedrock; **no water, no sand, no biomes** (v1.1 coverage items) |
| D3 | Mining/placement feedback | 10 | 88 | 880 | target outline + `"Oak Log LMB mine"` tooltip, crack overlay, particles, tool swing arc, synth sounds, placement refusal; no ghost placement preview |
| D4 | Inventory, crafting, progression **(signature)** | 22 | 86 | 1892 | 9-slot hotbar + backpack with counts + tool belt with durability; 16 recipes; handcraft vs. placed-workbench station; 3 tiers × 3 tool types; iron/amberstone gating; 8-step field-notes chain ending in the lantern; **no smelting/ingots** (raw iron shard is the input); discoverable from first-run (`E pack` on the tutorial card, HUD footer, guide, and quest step 2 "Press E.") and the log→planks craft was executed |
| D5 | Presentation, character, UI, audio | 18 | 84 | 1512 | layered parallax hills, gradient sky, drifting clouds, day/night with moon+stars, campfire/torch light pools, flowers and grass detail, character with held tool + walk bob + swing + attack streak, hearts, polished modals with backdrop blur, synth SFX + ambience + mute |
| D6 | Orientation & map | 6 | 40 | 240 | clock with clock track and day counter, seed in pause; **no coordinates, no minimap** (≤60 rule applied) |
| D7 | Replay, objectives, combat | 8 | 86 | 688 | seeded new world (confirm), pause/help, 8-step objective chain with progress, hollows at night with health/sword/death/respawn, completion overlay |
| D8 | Accessibility & responsive | 4 | 82 | 328 | extensive roles/aria-live/aria-labels, keyboard-only play, `prefers-reduced-motion` block, breakpoints at 900/620 px + height queries, fills 800/960/1280 with no clipping |
| D9 | First-run discoverability & docs | 6 | 86 | 516 | tutorial card with keys, field-notes objective + hint, `H` guide, HUD footer, README; crafting is visible twice before any menu is opened |
| | **PES total** | 100 | | **8076 → 80.76** | |

### B — Blockhaven-style compact sandbox

| ID | Dimension | Wt | Score | Weighted | Basis |
| --- | --- | ---: | ---: | ---: | --- |
| D1 | Core verbs & controls | 10 | 78 | 780 | walk, jump, swim-up, mine, place, 1–8/wheel, reach rules, coyote time, respawn; refusals named (`"No block selected in the hotbar."`); no sprint; no combat/health (absent, not penalised as a defect) |
| D2 | Worldgen, biomes, physics | 16 | 72 | 1152 | seeded 192×96, rolling surface, dirt/stone strata, caves + surface shafts, coal + crystal, trees, **sand patches and lakes with swimming and water light attenuation**; no biomes; sand does not fall (static water/sand) |
| D3 | Mining/placement feedback | 10 | 76 | 760 | target outline (reach-coloured), crack progression, break/place particles, synth SFX, place refusal toast; **no target name/action readout**, no placement preview |
| D4 | Inventory, crafting, progression **(signature)** | 22 | 64 | 1408 | 8-slot hotbar with counts, 5 recipes, atomic craft, executed wood→planks; **no backpack view, no station, no tool durability, no smelting/ingots, 2 pickaxe tiers, no goals/progression chain**; discoverable from first run (`"E craft"` in the HUD hint and the guide) |
| D5 | Presentation, character, UI, audio | 18 | 58 | 1044 | flat two-tone sky, two parallax ridges, blobs-as-clouds, day/night + stars/moon, water band, simple 18×44 character with arm/leg swing but **no held tool/block**, plain dark HTML panels, synth SFX; play area letterboxed in black at ≥1280 — plain-prototype band, capped at 60 |
| D6 | Orientation & map | 6 | 52 | 312 | live **X/Y coordinates** plus day/time and seed in pause; **no minimap** (≤60 rule applied) |
| D7 | Replay, objectives, combat | 8 | 50 | 400 | seed, new world with confirm, pause/help, day/night; **no objectives and no combat** |
| D8 | Accessibility & responsive | 4 | 55 | 220 | canvas/hotbar labels, scalable down to 800; fixed 960 cap + black letterbox above it, one media query, no reduced-motion |
| D9 | First-run discoverability & docs | 6 | 78 | 468 | one-line control hint including `E craft`, first-run toast objective, `H` guide with a progression note, README with controls and verification |
| | **PES total** | 100 | | **6544 → 65.44 raw; 60.0 after the high-defect cap** | |

---

## 5. ECS — engineering (25%)

### A

| ID | Dimension | Wt | Score | Weighted | Basis |
| --- | --- | ---: | ---: | ---: | --- |
| E1 | Tests & verification | 30 | 88 | 2640 | 29 Node tests (world determinism, cave/stair/camp invariants, RLE malformed rejection, bounded block access, collision, fall damage, damage cooldown, inventory binding, damaged-save sanitising, recipe/quest references, clock rollover) + 2 CDP browser scripts (interaction, full quest/death) + static/headless page check; 29/29 pass here |
| E2 | Architecture & readability | 25 | 68 | 1700 | clear module split with UMD wrappers and a separate content table, but `main.js` is a 2 106-line / 98-function god file (loop, input, enemies, saves, quests, crafting, UI wiring); `art.js` 995, `render.js` 957, `ui.js` 887, CSS 1 933 |
| E3 | Robustness, persistence, security | 20 | 84 | 1680 | versioned save, `sanitizeInventoryState`/`sanitizeProgress`/`getSafePlayer`, corrupt-save fallback verified, bounded world access, no network, text-built DOM; the parser error text leaks to the player (low) |
| E4 | Performance, accessibility, responsive | 15 | 82 | 1230 | fixed-step accumulator capped at 4 steps, resize handling, zero console spam, aria labels, reduced motion, three viewport regimes |
| E5 | Documentation & tooling | 10 | 88 | 880 | README covers controls, loop, saving, file map and reproducible checks; three local tools |
| | **ECS total** | 100 | | **8130 → 81.30** | |

### B

| ID | Dimension | Wt | Score | Weighted | Basis |
| --- | --- | ---: | ---: | ---: | --- |
| E1 | Tests & verification | 30 | 90 | 2700 | 41 Node tests over 9 suites (seed anchor, determinism, caves/ores/trees/water, RLE bounds, collision, coyote, swimming, respawn, snapshot round-trip, corrupt/foreign/out-of-range rejection, storage-failure reporting, atomic crafting, lighting, tool-gated mining) + a 702-line CDP interaction check that fails on console errors; 41/41 pass here |
| E2 | Architecture & readability | 25 | 88 | 2200 | 13 single-purpose modules, largest `main.js` 594 lines, clean data/state boundaries (`world`/`save`/`lighting`/`mining`/`crafting`), consistent UMD convention |
| E3 | Robustness, persistence, security | 20 | 90 | 1800 | strict snapshot validation (version, dimensions, block runs, player bounds, inventory, time), RLE length checks, storage probe with in-memory fallback + user warning, unbreakable floor/water, clamped player; corrupt-save verified |
| E4 | Performance, accessibility, responsive | 15 | 70 | 1050 | no console spam, sane loop, labels on canvas/hotbar; fixed 960 px cap and black letterboxing at ≥1280, no reduced-motion |
| E5 | Documentation & tooling | 10 | 86 | 860 | README documents controls, systems, deliberate scope, verification and layout; two local tools |
| | **ECS total** | 100 | | **8610 → 86.10** | |

The ECS totals are computed from the weights and scores in each table
(A: 2640 + 1700 + 1680 + 1230 + 880 = 8130; B: 2700 + 2200 + 1800 + 1050 + 860 = 8610).

---

## 6. Composite, floors and caps

```
composite = 0.75 × PES + 0.25 × ECS

A: 0.75 × 80.76 + 0.25 × 81.30 = 60.57 + 20.33 = 80.90 → 80.9
B, before caps: 0.75 × 65.44 + 0.25 × 86.10 = 49.08 + 21.53 = 70.61
B, one high defect (PES ≤60, composite ≤65): 0.75 × 60.00 + 0.25 × 86.10 = 45.00 + 21.53 = 66.53 → 65.0
```

| Cap | Rule | A | B |
| --- | --- | --- | --- |
| Blocker (unplayable / no offline boot) | PES ≤20, composite ≤30 | n/a | n/a |
| One high defect | PES ≤60, composite ≤65 | n/a | **applies** — PES 65.4 → 60.0, composite 66.5 → **65.0** |
| Two or more high defects | PES ≤50, composite ≤60 | n/a | n/a (one) |
| Three or more medium defects | composite −10 | n/a (1 medium) | n/a (1 medium) |
| Experience floor | PES<70 → composite ≤PES+10; PES<60 → ≤PES | n/a (PES 80.8) | ceiling 70.0; the high-defect cap (65) binds first |
| D4 hidden / absent crafting | ≤55 / ≤40 | not applied — crafting visible in first-run UI | not applied — `E craft` visible in first-run UI |
| D5 plain prototype | ≤60 | not in band (84) | **applied**, 58 |
| D6 without a real map | ≤60 | **applied**, 40 | **applied**, 52 |
| High-defect caps take precedence | — | none | **yes — overrides the higher raw composite** |

Global caps therefore: **none** for A; for B the **one-high-defect cap** sets PES 60.0 and composite
65.0, and it takes precedence over the PES<70 experience floor (which would have allowed 70.0).

---

## 7. Signature coverage

| Signature | A | B |
| --- | --- | --- |
| Seeded world beyond a flat strip | **Yes** — 224×96 hills, caves, ores, camp/stair landmarks; seed in pause | **Yes** — 192×96 rolling terrain, caves, surface shafts, lakes; seed in pause |
| Mine/place with readable feedback | **Yes** — outline + name/action tooltip + crack + particles + swing + SFX; place refusal named | **Yes** — reach-coloured outline + crack + particles + SFX; target has no name readout |
| Inventory/hotbar with counts or clear palette | **Yes** — 9 slots, counts, backpack, tool belt + durability | **Yes** — 8 slots, counts once held, clear palette |
| Crafting/progression loop | **Yes — deep.** 16 recipes, handcraft vs. placed-workbench station, 3 tiers × 3 tool types, durability, ore-tier gating, 8-step objective chain to a lantern; executed log→planks; **no smelting/ingots** | **Yes — shallow.** 5 recipes, atomic consumption, executed wood→planks; no station, no durability, 2 tiers, no objective, **no smelting/ingots** |
| Save/restore | **Yes** — versioned, sanitising, verified reload and corrupt fallback | **Yes** — versioned+validated, verified reload and corrupt fallback |
| Day/night or atmosphere | **Yes** — 5-min cycle, moon/stars, light pools, hollows at night | **Yes** — 4-min cycle, moon/stars, skylight attenuation |
| Orientation/minimap | **Partial** — clock/day/seed only; no coordinates, no map | **Partial** — clock/day, X/Y, seed; no map |
| Objectives/exploration loop | **Yes** — 8 field notes steps + completion overlay + death/respawn | **No** — first-run toasts only |

**Signature verdict:** both implement the defining gather→craft→build loop and save system.
A extends it into a progression chain with a station gate and a win condition; B stays at a compact
recipe list with no station, no durability and no goal. Neither implements smelting/ingots, and this
is scored in D4 (not treated as a defect, per the standard).

---

## 8. Where each artifact wins and loses

**A wins on experience.** Composition, character readability, held-tool visualisation, HUD craft,
atmosphere (night light pools), first-run teaching, and a genuine progression chain. It also has
combat and health, which B deliberately omits. It loses on engineering shape (one 2 106-line
god file behind otherwise good modules) and on orientation (no coordinates, no map).

**B wins on engineering.** Small single-purpose modules, the most thorough save validator in the pair,
and the widest automated coverage (41 invariants + a 702-line interaction driver). It loses on the
signature dimension's depth — no station, no durability, no progression, no goal — on presentation
(plain prototype, no held tool, letterboxed 960×540 frame), and it carries the pair's only confirmed
high defect: mined ground opens onto the sky/parallax layer, so digging breaks the world read.

Both are honest about their scope; B documents its deliberate omissions, A documents its survival
loop. Neither README is used as a substitute for discoverability: in both cases the crafting entry
point is visible in the first-run screen itself (`E pack` / `E craft`), so no D4 discoverability cap
was triggered.

---

## 9. Evidence limits and residual risk

1. **No full quest completion was driven by hand in A.** Log→planks was executed; the workbench
   station gate, stone/iron tiers and the lantern finale were verified by reading the live pack UI
   (station rows show "needs a placed workbench nearby") and by the artifact's unit invariant
   ("quest progress completes and the stone pickaxe step remains earned"), not by a hand-played
   end-to-end run. D4's 86 assumes the station path works as the tests assert.
2. **Combat was observed, not resolved.** Hollows were on screen at night with the player at full
   hearts; no hit/kill/death cycle was executed by the harness, so A's D7 combat credit rests on
   presence + code + unit coverage.
3. **World-border traversal was not driven.** Sealed floor and x-clamping rest on unit invariants
   (`player.js:242`, bedrock rows) and the deep-dig checks, not on a walk to the edge.
4. **One seed per journey.** Both worlds are random-seeded; the observed surfaces are not the only
   possible layouts.
5. **Audio is unverified.** Headless runs exercise the audio graph without audible output; only
   "no errors, mute toggle present, synthesized SFX/ambience code exists" is evidenced.
6. **The artifacts' own verification scripts were not run.** `tools/browser_check.mjs`,
   `tools/quest_check.mjs` and `tools/page_check.py` were located and are described by each README,
   but not executed, to keep the evidence independent (and to avoid writing into the artifact trees).
   Their claimed coverage is therefore not counted as executed evidence for PES; only the unit
   suites were executed.
7. **No touch/mobile pass.** Neither artifact claims mobile; tested viewports were 800×600,
   960×540 and 1280×800 only.
8. **B's high defect is a rendering judgement, but a well-evidenced one.** A single 1-block hole was
   ambiguous, so the finding was confirmed with a 3×2 excavation on both artifacts under identical
   coordinates and the same 1.9 s-per-block hold. If a reviewer rejects the classification, B would
   return to its raw 65.4 PES / 70.6 composite; the evidence (hill silhouette visible through the
   dug cells) supports the classification as written.
9. **Performance was not measured**, only the absence of console spam and a fixed-step loop.

---

## 10. Identity and v1.0 comparison

A and B were scored under hidden identities. No condition was inferred from file layout,
documentation style, tooling or process traces, and no mapping or prior evaluation was read.
Identity is intentionally left undetermined in this report.

No delta against the v1.0 evaluation is asserted, and no v1.0 score was reused: that evaluation was
out of scope by instruction, so the numbers above are an independent v1.1 re-score of the artifacts
as they exist on disk.

---

## 11. Reproduce

Probe sources (independent harness): `<workbench>/tmp/blind-eval-v11/probe*.mjs`
(`probe.mjs` boot/input/overlays/responsive, `probe2.mjs` target/mining/craft/save/corrupt,
`probe3.mjs` deep dig + corrupt + night, `probe4.mjs` placement, `probe5.mjs` bind-and-place,
`probe6.mjs` 3×2 excavation render check).
Each takes `(artifactLabel, artifactDir, evidenceDir)` and writes `facts*.json` + PNGs.

```console
# from each artifact root
node --test tests/*.test.js          # A 29/29, B 41/41

# evidence regeneration (example)
node tmp/blind-eval-v11/probe2.mjs A <artifactDir> <evidenceDir>
```

Evidence directory: `.xcoding/work-orders/20261102-open-sandbox-eval/artifacts/blind-v1.1-evidence/`
