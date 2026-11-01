---
schema_version: 1
document_kind: work-order-goal
content_language: "en"
work_order_id: "20261101-2045-open-sandbox-xc-2"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Goal — a small, playable, offline 2D Minecraft

## Requested outcome

Build a playable, offline 2D sandbox game inspired by Minecraft. The game must run by opening
`index.html` directly, with no build step, no external libraries, no CDNs and no network access. It
must feel like a small Minecraft, save the player's progress, and document its controls.

"Playable" is the centre of the request: a person who opens the page must be able to start playing
immediately, understand what to do, and keep playing for a meaningful session. "Small Minecraft"
means the recognisable block-world loop rather than a large feature catalogue.

## Intended capability scope

The delivered game is a compact but complete block-world sandbox in a 2D side view: a generated,
explorable world made of blocks; a controllable character who can move through it; the ability to
change the world by removing and adding blocks; a carried inventory and a usable hotbar; a coherent
progression or goal that gives play direction; persistent progress across reloads; and documented
controls.

The exact Minecraft-derived system set — including but not limited to crafting, survival pressure,
hostile or passive creatures, lighting, day/night time, tools, health, and redstone-like mechanisms —
is not fixed by this goal. Analysis must select a coherent small set, record what is in and what is
out, and justify each choice against the request and the Minecraft reference. No such system may be
treated as required or forbidden before that decision.

## Quality contract

The result is judged from a player's first-hand experience in a normal desktop browser, not only by
reading code:

1. **Immediate playability.** Opening `index.html` from the file system reaches a controllable world
   without console errors, a build step, or any network request. The first frame shows a legible
   world, the player, the hotbar, and an on-screen hint for at least movement, mining, building and
   help.
2. **Recognisable Minecraft loop.** The player can explore a varied generated world, break blocks,
   collect what they break, carry and select blocks, place them, and thereby build or dig something
   they chose. Removing blocks and placing them must feel deliberate (reach limits, break timing,
   selection feedback, block-specific behaviour), not like toggling an array.
3. **A small world with depth, not a flat strip.** Terrain must offer more than one horizontal layer
   and more than one kind of place to be: surface, underground, and enough material and structure
   variety that exploring in two directions discovers something. The world must remain readable at
   the viewport size.
4. **Progress that survives.** World edits, inventory and player position persist across a reload and
   are restored without manual file handling. Starting over is an explicit player action, and a
   missing or corrupt save must not brick the page.
5. **Feel.** The presentation should carry the Minecraft signature at this scale: blocky tiles,
   readable silhouettes, a day/night or light/dark rhythm where analysis selects it, responsive
   movement and interaction, and feedback for breaking, placing and selecting. It should look and
   sound like a deliberate game, not a debug canvas.
6. **Documentation and discoverability.** Controls are documented in `README.md` and discoverable
   inside the game itself. The README also states how to run and how to verify the project.
7. **Offline integrity.** No external library, font, image, audio file or network call at runtime.
   Everything is local plain HTML/CSS/JavaScript and works from `file://`.

### Reference and signature-experience challenge

The credible domain references are **Minecraft** (the requested inspiration) and, for the 2D
translation of movement, mining, placing and inventory, **Terraria** as a well-known 2D block
sandbox. The reference-informed challenge is: a player familiar with Minecraft should recognise the
loop, the block vocabulary and the interaction grammar (left/primary action breaks, secondary action
places, hotbar selection, world persistence) within the first minute, and should not be able to
exhaust the world's interest by walking one screen in either direction. The analysis records a small
signature-experience table and classifies each signature as must, should or non-goal with user value;
the goal does not turn that table into a feature-count target.

## Scope and constraints

- One self-contained browser game in this repository, opened directly from `index.html`; no build
  step, package manager, bundler, framework, external library, CDN, remote font, remote image, remote
  audio, or network request at runtime.
- Plain HTML, CSS and JavaScript in the existing seed layout; `file://` must be a supported origin.
- Progress is saved by the game itself, without a server or manual export.
- Controls are documented for the player.
- The work order does not create a project Git commit; the enclosing repository owns the sample
  commit.
- No product requirement is added beyond the prompt. System-level scope decisions (crafting,
  survival, mobs, redstone and similar) are made by analysis and recorded, not inherited.
- Verification uses the project bridge commands `node --test "tests/**/*.test.js"` and
  `python tools/page_check.py`, extended with tests and browser evidence appropriate to the built
  game; seed tests are not weakened.

### Provenance

| Item | Source |
| --- | --- |
| Playable offline 2D Minecraft-inspired sandbox, `index.html`, no build step, no external libraries/CDNs/network, feel like a small Minecraft, save progress, document controls | `user` — the product prompt, verbatim |
| English documents and code; UTF-8/LF; no project Git commit; seed verification commands; temporary files under the work order `tmp/` | `project` — `.xcoding/WORKFLOW.md` |
| Not adding product requirements; analysis decides and records Minecraft-system scope | `user` — the initiating XC instruction and the runner reference |
| Reference set (Minecraft; Terraria for the 2D translation) | `goal-authored` — used only to challenge signature depth, not to add scope |

No `goal-authored` exclusion is binding: analysis owns the system in/out decisions and must record
them with their user value.

## Acceptance conditions

1. `index.html` opens from `file://` in a normal desktop browser and reaches a playable state with no
   uncaught error and no network request.
2. A player can move, jump, break a block, collect it, select a carried block, place it, and observe
   the world change — all through normal input, demonstrated in a real browser.
3. The world is a generated block world with surface and underground content that is more than a flat
   strip, and the player can explore it.
4. The inventory/hotbar reflects collected and placed blocks and gives clear selection feedback.
5. Progress (world edits, inventory, player state as applicable) survives a page reload, and a
   corrupt or absent save recovers to a playable state.
6. `README.md` documents the controls, the run method and the verification commands; the game itself
   exposes help for the controls.
7. The project's verification commands pass: all seed tests and the added tests pass; the static
   page check passes; added browser evidence shows the interactive loop and persistence working.
8. No runtime network reference or external asset exists in the served files.
