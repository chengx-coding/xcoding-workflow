---
schema_version: 1
document_kind: work-order-goal
content_language: en
work_order_id: "20261030-1819-mc-2d-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Goal: a polished, playable offline 2D sandbox

## Requested outcome

The user asked for a managed `create` work order that implements the 2D Minecraft-style sandbox
described in `project/README.md` at the stated quality bar, run through the standard create lifecycle
on the 0.3.8 workflow, in an isolated workspace seeded only from the sample seed. The request is
preserved verbatim below; nothing in it is narrowed by this goal.

> Implement a playable, offline 2D sandbox in the consumer project:
>
> - Deterministic procedural terrain generated from a numeric seed, with at least grass, dirt and stone.
> - A player with horizontal movement, gravity, jumping and tile collision that cannot pass through
>   solid blocks.
> - Left-click mining of a block within reach and right-click placement of the selected block in an
>   empty adjacent cell. Placement must not overwrite the player and must explain a rejected placement.
> - A hotbar with at least four block types, number-key selection and a visible selected state.
> - A camera that follows the player and stays inside the world bounds.
> - Save and load of world and player state through `localStorage`, restored on page load.
> - A readable page with a hint line for the controls, and no external libraries, CDNs, fonts or
>   network requests. `index.html` must work when opened directly from the file system.
> - A short architecture and controls section in `project/README.md`.
>
> #### Acceptance
>
> - `node --test "tests/**/*.test.js"` passes and covers terrain determinism, block get/set bounds,
>   collision resolution, placement rules and save/load round-tripping. Add tests; do not weaken the
>   seed tests.
> - `python tools/page_check.py` passes: no external network references, required elements present, the
>   page status marker reports success, and the rendered canvas is not blank.
> - A 960x600 screenshot is captured under the work order `tmp/`, inspected, and compared with the
>   one-shot baseline after the run; the final page is at least as good on the quality bar.
> - The independent visual review is recorded and every required finding is fixed.
> - The page status marker contract (`#status` with `data-state="ready"` on success and a red error
>   state on failure) and the existing local file layout are preserved.
> - `project/README.md` describes what was built, how to run it, the controls and the test commands.
> - The work order records the standard lifecycle stages: goal, analysis, solution, approval,
>   implementation, verification and result.
>
> The result will be compared side-by-side with a strong one-shot attempt. It must be at least as
> visually polished and feature-rich as that bar: a distinctive interface with a clear visual
> hierarchy, satisfying interaction feedback, and world/feature variety.

The user also made binding decisions: keep analysis, solution and the solution gate; carry this quality
contract in the acceptance conditions; preserve the verbatim request without adding material
exclusions; add an independent visual review before the result; waive the change report; create no
project Git commit; ask no questions and self-complete every gate with recorded reasoning; use only the
runtime public interface; keep temporary files under the work workbench `tmp/`; and keep the run
isolated from the public sample, the one-shot baseline, prior sample results and any existing
implementation.

## Scope and constraints

### Intended capability scope

A visitor opens `index.html` directly from the file system and can, offline and without any external
resource:

- see a deterministic, seed-generated world with recognizable terrain layers, surface variety
  (hills, trees, sand, caves or comparable variety), a day/night sky and a visible camera view;
- move a player left and right, jump, fall under gravity, and be stopped by solid blocks instead of
  passing through them;
- mine a block within reach with the left mouse button and see the world change where it was;
- place the selected block with the right mouse button in an empty adjacent cell, without overwriting
  the player, and receive a clear explanation when a placement is refused;
- choose among at least four block types with number keys, a mouse wheel and a visible selected slot;
- see a camera that follows the player and never shows space outside the world bounds;
- see live coordinates, the current block palette, collected-block counts and the controls hint;
- pause the simulation, mute or unmute sound, and enter a numeric seed to generate another world;
- reload the page and find the world, player and collected counts restored from `localStorage`, with a
  visible recovery path when a saved payload is unreadable.

These are the user-observable capabilities the request names plus the continuity capabilities the
project has already accepted. The detailed capability map, the stateful journeys and integrity
invariants, and the signature-experience decisions are owned by `analysis.md`; this goal fixes the
required outcome, not an implementation.

### Quality contract

- The result is compared side-by-side with a strong one-shot attempt and must be at least as visually
  polished and feature-rich: a distinctive interface with a clear visual hierarchy, satisfying
  interaction feedback and world/feature variety.
- "At least as good" is a floor, not a ceiling, and it is not a permission to drop a requested
  capability.
- The page must be rendered, screenshotted at 960x600, inspected, compared against that bar and
  iterated before verification is considered done.
- A credible domain reference (the Minecraft family of block sandboxes, plus browser-native 2D
  sandbox exemplars) is used to challenge ambition: the result must be recognizably a complete
  experience of the requested kind, not merely a literal checklist of the prompt. The reference is a
  legibility argument, not a feature-count target.

### Exclusions and added constraints (with provenance)

| Item | Source | Note |
| --- | --- | --- |
| No third-party libraries, CDN assets, external fonts or runtime network requests | user, project | Requested constraint and bridge rule |
| `index.html` must run from `file://` with no build step or server | user, project | Requested constraint and bridge rule |
| Keep the `#status` marker contract and the existing local file layout | user, project | Requested constraint and bridge rule |
| Keep browser modules loadable in Node; do not weaken the seed tests | user, project | Requested constraint and bridge rule |
| No project Git commit from this work order | user, project | Explicit user decision; the enclosing repository owns the sample commit |
| The change-report stage is waived (`requires_report=false`, `report_skip_reason=user_waived`) | user | Explicit user decision |
| No user questions; main-session gates self-approve with recorded reasoning | user | No user is available |
| Do not consult the public sample, baseline, prior results or any existing implementation | user | Regression isolation for the published sample |

No material exclusion is `goal-authored`. There is no minimality presumption for this create task: the
goal keeps the requested scope and lets analysis/solution prioritize must and should work. Where a
capability is ambiguous and no user is available (for example how collected blocks interact with
placement), the ambiguity is carried as an open decision into analysis and resolved there by recorded
reasoning; it is not converted into a silent exclusion.

### Prior accepted capability inventory

Source and version: the initiating user instruction for this run ("Prior accepted capability
inventory", cumulative across prior standard versions). No version tag is given; the inventory is
treated as the accepted capability set of the product line, and that uncertainty is recorded rather
than inferred.

Every item below must receive a `preserve` / `improve` / `replace` / `retire` / `defer` disposition in
`analysis.md`, and the solution must account for every disposition. No item may be silently dropped.

1. per-block inventory counts
2. 52 automated tests (including the seed tests)
3. reduced-motion support
4. wheel selection
5. 1280-wide scaling
6. audio/mute
7. numeric seed entry
8. pause
9. the eighth hotbar block
10. day/night
11. nine-slot hotbar
12. coordinates

### Signature-experience challenge

A credible reference exists: the block-sandbox genre as defined by Minecraft, with browser-native 2D
exemplars as supporting evidence. Analysis records a small decision-changing signature table
(reference, signature capability, evidence, current goal coverage, must/should/non-goal decision) and
the solution covers accepted signature must/should capabilities. The reference may raise ambition
(for example terrain legibility, mining feedback, palette identity); it may not remove a requested
capability and may not become a feature-count target.

### Open decisions carried into analysis

- Whether mining should accumulate inventory that placement consumes, and how a rejected placement is
  surfaced when the selected block is unavailable. The request requires explanation of rejected
  placements but does not fix the resource model.
- How much world/feature variety is proportionate to the quality bar without weakening the requested
  minimum (for example trees, sand, caves, day/night, sound).
- Which interaction feedback is required for the quality bar versus optional polish.

## Acceptance conditions

1. `node --test "tests/**/*.test.js"` passes from `project/`, with at least 52 tests including the six
   unchanged seed tests, and covers terrain determinism (same seed → same world), block get/set
   bounds, collision resolution (no passing through solids, landing, ceiling, walls), placement rules
   (empty cell only, never over the player, refusal reason) and save/load round-tripping.
2. `python tools/page_check.py` passes from `project/`: no external network references, required
   elements present, `#status` reports `data-state="ready"`, and the rendered canvas is not blank.
3. A 960x600 screenshot is captured under this work order's `tmp/`, inspected, and compared with the
   one-shot baseline after the run; the final page is at least as good on the quality bar.
4. An independent visual review is recorded through `xc-review`, every required finding is fixed and
   re-checked, and the review is scored against M2D-SES v1.1 as required by the round-specific
   instruction.
5. The `#status` marker contract (`booting` → `ready`, red error state on failure) and the existing
   local file layout are preserved; the page remains a static, offline, `file://`-runnable page.
6. `project/README.md` describes what was built, how to run it, the controls and the test commands.
7. The work order records the standard lifecycle stages: goal, analysis, solution, approval,
   implementation, verification and result, with a self-approved solution gate that records its
   reasoning because no user is available.
8. The create-scope obligations are met: a capability map with source/priority/user value/acceptance/
   verification, stateful journeys and integrity invariants including visible before/after state at
   two materially different visual states, executed journey evidence, a credible signature-experience
   table with decisions, and a complete prior-capability disposition table; the solution records the
   accepted capability matrix and maps every must capability to implementation and verification.
9. The result stays offline: no external libraries, fonts, CDNs or network requests at runtime, and
   the logic modules remain require-able from Node.
10. No project Git commit is created; the enclosing repository owns the sample commit, and the result
    records that decision.
