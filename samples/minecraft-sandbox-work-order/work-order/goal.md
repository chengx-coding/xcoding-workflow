---
schema_version: 1
document_kind: work-order-goal
content_language: en
work_order_id: "20261030-0000-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Goal — 2D Minecraft-style sandbox

## Requested outcome

The user asked for a playable, offline 2D sandbox game inspired by Minecraft. The whole game is
delivered as `index.html` plus its local sibling assets, opened by double-clicking the file from the
file system: no build step, no package manager, no network access, no external libraries, CDNs or web
fonts. The finished page must be a game a player can actually sit down and play — generate a world,
move and jump through it, mine and place blocks, and come back later to the same world — rather than a
technical demo of those mechanics.

## Intended capability scope

The player must be able to do and observe the following in the delivered page:

- **Seed-driven world.** A numeric seed produces a deterministic world with grass, dirt and stone,
  plus further materials, surface variety and vegetation. The same seed always rebuilds the same
  world; a different seed builds a visibly different one.
- **Physical player.** Gravity, left/right movement, jumping, and solid collision on every side: the
  player stands on terrain, cannot walk or jump through solid blocks, and cannot fall out of the world.
- **Mining and building.** Left-click mines a block within reach; right-click places the selected
  block into an empty adjacent cell; a block can never be placed inside the player. Every block read
  and write is bounded by the world.
- **Block palette.** A hotbar with at least four usable block types, number-key selection, and a
  clearly visible selected state; the palette is large enough to be expressive while the scene stays
  readable.
- **Camera.** Follows the player with smooth motion and stays clamped inside the world bounds.
- **Persistence.** World edits and player state survive closing the page: reopening restores the same
  world and where the player left off.
- **Comprehensible delivery.** Clean, readable code and a short note describing the controls.

The intended capability scope also carries the product's cumulative accepted capabilities from prior
standard versions, which this goal must not silently lose: per-block inventory counts in the hotbar,
the full automated test suite (52+ tests including the seed tests), reduced-motion support, wheel
selection, 1280-wide page scaling, procedural audio with mute, numeric seed entry, pause, the eighth
hotbar block, day/night, the nine-slot hotbar, and the coordinate readout. `analysis.md` holds the
canonical disposition table for these items; the goal requires that every item be dispositioned
`preserve`, `improve`, `replace`, `retire`, or `defer` with a recorded source, and that no item be
dropped silently. A `replace` or `retire` needs a reason, impact, and a source independent of the
solution approval itself, and a wholly undispositioned item blocks solution approval.

## Quality contract

**Comparison target.** The result will be compared side-by-side against a strong one-shot attempt at
the same brief. The delivered page must be at least as visually polished and feature-rich as that
bar: a distinctive interface with an obvious visual hierarchy, satisfying interaction feedback
(hover, selection, mining, placing, toasts, sound), and genuine world and feature variety. Matching
the literal requirement list is the floor, not the bar.

**Reference-informed signature challenge.** The request names Minecraft, and the 2D sandbox genre has
credible references (Minecraft Java Edition; Terraria as the 2D exemplar). `analysis.md` records the
small signature-experience table for these references. The delivered experience must be recognisably
a *complete* experience of the requested kind — the signature must/should capabilities accepted in
the solution must be present, not merely the literal checklist — while not importing unrelated
reference features.

**Visual and interaction proof.** Before the result is written, the page must be rendered in headless
Chrome, its screenshots inspected at the default viewport, at 1280-wide scaling and with
reduced-motion forced, compared against the bar above, and iterated. An independent visual review of
the final page is required, and every required finding it raises must be fixed and re-verified before
the work order closes.

## Scope boundaries and provenance

No material exclusions. Nothing requested is dropped, and no capability is silently narrowed. The
following constraints are recorded with their sources:

| Constraint | Source |
| --- | --- |
| The game is delivered as `index.html` with local sibling CSS and JavaScript files rather than one literal file. | `user` — the request explicitly allows "local files next to it". This is a resolution of the delivery form, not an exclusion. |
| No third-party libraries, CDN assets, external fonts or network requests at runtime; the page works from `file://` with no build step. | `user` — request constraints; also `project` — the bridge repeats them. |
| Browser modules must stay loadable in Node so logic tests can require them without a DOM. | `project` — `.xcoding/WORKFLOW.md`. |
| The `#status` marker contract is kept: `booting` before boot, `ready` after a successful first frame, red error state on failure. | `project` — `.xcoding/WORKFLOW.md`. |
| Verification uses `node --test "tests/**/*.test.js"` and `python tools/page_check.py`. | `project` — `.xcoding/WORKFLOW.md`; no formatter or linter is configured. |
| Code, comments, README and work-order documents are English; two-space JavaScript indentation and the existing UMD-style module pattern are kept. | `project` — `.xcoding/WORKFLOW.md`. |
| No project Git commit is created from this work order. | `user` — run prompt; `project` — `.xcoding/WORKFLOW.md`. |
| The six seed tests are never deleted or weakened; coverage is added instead. | `project` — `.xcoding/WORKFLOW.md`. |

No capability is ambiguous enough to need a user decision in this work order. Where the request
leaves a detail open (for example the exact block palette, world size or visual style), the
implementation chooses the option that best serves the requested experience, and `analysis.md`
records that choice as a recorded open decision rather than as an exclusion.

## Acceptance conditions

1. A numeric seed deterministically generates terrain containing grass, dirt and stone, with surface
   variety and vegetation; entering a different seed rebuilds a visibly different world.
2. The player obeys gravity, moves left and right, jumps only from the ground, and collides with
   solid blocks on the ground and on both sides without passing through or leaving the world.
3. Left-click mines a reachable block; right-click places the selected block in an empty adjacent
   cell; placement inside the player, outside reach, or into an occupied cell is refused.
4. The nine-slot hotbar has at least four usable block types, number-key and wheel selection, a
   clearly visible selected state, and visible per-block counts that change with mining and placing.
5. The camera follows the player and remains inside the world bounds.
6. World edits, player position, hotbar state, selected slot, time of day and settings survive a page
   reload through `localStorage`, and a corrupt payload is ignored safely.
7. The page opens from `file://`, makes no network request, boots to `data-state="ready"`, and
   `python tools/page_check.py` passes with a non-blank canvas and the ready status pixel.
8. `node --test "tests/**/*.test.js"` passes with at least 52 automated tests, including the six
   browser-free seed tests, and the suite covers generation, physics, interaction, persistence,
   rendering helpers, UI state, day/night and setting persistence.
9. Prior accepted capabilities are all delivered or explicitly dispositioned: per-block counts,
   52+ tests, reduced motion, wheel selection, 1280-wide scaling, audio/mute, numeric seed entry,
   pause, the eighth hotbar block, day/night, nine-slot hotbar, and coordinates each have
   implementation and verification evidence.
10. The quality contract is met: rendered screenshots are inspected and compared against the strong
    one-shot bar, day/night and world variety are visible, interaction feedback is present, and the
    1280-wide and reduced-motion renders are checked.
11. `README.md` accurately documents what the page is, how to open it, the controls, how to run the
    checks, and a brief architecture overview.
12. An independent visual review of the final page is recorded, and every required finding is fixed
    and re-verified before the result is written.

## Verbatim request

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
