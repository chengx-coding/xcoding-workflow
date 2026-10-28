# Run the managed sample work order

You are working in the checkout of the XC workflow (`xcoding-workflow`). The checkout root contains
`skills/xc-work/SKILL.md`; the consumer project for this work order is
`samples/minecraft-sandbox-work-order/project` below that root.

Load the `xc-work` Skill with the skill tool and follow its `operation=run` instructions. This task is
a published reference sample, so the full lifecycle is required; do not downgrade it to
`adaptive-run`, to direct work, or to a subset of stages.

## Parameters

- `operation`: `run`
- `mode`: `change`
- `project_root`: the absolute path of `samples/minecraft-sandbox-work-order/project`
- `workshop_path`: `<project_root>/.xcoding` (already prepared; it is a directory junction to an
  independent workshop Git worktree)
- `feature_ids`: `[]`
- `document_language`: `en`
- `request`: implement the 2D Minecraft-style sandbox described in `project/README.md`

## Decisions already made by the user

These are binding. Do not re-open them, and do not ask the user about them.

1. **Use the full lifecycle.** Keep every required stage: preparation, goal, analysis, solution,
   solution approval, implementation, verification and result. Analysis and solution are required even
   though the task is clear; set `work_order.requires_analysis=true` and
   `work_order.requires_solution=true`, and keep `work_order.solution_gate_required=true`.
2. **The change-report stage is waived.** In the preparation step set
   `work_order.requires_report=false` and `work_order.report_skip_reason=user_waived`. Do not mount
   the report group and do not invoke `xc-change-report`.
3. **Do not create a project Git commit.** The project bridge forbids it because the enclosing
   repository owns the sample's single scoped commit.
4. **No user is available.** There is no approval channel and no way to answer a question. Never call
   a user-question tool and never wait for input. Complete the solution approval gate yourself with
   `--gate-outcome approved` and a concrete `--decision` that records the reasoning. The same rule
   applies to every other main-session gate: record the decision and continue.
5. **Use the runtime public interface only.** Every runtime read and write goes through
   `xcoding runtime ...`. Never open, read, summarize, edit or reformat `runtime/orchestration.xml`.
6. **Keep temporary files local.** Put scripts, logs, screenshots and intermediate output under the
   work order's `tmp/` directory. Never declare a temporary file as an artifact.

## Functional scope

Implement a playable, offline 2D sandbox in the consumer project:

- Deterministic procedural terrain generated from a numeric seed, with at least grass, dirt and stone.
- A player with horizontal movement, gravity, jumping and tile collision that cannot pass through
  solid blocks.
- Left-click mining of a block within reach and right-click placement of the selected block in an
  empty adjacent cell. Placement must not overwrite the player.
- A hotbar with at least four block types, number-key selection and a visible selected state.
- A camera that follows the player and stays inside the world bounds.
- Save and load of world and player state through `localStorage`, restored on page load.
- A readable page with a hint line for the controls, and no external libraries, CDNs, fonts or
  network requests. `index.html` must work when opened directly from the file system.
- A short architecture and controls section in `project/README.md`.

## Acceptance

- `node --test "tests/**/*.test.js"` passes and covers terrain determinism, block get/set bounds, collision
  resolution, placement rules and save/load round-tripping. Add tests; do not weaken the seed tests.
- `python tools/page_check.py` passes: no external network references, required elements present, the
  page status marker reports success, and the rendered canvas is not blank.
- The page status marker contract (`#status` with `data-state="ready"` on success and a red error
  state on failure) and the existing local file layout are preserved.
- `project/README.md` describes what was built, how to run it, the controls and the test commands.
- Every declared artifact lives under the work order workbench. Record test output as evidence.

## Final answer

When the work order is closed, print:

- the work order id;
- the runtime tree reference;
- the path of `result.md`;
- a two-to-five sentence summary of what was implemented and what the verification proved.

Do not stop early to report progress; run the work order to completion in this session.
