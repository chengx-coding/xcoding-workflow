# Docker blind evaluation — 0.4.16

First controlled Docker A/B run for the open sandbox sample. A = one-shot, B = XC 0.4.16;
same product prompt, model/provider (`deepseek-flash`), token budget, CPU/RAM, seed and timeout.
The evaluator saw anonymized X/Y candidates; the mapping was revealed after scoring.

| | XC (X) | One-shot (Y) |
| --- | ---: | ---: |
| PES | 74.2 | **85.2** |
| ECS | **87.9** | 46.2 |
| Composite | **77.6** | 75.4 |
| Experience | solid | **polished** |
| Art D5 | 69 | **86** |
| Tests | **58/58** | 0/1 (stale seed test fails) |
| page_check | **pass** | fail (missing seed IDs) |
| High / medium | 0 / 2 | 0 / 0 |

XC wins composite by 2.2, but loses PES by 11.0 and art by 17; this is not a significant experience
win. XC's D4 is capped by first-run discoverability (no visible help/craft entry); its mediums are
800×600 minimap clipping and vague insufficient-craft feedback. The one-shot has the stronger
experience/art but stale/broken seed tests and page check.

This run replaces the project in this sample with the Docker-verified XC artifact. It is **not** the
historical best XC score: 0.4.7 Emberdeep remains the score best at 81.1 vs one-shot 82.4.

## Evidence

- XC: 58/58 node tests; page_check ok; 16-state trusted-input play check; no high defects.
- One-shot: full survival sandbox; test file fails at `js/world.js` (`window is not defined`);
  page_check fails missing `status/hud/hotbar`.
- Visual: independent blind critic scored XC 77 / one-shot 86; both accepted, no high/medium.
- Artifacts are archived privately; the public project is the player-facing XC artifact only.
