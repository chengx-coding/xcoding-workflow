# M2D-SES v1.0 — sample score sheet

Use this sheet with [`STANDARD.md`](STANDARD.md). Score each domain 0-5 using the rubric's anchors,
record a separate T0/T1 core sub-score and a present/total criterion count per domain, then compute
the indices. Keep the completed sheet with the run's evaluation record; do not overwrite earlier
sheets.

## Formula

- **Base /100** = Σ(domain weight × domain score) / 100 × 20.
- **Core demo /100** = Σ(domain weight × T0/T1 sub-score) over domains that contain T0/T1 criteria,
  divided by the sum of those weights (86; D3 and D9 are excluded because they contain only T2/T3
  criteria), then ×20. The sub-scores are recorded per domain below.
- **Coverage** = Σ(present criteria across domains) / 86. A criterion is present only at score ≥2.
  This is an unweighted breadth count, not a domain-weighted average.
- **Depth** = average score of present criteria only (optional diagnostic).
- **Extras** = separate bonus/penalty score (−10 to +10); report it separately and as a sensitivity
  line `base + extras`.

## Current 0.3.3 scores (reference, not a template to overwrite)

### Domain scores (0-5)

| Domain | Weight | Baseline | Pre-correction (36d1315) | Standard |
| --- | ---: | ---: | ---: | ---: |
| D1 Core loop and controls | 10 | 4 | 5 | 5 |
| D2 World generation and biomes | 10 | 3 | 5 | 3 |
| D3 Terrain physics, fluids, weather | 8 | 1 | 1 | 1 |
| D4 Blocks, mining, building | 10 | 3 | 5 | 4 |
| D5 Inventory and items | 8 | 3 | 3 | 5 |
| D6 Crafting and progression | 8 | 0 | 0 | 0 |
| D7 Survival: health, hunger, death | 7 | 0 | 0 | 0 |
| D8 Mobs and combat | 7 | 0 | 1 | 1 |
| D9 Redstone and automation | 6 | 0 | 0 | 0 |
| D10 Day/night, weather, atmosphere | 6 | 2 | 5 | 2 |
| D11 UI/UX, audio, accessibility | 10 | 3 | 4 | 4 |
| D12 Persistence, engineering, tests | 10 | 2 | 4 | 5 |
| **Base /100** | **100** | **39** | **60** | **55** |

### Core sub-scores and coverage counts

| Domain | T0/T1 weight | Core B0 | Core P | Core S | Present/total B0 | Present/total P | Present/total S |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| D1 Core loop and controls | 10 | 4 | 5 | 5 | 8/8 | 8/8 | 8/8 |
| D2 World generation and biomes | 10 | 4 | 5 | 3 | 4/8 | 7/8 | 5/8 |
| D3 Terrain physics, fluids, weather | — | — | — | — | 0/6 | 0/6 | 0/6 |
| D4 Blocks, mining, building | 10 | 3 | 4 | 4 | 4/7 | 6/7 | 5/7 |
| D5 Inventory and items | 8 | 2 | 3 | 4 | 2/7 | 2/7 | 4/7 |
| D6 Crafting and progression | 8 | 0 | 0 | 0 | 0/7 | 0/7 | 0/7 |
| D7 Survival: health, hunger, death | 7 | 0 | 0 | 0 | 0/7 | 0/7 | 0/7 |
| D8 Mobs and combat | 7 | 0 | 1 | 1 | 0/7 | 1/7 | 1/7 |
| D9 Redstone and automation | — | — | — | — | 0/6 | 0/6 | 0/6 |
| D10 Day/night, weather, atmosphere | 6 | 2 | 5 | 2 | 1/6 | 5/6 | 2/6 |
| D11 UI/UX, audio, accessibility | 10 | 3 | 4 | 4 | 5/9 | 8/9 | 8/9 |
| D12 Persistence, engineering, tests | 10 | 2 | 4 | 5 | 3/8 | 6/8 | 7/8 |
| **Total / index** | **86** | **44/100** | **65/100** | **61/100** | **27/86 = 31%** | **43/86 = 50%** | **40/86 = 47%** |

The core index is computed from the T0/T1 sub-scores over the 86-weight subset:
`(Σ weight × sub-score) / 86 × 20`. Coverage is the unweighted present count / 86.

### Extras and sensitivity

| Artifact | Bonus | Penalty | Base + extras |
| --- | ---: | ---: | ---: |
| Baseline | +1 | −2 | 38 |
| Pre-correction | +3 | −2 | 61 |
| Standard | +4 | −1 | 58 |

Interpretation: the pre-correction special is the most Minecraft-complete; the standard is cleaner,
more responsive and more robust but loses world, blocks/interaction and day/night/HUD. All three
lack crafting, survival, mobs/combat, redstone, fluids/sand gravity, weather and structures.

## New run template

Run: ____________________  Version/commit: ____________________  Date: ____________

| Domain | Weight | Score 0-5 | Core T0/T1 0-5 | Present/total | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| D1 Core loop and controls | 10 | | | /8 | |
| D2 World generation and biomes | 10 | | | /8 | |
| D3 Terrain physics, fluids, weather | 8 | | — | /6 | |
| D4 Blocks, mining, building | 10 | | | /7 | |
| D5 Inventory and items | 8 | | | /7 | |
| D6 Crafting and progression | 8 | | | /7 | |
| D7 Survival: health, hunger, death | 7 | | | /7 | |
| D8 Mobs and combat | 7 | | | /7 | |
| D9 Redstone and automation | 6 | | — | /6 | |
| D10 Day/night, weather, atmosphere | 6 | | | /6 | |
| D11 UI/UX, audio, accessibility | 10 | | | /9 | |
| D12 Persistence, engineering, tests | 10 | | | /8 | |
| **Base /100** | **100** | | | | |

- Core demo /100 (T0/T1 weights 86):
- Coverage (present/86):
- Extras bonus/penalty:
- Base + extras:
- Comparison with baseline and previous standard run:
- Verdict (better / equal / regression signal / significant regression):
- Notes and controversies:

## Policy

- Compare with the one-shot baseline **and** the previous standard run, not only with the immediately
  previous special result.
- Small variation is acceptable; a whole-domain drop or consecutive declines trigger investigation.
- Extras are recorded separately and never excuse a missing T0/T1 criterion.
- A standard revision gets a new version number; prior sheets remain valid under their version.
