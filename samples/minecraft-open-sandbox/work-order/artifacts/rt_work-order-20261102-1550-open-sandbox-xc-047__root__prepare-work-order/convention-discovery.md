---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Convention discovery record (L1)

## Scope

L1 mandatory discovery floor for the create work order `20261102-1550-open-sandbox-xc-047` in the
project root. Targets inspected for nearest-neighbour relevance: the repository root, `index.html`
and `js/`. The fixed project bridge `.xcoding/WORKFLOW.md` was read in full before this scan; it is
the primary declared convention source for this work order.

## Evidence

Deterministic enumeration command and result:

```console
python C:\Users\Admin\.agents\skills\xc-conventions\scripts\scan_conventions.py --project-root . --tier l1-scan --target . --target index.html --target js
{"budget": {"deadline_ms": 5000, "max_files": 4000}, "c1": [], "c2": [], "ok": true,
 "project_root": "...\\xc\\project", "scanned_files": 0, "schema_version": 1,
 "status": "scanned", "tier": "l1-scan", "truncated": false}
```

The scanner returned `status=scanned` (not `scan-unavailable`) and enumerated no C1 declared
instruction file and no C2 configured signal file. The project has no `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `.cursorrules`, `.cursor/rules/`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`,
`.editorconfig` or `.github/workflows/` content.

## Findings

- Applicable C1 authority is the project bridge `.xcoding/WORKFLOW.md`. Its relevant rules for this
  work order are: English code, comments, README and work-order documents; UTF-8/LF; no project Git
  commit; verification with `node --test "tests/**/*.test.js"` and `python tools/page_check.py` from
  the project root; keep the seed tests intact; no build step and `file://` operation; no third-party
  libraries, CDN assets, external fonts or runtime network requests; no reading of the one-shot
  workspace, the old compact sample, its profile or its evaluation; temporary files stay under this
  workbench's `tmp/`; the change report is waived (`work_order.requires_report=false`,
  `work_order.report_skip_reason=user_waived`).
- No applicable C2 file exists, so no machine-enforced formatter, linter, type-check, build manifest
  or CI command exists to inherit. The bridge commands above are the complete declared verification
  set.
- C3 de-facto patterns observed in the seed (labelled inference, not mandatory): dependency-free
  CommonJS/global UMD wrappers per `js/` module so the same file runs under `node --test` and in the
  browser via classic script tags; a frozen shared config object; `node:test` with
  `node:assert/strict`; Python standard-library tooling; no ES module syntax because `file://`
  blocks module loading. The work order follows these patterns as a compatibility choice.

## Conclusion

Discovery status: `not-applicable` (the check ran and found no additional declared or configured
project convention beyond the project bridge). No C1/C2 conflict or ambiguity exists, so no
convention-review analysis is required. This record is routed into the implementation and
verification nodes as their convention input.
