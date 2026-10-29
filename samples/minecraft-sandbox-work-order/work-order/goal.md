---
schema_version: 1
document_kind: work-order-goal
content_language: "en"
work_order_id: "20261029-1459-2d-sandbox-game"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Goal — a playable, offline 2D Minecraft-style sandbox

## Requested outcome

Turn the static seed shell in `project/` into a complete, playable 2D sandbox game inspired by
Minecraft. The whole game must run from `index.html`, opened by double-clicking the file, with no
build step and no network access.

The finished page must:

- Generate terrain procedurally from a numeric seed, with at least grass, dirt and stone blocks and
  visually distinct additional blocks for world variety.
- Simulate a player with gravity, left/right movement and jumping, colliding with solid blocks so the
  player cannot pass through terrain.
- Let the player left-click to mine a block within reach and right-click to place the selected block
  into an empty adjacent cell, refusing placement inside the player.
- Show a hotbar with at least four block types, number-key selection, mouse-wheel selection, and a
  clearly visible selected state.
- Follow the player with a camera that stays inside the world bounds.
- Save world and player state to `localStorage` and restore it when the page is reopened.
- Keep clean, readable, modular code and document the controls in `README.md` and in the page itself.
- Preserve the existing verification contract: the `#status` marker, Node-loadable modules, the seed
  logic tests, and the two project check commands.

## Scope and constraints

In scope:

- `project/index.html`, `project/css/style.css`, `project/js/*.js`, `project/tests/*.js`,
  `project/README.md`, and only if a real need appears, `project/tools/page_check.py`.
- A distinctive, polished presentation: a layered sky and parallax, textured blocks, a character with
  animation, a day-lit palette, an in-page control legend, a seed panel, and a pause/save overlay.
- A richer but still focused feature set: seeded world generation, mining/placing with reach rules,
  block drops/particles, a small inventory count or creative palette, pause/resume, world reset with a
  new seed, save/restore, and a minimap-free but readable HUD.

Out of scope:

- External libraries, CDNs, web fonts, network requests, build tooling, or a server.
- Multiplayer, combat, mobs, crafting trees, or any scope that would weaken the core loop.
- Creating a managed feature baseline, or a project Git commit (the enclosing repository owns the
  sample commit).

Hard constraints from the project bridge:

- Offline and `file://`-runnable; no external references of any kind.
- `project/.xcoding/WORKFLOW.md` conventions apply, including UTF-8 with LF line endings, English
  prose, two-space JavaScript indentation, and the existing module style.
- Do not weaken or delete the seed tests; add coverage.
- Do not open or edit the runtime XML; use only the public `xcoding runtime` interface.
- Keep temporary and process files under this work order's `tmp/` directory.

## Acceptance conditions

The work order is accepted only when every condition below holds.

### Functional acceptance

1. Terrain is generated from a numeric seed and contains grass, dirt, stone, wood and leaves; distinct
   seeds produce different surface profiles, and the same seed reproduces the same world.
2. The player falls under gravity, walks left and right, jumps only from a supported state, and cannot
   pass through any solid block on any axis.
3. Left-click mines a solid block within reach and shows visible feedback; right-click places the
   selected hotbar block into an empty cell adjacent to an existing solid block, and never inside the
   player or outside the world.
4. The hotbar has at least four block types with number-key and mouse-wheel selection and an
   unmistakable selected state, including a visible block swatch and name.
5. The camera follows the player smoothly and clamps to the world bounds on both axes.
6. World edits and player position are persisted to `localStorage` and restored after reopening the
   page, with a visible save indicator.
7. Controls are documented in the page (a legend or overlay) and in `README.md`.

### Quality contract (side-by-side bar)

8. The result will be compared side-by-side with a strong one-shot attempt. It must be at least as
   visually polished and feature-rich as that bar: a distinctive interface with a clear visual
   hierarchy, satisfying interaction feedback, and world/feature variety.
9. Before finishing, the page must be rendered in headless Chrome, a screenshot inspected, compared
   against that bar, and iterated until the visual result is convincing.
10. An independent visual review of the final page must be recorded before the result document; every
    finding the reviewer marks required must be fixed and re-checked.

### Engineering acceptance

11. `node --test "tests/**/*.test.js"` passes, including the unchanged seed tests plus new coverage for
    generation, collision, reach/placement rules, and persistence serialization.
12. `python tools/page_check.py` passes: static offline checks, `#status` marker pixel ready, and a
    non-blank canvas.
13. No external network reference exists in any page-served file; all assets are inline or local.
14. The work order records its verification evidence, its independent visual review, its residual
    risks, and the no-commit decision in the final result document.
