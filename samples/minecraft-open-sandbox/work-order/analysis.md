---
schema_version: 1
document_kind: work-order-analysis
content_language: en
work_order_id: 20261104-1337-2d-sandbox-game
feature_ids: []
orchestration:
  main_tree_ref: /work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml
---

# Work Order Analysis: Emberblock

## Evidence and Current State

The starting project is a vanilla HTML/CSS/JavaScript canvas shell. Its world is flat and its
`player`, `render`, and `main` modules are placeholders: there is no movement, mining, building,
crafting, saving, or real HUD. The existing six Node tests verify the config contract, world
dimensions, terrain layering, bounded block access, serialization, and solidity. `page_check.py`
verifies required page IDs, offline asset references, the green `#status` ready pixel, and a
colour-rich canvas. These seed checks remain binding.

The request is a playable offline 2D sandbox inspired by Minecraft with local progress saving and
documented controls. The goal translates that into a pocket survival-sandbox loop: explore, mine,
collect, craft, build, and persist. It compares against Minecraft's core loop qualitatively, not its
content volume. No user-sourced material exclusion exists beyond the offline, no-build platform.
Mobs, hunger, redstone, and dimensions are unrequested; the analysis neither promises them nor bans
them.

The analysis evidence and full capability/journey tables are in
`artifacts/analysis-evidence.md`. Output surface: **visual**, with the proposed experience lens. This
is an interactive visual experience product, so the first-run affordance, visual-state backdrop,
interaction truth, and responsive checks apply. No stateful-surface gap is unresolved.

## Reconciliation and Request Fidelity

| Capability | Priority | Acceptance anchor | Verification |
| --- | --- | --- | --- |
| Offline launch, visible Play and Help | must | Fresh `file://` frame is interactive with no network request | page check, CDP, screenshot |
| Deterministic world with hills, caves, ores, trees | must | Recognizable layered terrain and safe spawn | Node generation tests, visual review |
| Move, jump, collide | must | Keyboard changes player position and solid tiles stop it | physics tests, CDP |
| Mine with reach, hardness, tool tier | must | Held pointer completes or refuses with visible reason; drop changes inventory | unit tests, CDP |
| Place/break blocks and persist edits | must | Right click consumes and changes tile; reload restores it | save tests, CDP |
| Inventory, stacking, hotbar | must | Transfer, merge, select and full-inventory refusal work | inventory tests, CDP |
| Hand/table/furnace crafting and progression | must | Recipe availability respects station and materials | recipe tests, CDP |
| Day/night, darkness, torch light | must | Night and caves are materially darker; torch lights locally | light tests, screenshots |
| Health, fall damage, death/respawn | must | Fall consequence and respawn preserve the pack | physics tests, CDP |
| Autosave, manual save, guarded reset | must | Primary journey survives reload; reset requires confirm | save tests, CDP |
| Cohesive HUD, pause, help, responsive layout | must | 960×600 and 480px-wide layouts keep primary actions visible | screenshots, DOM rect probe |
| Particles, procedural audio, minimap, quest strip | should | Each is visible/audible and toggleable where applicable | screenshots, manual, CDP |

The map has no silent omissions. Every must maps to implementation and an executable or manual
probe. The should rows materially improve feel and first-run discoverability; they are small enough
to include without diluting the core loop.

### Minecraft signatures

Editable blocks, tool-gated progression, light rhythm, and a cohesive survival HUD are musts.
Finite-world orientation (coordinates plus minimap) and ambient audio/particle feedback are shoulds.
Mobs/combat/hunger/redstone/dimensions are outside the pocket loop but are not recorded as binding
non-goals. This keeps the goal from narrowing the request while focusing implementation.

### Stateful journeys

1. Fresh launch: Play hides the overlay, starts input, shows the tutorial and save state.
2. Persistence: a marked block, inventory, position, health, and time survive reload.
3. Corrupt save: fallback to a new world with an explanatory, non-blocking notice.
4. Refused mining: no tier-appropriate pickaxe yields feedback and no drop.
5. Refused crafting: no nearby station or missing materials yields actionable feedback.
6. New-world reset: explicit second confirmation is required; cancel preserves the save.
7. Responsive: help, inventory, hotbar, and primary actions remain usable at narrow width.

## Impact, Risks, and Recommendations

- **Rendering budget:** a finite 320×144 tile world keeps only the visible window in the render loop.
  Cache procedural 24×24 textures and recompute light on edits and slow time ticks, not every frame.
- **Persistence:** store a compact diff against the generated baseline plus player/inventory/time.
  Validate every field and coordinate on load; a corrupt payload must not prevent boot. Use a
  memory fallback if `localStorage` itself is unavailable.
- **Input and accessibility:** use window-level keyboard handlers, ignore them in editable controls,
  and restore canvas focus after closing overlays. Buttons must be real DOM controls with labels.
- **First-run clarity:** the start overlay is more than a key hint; it has Play/Continue, New World,
  and How to Play. The in-game quest strip makes the next action obvious.
- **Visual-state truth:** day, night, and underground must be materially different, with a coherent
  sky/backdrop rather than a flat tint. Torch glow must be local and visible.
- **Scope discipline:** stop at the feature set above. Spend the remaining budget on texture detail,
  motion, feedback, save robustness, and verification rather than adding new systems.

Recommendation: proceed with an offline, side-view, finite tile world and DOM overlays, implemented as
pure testable modules (config, RNG, world, inventory/crafting, physics, save) plus browser modules
(textures, audio, renderer, UI, main). Verification profile: visual plus executed Node and headless
browser probes across start, core loop, persistence, refusal, reset, and responsive states.

## Design Options and Accepted Scope

- **Chosen:** 2D side-view finite tile world with DOM HUD/overlays. It preserves vertical mining,
  caves, gravity, and side-view building while staying accessible, testable, and library-free.
- **Rejected:** top-down view (loses Minecraft's vertical identity); WebGL 3D (contradicts the 2D
  request and adds needless risk); canvas-only UI (weaker hit-testing and accessibility).
- **Accepted scope:** the capability map above. **Release trigger:** all must capabilities pass their
  probes and the seed checks remain green. **Re-entry:** any failed must goes back through the
  approved solution's implementation/verification boundary rather than being silently dropped.
