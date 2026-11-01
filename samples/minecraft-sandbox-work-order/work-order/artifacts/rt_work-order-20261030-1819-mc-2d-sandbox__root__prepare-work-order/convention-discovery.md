---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work-order-20261030-1819-mc-2d-sandbox__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Convention discovery record (L1)

## Scope

Mandatory L1 convention scan for the create work order in
`C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project`. Targets inspected first because they will
change: `index.html`, `js/`, `css/`, `tests/`, `README.md`. The scan is read-only and precedes any
product edit.

## Evidence

Command and outcome:

```console
python .agents/skills/xc-conventions/scripts/scan_conventions.py \
  --project-root C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project \
  --tier l1-scan \
  --target index.html --target js --target tests --target css --target README.md
{"budget": {"deadline_ms": 5000, "max_files": 4000}, "c1": [], "c2": [],
 "ok": true, "project_root": "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project",
 "scanned_files": 0, "schema_version": 1, "status": "scanned", "tier": "l1-scan",
 "truncated": false}
```

The scan ran successfully and enumerated no C1 instruction-file candidate and no C2 configured
signal inside the project tree. Manual confirmation agrees with the enumeration: the project root
contains no `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.editorconfig`, package manifest, formatter
or linter configuration, or CI workflow. The nearest instruction file is the checkout-level
`AGENTS.md`, which belongs to the enclosing `xcoding-workflow` repository rather than to this consumer
project, and this project is not inside that repository's worktree. `.xcoding/KNOWLEDGE.md` does not
exist, so no knowledge source holds project conventions.

The project bridge `.xcoding/WORKFLOW.md` was read fully. Its rules are the applicable C1 declared
set for this work order:

- English for code, comments, project README and all work-order documents; UTF-8 with LF endings.
- Do not create a Git commit from this work order; the enclosing repository owns the sample commit.
- No build step; `index.html` must work from `file://`; no third-party libraries, CDN assets,
  external fonts or runtime network requests.
- Verification commands from the project root: `node --test "tests/**/*.test.js"` and
  `python tools/page_check.py` (the latter accepts `--screenshot <path>`).
- Two-space JavaScript indentation and the existing module style in `js/`; no formatter or linter.
- Keep `README.md` accurate about behavior and controls.
- Keep the `#status` marker contract (`booting` → `ready`, red error state) and keep browser modules
  loadable in Node; do not weaken the seed tests.

## Findings

- No conflict, ambiguity, or multiple governance source was found: the bridge is the only declared
  convention source, and it is silent on the remaining areas.
- No C3 de-facto rule is promoted to mandatory. The existing module style (UMD factory returning an
  API object, two-space indentation, `"use strict"`) is treated as a weak inference that the work
  order will follow for consistency, not as a declared rule.
- The scan boundary is the consumer project root; `.xcoding/` holds the bridge and the managed
  workbench and is not scanned as product convention content.
- No project command, formatter, or framework is invented beyond the bridge's declared commands.

## Conclusion

Outcome: `not-applicable` — the mandatory L1 check ran, the bridge was read, and no additional
project-owned convention file applies. The route value for the blackboard is `not-applicable`, with
this record as its artifact. The bridge rules above are routed as inputs to implementation and
verification; implementation must account for each as followed or explicitly deviated from with a
reason.
