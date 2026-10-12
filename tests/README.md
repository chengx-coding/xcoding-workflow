# Test Suite

The suite is organised into behaviour clusters, selected by tier, and executed by
a stdlib-only runner that shards modules across worker processes.

```text
tests/
  xc_test_plan.json            single authority: clusters, tiers, membership, selection rules
  xc_test_runner.py            tiered, parallel execution
  xc_test_manifest_check.py    structural integrity checks (M1-M10)
  support/                     the only shared layer
    paths.py                   repository, tests and source roots; fixture resolution
    tiers.py                   the only implementation of the selection rules
    worker.py                  isolated shard worker used by the runner
    cli.py git.py runtime.py templates.py
  runtime/       governance/   lifecycle/   change_report/   documents/
  packaging/     daemon/       viewer/      delegation/
  runtime_cli.py  viewer_cli.py  workflow_scenario_harness.py   (frozen paths)
  test_xc_workflow_governance.py                                (frozen path)
```

## Commands

| Purpose | Command |
| --- | --- |
| Fast check after any edit (target: under a minute) | `python tests/xc_test_runner.py --tier gate` |
| **Default local iteration** (target: a few minutes) | `python tests/xc_test_runner.py --tier focused` |
| See what `focused` would run before running it | `python tests/xc_test_runner.py --tier focused --explain` |
| Select from explicit paths instead of the Git diff | `python tests/xc_test_runner.py --tier focused --changed src/xcoding/runtime/core.py` |
| Everything before a merge (target: ten minutes) | `python tests/xc_test_runner.py --tier full` |
| Release gate | `python tests/xc_test_runner.py --tier release` |
| Force a single process (also the equivalence baseline) | `python tests/xc_test_runner.py --tier full --serial` |
| Structural integrity of the plan | `python tests/xc_test_manifest_check.py` |
| Plain `unittest`, if you need it | `python -m unittest discover -s tests -t .` |

The runner prints the clusters it selected **and the ones it excluded**, so what
was not run is visible rather than inferred.

## Clusters

A cluster is a behaviour domain, and its name is its directory. Every test module
belongs to exactly one cluster.

| Cluster | Domain |
| --- | --- |
| `runtime` | Orchestration runtime state machine: scheduling, transitions, integrity, persistence, subtree archival, restore points, control packets, milestones, work-order mount, resume brief, config drift |
| `governance` | Governance classification, adaptive planning and enforcement, recovery, decision registry, fact cache, verification staleness, convention scanning, workshop setup, lifecycle templates, orchestration author, runtime CLI parity; the private-workshop citation guard |
| `lifecycle` | Full lifecycle end to end, including feature adoption and new feature, plus document-evolution end to end |
| `change_report` | The `xc-change-report` package: enumeration, baseline, validation, protocol drift, author commit boundary |
| `documents` | Document frontmatter and schema, rendering, LF write contract, skill mirror |
| `packaging` | Packaging, wheel, bundle, CLI entry points, installation, agents export, version consistency |
| `daemon` | Daemon protocol, server, lifecycle |
| `viewer` | Read-only viewer |
| `delegation` | Delegation model, resolver, gateway, CLI, runtime security boundary |

## Tiers

| Tier | What it contains | When to run it |
| --- | --- | --- |
| `gate` | The mandatory guards, cheap in-process logic checks, and plan integrity | After every edit |
| `focused` | `gate` plus the clusters selected by the changed paths | Default local iteration |
| `full` | Every cluster in parallel, excluding release-only tests | Before a merge; in CI |
| `release` | `full` plus release-only tests | Release candidates |

A test belongs to `gate` only when all three hold: it does not start a process or
open a socket, it does not depend on process-global state, and it runs well under
a second. `gate` is a statement about execution characteristics, not about
importance — the mandatory guards are in it, and so are many ordinary tests.

`release` exists for behaviour a single-process assertion cannot reproduce: forced
process death and kernel-lock release, daemon signals, background launch and
readiness handoff, a bare interpreter without `site`, occupying a real TCP port,
the legacy adapter compared as a separate program, and committing the live
worktree. It also carries the recorded governance measurement replay, which pays
several hundred runtime CLI subprocesses by design.

## Selection

`focused` resolves changed paths to clusters through the ordered rule table in
`xc_test_plan.json`, longest prefix first. Two things are worth knowing:

- The `governance` cluster is added to **every** selection. Its citation guard
  enumerates the Git index, so any tracked file addition, edit or deletion can
  affect it. That is the guard's real scope, not caution.
- A path that matches no rule **escalates to every cluster** and says so. The
  suite fails closed: it will not silently run nothing.

## Adding or moving tests

1. Put the module in the cluster directory matching its behaviour domain.
2. Add the module name to that cluster's `modules` list in `xc_test_plan.json`.
3. Derive paths from `tests.support.paths` — `REPO_ROOT`, `TESTS_ROOT`,
   `fixture_path(...)` — never from `Path(__file__).resolve().parents[N]`.
   Counting parents makes a module's meaning depend on its depth, which is what
   made the cluster reorganisation risky in the first place.
4. If the module needs a new source-path rule, add it to `selection_rules`,
   most specific first.
5. Run `python tests/xc_test_manifest_check.py`. It fails when a collected test
   has no declared cluster, which is the failure mode that matters most: a
   reorganisation that silently stops running a test still reports success.

## Frozen paths

Four files must not move:

- `tests/runtime_cli.py`
- `tests/viewer_cli.py`
- `tests/workflow_scenario_harness.py`
- `tests/test_xc_workflow_governance.py`

The governance fixture records their paths as SHA-256 inputs, so relocating or
renaming them invalidates it. `test_xc_workflow_governance.py` therefore lives at
the tests root while belonging to the `governance` cluster; that is a deliberate,
declared exception rather than an oversight. If a frozen file's content must
change, re-record the fixture through
`python tests/workflow_scenario_harness.py record --manifest <path> --reason <text>`
and confirm `verify` still passes.

## Worker count

The runner defaults to `min(8, max(2, os.cpu_count() // 2))`. The ceiling is
measured, not guessed: on a 20-logical-core machine a full run took 603 s with 4
workers, 619 s with 8, and 713 s with 16 — and the 16-worker run produced a
failure caused by a subprocess timeout under contention. More workers is not
faster here.

Run **one suite instance at a time**. Concurrency is the runner's job; stacking a
second suite on top produces the contention that inflates wall clock and trips
timeouts.

## Output and progress

Long commands write their output to a file and the caller reads it incrementally.
Do not pipe suite output through a filter that buffers until exit: it makes
"running" indistinguishable from "wedged", which is how duplicate suite launches
happen in the first place.

## Structural checks

`xc_test_manifest_check.py` enforces ten properties. The important ones:

| Check | Property |
| --- | --- |
| M1 | Every collected test has exactly one declared cluster (no silent loss) |
| M3/M4 | Every rule points at a real cluster; every cluster is reachable |
| M5/M9 | No `gate`-tier test starts a process or touches the real worktree |
| M6 | Frozen paths are still in place |
| M7 | Clusters converted to in-process calls keep a process-bound sentinel |
| M8 | Declared cross-cluster couplings are data, not reviewer memory |
| M10 | Each cluster resolves from a representative source path |
