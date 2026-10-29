---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261029-1219-2d-sandbox-game
node_id: rt_work-order-20261029-1219-2d-sandbox-game__root__prepare-work-order
feature_ids: []
orchestration:
  tree_ref: runtime/orchestration.xml
---

# Convention Discovery Record

## Scope

L1 discovery covered the project bridge, the project root and the intended change surface: `index.html`, `css/`, `js/`, `tests/` and `tools/`. The scanner was invoked in `l1-scan` tier with those targets and a 5-second / 4000-file budget.

## Evidence

- `scan_conventions.py` returned `ok: true`, `status: scanned`, `scanned_files: 0`, with no C1 or C2 candidates inside the project tree.
- `.xcoding/WORKFLOW.md` is the authoritative project bridge. It declares: English text and UTF-8/LF; no Git commit from this work order; no build step; `node --test "tests/**/*.test.js"` and `python tools/page_check.py` as verification; two-space JavaScript indentation and the existing module style; no external libraries, CDNs, fonts or network requests; `file://` compatibility; preservation of the `#status` marker contract; Node-loadable browser modules; and no feature creation.
- `README.md` describes the seed architecture and the target controls, and confirms the same offline and Node-loadable constraints.
- Existing source files confirm the UMD-style module pattern in `js/*.js`, two-space indentation, and the status-marker contract in `index.html`, `css/style.css` and `js/main.js`.
- No formatter or linter configuration exists, matching the bridge's statement.

## Findings

The bridge is the only applicable declared convention source. No `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, CI workflow, formatter, linter or package manifest exists in the project tree. No same-level conflict or ambiguity was found. The project-local C3 pattern is the existing UMD module style, which is consistent with the bridge's declared module-style rule.

## Conclusion

Status: `found`. The applicable convention set is the project bridge plus the C3 module/indentation pattern. These rules must be routed into implementation and verification, especially the offline constraint, `file://` operation, status marker, LF/UTF-8, no commit, and the declared test commands.