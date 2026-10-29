# Work-order sample: a 2D sandbox built through XC

**Language:** **English** | [简体中文](README.zh-CN.md)

This sample is a real, complete XC **standard create-mode** work order. It is not a screenshot tour: a
seeded consumer project was driven through the normal managed lifecycle by the DeepSeek Harness
command line, the resulting work order was archived here, and the orchestration tree was rendered
from the runtime. A direct run of the same task without XC is included so the two results can be
compared.

The run uses `xc-work` with `mode=create`, a user-facing quality contract, and the normal complete
lifecycle: goal, analysis, solution, solution approval, implementation, verification and result. The
change report is deliberately waived. The run was isolated from the one-shot baseline and from every
previous sample implementation: its workspace contained only the workflow Skills, the seed project and
the bridge, and the prompt forbade consulting the baseline or a prior implementation.

## Quick facts

| Item | Value |
| --- | --- |
| Task | Build a playable, offline 2D Minecraft-style sandbox from scratch |
| Why this task | A common "model capability" prompt with a visual, inspectable result and real design decisions |
| Consumer project | [`project/`](project/README.md), the finished static page built from the seed in [`seed/`](seed/) |
| Host | DeepSeek Harness CLI, `dsh headless` |
| Model | `deepseek-flash` |
| Entry point | `xc-work` with `operation=run`, `mode=create` |
| Scope policy | create: no minimality presumption; a user-facing quality contract |
| Lifecycle shown | Goal, analysis, solution, approval, implementation, verification, result |
| Deliberately absent | Change report (explicit user waiver) |
| Quality bar | At least as visually polished and feature-rich as a strong one-shot attempt |
| Isolation | Run workspace had no sample, baseline, prior result or existing implementation |
| Work order | `20261029-1459-2d-sandbox-game` |
| Baseline | One direct run of the raw prompt with no workflow, archived in [`baseline/`](baseline/) |

## What is in this directory

```text
prompt.md                 the standard create-mode prompt sent to DeepSeek Harness
baseline-prompt.md        the raw task prompt used for the direct baseline
setup/WORKFLOW.md         the project bridge template for the consumer project
setup/xc-orchestration-runtime.json  runtime configuration for the sample workshop
seed/                     the starting snapshot the work order began from
project/                  the finished consumer project: the delivered game
baseline/                 the direct baseline: index.html, run record and final answer
work-order/               the archived standard work order: goal, analysis, solution, result,
                          review/verification artifacts, runtime and tmp evidence; no report
tree/                     the final orchestration tree as SVG (zoomable) and PNG (README image)
media/                    matched 960x600 screenshots of the managed and baseline pages
```

The live work order ran in an independent workshop Git repository outside this repository, and
`project/.xcoding` was a directory junction to it. The archived copy in `work-order/` is a copy of
that work order directory, including its `tmp/` scratch, plus the run's final answer in
`work-order/dsh-run.txt`. The live workshop is not part of this repository.

## Why this task

The task is deliberately of the kind people use to probe a new model: "build a game from scratch". It
has a visual result, it forces real decisions (terrain generation, collision, interaction rules,
camera, persistence), and it is small enough to finish in one work order. The raw prompt is in
[`baseline-prompt.md`](baseline-prompt.md); the managed prompt adds the workflow instructions, the
quality contract and the verification requirements while keeping the same functional scope.

## How the work order ran

1. The consumer project was seeded with a page shell, a small module skeleton, a Node test runner and
   a Python page check; the seed is archived in [`seed/`](seed/). The sandbox features were not
   implemented.
2. An isolated run workspace was created outside the checkout. It contained only the workflow Skills,
   the `.agents` skill mirror, the seed project and the project bridge. It did not contain the public
   sample, the baseline, a previous project or any other implementation.
3. The run was launched from that isolated workspace:

   ```powershell
   $env:DEEPSEEK_API_KEY = "<the key from the harness credential store>"
   $env:DSH_PERMISSION_MODE = "danger-full-access"
   dsh headless - < prompt.md
   ```

   The API key is required by the headless profile. The permission mode is required on this host
   because the default `workspace-write` sandbox fails to provision its Windows ACL and every shell
   call is rejected before it starts.
4. The work order ran the normal create lifecycle: goal with the quality contract, analysis, solution,
   solution approval, implementation, verification, an independent visual review and result. The
   change report was waived; the consumer project created no commit.
5. The prompt is written for a headless session: it forbids user questions, requires the main session
   to record its own decisions, and keeps all runtime access on the public `xcoding runtime` interface.

## Reading the orchestration tree

![The completed standard create-mode sample orchestration tree](tree/orchestration-tree.png)

The PNG is the full tree rendered from the Viewer's SVG export. The standalone
[`tree/orchestration-tree.svg`](tree/orchestration-tree.svg) is the zoomable version. The tree shows
the standard lifecycle: preparation, goal, analysis, solution and its approval gate, implementation,
verification with an independent visual review and recheck, result and finalizer. The change-report
group and the conditional review/recovery branches are skipped. The tree is sealed with 34 succeeded
nodes, 16 skipped nodes and 8 pending nodes; the pending nodes are the children of skipped conditional
branches and were never scheduled.

The archived runtime tree reports `status=complete` with valid SHA-256 integrity. The work order
documents are in [`work-order/`](work-order/): [`goal.md`](work-order/goal.md),
[`analysis.md`](work-order/analysis.md), [`solution.md`](work-order/solution.md) and
[`result.md`](work-order/result.md). The independent visual review is in
[`work-order/artifacts/verification/independent-visual-review.md`](work-order/artifacts/verification/independent-visual-review.md); the
verification evidence is under [`work-order/artifacts/verification/`](work-order/artifacts/verification/).

## What the work order produced

The delivered page is [`project/index.html`](project/index.html), supported by local CSS, six
JavaScript modules and five test files. It delivers:

- seeded terrain with grass, dirt, stone, trees, leaves, sandy clearings, caves and ore speckles;
- a player with gravity, acceleration, AABB collision, coyote-time jump, jump buffer, variable jump,
  landing events, facing and animation state;
- reach-limited left-click mining with particles/sound and right-click placement with reach,
  adjacency and player-body rules, including clear rejection feedback;
- an eight-block hotbar with number keys, mouse-wheel cycling, a raised selected slot, swatch, name and
  inventory count;
- a smooth world-clamped camera; a full-window DPR-aware canvas; layered sky, sun, clouds, birds,
  parallax ridges, haze, procedural tile textures, cave background, cliff walls, ambient occlusion,
  flowers, a character with helmet/scarf/backpack/lantern, and a vignette;
- a brand, seed chip, live save chip, sound/help buttons, hint bar, toasts and a field guide with
  controls, materials, field notes, seed generation, randomiser and a two-step reset;
- versioned `localStorage` persistence of seed, blocks, player, hotbar and inventory, with guarded
  access and an in-memory fallback.

Verification, reproduced from `project/`:

```text
node --test "tests/**/*.test.js"   33 tests, 33 pass
python tools/page_check.py --window 960x600
                                   static/network checks pass; status marker green;
                                   292 colour buckets in the rendered canvas
```

The screenshot used below is [`media/xc-sandbox.png`](media/xc-sandbox.png).

## The direct baseline, the current result and the regression history

The launching session used the same model (`deepseek-flash`), the same machine and the raw task prompt
for one direct run with the workflow disabled. The baseline ran outside the XC checkout, so the
checkout's `xc-*` Skills were not in the working directory. The launch configuration and final answer
are recorded in [`baseline/run.md`](baseline/run.md) and [`baseline/dsh-run.txt`](baseline/dsh-run.txt);
the internal transcript is not archived.

| Direct baseline | XC standard create-mode work order |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="Direct baseline sandbox screenshot" width="440"> | <img src="media/xc-sandbox.png" alt="XC standard create-mode sandbox screenshot" width="440"> |

| Fact | Direct baseline | XC standard create-mode work order |
| --- | --- | --- |
| Deliverable layout | 1 file | 15 files (page, CSS, 6 modules, 5 tests, tool, README) |
| Served page bytes | 98,883 | 111,090 |
| Total project bytes | 98,883 | 141,977 |
| Committed logic tests | 0 | 33, all passing |
| Automated page check | none provided | green status marker, 292 colour buckets |
| External references in served files | 0 | 0 |
| Screenshot colour buckets | 203 | 292 |
| Durable process record | none | full standard work order |
| Independent visual review | none | passed |

The standard result is at least equal to the one-shot baseline on the measured facts and the
screenshot comparison: it is a product with a stronger world presentation, an eight-slot inventory
hotbar with counts, a field guide, interaction feedback and a much larger test/verification record.
The baseline remains a clean single-file page with a compact HUD.

For regression context, the earlier results are retained in the project's history (the current
sample's own comparison table):

| Version / run | Run shape | Served bytes | Total bytes | Tests | Buckets | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 0.3.2 sample (C1) | full, no quality contract | 38.1 KB | 69,140 | 28 | 53 | historical; below baseline |
| 0.3.3 pre-correction | special create-minimal (stages skipped) | 132,680 | 168,758 | 34 | 285 | superseded; not a standard comparison |
| 0.3.3 standard | standard full lifecycle + quality contract | 111,090 | 141,977 | 33 | 292 | current; at least baseline |

A run-to-run difference from the superseded special result is expected: the special result skipped
analysis/solution, while the standard run keeps the normal lifecycle. The current result has fewer
files/bytes than that special result but more colour buckets and a complete standard process record;
the comparison is documented rather than treated as a regression. A significant or consecutive
decline would be investigated under the project's sample-regression rule.

Limits of this comparison: one run per side, the same launching configuration, different prompts (the
managed prompt also requires tests, documentation, verification, the quality contract and the
isolation rule), static screenshot comparison, and no human play session. It is an anecdote about what
happened here, not a controlled benchmark.

## Reproduce it

Prerequisites: Python 3.12, Node.js 24, Google Chrome, Git, and the `xcoding` package plus the XC
skills installed for your host. From the repository root:

```powershell
$Checkout = (Get-Location).Path
$Sample = Join-Path $Checkout "samples/minecraft-sandbox-work-order"
$Workshop = Join-Path (Split-Path $Checkout -Parent) "minecraft-sandbox-workshop"

# The committed project is the finished result; replace it with a clean copy of the seed.
if (Test-Path "$Sample/project/.xcoding") { [System.IO.Directory]::Delete("$Sample/project/.xcoding", $false) }
Remove-Item "$Sample/project" -Recurse -Force
New-Item -ItemType Directory -Force "$Sample/project" | Out-Null
Copy-Item "$Sample/seed/*" "$Sample/project/" -Recurse -Force

New-Item -ItemType Directory -Force (Join-Path $Workshop ".xcoding") | Out-Null
git -C $Workshop init
Copy-Item "$Sample/setup/WORKFLOW.md" (Join-Path $Workshop ".xcoding/WORKFLOW.md")
Copy-Item "$Sample/setup/xc-orchestration-runtime.json" (Join-Path $Workshop ".xcoding/xc-orchestration-runtime.json")
New-Item -ItemType Junction -Path (Join-Path $Sample "project/.xcoding") -Target (Join-Path $Workshop ".xcoding")

$env:DEEPSEEK_API_KEY = "<the key from the harness credential store>"
$env:DSH_PERMISSION_MODE = "danger-full-access"
Get-Content $Sample/prompt.md -Raw | dsh headless -
```

For a regression run, copy the seed, Skills and `.agents` mirror into a separate workspace that
contains no public sample, baseline or prior result, and run there. The prompt's isolation rule
forbids consulting those paths. The reset above removes the finished files and any stale `.xcoding`
junction; the workshop step creates a fresh junction.

When the run reports completion, the work order is
`$Workshop/.xcoding/work-orders/<work-order-id>/`. To render its tree:

```powershell
$Tree = "$Workshop/.xcoding/work-orders/<work-order-id>/runtime/orchestration.xml"
$viewer = xcoding viewer --tree $Tree --no-browser | ConvertFrom-Json
$svg = Invoke-WebRequest "$($viewer.url)api/trees/$($viewer.trees[0].tree_id)/svg"
[IO.File]::WriteAllBytes("orchestration-tree.svg", [Text.Encoding]::UTF8.GetBytes($svg.Content))
```

The archived `work-order/` directory is a copy of the original workshop directory plus the run's final
answer, normalized to LF; it therefore contains absolute paths from the original run.

## Evaluation standard

Every sample run is scored with the fixed [M2D-SES v1.0](evaluation/STANDARD.md): 12 domains, 86
criteria, T0-T3 tiers, weights, 0-5 anchors, and separate coverage/depth/extras reporting. The
reusable [score sheet](evaluation/SCORE-SHEET.md) records the domain scores and the base, core-demo
and coverage indices.

For the current 0.3.3 products, the base scores are **standard 55/100**, **pre-correction 60/100**
and **baseline 39/100**; core demo is 61/65/44 and coverage is 47/50/31 (standard/pre-correction/
baseline). The standard is cleaner, more responsive and more
robust; the pre-correction special is more Minecraft-complete and wins world/biomes, blocks/
interaction, day/night and the richer HUD. All three remain shallow relative to Minecraft: no
crafting, survival, mobs/combat, redstone, water/sand physics, weather or structures. See the
[score sheet](evaluation/SCORE-SHEET.md) for the domain table and the extras/controversy notes.

## Limitations

- This is a single sample run. It documents one execution, not a benchmark.
- `seed/` is a reconstruction of the starting snapshot, not a byte-for-byte recovery from the
  original run; the finished `project/` and the archived work order are the original artifacts.
- The baseline prompt and the managed prompt differ by design; the managed run also had to satisfy
  tests, documentation, verification, the quality contract and the isolation rule.
- No human play session was performed for either result; the checks are automated plus screenshot
  inspection. The independent visual review was static, not a live responsive or acoustic pass.
- The page-check tool is part of the sample's consumer project, not a generic XC capability.
- The workflow contracts live in [`docs/`](../../docs/index.md); this sample illustrates them and does
  not define or extend them.
