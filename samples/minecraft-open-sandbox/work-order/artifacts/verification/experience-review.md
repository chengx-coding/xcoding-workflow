---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__verify-experience
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Verification — experience, visual state and controls review

## Scope and method

Reviewed the ten final scene screenshots from
`artifacts/verification/browser/screenshots/` (`welcome`, `day`, `night`, `backdrop`, `zoom1`,
`zoom2`, `cave`, `inventory`, `crafting`, `guide`), the structured browser self-test result
(`summary.json`, 21 steps), the product `index.html`/CSS/UI sources, and `README.md`. The review
checks the user-facing quality contract Q2 (Minecraft feel), Q4 (first-run affordance), Q5
(visual-state backdrop), Q7 (documented controls) and Q8 (experience lens), plus legibility and
layout sanity. No product code was changed by this review.

## Findings against the quality contract

### Q2 — Minecraft feel: pass

- `day`/`night` screenshots show chunky 32 px blocks with generated textures (grass edge highlight,
  plank grain, cobble clusters, ore specks), trees with trunks/canopies, rolling surface, a player
  sprite with walk animation, a hotbar, a minimap and a generated sky with sun/clouds. `night` shows
  a star field, a moon, a darker world and warm torch pools around the hut — the reference's
  day/night and "dark places need light" feel is visibly present.
- The self-test proves the verbs behind the look: real pointer hold-to-mine breaks a block and
  grants the drop, real right-click places a block and consumes it, real keyboard input moves the
  player, the crafting panel is operated by clicking a real button, and both save and reload work.
- `cave` demonstrates light falloff and torch lighting in a way that is obviously different from
  the surface scene (35.3 mean-brightness difference), so light is not merely decorative.

### Q4 — First-run affordance: pass

- `welcome.png` shows the first screen with three large buttons (**Play now**, **Open the guide**,
  **New world**), a one-line controls summary and a storage note. The self-test confirms the overlay
  is visible on a fresh load, that all three entry points exist, and that clicking **Play now**
  dismisses it.
- Behind the overlay the HUD already exposes **Quests / Inventory / Crafting / Guide / Backdrop /
  Save / Menu** as real buttons; the self-test checks all seven are rendered with a non-zero size.
  The quest tracker is visible on first run with a concrete next action, a hint and a progress meter.
- Contextual hints exist for hover targets ("Mine Stone (hold left click)", "Needs a pickaxe",
  "Place …"), and every primary system therefore has a visible, clickable, or task-driven entry
  point — no system is discoverable only from a key list or the README.

### Q5 — Visual-state backdrop: pass

- Edit changes: mining/placement produce the bottom-right two-tile **Before / After** panel with
  labels (`Grass → Air`, `Air → Planks`) and a world-space ghost layer in backdrop mode
  (`backdrop.png` shows dashed before-state ghosts across the hut, and the frame differs from the
  normal day frame by 27 % of sampled pixels).
- Mode change: pressing **Backdrop** shows a `Build mode → Backdrop mode` pulse, dims the world veil
  and raises the ghost layer; the self-test asserts the pulse kind, labels, panel visibility and the
  pressed state of the button.
- Time change: waiting three hours raises a `10:47 → 13:47`-style time pulse, the phase chip updates,
  and the sky palette demonstrably changes (asserted by comparing sky colours before/after).
- Viewport change: mouse-wheel zoom raises a `1.0x → 1.8x`-style view pulse and the minimap keeps a
  dashed previous-viewport rectangle for a few seconds; the zoom pair differs by 56.8 % of sampled
  pixels and the `zoom1`/`zoom2` screenshots show different visible extents.
- Undo/redo replays the before/after states, so removed content is not only visible but recoverable.

### Q7 — Documented controls: pass

- The in-product guide (screenshot `guide.png`) lists 16 controls with their effects, a five-step
  how-to-play sequence, and a saving note. The self-test counts the rows (≥12) and asserts Mine,
  Place and Save are present.
- `README.md` carries the same complete controls table, plus saving/export/import, checks and
  layout documentation. The two sources agree on the bindings.

### Q8 — Experience lens: pass

- **Discoverability**: first-run welcome, persistent quest tracker, seven HUD buttons, hover hints
  and unlocking recipes ("Gather coal to unlock torches") form a layered entry path.
- **Visual review**: before/after pulse, ghost layer, minimap trail, day/night sky and the cave light
  pools make state changes inspectable without a debugger.
- **Progression**: the 8-step task chain is visible with meter and rewards, tool tiers change mining
  speed, recipes unlock with materials, and progress persists across reloads.

## Legibility and layout observations

- HUD badges, quest text, panel copy and the hotbar are legible at 1280×800; contrast is adequate on
  both day and night backgrounds.
- The inventory, crafting and guide panels are centered, scrollable at 86 vh, closable with a visible
  ✕ and `Esc`, and their icons read correctly (wood, planks, cobblestone, torch, pickaxe, axe,
  shovel, glass).
- The quest tracker occupies the upper-left quarter of the screen. It can be hidden with `Q` or its
  **Hide** control, and it is hidden by default below 900 px width. It can overlap the moon at some
  times of day; this is cosmetic and acceptable for a game HUD.
- The minimap is legible (surface colours, viewport rectangle, player dot) and hides below 780 px.
- At night the unlit underground is very dark, which is intentional (torches are the remedy); surface
  play and torch-lit areas remain readable.

## Minor limitations (no acceptance impact)

- The first-run welcome is blurred-background only; the world behind it is decorative rather than
  interactive until Play is pressed (intended).
- Sound quality cannot be judged from screenshots; only the gesture-gated state path is checked.
- The narrow (<780 px) layout is implemented but not screenshot-reviewed in this run.

## Conclusion

The visual and interaction evidence supports Q2, Q4, Q5, Q7 and Q8 without a blocking finding. The
game looks and behaves like a small Minecraft, the first screen offers a visible way in, and every
state change that removes, covers or recontextualises content leaves a visible before/after record.
