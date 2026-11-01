# Visual surface profile

**Scope:** task-class. **Owner:** `xc-work/references/profiles/visual.md`. **Promotion status:**
`validated-in-class` (Wildgrove visual sample). **Evidence surface:** rendered UI/page/canvas.
**Generality evidence:** 0.3.8 Wildgrove; not a universal rule. **Force:** convention-only.

**Applies when** the requested acceptance depends on a rendered/visual output
surface (UI, page, canvas, visual document). **Does not apply when** the artifact has no visual output
(for example a pure library, CLI-only tool, or source-only document pipeline).

Use this profile in addition to the universal observable-state integrity rule, not instead of it.

## Required evidence

- Visible before/after for journeys that remove, clear, hide, cover or change content; change
  mode/theme/time or viewport; or reach a boundary/terminal state.
- At least two materially different visual states when the experience has them (for example light/dark,
  theme, viewport, error/empty). A single default screenshot is not enough.
- Spatial/layer consistency where a global or screen-space default could misrepresent the state; for
  example, a removed-content background must be anchored to the state it belongs to.
- Responsive evidence at the project's required widths, and accessibility/reduced-motion evidence
  where the project requires it.
- An executed assertion or manual scenario with before/post observables. A static image, code reading,
  narrative claim, or single default frame is not enough.
- A `must` visual gap fails/blocks verification until executed or accepted as a recorded risk; a
  `should` gap may remain recorded.

This profile must not be applied to a non-visual task. A non-visual task records the visual surface as
not applicable and uses the CLI/API/file/docs profile instead.
