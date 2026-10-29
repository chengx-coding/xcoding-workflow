# Work-order sample: a 2D sandbox built through XC

**Language:** **English** | [简体中文](README.zh-CN.md)

This sample is a real, complete XC create-mode work order. It is not a screenshot tour: a seeded
consumer project was driven through the managed lifecycle by the DeepSeek Harness command line, the
resulting work order was archived here, and the orchestration tree was rendered from the runtime. A
second, direct run of the same task without XC is included so the two results can be compared.

This version of the sample uses the workflow's **dynamic scope policy**: the task is a from-zero
creation, so the run uses `xc-work` with `mode=create`, no minimality presumption, and an explicit
user-facing quality contract. Analysis, solution and the change report are deliberately absent; the
create lifecycle is goal, implementation, verification with an independent visual review, and result.

## Quick facts

| Item | Value |
| --- | --- |
| Task | Build a playable, offline 2D Minecraft-style sandbox from scratch |
| Why this task | A common "model capability" prompt with a visual, inspectable result and real design decisions |
| Consumer project | [`project/`](project/README.md), the finished static page built from the seed in [`seed/`](seed/) |
| Host | DeepSeek Harness CLI, `dsh headless` |
| Model | `deepseek-flash` |
| Entry point | `xc-work` with `operation=run`, `mode=create` |
| Scope policy | create: no minimality presumption; a user-facing quality contract in the goal |
| Lifecycle shown | Preparation, goal, implementation, verification, independent visual review, result |
| Deliberately absent | Analysis, solution, approval gate, change report |
| Quality bar | At least as visually polished and feature-rich as a strong one-shot attempt |
| Work order | `20261029-1219-2d-sandbox-game` |
| Baseline | One direct run of the raw prompt with no workflow, archived in [`baseline/`](baseline/) |

## What is in this directory

```text
prompt.md                 the managed create-mode prompt sent to DeepSeek Harness
baseline-prompt.md        the raw task prompt used for the direct baseline
setup/WORKFLOW.md         the project bridge template for the consumer project
setup/xc-orchestration-runtime.json  runtime configuration for the sample workshop
seed/                     the starting snapshot the work order began from
project/                  the finished consumer project: the delivered game
baseline/                 the direct baseline: index.html, run record and final answer
work-order/               the archived create work order: goal, review/verification artifacts,
                          result, runtime and tmp evidence (no analysis, solution or report)
tree/                     the final orchestration tree as SVG (zoomable) and PNG (README image)
media/                    matched 960x600 screenshots of the managed and baseline pages
```

The live work order ran in an independent workshop Git repository outside this repository, and
`project/.xcoding` was a directory junction to it. The archived copy in `work-order/` is a copy of
that work order directory, including its `tmp/` scratch, plus the run's final answer in
`work-order/dsh-run.txt`. The live workshop is not part of this repository.

## Why this task

The task is deliberately of the kind people use to probe a new model: "build a game from scratch".
It has a visual result, it forces real decisions (terrain generation, collision, interaction rules,
camera, persistence), and it is small enough to finish in one work order. The raw prompt is in
[`baseline-prompt.md`](baseline-prompt.md); the managed prompt adds the workflow instructions, the
quality contract and the verification requirements while keeping the same functional scope.

## How the work order ran

1. The consumer project was seeded with a page shell, a small module skeleton, a Node test runner and
   a Python page check; the seed is archived in [`seed/`](seed/). The sandbox features were not
   implemented.
2. An independent workshop Git repository was created outside the checkout, the bridge template and
   runtime configuration were copied into its `.xcoding`, and `project/.xcoding` was junctioned to it.
3. The run was launched from the XC checkout root:

   ```powershell
   $env:DEEPSEEK_API_KEY = "<the key from the harness credential store>"
   $env:DSH_PERMISSION_MODE = "danger-full-access"
   Get-Content samples/minecraft-sandbox-work-order/prompt.md -Raw | dsh headless -
   ```

   The API key is required by the headless profile. The permission mode is required on this host
   because the default `workspace-write` sandbox fails to provision its Windows ACL and every shell
   call is rejected before it starts.
4. The work order ran in create mode: preparation and goal (with the quality contract), one
   implementation subtree that built the page and its tests, verification, an independent visual
   review, a final recheck of the delivered files, and the result. It closed with the change report
   waived and no project Git commit; the enclosing repository owns the sample's commit.
5. The prompt is written for a headless session: it forbids user questions, requires the main session
   to record its own decisions, and keeps all runtime access on the public `xcoding runtime`
   interface.

## Reading the orchestration tree

![The completed create-mode sample orchestration tree](tree/orchestration-tree.png)

The PNG is the full tree rendered from the Viewer's SVG export. The standalone
[`tree/orchestration-tree.svg`](tree/orchestration-tree.svg) is the zoomable version. The tree shows
the create lifecycle: preparation, goal, implementation (build, verify, independent review and
recheck), result and finalizer. The analysis, feature-reconciliation, clarification, solution,
approval and solution-recovery branches are skipped, as is the change-report group. The tree is
sealed with 14 succeeded nodes and 7 skipped nodes, with no pending work.

The archived runtime tree reports `status=complete` with valid SHA-256 integrity. The work order
documents are in [`work-order/`](work-order/): [`goal.md`](work-order/goal.md) and
[`result.md`](work-order/result.md). The implementation evidence is in
[`work-order/artifacts/implementation/sandbox.md`](work-order/artifacts/implementation/sandbox.md),
the independent visual review in
[`work-order/artifacts/review/visual-review.md`](work-order/artifacts/review/visual-review.md), and the
verification in
[`work-order/artifacts/verification/acceptance.md`](work-order/artifacts/verification/acceptance.md)
and
[`work-order/artifacts/verification/final-recheck.md`](work-order/artifacts/verification/final-recheck.md).

## What the work order produced

The delivered page is [`project/index.html`](project/index.html), supported by local CSS, eight
JavaScript modules and five test files. The implementation includes:

- deterministic seeded terrain with meadow, woodland and dune biomes, layered grass, dirt, stone and
  bedrock, caves, coal, prism crystals, trees, a near-spawn grove, trail lanterns and a distant forest
  layer;
- a player with gravity, acceleration, sprinting, variable-height jumping, coyote time and
  axis-separated solid collision;
- reach-limited left-click mining and face-aware right-click placement, with target brackets, a block
  ghost, player-overlap rejection and clear blocked-action feedback;
- a nine-block hotbar with number-key and wheel selection, a raised/glowing selected state, block
  icons and names;
- a smoothly following, world-clamped camera; a stylized survey minimap with viewport framing; a
  day/night sky with stars, sun, moon, clouds, parallax ridges, birds and fireflies; cave mushrooms,
  lantern/crystal light, break/place particles, camera shake and generated Web Audio feedback;
- versioned `localStorage` persistence of the world, seed, player position, selected slot, time of day
  and progress, with safe fallback for missing, corrupt or stale saves;
- a field-notes checklist, seed/time/coordinate chips, save status, a full field manual, a seed-based
  New World dialog and a compact controls note.

Verification, reproduced from `project/`:

```text
node --test "tests/**/*.test.js"   34 tests, 34 pass
python tools/page_check.py --window 960x600
                                   static/network checks pass; status marker green;
                                   285 colour buckets in the rendered canvas
```

The screenshot used below is [`media/xc-sandbox.png`](media/xc-sandbox.png).

## The direct baseline and the comparison

The launching session used the same model (`deepseek-flash`), the same machine and the raw task prompt
for one direct run with the workflow disabled. The baseline ran outside the XC checkout, so the
checkout's `xc-*` Skills were not in the working directory. The launch configuration and final answer
are recorded in [`baseline/run.md`](baseline/run.md) and [`baseline/dsh-run.txt`](baseline/dsh-run.txt);
the internal transcript is not archived.

| Direct baseline | XC create-mode work order |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="Direct baseline sandbox screenshot" width="440"> | <img src="media/xc-sandbox.png" alt="XC create-mode sandbox screenshot" width="440"> |

Measured facts:

| Fact | Direct baseline | XC create-mode work order |
| --- | --- | --- |
| Deliverable layout | 1 file | 17 files (page, CSS, 8 modules, 5 tests, tool, README) |
| Served page bytes | 98,883 | 132,680 |
| Total project bytes | 98,883 | 168,758 |
| Committed logic tests | 0 | 34, all passing |
| Automated page check | none provided | green status marker, 285 colour buckets |
| External references in served files | 0 | 0 |
| Screenshot colour buckets | 203 | 285 |
| Durable process record | none | full create work order |
| Independent visual review | none | passed against strong one-shot references |

The managed result now has the stronger visual identity and the wider feature set. It fills the
window with a field-journal interface, a "Verdant Depths" wordmark, a survey minimap, a field-notes
checklist, a day/night sky, a nine-slot hotbar, cave/crystal lighting, particles and clear
place/reject feedback. The direct baseline still has a clean branded title bar and a compact HUD, but
it does not have the minimap, the field notes, the day/night cycle, the same block variety or the
interaction feedback. On the measured facts and the screenshots, the create-mode run is at least equal
to the baseline and is visibly richer.

This is the result of the **dynamic scope policy**: the earlier sample ran the creation task as a
`change` with a strong minimality rule, and its result was thin; this run uses `create`, a quality
contract and an independent visual review, and the product is no longer capped at the smallest
extension. The sample does not claim that XC improves model output in general; it documents what this
policy produced on one task.

Limits of this comparison: one run per side, the same launching configuration, different prompts (the
managed prompt also requires tests, documentation, verification and the quality bar), static
screenshot comparison, and no human play session. It is an anecdote about what happened here, not a
controlled benchmark.

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

The reset removes the finished files and any stale `.xcoding` junction, then copies the seed; the
workshop step creates a fresh junction. Without it, a rerun would start from the completed project
instead of the task's starting point.

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

## Limitations

- This is a single sample run. It documents one execution, not a benchmark.
- `seed/` is a reconstruction of the starting snapshot, not a byte-for-byte recovery from the
  original run; the finished `project/` and the archived work order are the original artifacts.
- The baseline prompt and the managed prompt differ by design; the managed run also had to satisfy
  tests, documentation, verification and the quality contract.
- No human play session was performed for either result; the checks are automated plus screenshot
  inspection. The independent visual review was static, not a live responsive or acoustic pass.
- The page-check tool is part of the sample's consumer project, not a generic XC capability.
- The workflow contracts live in [`docs/`](../../docs/index.md); this sample illustrates them and does
  not define or extend them.
