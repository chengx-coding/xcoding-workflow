---
schema_version: 1
document_kind: work-order-result
content_language: en
work_order_id: 20261104-1337-2d-sandbox-game
feature_ids: []
orchestration:
  main_tree_ref: /work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml
---

# Work Order Result: Emberblock

## Delivered

Emberblock is a complete, playable, offline 2D sandbox game. Opening `/work/index.html` directly in a
modern browser starts a compact Minecraft-inspired loop: explore a generated valley, mine blocks,
collect materials, craft at a pack/table/furnace, build, light caves, survive falls, and return later
to the same saved world. The game uses only local HTML, CSS, and vanilla JavaScript; all block art,
sky/lighting, audio, and world data are generated in the browser.

Delivered product surface:

- Seeded 320 × 144 tile world with hills, soil/stone strata, winding caves, coal and iron, oak trees,
  flowers, tall grass, sky light, day/night, parallax hills, clouds, and a surface map.
- Movement, sprint, coyote-time jump, collision, fall damage, ten hearts, regeneration, death, and
  respawn with the pack retained.
- Held-pointer mining with reach limits, per-block hardness, pickaxe-tier gates, drops, stackable
  inventory, hotbar selection, right-click placement, middle-click pick, torch support, and particles.
- Hand, crafting-table, and furnace recipes: planks, sticks, table, torches, wooden/stone/iron
  pickaxes, furnace, stone bricks, iron ingot, and glass. Stations must be placed within reach.
- Local persistence with a versioned diff save, autosave, manual save, visible save state, guarded
  new-world reset, and safe recovery from corrupt data.
- First-run title with visible Play/Continue and How to Play, in-game quest strip, help/pause/death/
  confirm panels, responsive HUD, minimap, procedural audio with mute, and documented controls.
- 25 automated unit tests, the seed's static/browser check, a standard-library CDP interaction probe,
  and durable screenshots under `artifacts/evidence/`.

**Controls:** A/D or arrows move; W/Space/Up jumps; Shift sprints; hold left mouse mines; right mouse
places or opens a targeted table/furnace; 1–9 or wheel selects; E opens the pack; H/? opens help;
M toggles the map; Ctrl/Cmd+S saves; Esc closes a panel or pauses. The same list is in the README and
in the in-game How to Play panel.

## Validation Evidence

Executed in `/work` with Node v24.22.2, Python 3.12.3, and Google Chrome 157.0.8103.38:

```console
node --test "tests/**/*.test.js"
# 25/25 pass (6 seed + 19 project tests)

python tools/page_check.py
# exit 0; static asset/reference checks pass; required page IDs present;
# green ready marker [46, 204, 113]; 145 canvas colour buckets

python tools/play_probe.py --page index.html --out <workbench>/tmp/verification-browser
# exit 0; ok=true; 34/34 checks; 10/10 pointer clicks; 60.7 fps;
# no external requests; no console exceptions or error logs
```

Visual evidence: `artifacts/evidence/start.png`, `help.png`, `playing.png`, `day.png`, `night.png`,
`cave-torch.png`, `inventory.png`, `narrow.png`, `corrupt-recovery.png`, and `pointer-state.png`.
Stateful evidence: persistence after manual save/reload, corrupt-save recovery, full-pack craft
refusal, tool-gated stone refusal, table/furnace/iron progression, stack transfer/split/quick move,
lethal fall → death → respawn, pause → guarded New World cancel/confirm, Return to Title/Continue, and
M-key minimap toggle. Full mapping is in `artifacts/verification.md`.

The verification confirms every must capability and the should capabilities for particles, audio
dispatch, minimap, and quests. The only should-level quality gap is that headless verification cannot
judge subjective audio timbre; the WebAudio calls and mute state executed without error.

## Baseline, Version, and Report

**Feature baseline:** not applicable. This create work order had no existing feature directory and
no prior capability inventory; none was created.

**Version:** the project bridge declares no version policy. The game uses internal build `1.0.0` and
save schema `1`; no external release asset or package version was changed.

**Report:** waived by the project bridge — `work_order.requires_report=false` and
`work_order.report_skip_reason=user_waived`. No change-report HTML or manifest was produced. Workbench:
`/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/`.

## Deviations and Residual Risks

- **Scope:** no approved-capability deviations. The implementation removed the unused seed
  `js/player.js` placeholder, because `js/physics.js` now owns the player; no user-facing capability
  was dropped or thinned.
- **Coherence additions:** the initial save on Play, block-edge seams, cave visibility floor, inline
  inventory feedback, and the CDP evidence harness are implementation/quality details inside the
  accepted offline, persistent, readable game scope, not new product systems.
- **Fixed-aspect canvas:** the 960 × 540 render is scaled to the viewport. Extremely tall portrait
  windows stretch scene proportions, though the HUD and panels remain usable and were checked at
  480 × 700. The product is documented as designed for landscape.
- **Storage availability:** a browser that disables local storage can still play but cannot guarantee
  reload persistence; the game shows a session-only warning instead of crashing.
- **Audio:** procedural effects run and mute persists; subjective loudness/timbre was not audited on
  physical speakers in this headless environment.
- **No project commit** was created, per the bridge; the enclosing repository owns the sample commit.
