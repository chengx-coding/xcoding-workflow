---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261028-1731-implement-minecraft-sandbox"
node_id: "rt_work-order-20261028-1731-implement-minecraft-sandbox__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: "C:/dev/xcoding-workflow-dev/minecraft-sandbox-workshop/.xcoding/work-orders/20261028-1731-implement-minecraft-sandbox/runtime/orchestration.xml"
---

# Convention Discovery Record

## Scope

Mandatory L1 scan for the managed mutation. Targets: `js/`, `tests/`, `index.html`, and
`README.md` under the consumer project.

- Scanner: `skills/xc-conventions/scripts/scan_conventions.py --tier l1-scan`.
- Result: `status=scanned`, zero C1 and zero C2 candidates, zero scanned files, not truncated.
- The scanner's default families do not include the fixed `.xcoding/` bridge location, so the
  bridge was read directly as part of the same discovery step.

## Applicable C1 declared rules

| Source | Rule relevant to this work order | Disposition |
| --- | --- | --- |
| Project bridge `.xcoding/WORKFLOW.md` | Code, comments, README and work-order documents are English | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | Do not create a project Git commit from this work order | Follow; record the decision in the result |
| Project bridge `.xcoding/WORKFLOW.md` | Repository text is UTF-8 with LF line endings | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | No build step; `index.html` must work from `file://` | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | Checks: `node --test "tests/**/*.test.js"` and `python tools/page_check.py` | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | No formatter or linter; keep two-space JavaScript indentation and the existing module style | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | No third-party libraries, CDNs, external fonts or runtime network requests | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | Preserve the `#status` marker contract (`booting`, `ready`, red error) | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | Keep browser modules loadable in Node for logic tests | Follow |
| Project bridge `.xcoding/WORKFLOW.md` | Do not delete or weaken the seed tests; add coverage | Follow |
| Root `AGENTS.md` (checkout context) | Preserve unrelated worktree changes; do not commit unless required | Follow |
| Root `AGENTS.md` (checkout context) | Temporary/process files stay in the workbench `tmp/`; never declare them as artifacts | Follow |

## C2 configured facts

- No formatter, linter, type-checker, or CI configuration applies to this consumer project.
- The project harness `tools/page_check.py` is a configured verification command (static checks plus
  headless Chrome render check).
- Node.js 24, Python 3.12 and Google Chrome are the declared host tools.
- The page shell and harness already fix the required element ids `game`, `status`, `hud` and
  `hotbar`, and the `js/` UMD module layout.

## C3 de-facto observations (inference, not mandatory)

- The seed modules use an IIFE UMD wrapper, two-space indentation, double-quoted strings and
  `Object.freeze` for exported constants. This is a weak local pattern; the bridge already declares
  the two-space and module-style expectation, so no additional obligation is inferred.
- `tests/world.test.js` uses `node:test` and `node:assert/strict`. New tests follow that pattern
  because it is the only executable test style present.

## Conflicts and ambiguity

None. The project bridge, the root instructions, and the seed code agree. The scanner's empty
candidate list is explained by the bridge living under `.xcoding/` and by the absence of any extra
instruction file inside the project root.

## Scan boundaries

Read-only deterministic scan with the scanner defaults (5,000 ms deadline, 4,000 file cap) over the
consumer project root; `.gitignore` is honored. Sibling sample files, the enclosing checkout's
`skills/`, `tests/` and `docs/` trees, and the workshop worktree were out of scope and were not
scanned for project conventions.

## Conclusion

Discovery outcome: `not-applicable` for scanner candidates, with the applicable declared rules
coming from the project bridge and the root `AGENTS.md`. No L2 convention-review escalation is
required; this record is routed into implementation and verification inputs.
