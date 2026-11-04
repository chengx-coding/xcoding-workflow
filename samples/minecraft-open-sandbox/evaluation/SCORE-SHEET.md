# Score sheet 鈥?open sandbox sample

Standard: **M2D-SES-OSS v1.2**. Blind evaluator; identity revealed after scoring:
**A = one-shot (MOSSWILD), B = XC 0.4.4 (Cubewood)**.

## Current Docker-verified artifact 鈥?0.4.16 Blockfall

Standard: **M2D-SES-OSS v1.3**. One controlled Docker run each; X = XC, Y = one-shot, revealed after
scoring. Same prompt/model/provider/budget, separate containers.

| Field | One-shot A | XC 0.4.16 B |
| --- | ---: | ---: |
| PES | **85.2** | 74.2 |
| ECS | 46.2 | **87.9** |
| Composite | 75.4 | **77.6** |
| Experience tier | **polished** | solid |
| Art D5 | **86** | 69 |
| Tests | 0/1 (stale test fails) | **58/58** |
| page_check | fail | **pass** |
| High / medium / low | 0 / 0 / 3 | 0 / 2 / 2 |

XC wins composite by 2.2 but loses PES by 11.0 and art by 17; not a significant experience win.
XC's D4 is capped by first-run discoverability; its mediums are 800x600 minimap clipping and vague
insufficient-craft feedback. The one-shot's seed tests/page check fail.

## Historical best 鈥?0.4.7 Emberdeep


Standard: **M2D-SES-OSS v1.3** (real-pointer interaction truth, blind pairwise art). Blind:
**A = one-shot MOSSWILD; B = XC 0.4.7 Emberdeep.**

| Field | One-shot A | XC 0.4.7 B |
| --- | ---: | ---: |
| PES | 82.4 | 78.8 |
| ECS | 82.2 | **88.2** |
| Composite | **82.4** | **81.1** |
| Experience tier | polished | prototype (D5 <55) |
| Art D5 | **89 polished** | **51 prototype** |
| High / medium / low | 0 / 1 / 1 | 0 / 1 / 2 |

A wins by 1.3. The only decisive gap is D5 art (89 vs 51); B has real interaction
truth, craft, map, 8-stage progression, save/reload, and no high defect. B is not a valid stop under
the "highest overall and no aspect worse" rule.

### 0.4.9 cap

The 0.4.9 final sample was **A 81.8 / B 79.2** (PES 77.6, ECS 84.1; D5 62, two medium defects). It is
lower than 0.4.7, so the 0.4.9 cap stops as **not-best**, not as a pass. The 0.4.8 visual-direction
attempt was rolled back because it dropped crafting/survival/progression (35 tests, no station chain).

## Evidence

- 0.4.7 blind report: [`blind-evaluation-0.4.7.md`](blind-evaluation-0.4.7.md)
- Emberdeep: 80/80 tests; real-pointer 10/10; screenshots
  [`../media/xc-emberdeep-day.png`](../media/xc-emberdeep-day.png),
  [`../media/xc-emberdeep-restored.png`](../media/xc-emberdeep-restored.png)
- 0.4.9 report: `.coding` work order `20261102-open-sandbox-eval-049` (private context)
- One-shot: 29/29 tests; [`../media/one-shot-mosswild.png`](../media/one-shot-mosswild.png)
## Evidence

- Blind report: [`blind-evaluation-0.4.4.md`](blind-evaluation-0.4.4.md)
- Cubewood: 79/79 tests, 21/21 browser steps; screenshots
  [`../media/xc-cubewood-day.png`](../media/xc-cubewood-day.png),
  [`../media/xc-cubewood-backdrop.png`](../media/xc-cubewood-backdrop.png)
- One-shot: 29/29 tests, browser/quest checks; [`../media/one-shot-mosswild.png`](../media/one-shot-mosswild.png)

