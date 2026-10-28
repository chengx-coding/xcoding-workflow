# Work-order sample: a 2D sandbox built through XC

**Language:** **English** | [简体中文](README.zh-CN.md)

This sample is a real, complete XC work order. It is not a screenshot tour: a seeded consumer project
was driven through the managed lifecycle by the DeepSeek Harness command line, the resulting work
order was archived here, and the orchestration tree was rendered from the runtime. A second, direct
run of the same task without XC is included so the two results can be compared.

## Quick facts

| Item | Value |
| --- | --- |
| Task | Build a playable, offline 2D Minecraft-style sandbox from scratch |
| Why this task | A common "model capability" prompt with a visual, inspectable result and real design decisions |
| Consumer project | [`project/`](project/README.md), the finished static page built from the seed in [`seed/`](seed/) |
| Host | DeepSeek Harness CLI, `dsh headless` |
| Model | `deepseek-flash` |
| Entry point | `xc-work` with `operation=run`, `mode=change` |
| Lifecycle shown | Preparation, goal, analysis, solution, approval gate, implementation, verification, result |
| Change report | Deliberately waived for this sample (`requires_report=false`, `report_skip_reason=user_waived`) |
| Work order | `20261028-1731-implement-minecraft-sandbox` |
| Baseline | One direct run of the raw prompt with no workflow, archived in [`baseline/`](baseline/) |

## What is in this directory

```text
prompt.md                 the managed work order prompt sent to DeepSeek Harness
baseline-prompt.md        the raw task prompt used for the direct baseline
setup/WORKFLOW.md         the project bridge template for the consumer project
setup/xc-orchestration-runtime.json  runtime configuration for the sample workshop
seed/                     the starting snapshot the work order began from
project/                  the finished consumer project: the delivered game
baseline/                 the direct baseline: index.html, run record and final answer
work-order/               the archived work order: goal, analysis, solution, result, artifacts, runtime, tmp
tree/                     the final orchestration tree as SVG (zoomable) and PNG (README image)
media/                    matched 960x600 screenshots of the managed and baseline pages
```

The live work order ran in an independent workshop Git repository outside this repository, and
`project/.xcoding` was a directory junction to it. The archived copy in `work-order/` is a copy of
that work order directory, including its `tmp/` scratch, plus the run's final answer. In that copy,
files whose names ended in `.log` are stored with a `.txt` suffix and the references were updated,
because this repository ignores `*.log`; their line endings were normalized to LF. The live workshop is not part of this repository.

## Why this task

The task is deliberately of the kind people use to probe a new model: "build a game from scratch".
It has a visual result, it forces real decisions (terrain generation, collision, interaction rules,
camera, persistence), and it is small enough to finish in one work order. The raw prompt is in
[`baseline-prompt.md`](baseline-prompt.md); the managed prompt adds the workflow instructions and
verification requirements while keeping the same functional scope.

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
4. The work order closed with the change report explicitly waived and no project Git commit; the
   enclosing repository owns the sample's commit. The archived run kept the final answer in
   [`work-order/dsh-run.txt`](work-order/dsh-run.txt).

The prompt is written for a headless session: it forbids user questions, requires the solution gate
to be approved with a recorded decision by the main session, and keeps all runtime access on the
public `xcoding runtime` interface.

## Reading the orchestration tree

![The completed sample orchestration tree](tree/orchestration-tree.png)

The PNG is the Viewer's own export, rasterized at its natural size. The standalone
[`tree/orchestration-tree.svg`](tree/orchestration-tree.svg) is the zoomable version. The tree shows
the full lifecycle: prepare, goal, analysis, solution and its approval gate, implementation,
verification, result and finalizer, with the document-evolution subtrees that wrote and validated
each document.

Two details are worth pointing out:

- **The report group is skipped, not missing.** The node titled "Produce change review report" is
  `skipped` because the user explicitly waived the change-report stage. The waiver is recorded in the
  work order itself (`work_order.requires_report=false`, `work_order.report_skip_reason=user_waived`).
- **Pending nodes are unreachable branches.** Sixteen nodes are skipped and eight remain pending.
  The skipped nodes are the conditional branches themselves: four document review loops, four
  document gates, four non-accepting recovery groups, the reconciliation group, the clarification
  group, the solution recovery group and the report group. The eight pending nodes are the children
  of the four skipped review loops, which never ran. The tree is sealed with 30 succeeded nodes
  (17 executable task leaves plus one gate; the rest are composite groups), so the pending nodes
  were never scheduled rather than left unfinished.

The archived runtime tree reports `status=complete` with valid SHA-256 integrity. The work order
documents are in [`work-order/`](work-order/): [`goal.md`](work-order/goal.md),
[`analysis.md`](work-order/analysis.md), [`solution.md`](work-order/solution.md) and
[`result.md`](work-order/result.md). The verification evidence is in
[`work-order/artifacts/verification/verification.md`](work-order/artifacts/verification/verification.md).

## What the work order produced

The delivered page is [`project/index.html`](project/index.html), supported by seven JavaScript
modules and six test files. The implementation includes:

- deterministic seeded terrain with grass, dirt, stone and trees;
- a player with gravity, jumping, horizontal collision and substepped tile collision;
- left-click mining and right-click placement with reach, emptiness, support and player-overlap rules;
- a four-block hotbar with number-key and click selection;
- a camera that follows the player and clamps to the world bounds;
- `localStorage` save and load of the world, player and selection;
- a page-status marker used by the automated check.

Verification, reproduced from `project/`:

```text
node --test "tests/**/*.test.js"   28 tests, 28 pass
python tools/page_check.py         static checks pass; status marker green; 53 colour buckets
```

The screenshot used below is [`media/xc-sandbox.png`](media/xc-sandbox.png).

## The direct baseline and the comparison

The launching session used the same model (`deepseek-flash`), the same machine and the raw task prompt
for one direct run with the workflow disabled. The baseline ran outside the XC checkout, so the
checkout's `xc-*` Skills were not in the working directory; the harness's global skill discovery was
not instrumented. The launch configuration and final answer are recorded in
[`baseline/run.md`](baseline/run.md) and [`baseline/dsh-run.txt`](baseline/dsh-run.txt); the internal
transcript is not archived.

| Direct baseline | XC work order |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="Direct baseline sandbox screenshot" width="440"> | <img src="media/xc-sandbox.png" alt="XC work order sandbox screenshot" width="440"> |

Measured facts:

| Fact | Direct baseline | XC work order |
| --- | --- | --- |
| Deliverable layout | 1 file | 17 files (page, CSS, 7 modules, 6 tests, tool, README) |
| Total bytes | 98,883 | 69,035 |
| Committed logic tests | 0 | 28, all passing |
| Automated page check | none provided | green status marker, 53 colour buckets |
| External references in served files | 0 | 0 |
| Screenshot colour buckets | 203 | 53 |
| Durable process record | none | full work order |

What the two screenshots show is not ambiguous. The direct baseline produced a visibly more polished
page: a branded title bar, seed and autosave indicators, Help and New World buttons, layered
grass/sand/stone terrain, mountains, an eight-slot hotbar with per-block counts and a control strip.
The managed result is a smaller, plainer page with a four-slot hotbar and a two-line HUD panel (the
control hint and the selected block).

So on this single pair of runs the workflow did **not** produce a better-looking or more
feature-rich game. What it added was verifiability and traceability: committed tests, a repeatable
page check, a written architecture, a verification record and a complete work-order history. The
direct baseline added visual polish and extra features; its prompt asked only for the game, while the
managed prompt also required tests, documentation and verification.

Limits of this comparison: one run per side, the same launching configuration, different prompts (the
managed prompt also requires tests, documentation and verification), and no blind judging. It is an
anecdote about what happened here, not evidence that XC improves or degrades model output in general.
A useful follow-up experiment would add a visual-acceptance criterion to the managed prompt and check
whether the presentation gap closes.

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
answer, with `.log` files renamed to `.txt` and normalized to LF; it therefore contains absolute
paths from the original run.

## Limitations

- This is a single sample run. It documents one execution, not a benchmark.
- `seed/` is a reconstruction of the starting snapshot, not a byte-for-byte recovery from the
  original run; the finished `project/` and the archived work order are the original artifacts.
- The baseline prompt and the managed prompt differ by design; the managed run also had to satisfy
  tests, documentation and verification requirements.
- No human play session was performed for either result; the checks are automated plus screenshot
  inspection.
- The page-check tool is part of the sample's consumer project, not a generic XC capability.
- The workflow contracts live in [`docs/`](../../docs/index.md); this sample illustrates them and
  does not define or extend them.
