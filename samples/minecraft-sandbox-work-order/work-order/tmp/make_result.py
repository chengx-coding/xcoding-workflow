from pathlib import Path

workbench = Path(r"C:\dev\xcoding-workflow-dev\wf-ablation\standard-sample\workspace\workshop\.xcoding\work-orders\20261029-1459-2d-sandbox-game")
draft = (workbench / "tmp" / "result-draft.md").read_text(encoding="utf-8")
summary = (
    "The reviewer re-rendered 960x600 and 1440x900, measured the field guide at "
    "`scrollHeight 471 = clientHeight 471` with all seed actions visible, sampled cave air at "
    "`rgb(22,41,42)` with zero pure-black pixels, confirmed 9px/10px hotbar labels and valid "
    "mine/place hover states, and found no new required finding."
)
draft = draft.replace("{{FINAL_REVIEW_VERDICT}}", "ACCEPT")
draft = draft.replace("{{FINAL_REVIEW_SUMMARY}}", summary)
assert "{{" not in draft, "unresolved placeholder"
(workbench / "result.md").write_text(draft, encoding="utf-8", newline="\n")
print("result.md written", len(draft), "chars")
