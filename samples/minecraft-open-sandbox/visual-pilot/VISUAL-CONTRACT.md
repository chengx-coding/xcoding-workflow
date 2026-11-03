# Visual quality contract — sample pilot (project-level, not portable)

This is a **quality method**, not an extra product feature. The product prompt and scope are
unchanged. It applies only to this sample run; it must not be copied into a generic Skill.

## 1. Visual brief before implementation

Write `.xcoding/visual-brief.md` before the first rendering implementation:

- audience and intended feeling (one sentence);
- 3 candidate visual directions in text, then one chosen direction;
- a one-sentence visual thesis;
- palette: 8–12 named tokens with hex values (sky, horizon/far, mid, near, surface, accent, UI bg,
  UI text, danger, light);
- type scale: 3–4 sizes and weights using local/system fonts;
- spacing scale: 4–6 steps;
- composition: focal point, horizon/layer structure, foreground/midground/background, negative space;
- character silhouette/readability rules (size, outline/contrast, animation states);
- lighting/atmosphere: day/night/underground behavior and contrast;
- UI hierarchy: HUD, panels, buttons, focus/disabled states;
- anti-slop list: what this product must not look like (generic template, random gradients,
  centered-card-only, default-font-only, flat single-band horizon).

## 2. Tokens in code

All colors, spacing, type sizes and UI surfaces use named tokens/constants. No ad-hoc hex values in
individual components unless the token is defined in the visual system.

## 3. Matched-state renders

Capture and review at least:

- title/first-run, day, night, underground/torch, inventory/crafting;
- 1280×800 and 800×600;
- one before/after state for a transition (overlay opens/closes, mode/time change).

## 4. Independent visual critic (mandatory)

Spawn a separate critic agent with `.xcoding/visual-critic.md` and the screenshots. Do **not**
self-review. The critic returns severity-ranked findings. Fix every high/medium finding and re-render;
run at least **two** critique/fix cycles. Record the critic outputs and fixes in
`.xcoding/visual-review.md`. A self-review cannot close this gate.

## 5. Preservation

A visual change must not remove or thin a prior accepted must capability. If a visual direction
conflicts with crafting/survival/progression/save/interaction truth, preserve the capability and
change the visual approach instead. Record the check.

## 6. Hard constraints unchanged

No external assets, libraries, CDNs, network or build step. All art remains local/procedural. The
product prompt remains exactly the same.
