---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__root__prepare-work-order"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Preparation and convention discovery record

## Scope

Preparation of the `create` work order `20261030-0000-minecraft-sandbox` for the isolated
standard-sample workspace. The request is the verbatim Minecraft-style 2D sandbox task supplied to
`xc-work operation=run`, with `document_language=en`, `mode=create`, `feature_ids=[]`,
`project_root=...\workspace\project`, and `workshop_path=...\workspace\workshop\.xcoding`.

## Evidence

- Workbench opened through `xc-open-work-order`; returned `workbench_path`, `runtime_path` and
  `tmp_path` were consumed verbatim. The runtime tree was initialized from the work order template
  and its integrity verifies as `valid`.
- `project_root` is not itself a Git worktree; `project/.xcoding` is a directory junction to the
  workshop `.xcoding`. No project commit is expected from this work order, matching the bridge.
- `xc-document/scripts/validate_language.py --language en` returned `ok=true`, so
  `work_order.document_language=en` is valid and was published before any document write.
- `feature_ids=[]`; no feature directory was created and `work_order.has_features=false`.
- Knowledge source: `.xcoding/KNOWLEDGE.md` does not exist in this workshop, so no project knowledge
  source applies (not a failure; recorded as not applicable).
- L1 convention scan (`xc-conventions` tier `l1-scan`, targets `project/index.html`, `project/js`,
  `project/css`, `project/tests`): status `scanned`, `scanned_files=0`, `c1=[]`, `c2=[]`,
  `truncated=false`. The scan ran and found no project-local instruction files (`AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`, `.cursor/rules`, `.cursorrules`, `copilot-instructions.md`,
  `CONTRIBUTING.md`), no `.editorconfig`, and no CI workflow.
- The fixed project bridge `.xcoding/WORKFLOW.md` is the applicable C1 source and was read in full.
  Its binding rules for this work order: English for code, comments and work-order documents; no
  project Git commit; verification commands `node --test "tests/**/*.test.js"` and
  `python tools/page_check.py`; no formatter or linter, keep two-space JavaScript indentation and the
  existing module style; keep `README.md` accurate; no third-party libraries, CDNs, external fonts or
  network requests; keep `index.html` runnable from `file://`; keep the `#status` marker contract;
  keep browser modules loadable in Node; never delete or weaken seed tests.

## Findings

- No C1/C2 conflict exists. The bridge is the single governance source for project conventions.
- C3 de-facto patterns (UMD-style module wrapper, two-space indentation, one module per concern) are
  labeled inference only, and the bridge independently declares the indentation and module-style
  expectation, so they are followed as a stated project convention rather than as inferred law.
- No applicable convention is missing a record: the outcome status is `found` (bridge rules
  applicable), and the record is this artifact.

## Conclusion

Convention discovery is complete with status `work_order.convention_discovery=found`, record path
`artifacts/prepare-work-order/convention-discovery.md`. Report commitment resolved to
`work_order.requires_report=false` with `work_order.report_skip_reason=user_waived` from the explicit
binding instruction in the run prompt and the project bridge; because the commitment is false, no
`work_order.report_baseline` is captured, as the contract requires. Temporary files for this work
order stay under the workbench `tmp/` directory.
