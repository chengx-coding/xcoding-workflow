# Profile: compact 2D sandbox sample

This profile applies M2D-SES v1.1 to the sample task: a compact, offline 2D Minecraft-style sandbox
built from the seed. It defines what a player should experience, but it is not a feature-count
checklist and it does not require every Minecraft system.

## Integrity requirements (high defects if broken)

These are player-visible world/game invariants, not optional features:

- **Solid world floor.** The bottom of the world must be a sealed, unbreakable floor (bedrock or
  equivalent); the player must not be able to mine through it or leave the world.
- **Underground reads as underground.** Removing blocks underground must expose a cave/earth
  backdrop, not sky, blank canvas or a floating world.
- **Collision/placement safety.** The player cannot pass through solid blocks or place a block
  inside itself; rejected actions report why.
- **Persistence and boot.** The page boots offline, saves and restores world/player state, and
  survives a corrupt or unavailable save without a fatal error.

A broken requirement is a high defect (PES cap), not a lower domain score.

## Experience expectations

### Must

- Readable movement, jumping, collision, camera and mining/placing; controls visible in the page.
- Mining/placing feedback: target outline/ghost, break progress, particles/sound, and a visible
  character/tool or block-break animation that makes the action read.
- A world that is worth looking at: coherent palette, readable block textures, character silhouette,
  depth/lighting, and a composed first frame.
- Orientation: essential status (seed/position/time) and a minimap or equivalent spatial aid for a
  sandbox world.
- Day/night or equivalent atmosphere; audio/feedback with mute.
- A compact inventory/hotbar with a clear selected state; counts are expected when the game presents
  a survival-like economy, but a creative palette is acceptable if the experience is coherent.

### Should

- Multiple biomes with distinct surface/vegetation/atmosphere; ores/caves/underground features.
- Field notes/objectives or another lightweight direction layer.
- Save/status feedback; pause/help; new-world/seed control.
- Responsive 960/800/1280; reduced motion; keyboard/accessible labels; stable performance.
- Replay value through seed/new world and a small progression/economy loop.

### Optional / profile non-goals

The compact prompt does not require crafting trees, survival health/hunger, mobs/combat, redstone,
water/sand physics, weather or structures. Their absence is a **coverage/profile choice**, not a
high defect. If present, they are evaluated as experience depth, not as a reason to ignore the
integrity requirements.

## Journey focus

J4 is the decisive journey for this profile:

1. dig down through the surface;
2. remove blocks in an underground pocket and inspect the exposed background;
3. reach the bottom of the world;
4. try to mine the floor;
5. record whether the world is sealed and whether the background reads as underground.

If the hotbar/HUD covers the bottom row at the clamped camera position, move or zoom to an
unobstructed position; record the occlusion as a medium usability issue, not as a pass. A first-frame
screenshot is not evidence for J4. The evaluator must record the state before/after removing
underground blocks and at the bottom.

## Defect examples

| Observation | Classification |
| --- | --- |
| Bottom layer is ordinary stone and can be mined away | **High** — no world floor |
| Removed underground block reveals sky/blank canvas | **High** — underground void/background |
| Player can place a block inside itself or escape collision | **High** — core verb/world integrity |
| Mining removes a block but shows no readable progress/animation | **Medium** — interaction feedback |
| No minimap/spatial aid in a large sandbox world | **Medium** — orientation |
| Character/art is simpler than a richer reference, but readable | Domain score (D5), not a defect |
| One biome, no ores | Domain scores D3/D2, not a high defect by themselves |
| No crafting/survival/mobs/redstone | Optional/profile coverage, not a high defect |

## Engineering and code quality

ECS is a flexible 25% score, not a pile of gates. It evaluates test quality (assertions on real
invariants, edge/recovery cases), architecture/readability, persistence/robustness/security,
performance/accessibility/responsiveness and documentation/tooling. Test count is evidence, not a
score. Only G1–G3 are hard gates (boot/offline, no fatal errors, save/recovery); performance,
accessibility, responsive and tests are scored. A high player-visible defect still caps PES and the
composite, so strong engineering cannot erase a missing world floor.

## Journey driver

The evaluation should use a reproducible browser/input driver for the critical journeys, especially
J4 (dig down, remove underground blocks, inspect the background, reach the bottom, try the floor).
If no driver is available, record the evidence limit and do not award a pass for J4 based on a
first-frame screenshot. A high-defect finding should close with a machine-checkable invariant test,
not a test named after the requirement.

## Scoring note

A compliant compact sandbox can score well without crafting or survival, but it cannot score well
with a missing floor, a void underground, or unreadable mining feedback. This is the line v1.0 got
wrong and v1.1 is designed to enforce.
