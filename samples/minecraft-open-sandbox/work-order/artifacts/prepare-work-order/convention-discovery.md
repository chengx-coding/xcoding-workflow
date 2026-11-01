---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Convention discovery (L1)

## Scope

- Project root: repository root of the isolated XC consumer project (plain HTML/CSS/JavaScript seed).
- Tier: `l1-scan`, run before any document or product write.
- Targets: the whole project; this is a `create` work order and no target path is excluded.
- Bridge locations: none declared beyond `.xcoding/WORKFLOW.md`.
- Scanner: `xc-conventions/scripts/scan_conventions.py --project-root . --tier l1-scan`,
  output kept at `.xcoding/work-orders/20261101-2045-open-sandbox-xc-2/tmp/convention-scan.json`.
- Scan result: `ok=true`, `status=scanned`, `scanned_files=0`, `c1=[]`, `c2=[]`,
  `truncated=false`. `AGENTS.md` and `.xcoding/KNOWLEDGE.md` do not exist in this project.

## Applicable C1 rules (from the project bridge)

`.xcoding/WORKFLOW.md` is the only declared instruction source and it is binding:

1. Code, comments, README and work-order documents are English; files are UTF-8 with LF line endings.
2. No project Git commit; the enclosing repository owns the sample commit.
3. No third-party libraries, CDN assets, external fonts or network requests at runtime; `index.html`
   must run from `file://` with no build step.
4. Verification from the project root: `node --test "tests/**/*.test.js"` and
   `python tools/page_check.py`; seed tests must not be weakened and new checks are added as needed.
5. Temporary files stay under the work order `tmp/`.
6. The change-report stage is waived for this work order (`work_order.requires_report=false`,
   `work_order.report_skip_reason=user_waived`).

## C2 configured facts

None found: the seed has no package manifest, formatter/linter configuration, `.editorconfig`, or CI
workflow. The verification commands in the bridge are the only machine-enforced facts.

## C3 de-facto patterns (non-mandatory, follow where sensible)

The seed source uses UMD-style modules (`module.exports` for Node tests plus a browser global),
`"use strict"`, two-space indentation, `Object.freeze` configuration, `node:test` + `node:assert/strict`,
and a standard-library-only Python page check. These are recorded as inference for consistency, not as
binding rules.

## Conflicts

None. No same-level conflict or ambiguous source was found.

## Status

`found` — the bridge supplies applicable declared rules (enumerated above) and the scanner found no
additional project instruction or configuration files. The discovery record is consumed by the
implementation and verification nodes.
