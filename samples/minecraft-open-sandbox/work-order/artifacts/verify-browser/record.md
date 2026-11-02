---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__dyn-1__verify-browser"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Verification record - browser interaction, persistence and first run

## Command and environment

```console
node tools/browser_check.js --profile <workbench>/tmp/chrome-verify \
  --shots <workbench>/artifacts/screens \
  --out <workbench>/artifacts/verify-browser/browser-check.json
```

Chrome stable (`C:\Program Files\Google\Chrome\Application\chrome.exe`) launched headless with a
fresh profile and `--remote-debugging-port=0`; the harness is dependency-free and talks to the
DevTools protocol with Node 24's global `WebSocket`. Result: exit 0, `ok=true`, 13 of 13 checks true,
no page exceptions, console errors or error-level log entries. Raw evidence:
`artifacts/verify-browser/browser-check.json`.

## Real-pointer interaction truth

Ten independent trials. Each trial computed a reachable, exposed surface tile from the live game,
converted it to viewport coordinates through the same camera transform the game uses, dispatched
`Input.dispatchMouseEvent` mouseMoved + mousePressed (button left), held, then mouseReleased, and
re-read the block:

| Trial | Tile (x,y) | Before | After | Measured hold |
| --- | --- | --- | --- | --- |
| 1 | 23, 91 | grass (1) | air (0) | 357 ms |
| 2 | 25, 91 | grass (1) | air (0) | 355 ms |
| 3 | 22, 91 | grass (1) | air (0) | 350 ms |
| 4 | 26, 91 | grass (1) | air (0) | 359 ms |
| 5 | 21, 91 | grass (1) | air (0) | 354 ms |
| 6 | 27, 91 | grass (1) | air (0) | 364 ms |
| 7 | 20, 91 | grass (1) | air (0) | 360 ms |
| 8 | 28, 91 | grass (1) | air (0) | 353 ms |
| 9 | 19, 91 | grass (1) | air (0) | 364 ms |
| 10 | 29, 91 | grass (1) | air (0) | 357 ms |

10/10 hits, every hold far above the 90 ms floor. The negative control called
`document.getElementById('game').click()` on a valid target and the block stayed unchanged
(`2 -> 2`), proving the mining result comes from the pointer pipeline, not from synthetic element
activation.

## Other checks

- **First-run affordance** - fresh profile: overlay screen `title`, primary `Enter world`,
  `hasSave=false`, no saved summary. A real pointer click on the primary button entered
  `mode=playing`. The title screenshot is `artifacts/screens/01-title-first-run.png`.
- **Placement** - a real right-button press on a mined tile restored grass (`0 -> 1`) and reduced the
  grass count by exactly one (10 -> 9).
- **Save, reload and continue** - Escape opened the pause screen; a real click on **Save now**
  produced `hasSave=true` and `status.kind=ok` (`Saved ... just now`). After `Page.reload` the title
  offered **Continue** with the saved summary `Day 1, 10 blocks mined, 0m 06s played, just now`.
  Continuing restored an untouched hole (`0`), the placed grass (`1`) and the expected grass count
  (`9`). The save summary and the in-game save indicator therefore read the same stored state.
- **Crafting UI wiring** - after injecting six logs, real clicks on the Planks recipe then the
  Workbench recipe produced exactly wood `6 -> 5`, planks `4 -> 0`, workbench `1`.
- **Night threat** - clock set to 0.78: `isNight=true` and `mobCount > 0` (a hollow appeared in the
  dark); captured in `artifacts/screens/06-night.png`.
- **Visual states** - title, day surface, pause menu, continue title, restored world, night, an
  underground chamber lit by a torch (`07-underground-torch.png`), and the inventory/crafting panel
  with 36 slots, 15 recipes and station-aware availability (`08-inventory.png`).

## Capability mapping

| Capability | Browser evidence |
| --- | --- |
| C1 offline boot | page loaded from `file://`, game ready, zero console errors |
| C2 first-run affordance | title overlay, primary start button, control cards, real-pointer start |
| C4 real-pointer mining | 10/10 trials with 350-364 ms holds and the click negative control |
| C5 placement | right-button placement with exact inventory delta |
| C6 inventory and hotbar | inventory panel with 36 slots and live counts; hotbar icons/counts in play captures |
| C7 crafting | recipe panel availability and two real-button crafts with exact deltas |
| C11 day/night | day and night captures from the same running session |
| C12 night threat | hollow spawns in darkness |
| C14 persistence | save/reload/continue with world, inventory and summary consistency |
| C15 orientation | HUD coordinate/depth readout and minimap present in captures |
| C16 art direction | eight captured states across day, night, underground and menus |
| C17 audio mechanism | mute/unmute path exists; audio quality is outside headless verification |
| C18 controls documentation | Controls menu reachable from the pause/title path; README reviewed separately |

## Gaps

- The beacon/victory end-to-end flow is covered by unit tests of the progression chain, not by a
  browser-driven playthrough; a full playthrough would take many minutes of real mining.
- Hollow contact damage and death/respawn are unit-tested; the browser run only proves spawning.
- Audio is muted in the headless run; audible quality is a human judgement, not automated.
- Touch/mobile input is not a target of this work order.

## Conclusion

The interaction-truth requirement is met with genuine dispatched pointer input at a 350-364 ms hold
across 10/10 stable world-changing trials, backed by a synthetic-click negative control. First-run,
crafting, night and persistence behave as accepted, with screenshots as visual evidence.
