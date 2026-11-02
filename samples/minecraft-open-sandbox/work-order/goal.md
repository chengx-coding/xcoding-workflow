---
schema_version: 1
document_kind: work-order-goal
content_language: "en"
work_order_id: "20261102-1550-open-sandbox-xc-047"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Work order goal — playable offline 2D Minecraft-inspired sandbox

## Requested outcome

Deliver, in this repository, a playable 2D sandbox game inspired by Minecraft that a person can
play by opening `index.html` directly from the file system. The game must run with no build step, no
package manager, no third-party libraries, no CDN, no external fonts and no network access. It must
feel like a small Minecraft, keep the player's progress between sessions, and document its controls.

The requested capability scope is exactly the product prompt: a small Minecraft-like 2D sandbox with
a playable core loop, progress saving and documented controls. This goal does not pre-declare which
Minecraft systems belong in that small sandbox; which systems are included is an analysis decision
recorded in `analysis.md` and accepted in `solution.md`.

## Scope and constraints (with provenance)

| Constraint | Provenance | Consequence |
| --- | --- | --- |
| Playable, offline, 2D sandbox inspired by Minecraft | user (product prompt) | The deliverable is a game, not a demo or an engine shell. |
| Runs by opening `index.html`, no build step | user (product prompt) + project bridge | Classic browser scripts only; no bundler, no ES module `import` from `file://`. |
| No external libraries, CDNs, network access, external fonts | user (product prompt) + project bridge | Everything, including art and audio, is generated locally from code and CSS. |
| Feel like a small Minecraft | user (product prompt) | The reference's defining loop and legible world must be present at small scale; the analysis records which reference capabilities are must, should or non-goal. |
| Save progress | user (product prompt) | Progress survives a page reload with a user-visible save/continue state. |
| Document the controls | user (product prompt) | Controls exist in the rendered game and in the repository README. |
| English code, comments, README and work-order documents; UTF-8/LF | project bridge | All authored files follow this. |
| Verification: `node --test "tests/**/*.test.js"` and `python tools/page_check.py`; do not weaken seed tests | project bridge | Both commands pass; the seed test file keeps its assertions; new tests are added for new behaviour. |
| No third-party runtime assets; `file://` operation | project bridge | Same as the prompt; enforced by the page check. |
| Change report waived | user instruction through the project bridge | `work_order.requires_report=false`; `work_order.report_skip_reason=user_waived`. |

No goal-authored exclusion is added. Nothing in the prompt is excluded, and no extra product
feature is declared as required by this goal.

## Acceptance conditions

1. **Runs offline from `file://`.** Opening `index.html` directly boots the game with no build step,
   no network request, no external library, font or asset, and no console error.
2. **Playable first contact.** A first-time player can start the game without prior knowledge: the
   first screen identifies the game, the primary start control is visible, and the controls needed
   for the first action are shown before or at the moment they are needed.
3. **Defining Minecraft-like loop and progression depth.** The game presents a real loop — gather
   material, refine it, build with it, and advance toward a world-scale goal — with enough depth that
   later progress depends on earlier progress. A gather-only or mine-only slice does not satisfy
   "feels like a small Minecraft". The analysis must name the loop and the reference capabilities
   that support it, and the solution must map each accepted capability to implementation and
   verification.
4. **Navigable, legible world.** The player can tell where they are and how to orient within a world
   larger than the screen, and the world contains places worth finding.
5. **Real interaction truth.** The primary world interaction works through genuine pointer input:
   pressing and holding the pointer on a world target for at least 90 ms changes that world target,
   repeatably across trials, and it is proven with browser-dispatched pointer input rather than a
   synthetic element activation.
6. **Visual and audio direction beyond functional UI.** The presentation establishes a coherent art
   direction (palette, tile treatment, depth, atmosphere) and a scene state that visibly responds to
   game state, so the result reads as a small game rather than a debug canvas.
7. **Progress is saved and shown consistently.** If the game claims saving, a saved session reloads
   with the same world, inventory and progression, and the interface reports the save state and saved
   summary truthfully.
8. **Controls are documented.** The README documents every control and the game itself exposes a
   controls reference.
9. **Quality bar.** `node --test "tests/**/*.test.js"` and `python tools/page_check.py` pass from the
   project root, the seed test assertions are unchanged, and additional automated tests cover the
   game logic and the browser interaction truth above.
10. **No scope narrowing.** Every material capability promised by the product prompt or accepted by
    the solution is implemented or its absence is recorded with provenance; the result document
    reports evidence per acceptance condition.

## Reference-informed signature challenge

The credible reference is Minecraft (Mojang, 2011) as a genre-defining sandbox, plus its 2D
side-scrolling descendants. The reference is used for domain legibility, not for copying content.
The signature elements that make a sandbox read as Minecraft-like, and that this goal expects the
analysis to disposition, are: a block-based editable world; mining and placing blocks; a crafting
step that converts raw material into better capability; a tool/material progression that gates
deeper parts of the world; survival pressure that gives preparing and building a purpose; and a
persistent world the player returns to. A small Minecraft may legitimately reduce or omit a
signature element, but the omission must be a recorded analysis decision with user value and
impact, and the accepted must/should elements must reach a depth where the loop sustains play rather
than stopping after the first resource.
