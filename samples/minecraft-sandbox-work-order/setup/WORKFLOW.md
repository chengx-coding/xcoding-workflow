---
schema_version: 1
document_kind: project-workflow
content_language: en
---

# Project Workflow

## Project Identity

This directory is the consumer project of the XC work-order sample. The product is a 2D
Minecraft-style browser sandbox: a static page built from plain HTML, CSS and JavaScript, with no
framework, no build step and no package manager. The seed snapshot shipped with this sample (`seed/`,
beside `project/`) provides the page shell, module skeleton and verification harness; the committed
`project/` is the finished result produced by the sample's create-mode managed work order. To run the work order
again, remove `project/.xcoding` and `project/`, recreate `project/`, and copy `seed/` into it so the
starting state contains no finished files or stale runtime link; the workshop step then recreates the
junction.

Python 3.12, Node.js 24 and Google Chrome are available on the host. Node runs the logic tests and
Chrome renders the page for the screenshot check.

## Language and Commit Conventions

Code, comments, the project README, and all work-order documents are written in English.

Do not create a Git commit from this work order. The enclosing `xcoding-workflow` repository owns the
sample's single scoped commit, and this project is a subdirectory of that repository, so a commit from
here would capture unrelated paths. A work order that changed this project therefore leaves the
commit to the enclosing repository and records that decision.

Repository text files use UTF-8 with LF line endings.

## Code Repository and Verification Commands

There is no build step. The page must keep working when `index.html` is opened directly from the file
system.

Run these checks from the project root:

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` runs the logic tests. `tools/page_check.py` performs the static checks (required
elements, no external network references, local assets exist) and then loads the page in headless
Chrome, verifies the status marker and samples the canvas for non-blank rendering. It accepts
`--screenshot <path>` to keep the captured PNG; pass a path under the work-order `tmp/` directory when
a screenshot is only diagnostic evidence.

There is no formatter or linter configured. Keep the existing two-space JavaScript indentation and
the module style already used in `js/`.

## Documentation

`README.md` in this directory is the project's user documentation. Keep it accurate when behavior or
controls change: what the page is, how to open it, the controls, how to run the checks, and the small
architecture overview.

## Feature and Work Order Conventions

No managed features exist; the sample work order has `feature_ids=[]` and must not create one.

This work order is a published create-mode reference sample. Use `xc-work` `operation=run` with `mode=create`. The create lifecycle is goal, implementation, verification and result; set `work_order.requires_analysis=false`, `work_order.requires_solution=false` and `work_order.solution_gate_required=false`. The goal's acceptance conditions must include a user-facing quality contract: the result will be compared side-by-side with a strong one-shot attempt and must be at least as visually polished and feature-rich. Render the page, inspect a screenshot, compare it against that bar, and iterate. Add an independent visual review node before the result and fix any required findings. The change-report stage is explicitly waived by the user: write `work_order.requires_report=false` and `work_order.report_skip_reason=user_waived` during preparation and do not mount the report group.

## Project-Specific Constraints

- No third-party libraries, no CDN assets, no external fonts, no network requests at runtime.
- Keep `index.html` runnable from `file://`; do not depend on a bundler or a development server.
- Keep the `#status` marker contract: `data-state="booting"` before boot, `data-state="ready"` after a
  successful first frame, and a red error state when a runtime error occurs. The page check reads the
  marker pixel.
- Keep the browser modules loadable in Node so logic tests can require them without a DOM.
- Do not delete or weaken the seed tests; add coverage instead.
