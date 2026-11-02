# Minecraft open 2D sandbox sample

This sample tests **one simple product prompt** under two conditions:

- **one-shot**: a single agent gets the prompt and the shared starter seed;
- **XC**: an agent gets the same product prompt and the starter seed, with the XC managed workflow
  available as process tooling.

The product prompt is identical: [`prompt.md`](prompt.md) and
[`baseline-prompt.md`](baseline-prompt.md). The XC runner has process instructions only
([`xc-runner.md`](xc-runner.md)); it must not add product requirements.

## Why this sample exists

The earlier compact sample explicitly made crafting/survival/mobs/redstone optional. That was useful
for a controlled regression, but it could not test whether an agent would discover Minecraft's
gather→craft→build loop. This sample does not pre-declare those systems as non-goals. The open prompt
and the new standard score what the agent actually chooses.

## Fairness rules

- Both runs start from the same `seed/` and the same product prompt.
- The one-shot run has no XC skills, workshop or process instructions.
- The XC run may use the workflow, but not extra product requirements or the old sample's profile.
- The evaluator sees anonymized A/B artifacts and does not know which is one-shot or XC.
- The new standard/profile is fixed before the runs; do not tune it to either result.

## Directory

| Path | Meaning |
| --- | --- |
| `prompt.md` | Product prompt used by both runs |
| `baseline-prompt.md` | The same prompt, for the one-shot condition |
| `xc-runner.md` | Process-only instructions for the XC condition |
| `seed/` | Shared starter project |
| `baseline/` | One-shot result (populated after the run) |
| `project/` | XC result (populated after the run) |
| `evaluation/` | New open-sandbox standard, profile, score sheet and blind review |
| `media/` | Screenshots |

## Result

Best XC artifact: **Emberdeep (0.4.7)**. One-shot **MOSSWILD** compared blind under **v1.3**.

| | One-shot A | XC 0.4.7 B |
| --- | ---: | ---: |
| PES | **82.4** | 78.8 |
| ECS | 82.2 | **88.2** |
| Composite | **82.4** | **81.1** |
| Experience tier | polished | prototype (D5 <55) |
| Art D5 | **89 polished** | **51 prototype** |
| High / medium / low | 0 / 1 / 1 | 0 / 1 / 2 |
| Higher | **A** | — |

A wins by 1.3; the only decisive gap is art. Emberdeep has real-pointer interaction truth, crafting,
map, 8-stage progression and save/reload, but its D5 is below 55, so it is not a stop.

The 0.4.9 cap sample scored **A 81.8 / B 79.2**, lower than 0.4.7; it stops at the cap as **not-best**.
The 0.4.8 visual-direction attempt was rolled back after dropping crafting/survival/progression.

![Emberdeep](media/xc-emberdeep-day.png)

![One-shot MOSSWILD](media/one-shot-mosswild.png)

## Status

The runs and scores are recorded after both outputs exist. Do not compare this sample's score with the
compact `minecraft-sandbox-work-order` score; the prompts and profiles differ.


