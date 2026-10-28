# Build a 2D Minecraft-style sandbox

Create a playable, offline 2D sandbox game inspired by Minecraft. The whole game must live in a
single self-contained `index.html` file (inline CSS and JavaScript, or local files next to it), open
by double-clicking the file, with no build step and no network access.

Requirements:

- Procedurally generated terrain from a numeric seed, with at least grass, dirt and stone blocks.
- A player with gravity, left/right movement and jumping. The player collides with solid blocks and
  cannot pass through them.
- Left-click mines a block within reach. Right-click places the selected block in an empty adjacent
  cell. Blocks cannot be placed inside the player.
- A hotbar with at least four block types, number-key selection and a clearly visible selected state.
- A camera that follows the player and stays inside the world bounds.
- World and player state saved to `localStorage` and restored when the page is reopened.
- Clean, readable code and a short note describing the controls.

Deliver the finished page as `index.html` in the current working directory. Do not use external
libraries, CDNs, web fonts or network requests of any kind.
