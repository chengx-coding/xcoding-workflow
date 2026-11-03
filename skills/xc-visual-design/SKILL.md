---
name: "xc-visual-design"
description: "Guides visual design and independent visual critique when visual quality is part of a rendered deliverable's acceptance. Invoke when the user explicitly asks for visual quality, polish, identity, or a specific look, or when the project bridge declares a visual target; do not invoke for CLI, library, data-only, or source-only documentation tasks."
---

# XC Visual Design

This Skill owns the **process** for visual quality, not a style, palette, genre or universal score.
The project bridge or the request supplies the visual target; the evaluation standard supplies any
score. The process is: record the target, produce rendered states, get independent visual critique,
fix, and prove prior functionality still works.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Workbench that owns the visual brief, screenshots and review record.
- `brief_path` - `path`; required
  - Scope: Visual brief artifact. Create it before rendering code.
- `review_path` - `path`; required
  - Scope: Visual review record: target, critic identity, cycles, findings, fixes, functional gate.
- `screenshots` - `path[]`; required
  - Scope: Matched rendered states supplied to the independent critic.
- `functional_evidence` - `path[]`; optional
  - Scope: Existing verification evidence for the prior accepted capability inventory. Required when
    the visual work changes an interactive/stateful product.

## Operation

1. **Select conditionally.** Apply when visual quality is part of acceptance: an explicit visual
   request or a project bridge visual target. Do not apply to a pure CLI, library, data pipeline,
   source-only docs or a surface whose acceptance does not include visual quality. Record the
   selection or a not-applicable reason.
2. **Record the visual target.** Use `references/visual-brief.md`. Capture the target and constraints
   from the request/bridge, the states and viewports to compare, and the visual direction the author
   intends. Do not import a fixed list of visual dimensions or a preferred style.
3. **Make the system reusable only where the project already uses one.** If the project uses tokens or
   a design system, express colors/spacing/type/UI through it. Do not require a token system, a
   palette size, a font choice or a specific composition.
4. **Render matched states.** Capture the states/viewports named in the brief. A single default
   screenshot, code reading or narrative is not visual evidence.
5. **Run an independent critic loop.** Spawn a visually independent reviewer (a separate agent or
   VLM) with `references/critic-loop.md` and only the screenshots and the brief. It must not read the
   implementation or a prior self-review. Require severity-ranked findings and at least two
   critique/fix cycles. Record the critic identity and inputs in `review_path`.
6. **Preserve function.** Before and after the visual work, execute the prior accepted capability
   inventory's existing verification, including real-pointer interaction evidence where the product
   has interactive capabilities. The functional preservation gate is owned by `xc-verification`; this Skill
   requires its evidence and does not restate a capability list. A high interaction defect rejects the
   visual work. If the product has no interactive capability, record `not applicable`.
7. **Close only on both gates.** Accept only when the critic has no unresolved high finding and the
   functional evidence passes. Name any residual low/medium findings; only the **user or the project
   risk gate** may accept them. The implementer or a generic "caller" cannot self-accept. If either
   gate fails, record the failed gate and do not claim visual completion.

## Boundaries

- Do not prescribe a specific style, palette, font, genre, composition or score rubric. That is project-specific.
- Do not hardcode functional capabilities; use the prior accepted inventory's own verification.
- Do not add features, assets, libraries or network access that the request/bridge does not allow.
- Do not replace interaction truth, persistence, accessibility or tests with a visual critic.
- Do not introduce a new runtime mechanism or read another Skill's private references. Communicate
  through Skill names and documented artifacts.
- A plain result may be correct when the target says so; a generic/under-composed result cannot pass
  merely because it is functional.

## References

- `references/visual-brief.md` - target, direction, states and evidence planning.
- `references/critic-loop.md` - independent critic method, severity and acceptance.
- `references/review-record.md` - review artifact schema and dual-gate closure.
