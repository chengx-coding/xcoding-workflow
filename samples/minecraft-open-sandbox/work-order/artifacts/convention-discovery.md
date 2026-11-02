---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__root__prepare-work-order
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Convention discovery — L1 scan record

## Scope

Mandatory L1 convention-discovery floor for managed work order
`20261102-1145-open-sandbox-xc-044` (mode `create`, no features). Targets: the whole project root,
which the lifecycle expects to touch at `index.html`, `css/`, `js/`, `tests/`, `tools/`, and
`README.md`.

## Evidence

- Scanner: `python C:\Users\Admin\.agents\skills\xc-conventions\scripts\scan_conventions.py
  --project-root . --tier l1-scan` → `{"ok": true, "status": "scanned", "c1": [], "c2": [],
  "scanned_files": 0, "truncated": false}`. No convention file family (AGENTS.md, CLAUDE.md,
  GEMINI.md, .cursor/rules, .github/copilot-instructions.md, CONTRIBUTING.md, .editorconfig,
  formatter/linter/type-check configuration, build manifest, CI workflow) exists in the project.
- C1 read: `.xcoding/WORKFLOW.md`, the project bridge, is the only declared governance source. Its
  binding rules for this work order are: English code/comments/README/work-order documents; UTF-8
  with LF endings; no project Git commit (the enclosing repository owns the sample commit); no
  third-party libraries, CDN assets, external fonts, or network requests at runtime; `index.html`
  must keep working from `file://`; temporary files stay under the work order `tmp/`; verification
  runs `node --test "tests/**/*.test.js"` and `python tools/page_check.py` from the project root,
  and the seed checks must not be weakened; change-report stage waived
  (`work_order.requires_report=false`, `work_order.report_skip_reason=user_waived`).
- C2 read: none present. The seed has no package.json, lockfile, formatter, linter, or CI
  configuration. The only machine-checkable convention is the two verification commands above,
  declared by the bridge.
- C3 inference (weak evidence, labeled): the seed's files use an IIFE UMD wrapper
  (`config.js`, `world.js`, `player.js`, `render.js`) so the same module runs under Node's
  CommonJS loader and inside the browser page; `main.js` is browser-only. New code should follow
  that pattern where a module must be unit-tested, but this is inference, not a binding rule.

## Findings

- Status: `found`. One applicable C1 source (the project bridge) with concrete, binding rules;
  no conflict and no ambiguity between sources; no unusually large convention set. L2
  convention-review analysis is not triggered.
- Deviation: none. The L1 scan is the complete discovery depth this work order needs.
- Boundary: the scanner reported `scanned_files: 0`, so discovery is limited to the bridge and the
  three seed files read directly during preparation; no hidden convention source was skipped.

## Conclusion

Route these rules into implementation and verification: ES5-compatible browser JavaScript with
Node-testable UMD wrappers, UTF-8/LF, no network or third-party assets, unchanged working
`file://` load, the two declared verification commands kept green, no Git commit, and process
files confined to the work order `tmp/`.
