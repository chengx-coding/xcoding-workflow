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

The two runs are complete and blind-scored. Identity reveal: **A = one-shot (MOSSWILD)**, **B = XC
(Blockhaven)**.

| | One-shot A | XC B |
| --- | ---: | ---: |
| PES | **89.4** | **60.0** (raw 76.8) |
| ECS | **87.0** | **88.3** |
| Composite | **88.8** | **65.0** (raw 79.7) |
| High / medium / low | 0 / 0 / 3 | **1 / 1 / 3** |
| Higher | **A** | — |

The XC result has the higher engineering score and a real crafting loop, but one high defect:
underground air is transparent to the sky/sun/clouds layer. That caps PES at 60 and composite at 65.
See [`evaluation/SCORE-SHEET.md`](evaluation/SCORE-SHEET.md) and the blind report
[`evaluation/blind-evaluation.md`](evaluation/blind-evaluation.md).

![One-shot MOSSWILD](media/one-shot-mosswild.png)

![XC Blockhaven](media/xc-blockhaven.png)

## Status

The runs and scores are recorded after both outputs exist. Do not compare this sample's score with the
compact `minecraft-sandbox-work-order` score; the prompts and profiles differ.

