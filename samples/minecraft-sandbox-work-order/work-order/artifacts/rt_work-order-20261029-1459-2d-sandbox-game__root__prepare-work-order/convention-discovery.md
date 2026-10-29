---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261029-1459-2d-sandbox-game"
node_id: "rt_work-order-20261029-1459-2d-sandbox-game__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Convention discovery record — L1 scan

## Scope

Mandatory L1 convention discovery for work order `20261029-1459-2d-sandbox-game` (mode `create`,
targets `index.html`, `css/`, `js/`, `tests/`, `tools/`). The scan ran before the first mutating
node. Temporary output stays under the work-order `tmp/` directory.

## Evidence

Scanner command (read-only, deterministic enumeration):

```console
python .agents/skills/xc-conventions/scripts/scan_conventions.py \
  --project-root project \
  --target index.html --target css --target js --target tests --target tools \
  --tier l1-scan
```

Scanner outcome: `status=scanned`, `ok=true`, `truncated=false`, `scanned_files=0`, `c1=[]`,
`c2=[]`. No `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/**`, `.editorconfig`, or GitHub workflow file
exists inside the project root.

Semantic read of the applicable C1 source, the project bridge at
`workshop/.xcoding/WORKFLOW.md` (mirrored into `project/.xcoding/WORKFLOW.md`):

- Code, comments, README and work-order documents are English.
- Do not create a project Git commit from this work order; the enclosing repository owns the sample
  commit, and the result must record that decision.
- Repository text files are UTF-8 with LF line endings.
- No third-party libraries, CDN assets, external fonts or network requests at runtime.
- `index.html` must run from `file://` with no build step or server.
- Keep the `#status` marker contract: `booting` before boot, `ready` after the first successful
  frame, red `error` state on a runtime error; the page check samples the marker pixel.
- Keep the browser modules loadable in Node so logic tests can require them without a DOM.
- Do not delete or weaken the seed tests; add coverage instead.
- Verification commands: `node --test "tests/**/*.test.js"` and `python tools/page_check.py`.
- Keep two-space JavaScript indentation and the module style already used in `js/`.

C2 configured signals: none declared.

## Findings

Outcome: `found`. The scanner surfaced no candidate files, and the project bridge supplies the
applicable declared rules. There is no C1/C2 conflict and no ambiguity, so no L2 `convention-review`
analysis node is required.

Applicable rules mapped to downstream work:

| Rule | Applies to |
| --- | --- |
| Offline only, no external assets or network | implementation, verification (`page_check.py` static half) |
| `file://` runnable, no build step | implementation, verification |
| `#status` booting/ready/error marker | implementation, verification (marker pixel check) |
| Modules loadable in Node, no DOM at require time | implementation, tests |
| Keep seed tests, add coverage | implementation, verification |
| UTF-8 + LF line endings | every authored file |
| English prose and comments | documents, README, code comments |
| No project Git commit | result/finalization |
| Two-space JS indentation, existing module style | implementation |

## Conclusion

The convention floor is satisfied with outcome `found`. The record is routed into the implementation
and verification node inputs. No convention-related blocker exists.
