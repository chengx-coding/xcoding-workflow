(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const BLOCK_COLORS = Object.freeze({
    1: "#57a05a",
    2: "#8d6e63",
    3: "#78909c",
    4: "#a1887f",
    5: "#66bb6a"
  });

  function drawSky(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 0, CONFIG.viewHeight);
    gradient.addColorStop(0, "#8fd3f4");
    gradient.addColorStop(1, "#d7f0fb");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
  }

  function renderFrame(ctx, state) {
    const world = state.world;
    const player = state.player;
    const camera = state.camera;
    const tile = CONFIG.tileSize;

    drawSky(ctx);

    const firstColumn = Math.max(0, Math.floor(camera.x / tile));
    const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + CONFIG.viewWidth) / tile));
    const firstRow = Math.max(0, Math.floor(camera.y / tile));
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + CONFIG.viewHeight) / tile));

    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const block = world.data[y * world.width + x];
        if (block === CONFIG.blocks.air) {
          continue;
        }
        ctx.fillStyle = BLOCK_COLORS[block] || "#9e9e9e";
        ctx.fillRect(
          Math.round(x * tile - camera.x),
          Math.round(y * tile - camera.y),
          tile,
          tile
        );
        ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
        ctx.strokeRect(
          Math.round(x * tile - camera.x) + 0.5,
          Math.round(y * tile - camera.y) + 0.5,
          tile - 1,
          tile - 1
        );
      }
    }

    const playerWidth = player.width * tile;
    const playerHeight = player.height * tile;
    ctx.fillStyle = "#263238";
    ctx.fillRect(
      Math.round(player.x * tile - camera.x - playerWidth / 2),
      Math.round(player.y * tile - camera.y - playerHeight),
      playerWidth,
      playerHeight
    );
    ctx.fillStyle = "#ffcc80";
    ctx.fillRect(
      Math.round(player.x * tile - camera.x - playerWidth / 2 + 4),
      Math.round(player.y * tile - camera.y - playerHeight + 4),
      playerWidth - 8,
      8
    );
  }

  return {
    renderFrame: renderFrame,
    BLOCK_COLORS: BLOCK_COLORS
  };
});
