---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__dyn-1__implement-game"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Implementation: Browser Game

## Scope

Integrated the approved sandbox into a playable browser product: procedural textures, layered
rendering and lighting, the DOM HUD and overlays, procedural audio, real input mapping, mining and
placement, crafting stations, persistence, tutorial, pause/death/reset flows, and responsive layout.
Removed the unused seed `js/player.js` placeholder now that `js/physics.js` owns the player.

## Changed Paths

- `index.html` — replacement page shell: canvas, HUD, minimap, hotbar, overlays, dialogs, local script
  order. Kept the required `game`, `status`, `hud`, and `hotbar` IDs.
- `css/style.css` — full Emberblock visual system, responsive breakpoints, focus states, reduced
  motion, inventory/recipe layout, scrollbars, overlay states, ready marker.
- `js/textures.js` — deterministic 24×24 block variants, transparent leaves/glass/torch/plants, item
  and tool icons, cached procedural canvases.
- `js/audio.js` — WebAudio source synthesis for mine/break/place/jump/hurt/craft/pickup/save and mute.
- `js/render.js` — sky, stars, sun/moon, clouds, parallax hills, cave backdrop, tiles, sky/torch light,
  hover/cracks, particles, player animation, torch glow, minimap.
- `js/ui.js` — HUD, hearts, clock, quests, hotbar, start/help/pause/inventory/death/confirm screens,
  slot drag/right-click/Shift-click, crafting rows, station chips, inventory feedback, toasts, focus.
- `js/main.js` — boot/load, fixed-step game loop, camera, input, mining/placement, pick block,
  inventory/crafting actions, tool tiers, particles, health/regen/fall/death/respawn, day cycle,
  autosave/manual save, guarded reset, tutorial, minimap, error handling, debug verification surface.
- `tools/cdp_client.py` — standard-library Chrome DevTools Protocol client (Page, Runtime, Network,
  Input, screenshots, device metrics) for evidence.
- `tools/play_probe.py` — 34-check real-browser product probe with screenshots and JSON report.
- `tests/foundations.test.js` — added the furnace → iron ingot → iron pickaxe recipe chain test;
  suite is now 25 tests.
- `js/player.js` — removed as superseded placeholder.

## Evidence

All commands ran from `/work`. The Chrome profile `HOME` was a writable directory under the workbench
`tmp/` because the restricted container cannot create Chrome's default profile.

```console
node --test "tests/**/*.test.js"
# 25/25 pass

python tools/page_check.py
# ok=true: static references, required IDs, green status marker, 145 canvas colour buckets

python tools/play_probe.py --page index.html --out <workbench>/tmp/final-probe4
# ok=true: 34/34 checks, 10/10 pointer clicks, 60.4 fps, no external requests,
# no console exceptions/errors
```

The probe's durable screenshots are under `artifacts/evidence/`:

- `start.png`, `help.png`, `playing.png`, `inventory.png`
- `day.png`, `night.png`, `cave-torch.png`
- `narrow.png` (480 × 700 viewport)
- `corrupt-recovery.png`, `pointer-state.png`, `day-seams.png`

Additional manual browser scenarios executed through the same CDP harness:

- Placed a crafting table and furnace; crafted wood/stone/iron pickaxes; smelted three iron ingots;
  placed a torch in a cave and observed local warm light.
- Mined grass/dirt/stone in sequence; confirmed stone refused without a pickaxe with visible
  "needs a wooden pickaxe" feedback, then broke it with the wooden pickaxe and collected cobblestone.
- Moved stacks between hotbar and pack, right-click split/place-one, Shift-click quick move, held-stack
  return on close.
- Died from a lethal fall, confirmed the death overlay, respawned with retained pack, then reloaded.
- Confirmed pause → New World asks for confirmation even before the first save exists; cancel keeps
  the pause state; confirm begins a fresh world.
- Confirmed Return to Title saves and presents Continue; the M key hides/shows the surface map.
- Confirmed corrupt storage starts a fresh world with a visible notice.

## Acceptance Mapping

| Accepted capability | Implementation | Evidence |
| --- | --- | --- |
| Offline launch and first-run start/help | `index.html`, `ui.js`, `main.js` | page check; probe start/help checks; screenshots |
| World generation, caves, ores, trees | `world.js`, `rng.js` | deterministic/layer/cave/ore tests; screenshots |
| Movement, jump, collision | `physics.js`, `main.js` | physics tests; probe movement; manual jump |
| Mine with reach/hardness/tier | `config.js`, `main.js`, `render.js` | probe mining; manual stone refusal and pickaxe break |
| Place blocks and persist | `main.js`, `world.js`, `save.js` | probe placement; manual save/reload journey |
| Inventory/hotbar transfers | `inventory.js`, `ui.js`, `main.js` | probe inventory; manual drag/right/Shift-click |
| Crafting and stations | `config.js`, `inventory.js`, `ui.js` | recipe tests; manual furnace/iron flow; recipe UI screenshots |
| Day/night and torch light | `world.js`, `render.js` | day/night/cave screenshots; lighting tests |
| Health/fall/respawn | `physics.js`, `main.js`, `ui.js` | damage tests; manual death/respawn |
| Save/autosave/reset/corruption | `save.js`, `main.js`, `ui.js` | probe manual save/reload/corruption; manual reset |
| Responsive HUD/UI | `style.css` | 960 × 600 and 480 × 700 screenshots; narrow layout checks |
| Particles/audio/minimap/quests | `render.js`, `audio.js`, `ui.js`, `main.js` | visual/audio behavior; map toggle; probe screenshots |

## Convention Accounting

- **C1 project bridge:** English, UTF-8/LF, vanilla HTML/CSS/JS, no external libraries, CDNs, fonts,
  third-party assets, or runtime network access; no project commit. All followed. The game's only
  network-like strings are in the loopback CDP verification tool, which is not served or loaded by
  the game.
- **L1 convention discovery:** `found`, with the bridge as the applicable C1 source; no additional
  C1/C2 files, conflict, or ambiguity.
- **Seed checks:** unchanged tests preserved and passing; page shell IDs/status contract preserved.
- **No feature baseline change.**

## Residual Risk

None blocking. The render is a fixed 960×540 scene scaled to the viewport; extremely tall portrait
windows stretch block proportions even though the HUD/panels remain usable and tested at 480 × 700.
The game targets a normal landscape browser window. Browser storage availability is handled with a
session-only warning, but a browser that disables local storage cannot guarantee reload persistence.
