# Output-surface evidence contract

**Scope:** task-class. This is the single detail contract for the output surfaces; `experience` is a proposed task-class overlay, not a fifth surface. The public table in
`xc-work/SKILL.md` is the index and applicability contract; this file is the evidence detail. It is
private to `xc-work`; analysis and verification use the public table and their own concise rules.

Every surface is additional to the universal observable-state rule; never replace the before/action/
after assertion with a surface-specific screenshot or a state label.

## universal (baseline, not selectable)

- Before/action/after on the declared surface; executed probe, not inspection.
- Unrun probe is a gap; a `must` gap fails/blocks unless a recorded user-accepted risk.
- A state-label-only row or a test that never enters the state is not evidence.

## visual

**Applies when** acceptance depends on a rendered/visual surface (UI/page/canvas/visual document).
**Does not apply** to a pure library/CLI/source-only docs task.

**First-run affordance (2D sandbox visual products, validated-in-class).** A 2D sandbox visual
product must expose its primary systems from the first-run UI: a visible button/tutorial/task/menu
entry. A passive key hint, in-game help, or README alone is insufficient. Verify from a fresh state
that a new user can find the primary system without prior knowledge; record the visible entry point.
This is a must for the 2D sandbox subclass, not for all visual products; other visual subclasses use
the proposed experience lens.

- Visible before/after when content is removed/cleared/hidden/covered/changed, mode/theme/time or
  viewport changes, or a boundary/terminal state is reached.
- At least two materially different visual states when present (theme, viewport, error/empty).
- Background/occlusion/layer/spatial anchor when a global or screen-space default could misrepresent
  the state.
- Responsive evidence at required widths; accessibility/reduced-motion where required.
- Executed assertion or manual scenario; a single default screenshot, code reading, or narrative is
  not evidence.

## cli-library-api

**Applies when** the user/operator observes commands, exit codes, stdout/stderr, API status/body,
files, side effects or persisted state. **Does not apply** to a pure rendered-visual task.

- Exact command/call and observable before/after: exit, stdout/stderr, status/body, file/diff, state.
- Success/error/empty/limit/recovery where behavior depends on them.
- Side effects/idempotence/cleanup where external state changes.
- No screenshot as substitute; executed command/API probe, not inspection.

## docs

**Applies when** the reader observes source text or a rendered documentation page. **Does not apply**
to a game/UI or CLI-only artifact with no documentation surface.

- Affected source/rendered page and reader-observable before/after: content, table/list, navigation,
  link/anchor, search, cross-reference.
- Execute the render/link/anchor/navigation check or a recorded manual reading; a source diff alone
  does not prove a rendered claim.
- Visual profile only if the docs task explicitly includes a rendered visual design surface.
- No gameplay/CLI-only checks.

## Status

The **2D sandbox visual-state backdrop** and **first-run affordance** are `validated-in-class` by two
independent instances: the compact 0.3.6 Wildgrove run (only footer key hints for the primary loop)
and the open 0.4.3 Blockhaven run (passive hint, hidden crafting, D9 62 capped). The general visual
profile, CLI, docs and the experience lens remain `proposed`; universal promotion requires a
different-class probe and a negative probe.

**Force:** convention-only; no runtime check proves a profile is universal.

## Visual-state backdrop

For a 2D sandbox visual product where content can be removed, cleared, hidden or covered, or a
mode/theme/time/viewport changes, the state must show a coherent backdrop/empty/fallback and be
verified before/after. This is a task-class must; it does not apply to static docs/CLIs/data
dashboards.
