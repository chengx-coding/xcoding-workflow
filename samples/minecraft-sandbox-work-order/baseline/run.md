# Direct baseline run record

This directory holds the direct-execution baseline for the sample's comparison.

## What ran

- **Date:** 2026-10-28 (Asia/Shanghai).
- **Host:** DeepSeek Harness CLI, `dsh headless`.
- **Model:** `deepseek-flash` (the headless profile's `deepseek-official` route).
- **Working directory:** `C:\dev\xcoding-workflow-dev\minecraft-sandbox-baseline`, outside the XC
  checkout so the checkout's `xc-*` Skills were not part of the working directory.
- **Prompt:** [`../baseline-prompt.md`](../baseline-prompt.md), sent on standard input.
- **Launch:** the same launch configuration as the managed run:

  ```powershell
  $env:DEEPSEEK_API_KEY = "<the key from the harness credential store>"
  $env:DSH_PERMISSION_MODE = "danger-full-access"
  Get-Content baseline-prompt.md -Raw | dsh headless -
  ```

- **Deliverable:** a single `index.html`, archived here as [`index.html`](index.html).
- **Final answer:** archived here as [`dsh-run.txt`](dsh-run.txt). The run's stderr reasoning stream
  and its own scratch test scripts are not archived.

## What this record does and does not prove

It records the launch configuration, the working directory, the prompt and the delivered artifact.
That is enough to show what was asked and what came back.

It does **not** independently prove the model identity beyond the launching configuration, and it
does not record whether the harness discovered any skill outside the checkout. The baseline
directory was outside the checkout, so the checkout's `xc-*` Skills were not in the working
directory; the harness's global discovery was not instrumented.

No transcript of the baseline's internal decisions is archived, so this sample makes no claim about
how the baseline chose its approach or whether it inspected screenshots.
