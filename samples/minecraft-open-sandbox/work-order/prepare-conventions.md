---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Preparation and Convention Discovery

## Scope

Prepared the create work order for a playable, offline 2D Minecraft-inspired sandbox. No feature
directory was created and `feature_ids` remains empty.

## Evidence

- Project bridge: `/work/.xcoding/WORKFLOW.md` read in full. It selects `xc-work operation=run`,
  `mode=create`, `feature_ids=[]`, waived the change report, requires English, and requires the seed
  checks plus project-appropriate additions.
- Language: `xc-document` validated `en`.
- Report commitment: `work_order.requires_report=false` with
  `work_order.report_skip_reason=user_waived`, matching the bridge.
- L1 convention scan: `l1-scan` completed with status `scanned`; it found zero C1/C2 candidates.
  The bridge itself is the applicable C1 source and was read directly.
- Seed verification commands: `node --test "tests/**/*.test.js"` and
  `python tools/page_check.py`; the bridge requires both to keep passing and permits additional
  checks. No build step, package manager, network request, CDN, or external font may be introduced.
- Git commits are owned by the enclosing repository; this work order must not create one.

## Findings

The effective development conventions are the project bridge constraints, UTF-8/LF text, vanilla
HTML/CSS/JavaScript, and preserving the seed's static/browser checks. No conflicting convention
source or ambiguity was found, so no L2 convention review is required.

## Conclusion

Convention discovery is `found`; implementation and verification must consume this record. The
work order language is `en` and the report obligation is explicitly waived.
