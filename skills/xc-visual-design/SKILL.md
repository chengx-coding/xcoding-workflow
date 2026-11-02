---
name: "xc-visual-design"
description: "Guides visual design, art direction, and independent visual critique for a task whose primary deliverable is a rendered visual surface and whose acceptance includes visual quality. Invoke when the user asks for visual polish, identity, or a specific look, or when the project bridge declares a visual quality contract; do not invoke for CLI/docs/data-only work."
---

# XC Visual Design

This Skill owns the **method** for visual quality. It does not own a style, palette, genre or a
universal beauty score. The project bridge supplies the visual target; the evaluation standard owns
scoring. The Skill turns "make it look good" into a brief, tokens, executed states, independent
critique and a functional preservation gate.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Workbench that owns the visual brief, screenshots and review artifacts.
- `brief_path` - `path`; required
  - Scope: Artifact for the visual brief. Create it before rendering code.
- `review_path` - `path`; required
  - Scope: Artifact for critic cycles, findings, fixes and the final gate.
- `screenshots` - `path[]`; required
  - Scope: Matched rendered states supplied to the independent critic.
- `functional_evidence` - `path[]`; optional
  - Scope: Real-pointer regression evidence for the prior must capabilities. Required when a visual
    pass changes a stateful/interactive product.

## Operation

1. **Select conditionally.** Apply only when visual quality is part of acceptance: the user asks for
   polish/identity/a look, or the project bridge declares a visual quality contract. Do not apply to a
   pure CLI, library, data pipeline, source-only docs or an informational dashboard with no rendered
   experiential surface. Record the selection or a not-applicable reason.
2. **Write the visual brief before rendering code.** Use `references/visual-brief.md`. Include the
   audience/feeling, 3 candidate directions and a chosen one, a one-sentence thesis, palette tokens,
   type and spacing scales, composition/depth, character readability, lighting and UI hierarchy. The
   project bridge supplies the concrete style and constraints; do not invent a universal style.
3. **Define tokens.** Use named tokens/constants for colors, spacing, type and UI surfaces. Every
   component consumes tokens; avoid ad-hoc values that bypass the visual system.
4. **Render matched states.** Capture the primary states and at least two viewports. The states and
   viewports come from the project bridge; a single default screenshot is not evidence.
5. **Run an independent critic loop.** Spawn a visually independent reviewer (a separate agent/VLM)
   with `references/critic-loop.md` and the screenshots only. It must not read implementation code or
   prior self-reviews. Require severity-ranked findings and at least two critique/fix cycles. Fix every
   high/medium finding or record an explicit accepted-with-residuals decision by the caller. Self-review
   cannot close this gate.
6. **Preserve function.** Before and after the visual pass, execute the prior must-capability
   interactions with a real pointer: placement, crafting/output, world bounds/containment, save/reload,
   first-run controls and the core loop. Module tests or screenshots do not prove these still work. A
   high interaction defect rejects the visual pass; a visual change may not thin or break a capability.
7. **Close only on both gates.** A visual pass is accepted only when the critic has no unresolved high
   finding (or the caller explicitly accepts named residuals) **and** functional preservation passes.
   Record the accepted states, findings, fixes, residual risks and evidence paths in `review_path`.

## Boundaries

- Do not prescribe a specific style, font, palette, genre or D5 rubric. That is project-specific and
  belongs in the bridge or evaluation standard.
- Do not add features or systems that the request does not support; visual work is presentation of
  the requested experience, not a scope expansion.
- Do not use external assets, libraries, CDNs or network when the project's constraints forbid them.
- Do not replace interaction truth, save/reload, accessibility or tests with a visual critic.
- Do not introduce a new runtime mechanism or read another Skill's private references. Communicate
  through Skill names and documented artifacts.
- The Skill is a method, not a guarantee of taste; a plain but coherent result may be accepted when
  the project's visual target says so.

## References

- `references/visual-brief.md` - brief and token template.
- `references/critic-loop.md` - independent critic instructions, severity and acceptance.
