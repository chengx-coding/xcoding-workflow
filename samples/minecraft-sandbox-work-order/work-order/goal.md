---
schema_version: 1
document_kind: work-order-goal
content_language: en
work_order_id: 20261029-1219-2d-sandbox-game
feature_ids: []
orchestration:
  main_tree_ref: runtime/orchestration.xml
---

# Build a polished offline 2D sandbox game

## Requested outcome

Create a playable, offline 2D sandbox game inspired by Minecraft. The deliverable is
`index.html` in the project root, supported only by local CSS, JavaScript and test files beside it.
It must open by double-click and run from `file://` with no build step, package manager, external
library, CDN, web font, asset service or network request of any kind.

The verbatim product request is:

```text
# Build a 2D Minecraft-style sandbox

Create a playable, offline 2D sandbox game inspired by Minecraft. The whole game must live in a
single self-contained `index.html` file (inline CSS and JavaScript, or local files next to it), open
by double-clicking the file, with no build step and no network access.

Requirements:

- Procedurally generated terrain from a numeric seed, with at least grass, dirt and stone blocks.
- A player with gravity, left/right movement and jumping. The player collides with solid blocks and
  cannot pass through them.
- Left-click mines a block within reach. Right-click places the selected block in an empty adjacent
  cell. Blocks cannot be placed inside the player.
- A hotbar with at least four block types, number-key selection and a clearly visible selected state.
- A camera that follows the player and stays inside the world bounds.
- World and player state saved to `localStorage` and restored when the page is reopened.
- Clean, readable code and a short note describing the controls.

Deliver the finished page as `index.html` in the current working directory. Do not use external
libraries, CDNs, web fonts or network requests of any kind.
```

The experience should read as a finished small game rather than a mechanics demo: immediate visual
identity, a readable world, clear interaction feedback, and enough environmental variety that
exploration and building feel rewarding.

## Scope and constraints

### Product scope

- Retain and extend the seed's plain HTML/CSS/JavaScript structure. Do not introduce a framework,
  bundler, dependency, or network-loaded resource.
- Generate an interesting world from a numeric seed. The seed must be visible and reproducible, and
  the world must contain at least grass, dirt and stone with varied surface elevation and subsurface
  structure. Additional natural materials and decorative features are expected where they improve
  the world without obscuring the core blocks.
- Provide a player with acceleration-aware horizontal movement, gravity, jumping, coyote time or an
  equivalent forgiving control feel, and deterministic collision against solid blocks on all sides.
  The player must never tunnel through terrain during ordinary play.
- Provide click-to-mine and click-to-place interaction within a finite reach. Show the targeted cell
  before acting. Mining must remove only the targeted block; placement must reject occupied cells,
  out-of-world cells, unreachable cells, and cells that would intersect the player.
- Provide a hotbar of at least four placeable block types with visible icons and names. Number keys
  select slots, the selected slot is unmistakable, and the mouse wheel may also cycle selection.
- Keep the camera centered on the player where the world allows it, clamped to the world bounds at
  every edge, with no blank area outside the world.
- Persist world edits, the seed, the player's position and the selected hotbar slot to
  `localStorage`. Restore them when the page reopens. Corrupt or incompatible saves must fail safely
  to a fresh world without preventing the game from booting.
- Include a short, discoverable controls note in the page, plus an accurate README note covering
  what the page is, how to open it, the controls, the checks, and the architecture.
- Keep the browser modules loadable in Node for the existing logic tests. Add focused tests for the
  new world, physics, interaction and persistence behavior rather than weakening existing coverage.

### Technical and delivery constraints

- Offline operation and `file://` compatibility are hard requirements.
- No external libraries, CDNs, web fonts, remote images, analytics, fetches, sockets or other network
  requests. Visual assets must be drawn procedurally or stored locally.
- UTF-8 with LF line endings, two-space JavaScript indentation, and the existing UMD module style.
- Preserve the `#status` marker contract: `data-state="booting"` before boot, `data-state="ready"`
  after the first successful frame, and an error state for runtime failures. The page check samples
  this marker.
- No Git commit from this work order; the enclosing repository owns the sample's commit.
- Temporary screenshots, scripts and diagnostics stay under the work-order `tmp/` directory.
- No managed features are created; `feature_ids` remains empty.

### Quality contract

This result will be compared side-by-side with a strong one-shot attempt. It must be at least as
visually polished and feature-rich as that bar. Concretely, the finished page must have:

1. A distinctive, coherent visual identity with a clear hierarchy between world, HUD, target
   feedback, controls, and hotbar. It must not look like an unstyled mechanics demo.
2. Satisfying interaction feedback for movement, jumping, mining, placing, hotbar selection,
   save/restore, and error or blocked-action states.
3. World and feature variety: varied terrain silhouettes and materials, visible depth and surface
   detail, atmospheric background or lighting, and enough discoverable interactions to reward play.
4. Responsive presentation that remains legible and playable at common desktop viewport sizes,
   including canvas scaling without blurry or clipped UI.
5. A rendered-page verification pass: capture a screenshot, inspect it, compare it against the
   strong one-shot bar, and iterate on visual defects before verification is accepted.
6. An independent visual review of the final rendered page before the result is recorded. Any
   required finding from that review must be fixed and re-checked, or explicitly dispositioned with
   evidence.

## Acceptance conditions

The work order is complete only when all of the following are demonstrated:

- [ ] `index.html`, local CSS/JS, and the README form a runnable offline page with no network
      references or external assets.
- [ ] A numeric seed generates reproducible terrain containing at least grass, dirt and stone, with
      meaningful surface and subsurface variation.
- [ ] The player experiences gravity, left/right movement, and jumping; solid-block collision works
      on every side and the player cannot pass through terrain in ordinary play.
- [ ] Left-click mines one targeted block within reach; right-click places the selected block only
      in a valid empty adjacent cell; neither action can place a block inside the player.
- [ ] The hotbar exposes at least four block types, supports number-key selection, and renders an
      unmistakable selected state with recognizable block identity.
- [ ] The camera follows the player and remains clamped inside the world bounds.
- [ ] World edits, seed, player state and selected slot round-trip through `localStorage`, and a
      reopen restores them; invalid saved data falls back safely.
- [ ] The controls note and README accurately describe the delivered game.
- [ ] Existing tests still pass, new focused tests cover the added behavior, and
      `python tools/page_check.py` passes.
- [ ] A rendered screenshot has been captured under `tmp/`, visually inspected, compared with the
      strong one-shot quality bar, and the page iterated where the comparison exposed a gap.
- [ ] An independent visual review of the final page records no unresolved required findings; fixes
      are re-rendered and re-checked.
- [ ] No project Git commit is created, no managed feature is created, and the work-order result
      records evidence and residual risks.
