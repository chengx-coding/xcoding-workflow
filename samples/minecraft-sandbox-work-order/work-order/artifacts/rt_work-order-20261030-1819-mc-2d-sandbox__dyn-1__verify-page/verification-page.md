---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__verify-page"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Verification — page, status marker and offline contract (focused scope)

## Scope

Executed the project's declared page check, captured and inspected the 960x600 screenshot, and
verified the offline, static-file contract, the required page structure and the status-marker
behaviour.

## Evidence

### Command and outcome

```console
cd C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project
python tools/page_check.py --screenshot <workbench>/tmp/verify-page-960x600.png
```

```json
{
  "ok": true,
  "checks": {
    "static": {"ok": true, "problems": []},
    "status_marker": {"ok": true, "pixel": [46, 204, 113], "expected": [46, 204, 113], "distance": 0.0},
    "canvas_colours": {"ok": true, "buckets": 251}
  },
  "screenshot": "...\\tmp\\verify-page-960x600.png",
  "viewport": [960, 600]
}
```

Screenshot SHA-256: `AFC1BC8D9978E5FCD1FB06B0E8F76A4C094A5CFB270B6AA7088114F0407C8821`.

### Static contract

- Required elements present: `id="game"`, `id="status"`, `id="hud"`, `id="hotbar"`.
- Only local references: `css/style.css` and the thirteen `js/*.js` scripts; no `http(s)://`, `//cdn`,
  `data:` or external font reference in the page or in any referenced file.
- `#status` starts at `data-state="booting"` and reaches `data-state="ready"`; the CSS keeps the
  required `data-state="ready"` and `data-state="error"` rules.
- The page is static: no build step, no module loader, no server; it runs from a `file://` URL (the
  check itself loads it from a file URL).
- `prefers-reduced-motion: reduce` rules are present in `css/style.css` (line 601) and remove
  transitions/animations and the hover transform.

### Screenshot inspection (960x600)

The captured frame shows:

- A dark glass top bar with the Wildgrove brand at the left, three live stat pills in the centre
  (Position `12, 41`, Time `07:41 day`, Seed `1337`) and the Pause, Sound on, seed input and New world
  actions at the right.
- A canvas scene with a soft dawn sky gradient, a low sun with a warm glow, layered blue-grey
  parallax hills, clouds, a green plateau with grass tufts and small flowers, deterministic trees, the
  player sprite standing on the surface, and a stone foreground with a few dark cave openings.
- A floating HUD pill at the upper left (`Looking at the sky`) and the nine-slot hotbar at the bottom
  centre, each slot carrying its key number, block swatch and count; slot 1 is lifted and ringed in
  amber, with the caption `GRASS · 16 IN HAND` above it.
- The controls hint line below the canvas and the green status dot at the bottom-left.
- Clear visual hierarchy: brand/status, world, then controls; the warm amber selection and caption
  read against the cool scene.

### Capability mapping

| Capability | Evidence |
| --- | --- |
| C5 palette and selected state | nine slots visible with counts; slot 1 selected ring and caption |
| C8 readable offline page and hint line | static check clean, hint line rendered with all controls |
| C9 README | README describes build, run, controls, tests and architecture (reviewed in the document stage) |
| C10 status marker | `ready` pixel exactly rgb(46,204,113); error-red rule present and exercised by the journey probe |
| C12 no external resources | static scan found no network reference |
| C13 960x600 screenshot | captured and inspected; path and hash recorded |
| J1/J3/J5/J8/J9 presentation | the rendered world, palette, HUD and controls needed by those journeys are visible; the journeys themselves are executed by `verify-journeys` |

### Gaps

- The 1280-wide scaling check and the live error-state flag are exercised by the journey probe rather
  than by this page check; this node records them as deferred, not as passed.
- Reduced motion is verified as a source/CSS fact here and by the render/camera unit tests; no
  reduced-motion browser screenshot is captured. That is a recorded gap, not a failure.

## Findings

- The page check passes exactly, including a zero-distance marker and 251 canvas colour buckets.
- The static contract is clean: no external references and the required ids are present.
- The screenshot is a coherent, distinctive interface with a readable hierarchy and an obvious
  selected palette slot; it is a suitable 960x600 quality-bar artifact.

## Conclusion

Focused page verification passes. Browser journey evidence and the 1280-wide state are verified by
the next node.
