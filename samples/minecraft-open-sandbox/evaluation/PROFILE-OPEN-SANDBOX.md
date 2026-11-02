# Open 2D sandbox profile — v1.3

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
It must consume inputs and produce outputs and be **discoverable from the first-run UI or help**; a
decorative menu is not a loop. If absent, D4 caps at 40. If crafting exists only behind a passive HUD key hint and no visible
button/tutorial/quest entry, D4 caps at 55 and D9 at 70; a real user failing to find it is decisive
evidence. It is **not** a high integrity defect, but it prevents a `polished` tier.

A real map/minimap is required for D6 >60. Coordinates/field notes alone are not a map. Visual
composition, character readability and tool animation are primary D5 evidence; a plain prototype
cannot score above 60. Water/sand physics, smelting/ingots and combat are coverage/depth items under
D2/D4/D1, not high defects.

## No pre-exclusions

Do not say "the compact prompt does not require X" and stop. This profile has no compact-scope
escape. If a reference signature is absent, record it as a domain gap and score it; if the agent
chose a smaller scope, record the reason and the lost experience value.

## Interaction truth

Exercise every visible primary control with a real pointer at its rendered position. A control that
looks enabled but silently does nothing is a defect; it must be visibly disabled with a reason or
execute with feedback. Crafting must be tested with insufficient materials (clear missing list) and
with sufficient materials (output + count update). Code/README presence is not interaction evidence.

## Art quality

D5 is a blind pairwise visual score at matched states: composition 5, character readability/animation
5, asset detail 3, UI/typography coherence 3, atmosphere/lighting 2. Record an art tier
(`rough`/`prototype`/`coherent`/`polished`). If one artifact is clearly more polished, D5 differs by
at least 15 and the weaker is not `polished`. A functional but plain UI is `prototype`/`coherent`, not
a polished art result.

## Integrity

High defects: unsealed floor, underground sky, collision/placement corruption, save/boot failure,
unplayable controls. One high defect caps PES/composite at 55; two at 45. A high-defect result is
`prototype` even with strong ECS; a polished but hollow sandbox cannot erase a broken world.

## Comparison

Both conditions use this profile and the same prompt. A/B is anonymized; do not infer XC from file
layout or documentation style before scoring. Report dimension scores, caps, defects and signature
coverage.
