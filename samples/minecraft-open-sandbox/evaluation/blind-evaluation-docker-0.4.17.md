# Docker blind evaluation — 0.4.17

Controlled Docker A/B for the open sandbox sample. A = one-shot, B = XC 0.4.17; same product
prompt, model/provider (`deepseek-flash`), budget, seed and container limits. Candidates were
anonymized X/Y; the mapping was revealed after scoring.

| | XC (X) | One-shot (Y) |
| --- | ---: | ---: |
| PES | 83.7 | **88.3** |
| ECS | **91.5** | 50.8 |
| Composite | **85.7** | 78.9 |
| Experience | **polished** | **polished** |
| Art D5 | 81 | **89** |
| D4 / D6 / D7 | 85 / 90 / 78 | 90 / 90 / 88 |
| Tests | **25/25** | 0/1 (stale seed test fails) |
| page_check | **pass** | fail (missing seed IDs) |
| High / medium | 0 / 0 | 0 / 0 |

XC wins composite by **6.8** and ECS by **40.7**; one-shot leads PES by **4.6** and art by **8**.
Both are polished; no high/medium defects. This is the first significant composite/engineering win
for XC, not an all-aspect win.

XC's 0.4.17 Docker artifact adds a visible first-run help/controls entry, actionable insufficient
crafting feedback, and a responsive HUD, removing the 0.4.16 D4 cap. The one-shot still has the
stronger experience/art but its seed tests and page check fail.

## Evidence

- XC: 25/25 Node tests; page_check pass; 34/34 trusted-input play probe; independent 24/24 probe.
- One-shot: full survival sandbox; test import fails (`window is not defined`); page_check fails
  missing `status/hud/hotbar`.
- Visual: independent blind critic X 75 / Y 86; both accepted, no high/medium.
- Historical: 0.4.16 Blockfall 77.6 vs 75.4; 0.4.7 Emberdeep 81.1 vs 82.4.
