---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__dyn-1__analysis-evidence"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Analysis Evidence: Emberblock

## Evidence and Current State

- Request: `prompt.txt` asks for a playable offline 2D sandbox inspired by Minecraft, launched by
  opening `index.html`, with no build, libraries, CDNs, or network access, local saving, and controls
  documentation.
- Project bridge: `/work/.xcoding/WORKFLOW.md` confirms the vanilla HTML/CSS/JavaScript seed, English
  deliverables, no project commit, the seed test commands, and a waived change report.
- Current code: the seed is a 960×540 canvas `game` with `status`, `hud`, and `hotbar` elements and
  placeholder modules for config, world, player, render, and main. It has flat terrain, no input,
  no persistence, and placeholder-only UI. Existing seed tests verify dimensions, bounded block
  access, air/solid behavior, and round-trip block serialization; `page_check.py` verifies required
  IDs, offline references, a green ready marker, and a colour-rich canvas.
- Environment: Chrome 157 is installed. `page_check.py` passes when `HOME` points into the workbench
  `tmp/` (Chrome otherwise cannot create its default profile). Node's built-in test runner is
  available. No browser automation package is installed, so interaction evidence will use a small
  standard-library Chrome DevTools Protocol probe or documented manual probes.
- Constraint facts: the game must be an actual product, not a screenshot or shell. Canvas art must
  be generated in the browser; no bitmap, font, or audio downloads are permitted.

## Request-to-Goal Comparison

The goal preserves every requested outcome. It adds no user-visible system that the request does not
support; the survival-lite health layer, quest strip, and sound/particle feedback are quality
supports for "playable" and "feels like a small Minecraft". No material exclusion is goal-authored.
The pocket scope prioritizes the Minecraft signature loop over content parity; mobs, hunger, and
dimensions are unrequested, so they are not recorded as binding non-goals or promised features.

## Capability Map

| Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- |
| Open and play offline | request, project | must | The product exists without installation or network | Fresh `file://` load reaches interactive world with no external requests | `page_check.py`; static reference scan; CDP load probe |
| First-run start and help | visual contract | must | A new player knows how to begin and find controls | Visible Play/Continue and Controls entry on first frame; help opens and closes | CDP visible-element assertion; screenshot review; 10/10 pointer clicks |
| Generated block world | request | must | Exploration and building require a world worth inhabiting | Seeded terrain has hills, layered strata, caves, ores, trees, and safe spawn | Node determinism and layer tests; visual screenshot |
| Move, jump, collide | request "playable" | must | The player can traverse the world | A/D or arrows move; Space/W jump; solid tiles block and ground the player | Physics unit tests; CDP movement before/after |
| Mine with reach, hardness, tool tier | Minecraft signature | must | Gathering changes what the player can do | Hold pointer: hardness and tool change duration, tier gates stone/ores, reach refuses distant tiles, feedback on refusal | Mining unit tests; CDP before/action/after inventory and block state |
| Place and break blocks persistently | Minecraft signature | must | Building is meaningful and durable | Right click consumes a block and changes the tile; break returns it; reload restores | World/save tests; CDP place/reload probe |
| Inventory, stacking, hotbar | Minecraft signature | must | Collected materials are usable | Items stack to limits, hotbar selects, inventory transfers, full inventory reports refusal | Inventory unit tests; CDP slot interaction |
| Crafting and station progression | Minecraft signature | must | Tools and building unlock progressively | Hand/table/furnace recipes filter by nearby station and ingredients; craft consumes and outputs | Recipe unit tests; CDP craft sequence |
| Light, night, torches | Minecraft signature | must | Darkness creates a navigation and building rhythm | Day/night changes palette and light; underground is darker; torch emits local light | Light unit tests; two screenshots day vs night/cave |
| Health, fall damage, respawn | goal quality | must | Risk gives movement consequence without hard loss | Fall >4 tiles damages, hearts update, zero health shows respawn with retained pack | Physics/damage unit tests; CDP death setup |
| Save, autosave, load, reset | request | must | Progress survives closing the game | Edits/inventory/position/time/health restore; corrupt save falls back; reset confirms | Save unit tests; CDP place/reload/reset journey |
| HUD, inventory, help, pause | request | must | Controls and state are legible | Readable at 960×600 and 480px width; Escape resumes; help lists all keys | Responsive screenshots; CDP 10/10 controls |
| Audio and particles | "playable", feel | should | Feedback and atmosphere make actions feel physical | Mute toggle; mine/place/craft/jump/hurt sounds; dust, chips, embers | Manual listening; particle state screenshot |
| Minimap / orientation | signature should | should | A finite world is understandable | Toggle M; terrain profile and player marker update | Screenshot; CDP toggle |
| Quest/tutorial strip | first-run affordance | should | New players have an obvious next step | Four visible objectives complete from real actions and persist | CDP action sequence; screenshot |

## Stateful Journeys and Integrity

| Journey | Before | Action | After | Verification |
| --- | --- | --- | --- | --- |
| Fresh start | Start overlay with saved world or no save | Click Play | Overlay hides, world is interactive, tutorial visible, save state shown | CDP: overlay hidden and canvas receives key input; 10/10 real pointer clicks |
| Persistence (primary) | Player has placed a marked block and moved | Wait for autosave, reload | Marked block, inventory, position, health, time restored | CDP set state, reload, inspect runtime state and screenshot |
| Corrupt save | Valid save | Corrupt storage, reload | New world generated; visible non-blocking notice explains fallback | Unit test decoder; CDP storage corruption and reload |
| Refused mining | Selected empty hand facing stone | Hold mine | No break/drop; visible "needs pickaxe" feedback; progress does not silently complete | CDP hold; assert block unchanged and toast visible |
| Refused crafting | No table nearby | Open crafting, click tool recipe | Disabled/blocked row says place a crafting table; inventory unchanged | CDP click; assert toast and inventory |
| Empty inventory | All slots empty | Open inventory | Slots show empty affordance; crafting list shows missing ingredients, no dead primary control | CDP reset inventory; inspect UI text |
| New-world reset | Existing world | Choose New World then confirm | Old save replaced only after explicit confirm; cancel preserves it | CDP cancel then confirm; compare seed/storage |
| Death/respawn | Health >0 | Fall from lethal height | Death overlay; Respawn returns at safe spawn with pack retained | CDP direct state setup; screenshot and storage |
| Responsive layout | 960×600 | Resize 480×700 | HUD, hotbar, help, and inventory stay within viewport; no clipped primary action | Headless screenshots and DOM rect checks |

## Signature-Experience Table (Minecraft)

| Reference capability | Evidence in Minecraft | Goal coverage | Decision | User value |
| --- | --- | --- | --- | --- |
| Editable block world | Break/place any block; builds persist | Covered | must | The core creative verb |
| Tool-gated progression | Wood → stone → iron pickaxes gate ores | Covered | must | Crafting changes capability, not just numbers |
| Day/night + underground light | Torches and daylight govern visibility | Covered | must | Exploration has rhythm and preparation |
| Cohesive survival HUD | Hearts, hotbar, inventory, crafting together | Covered | must | The game reads as one product, not a demo |
| Finite-world orientation | Coordinates, maps, landmarks | Covered via coords + minimap | should | Reduces lost-in-a-demo feeling |
| Ambient feedback | Particles, footsteps, block sounds | Covered | should | Actions feel physical |
| Mobs/combat/hunger/redstone/dimensions | Deep Minecraft systems | Absent | unrequested | Not required for a pocket sandbox; would expand scope without serving the requested loop |

The signature set is deliberately small and decision-changing. It is not a content-parity checklist.

## Alternatives Considered

1. **2D side-view finite tile world with DOM overlays (chosen).** Fits the "2D" request, makes block
   collision and light understandable, needs no libraries, and keeps UI accessible and testable.
2. **Top-down tile sandbox.** Easier collision but loses Minecraft's vertical mining, caves, falling,
   and side-view building identity.
3. **WebGL 3D voxel renderer.** Closer to Minecraft's camera, but conflicts with the explicit 2D
   request, adds substantial matrix/mesh complexity, and raises offline/performance risk.
4. **Canvas-only UI.** More game-like but weaker keyboard/accessibility and more hit-testing risk.
   DOM overlays plus a canvas world give the best mix.

## Impact and Risks

- **Performance:** visible tile rendering plus a light overlay must stay under frame budget. Mitigate
  with cached procedural textures, visible-range loops, and light recomputation only on edits/time
  ticks. Verify frame cadence and inspect long tasks.
- **Storage on `file://`:** localStorage is broadly available but may be disabled. Implement a
  memory fallback and a visible "Saving unavailable" notice; never crash.
- **Save integrity:** store a compact diff against the generated baseline, validate every field and
  coordinate, and fall back to a fresh world on corrupt data.
- **Input focus:** canvas/overlay focus can swallow keys. Bind window-level keys, ignore them while
  text-like controls are focused, and return focus to the canvas after closing overlays.
- **Scope drift:** adding mobs or a full tech tree would dilute the loop. Stop at the agreed
  signature set and spend remaining effort on feel, persistence, and verification.
- **Responsive layout:** a dense HUD can occlude the canvas at 480px. Hide non-essential HUD text and
  allow the minimap/tutorial to collapse without hiding primary actions.

## Recommendation

Proceed with the 2D, finite, side-view tile world and DOM HUD. Output-surface profile: `visual`
(this is an interactive visual experience product; also apply the proposed `experience` lens for
discoverability, signature progression, and visual review). Implement the capability map as one
coherent vanilla JavaScript product, with pure modules for world/inventory/physics/save so they can be
tested in Node, and browser-only modules for procedural textures, audio, renderer, and UI.
