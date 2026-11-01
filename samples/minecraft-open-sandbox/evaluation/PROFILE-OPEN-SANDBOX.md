# Open 2D sandbox profile

**Prompt:** the exact `prompt.md`; no feature list and no non-goal list. The agent decides which
Minecraft systems belong in a small sandbox and records the reasoning.

## What is scored

- Core sandbox verbs and controls (D1).
- World generation/exploration (D2).
- Action feedback (D3).
- Inventory + **gather→craft→build progression** (D4, signature).
- Presentation/audio/atmosphere (D5), orientation (D6), replay (D7), accessibility/responsive (D8),
  first-run/docs (D9).
- Engineering (E1–E5).

## Signature coverage

| Signature | Present? | Depth | Evidence |
| --- | --- | --- | --- |
| Seeded world with more than a flat strip | | | |
| Mine/place with readable feedback | | | |
| Inventory/hotbar with counts or clear palette | | | |
| Crafting/progression loop | | | recipe/station/inputs/outputs/progression |
| Save/restore | | | |
| Day/night or atmosphere | | | |
| Orientation/minimap | | | |
| Objectives/exploration loop | | | |

Crafting/progression may be a recipe list, a 2×2/3×3 grid, a station, or a small progression chain.
It must consume inputs and produce outputs; a decorative menu is not a loop. If absent, D4 is capped
at 50 and the report records the absence; it is **not** a high integrity defect.

## No pre-exclusions

Do not say "the compact prompt does not require X" and stop. This profile has no compact-scope
escape. If a reference signature is absent, record it as a domain gap and score it; if the agent
chose a smaller scope, record the reason and the lost experience value.

## Integrity

High defects: unsealed floor, underground sky, collision/placement corruption, save/boot failure,
unplayable controls. A polished but hollow sandbox cannot erase a broken world.

## Comparison

Both conditions use this profile and the same prompt. A/B is anonymized; do not infer XC from file
layout or documentation style before scoring. Report dimension scores, caps, defects and signature
coverage.
