# CLI / library / API surface profile

**Scope:** task-class. **Owner:** `xc-work/references/profiles/cli-library-api.md`. **Promotion
status:** `validated-in-class` (contract probe: `check_version.py` exit 0/2; see
`applicability-probes.md`). **Evidence surface:** CLI/API/file. **Generality evidence:** executed
CLI probe; not a universal rule. **Force:** convention-only.

**Applies when** the user/operator observes the artifact through commands,
exit codes, stdout/stderr, API status/body, files, side effects or persisted state. **Does not apply**
to a pure rendered-visual task with no command/API/file surface.

## Required evidence

- The exact command/API call and its observable before/after: exit code, stdout/stderr, HTTP status
  and body, written file/diff, or persisted state.
- For each journey, an executed probe or manual scenario; a first frame or screenshot is irrelevant
  here.
- Error/empty/limit/recovery states where the behavior depends on them. A successful happy-path call
  does not prove them.
- Side effects and idempotence where the task changes external state; record cleanup/rollback.
- A `must` gap fails/blocks verification until executed or accepted as a recorded risk; a `should`
  gap may remain recorded.

Do not invent visual evidence for this profile. A screenshot is not a substitute for stdout/exit/
status/diff evidence.
