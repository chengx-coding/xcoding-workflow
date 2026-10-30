---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__impl-review-polish"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Implementation — help dialog freeze repair

## Finding

During the screenshot inspection that feeds the verification stage, the rendered page showed a real
usability gap: opening the controls dialog left the simulation running behind it. Keyboard movement
still reached the player while the dialog covered the scene, so a player reading the controls could
walk off an edge unnoticed. The same inspection showed the controls panel had no height guard, so on
a shorter stage the ten-row list could overflow the dialog.

Severity: medium (usability/accessibility). This is inside the accepted S4/M14/M16 area, not a new
capability.

## Repair

- `project/js/main.js` — `toggleHelp` now freezes the simulation when the dialog opens, remembers
  whether the player was already paused, and restores the exact prior state on close. The pause
  overlay stays hidden while the help dialog is open, and mining/input flags are cleared on open so a
  held key cannot carry into the frozen state. `syncPauseButton` hides the pause dialog whenever help
  is open.
- `project/css/style.css` — `.panel` now has a stage-relative `max-height` and vertical scrolling so a
  long control list stays inside the stage.
- `project/js/ui.js` — the in-page control list also documents the `R` respawn shortcut, matching the
  README (the list had ten rows after this correction).

## Validation

- `node --test "tests/**/*.test.js"` -> `tests 124`, `pass 124`, `fail 0`.
- `python tools/page_check.py --screenshot <workbench>/tmp/shot-final.png` -> `ok true`, status pixel
  distance `0.0`, `202` canvas colour buckets.
- Browser harness after the repair (`tmp/visual-verify.json`): `help-pauses-game = true`,
  `help-restores-game = true`, `help-count = 10`, no console errors or exceptions; the rest of the
  interaction, persistence, scaling and reduced-motion checks still pass in the same run.

## Convention accounting

- C1 bridge — English, two-space JavaScript, UMD modules, Node-loadable, no network, `file://`
  friendly: followed. No formatter or linter exists; no formatting churn.
- C1 bridge — keep the `#status` contract and tests: untouched and still passing.
- No project commit was created.

## Residual risk

- Pressing `P` while the help dialog is open toggles pause underneath the dialog; closing help then
  restores the pre-help running state rather than the toggled one. The behaviour is harmless and the
  normal path is covered, but the key combination is not separately surfaced in the help copy.
- The dialog scrolls rather than shortening its list on very short stages; that is intentional so no
  control is hidden.
