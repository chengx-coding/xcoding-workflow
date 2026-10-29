# Run the standard-lifecycle sample work order

You are working in the checkout of the XC workflow (`xcoding-workflow`). The checkout root contains
`skills/xc-work/SKILL.md`; the consumer project for this work order is
`samples/minecraft-sandbox-work-order/project` below that root.

Load the `xc-work` Skill with the skill tool and follow its `operation=run` instructions. This task is
a published reference sample for the **standard create lifecycle**: keep goal, analysis, solution,
solution approval, implementation, verification and result. Do not skip stages, and do not add
one-off tuning merely to beat a comparison target.

## Parameters

- `operation`: `run`
- `mode`: `create`
- `project_root`: the absolute path of `samples/minecraft-sandbox-work-order/project`
- `workshop_path`: `<project_root>/.xcoding` (already prepared; it is a directory junction to an
  independent workshop Git worktree)
- `feature_ids`: `[]`
- `document_language`: `en`
- `request`: implement the 2D Minecraft-style sandbox described in `project/README.md`, at the quality
  bar below

## Decisions already made by the user

These are binding. Do not re-open them, and do not ask the user about them.

1. **Use the standard create lifecycle.** Keep `work_order.requires_analysis=true`,
   `work_order.requires_solution=true` and `work_order.solution_gate_required=true`; do not treat
   analysis or solution as optional. The goal must carry the quality contract below in its acceptance
   conditions; create has no minimality presumption. The goal must also preserve the verbatim
   request: do not add material exclusions or constraints the request does not contain. If a
   capability is ambiguous and no user is available, carry it as an open decision, not a silent
   exclusion. Analysis must produce a capability map (must/should/non-goal with source, user value,
   acceptance and verification); the solution must record the accepted capability matrix; the map is
   a fidelity instrument, not a breadth target. Analysis must also record a small
   signature-experience table from a credible domain reference (reference, signature capabilities,
   evidence, decision); the solution must cover accepted signature must/should capabilities. A
   reference is not a checklist or a feature-count target; a small task with a credible reference
   uses a reduced decision-changing set with a recorded reason, and if none is credible, record that.
2. **Prior accepted capability inventory.** Treat the following cumulative inventory from prior
   standard versions as accepted capabilities: per-block inventory counts; 52 automated tests
   including the seed tests; reduced-motion support; wheel selection; 1280-wide scaling; audio/mute;
   numeric seed entry; pause; the eighth hotbar block; day/night; nine-slot hotbar; coordinates.
   Disposition every item as preserve/improve/replace/retire; replace/retire requires reason, impact
   and source, and no item may be silently dropped.
3. **Add an independent visual review.** Before the result, render the page, inspect a 960x600
   screenshot, and run an independent visual review (for example through `xc-review`). Fix every
   required finding and re-check.
4. **The change-report stage is waived.** Set `work_order.requires_report=false` and
   `work_order.report_skip_reason=user_waived`; do not mount the report group.
5. **Do not create a project Git commit.** The project bridge forbids it because the enclosing
   repository owns the sample's single scoped commit.
6. **No user is available.** Never ask a question; complete any main-session gate yourself with a
   concrete decision that records the reasoning.
7. **Use only the runtime public interface.** Every runtime read and write goes through
   `xcoding runtime ...`; never open or edit `runtime/orchestration.xml`.
8. **Keep temporary files local.** Put scripts, logs, screenshots and intermediate output under the
   work order's `tmp/` directory; never declare a temporary file as an artifact.
9. **Regression isolation is binding.** Run from a clean seed in an isolated workspace that contains
   no public sample, baseline, prior sample result, or any existing implementation. Do not read,
   search for, or consult those paths. The baseline and historical results are used only for
   evaluation after the run, never as implementation input.

## Quality contract

This result will be compared side-by-side with a strong one-shot attempt. It must be at least as
visually polished and feature-rich as that bar: a distinctive interface with a clear visual
hierarchy, satisfying interaction feedback, and world/feature variety. Before finishing, render the
page, inspect a screenshot, compare it against that bar, and iterate.

## Functional scope

Implement a playable, offline 2D sandbox in the consumer project:

- Deterministic procedural terrain generated from a numeric seed, with at least grass, dirt and stone.
- A player with horizontal movement, gravity, jumping and tile collision that cannot pass through
  solid blocks.
- Left-click mining of a block within reach and right-click placement of the selected block in an
  empty adjacent cell. Placement must not overwrite the player and must explain a rejected placement.
- A hotbar with at least four block types, number-key selection and a visible selected state.
- A camera that follows the player and stays inside the world bounds.
- Save and load of world and player state through `localStorage`, restored on page load.
- A readable page with a hint line for the controls, and no external libraries, CDNs, fonts or
  network requests. `index.html` must work when opened directly from the file system.
- A short architecture and controls section in `project/README.md`.

## Acceptance

- `node --test "tests/**/*.test.js"` passes and covers terrain determinism, block get/set bounds,
  collision resolution, placement rules and save/load round-tripping. Add tests; do not weaken the
  seed tests.
- `python tools/page_check.py` passes: no external network references, required elements present, the
  page status marker reports success, and the rendered canvas is not blank.
- A 960x600 screenshot is captured under the work order `tmp/`, inspected, and compared with the
  one-shot baseline after the run; the final page is at least as good on the quality bar.
- The independent visual review is recorded and every required finding is fixed.
- The page status marker contract (`#status` with `data-state="ready"` on success and a red error
  state on failure) and the existing local file layout are preserved.
- `project/README.md` describes what was built, how to run it, the controls and the test commands.
- The work order records the standard lifecycle stages: goal, analysis, solution, approval,
  implementation, verification and result.

## Final answer

When the work order is closed, print:

- the work order id;
- the runtime tree reference;
- the path of `result.md`;
- a two-to-five sentence summary of what was implemented, what the visual review found, and what the
  verification proved.

Do not stop early to report progress; run the work order to completion in this session.
