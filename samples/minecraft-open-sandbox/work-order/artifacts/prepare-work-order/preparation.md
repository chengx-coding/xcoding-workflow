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

# Work order preparation

## Inputs read

- Project bridge: `.xcoding/WORKFLOW.md`.
- XC runner instruction: `samples/minecraft-open-sandbox/xc-runner.md` in the workflow checkout.
- Seed code, tests, page check and `README.md` in the project root.

## Workbench

The `.xcoding` workshop is an independent nested Git worktree. The prepared work order
`20261101-2045-open-sandbox-xc-2` already contains the standard workbench (`runtime/`, `artifacts/`,
`tmp/`), so it is reused through its public runtime path rather than opening a duplicate work order
directory. `xc-open-work-order` was not invoked a second time because its collision behaviour would
create `20261101-2045-open-sandbox-xc-2-2` instead of this prepared identity.

- Workbench: `.xcoding/work-orders/20261101-2045-open-sandbox-xc-2/`
- Runtime: `.xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml`
- Artifacts: `.xcoding/work-orders/20261101-2045-open-sandbox-xc-2/artifacts/`
- Temporary files: `.xcoding/work-orders/20261101-2045-open-sandbox-xc-2/tmp/`

## Requested scope

Product request, verbatim: "Build a playable, offline 2D sandbox game inspired by Minecraft. It must
run by opening `index.html`, with no build step, external libraries, CDNs, or network access. Make it
feel like a small Minecraft, save progress, and document the controls."

Mode: `create`. No features were supplied (`feature_ids=[]`), so no feature directory was created and
`work_order.has_features=false`. The initiating instruction explicitly delegates Minecraft-system
scope decisions (crafting, survival, mobs, redstone, and similar systems) to this work order's
analysis, which must record the choice rather than inherit a pre-declared requirement or prohibition.

## Document language

`work_order.document_language=en`, validated with `xc-document/scripts/validate_language.py` and taken
from the bridge's declared content language. Top-level documents are English.

## Report commitment

Resolved through the fixed report policy. The initiating instruction carried by the project bridge
explicitly waives the change report, so `work_order.requires_report=false` and
`work_order.report_skip_reason=user_waived` are written during preparation. Because the resolved
commitment is false, no `work_order.report_baseline` is captured and no report group is mounted. The
initial `report.strength` is `standard` under the risk/audit rule; it is not used by a waived report.

## Convention discovery

`work_order.convention_discovery=found`; the record is
`artifacts/prepare-work-order/convention-discovery.md`.
