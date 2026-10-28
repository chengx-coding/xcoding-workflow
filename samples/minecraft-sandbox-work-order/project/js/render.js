(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxRender");
  }

  const BLOCK_COLORS = Object.freeze({
    1: "#57a05a",
    2: "#8d6e63",
    3: "#78909c",
    4: "#a1887f",
    5: "#66bb6a"
  });

  function clamp(value, min, max) {
    if (max < min) {
      return min;
    }
    return Math.min(Math.max(value, min), max);
  }

  function cameraForPlayer(world, player) {
    const tile = CONFIG.tileSize;
    const worldPixelWidth = world.width * tile;
    const worldPixelHeight = world.height * tile;
    const maxX = Math.max(0, worldPixelWidth - CONFIG.viewWidth);
    const maxY = Math.max(0, worldPixelHeight - CONFIG.viewHeight);
    const playerCenterY = player.y - player.height / 2;
    return {
      x: clamp(player.x * tile - CONFIG.viewWidth / 2, 0, maxX),
      y: clamp(playerCenterY * tile - CONFIG.viewHeight / 2, 0, maxY)
    };
  }

  function tileHash(x, y) {
    let hash = Math.imul(x, 73856093) ^ Math.imul(y, 19349663);
    hash = Math.imul(hash ^ (hash >>> 13), 0x5bd1e995);
    return (hash ^ (hash >>> 15)) >>> 0;
  }

  function drawSky(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 0, CONFIG.viewHeight);
    gradient.addColorStop(0, "#78b9e6");
    gradient.addColorStop(0.55, "#b9e2f4");
    gradient.addColorStop(1, "#e7f7fb");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);

    ctx.fillStyle = "rgba(255, 244, 196, 0.9)";
    ctx.beginPath();
    ctx.arc(72, 66, 27, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawBlock(ctx, block, screenX, screenY, tile, x, y) {
    const color = BLOCK_COLORS[block] || "#9e9e9e";
    const hash = tileHash(x, y);
    ctx.fillStyle = color;
    ctx.fillRect(screenX, screenY, tile, tile);

    if (block === CONFIG.blocks.grass) {
      ctx.fillStyle = "#7dc47e";
      ctx.fillRect(screenX, screenY, tile, 5);
      ctx.fillStyle = "#3f7f45";
      for (let blade = 0; blade < 3; blade += 1) {
        const offset = 3 + ((hash >>> (blade * 5)) % Math.max(1, tile - 8));
        ctx.fillRect(screenX + offset, screenY + 3, 2, 4);
      }
    } else if (block === CONFIG.blocks.dirt) {
      ctx.fillStyle = "rgba(62, 39, 35, 0.28)";
      for (let speck = 0; speck < 3; speck += 1) {
        const offsetX = 3 + ((hash >>> (speck * 4)) % Math.max(1, tile - 8));
        const offsetY = 5 + ((hash >>> (speck * 7 + 2)) % Math.max(1, tile - 10));
        ctx.fillRect(screenX + offsetX, screenY + offsetY, 3, 3);
      }
    } else if (block === CONFIG.blocks.stone) {
      ctx.fillStyle = "rgba(236, 239, 241, 0.22)";
      ctx.fillRect(screenX + 3, screenY + 4, 7, 4);
      ctx.fillStyle = "rgba(38, 50, 56, 0.22)";
      ctx.fillRect(screenX + tile - 11, screenY + tile - 10, 8, 5);
    } else if (block === CONFIG.blocks.wood) {
      ctx.fillStyle = "rgba(62, 39, 35, 0.32)";
      ctx.fillRect(screenX + 4, screenY, 2, tile);
      ctx.fillRect(screenX + tile - 7, screenY, 2, tile);
    } else if (block === CONFIG.blocks.leaves) {
      ctx.fillStyle = "rgba(27, 94, 32, 0.35)";
      ctx.fillRect(screenX + 3, screenY + 3, 5, 5);
      ctx.fillStyle = "rgba(200, 230, 201, 0.35)";
      ctx.fillRect(screenX + tile - 10, screenY + tile - 10, 5, 5);
    }

    ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
    ctx.lineWidth = 1;
    ctx.strokeRect(screenX + 0.5, screenY + 0.5, tile - 1, tile - 1);
  }

  function drawTarget(ctx, camera, target, tile) {
    if (!target || !Number.isInteger(target.x) || !Number.isInteger(target.y)) {
      return;
    }
    const screenX = Math.round(target.x * tile - camera.x);
    const screenY = Math.round(target.y * tile - camera.y);
    ctx.save();
    ctx.strokeStyle = target.inReach ? "rgba(255, 255, 255, 0.95)" : "rgba(255, 255, 255, 0.35)";
    ctx.lineWidth = 2;
    ctx.strokeRect(screenX + 1.5, screenY + 1.5, tile - 3, tile - 3);
    ctx.restore();
  }

  function drawPlayer(ctx, camera, player, tile) {
    const centerX = Math.round(player.x * tile - camera.x);
    const feetY = Math.round(player.y * tile - camera.y);
    const width = Math.max(10, Math.round(player.width * tile));
    const height = Math.max(24, Math.round(player.height * tile));
    const left = centerX - Math.round(width / 2);
    const top = feetY - height;

    ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
    ctx.beginPath();
    ctx.ellipse(centerX, feetY + 1, width * 0.7, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#263238";
    ctx.fillRect(left + 2, top + height - 8, width - 4, 8);
    ctx.fillStyle = "#3949ab";
    ctx.fillRect(left, top + 9, width, height - 17);
    ctx.fillStyle = "#ffcc80";
    ctx.fillRect(left + 2, top, width - 4, 10);
    ctx.fillStyle = "#263238";
    ctx.fillRect(left + 3, top + 3, 3, 3);
    ctx.fillRect(left + width - 6, top + 3, 3, 3);
    ctx.fillStyle = "#ef5350";
    ctx.fillRect(left + Math.round(width / 2) - 1, top + 11, 3, height - 24);
  }

  function renderFrame(ctx, state) {
    const world = state.world;
    const player = state.player;
    const camera = state.camera || { x: 0, y: 0 };
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
        drawBlock(
          ctx,
          block,
          Math.round(x * tile - camera.x),
          Math.round(y * tile - camera.y),
          tile,
          x,
          y
        );
      }
    }

    drawTarget(ctx, camera, state.target, tile);
    drawPlayer(ctx, camera, player, tile);
  }

  return {
    renderFrame: renderFrame,
    cameraForPlayer: cameraForPlayer,
    BLOCK_COLORS: BLOCK_COLORS
  };
});
