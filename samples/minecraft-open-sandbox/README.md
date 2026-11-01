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
| PES | **80.8** | **55.0** (raw 63.0; high cap 55) |
| ECS | **81.3** | **86.1** |
| Composite | **80.9** | **55.0** (raw 68.8; cap) |
| Experience tier | **polished** | **prototype** |
| High / medium / low | 0 / 1 / 1 | **1 / 2 / 2** |
| Higher | **A** | — |

The XC result has the higher engineering score and a real crafting loop, but it is visually and
experientially far behind, and it has one high defect: underground air is transparent to the
sky/hill layer. The v1.2 standard caps a high defect at 55 and treats a passive `E craft` hint as
insufficient discoverability; see [`evaluation/SCORE-SHEET.md`](evaluation/SCORE-SHEET.md), the v1.1
blind report [`evaluation/blind-evaluation-v1.1.md`](evaluation/blind-evaluation-v1.1.md), and the
v1.0 history [`evaluation/blind-evaluation.md`](evaluation/blind-evaluation.md).
v1.2 is a standards correction applied mechanically to the v1.1 blind dimension evidence, not a new
blind run.

The dimension-level gap is larger than the composite: D5 84 vs 58, D4 86 vs 55, D7 86 vs 50. The
composite is compressed by A's own gaps (no map, no biomes/water physics, no smelting) and B's
higher ECS; the **tier** label is the clearer product comparison.

![One-shot MOSSWILD](media/one-shot-mosswild.png)

![XC Blockhaven](media/xc-blockhaven.png)

## Status

The runs and scores are recorded after both outputs exist. Do not compare this sample's score with the
compact `minecraft-sandbox-work-order` score; the prompts and profiles differ.


