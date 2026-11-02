---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__i4-docs-evidence
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# I4 implementation record — documentation and browser evidence

## Changed paths

- `README.md` — rewritten product documentation: what Cubewood is, how to play, the complete
  controls table, the world systems, saving/export/import/fallback behaviour, the backdrop
  before/after design, accessibility notes, both check commands, the new browser check, and the
  project layout.
- `tools/browser_check.py` — new stdlib-only evidence tool: runs the untouched seed page check,
  drives the in-page self-test in headless Chrome (DOM clicks, real pointer/keyboard events,
  before/after pulses, save payload parsing), proves save persistence across two browser launches
  with a shared profile, captures ten deterministic scene screenshots with pixel-pair assertions,
  and proves offline rendering with all DNS resolution blocked (`MAP * ~NOTFOUND`), comparing the
  frame byte-for-byte against the online capture.
- Evidence generated under
  `.xcoding/work-orders/20261102-1145-open-sandbox-xc-044/artifacts/verification/browser/`
  (`summary.json`, `screenshots/*.png`, `offline-day.png`, `chrome-profile/`).

## Validation

- `node --test "tests/**/*.test.js"` → 79/79 pass, unchanged scope.
- `python tools/page_check.py` → ok, static clean, exact green status marker, 124 colour buckets.
- `python tools/browser_check.py …` → **ok=true**:
  - self-test: **21/21 steps pass**;
  - persistence: save-write and save-read both pass in separate launches;
  - screenshots: ten scenes, each with ≥8 colour buckets;
  - pairs: night 43.3 darker than day, cave 38.9 darker than day, backdrop changes 27.2 % of
    sampled pixels, zoom pair 56.2 %, inventory/crafting/guide 74–76 %;
  - offline: frame identical (`diff_vs_online = 0.0`) with DNS resolution blocked.

## Notes and residual risk

- The screenshot scenes now freeze simulation time and camera so paired evidence is deterministic;
  normal play is unaffected (the freeze is scene-only).
- The performance self-test step records `lastRelightMs`/`lastFrameMs`; headless virtual time does
  not advance the high-resolution clock during synchronous work, so those numbers read 0 in this
  environment. The bound on work is structural (18,432 tiles relit per edit) and the browser check
  asserts the metric path runs without error.
- Export/import is covered by unit tests on the envelope plus the menu wiring; a real file download
  is not automatable in the headless capture path and is recorded as a manual-path residual risk.
- No external asset, network reference, dependency, or Git commit was introduced.
