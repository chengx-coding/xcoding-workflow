/* Tile-resolution light map: sky/depth darkness plus torches and furnaces. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./render.js"));
  } else {
    root.SandboxLighting = factory(root.SandboxConfig, root.SandboxRender);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RENDER) {
  "use strict";

  const B = CONFIG.blocks;
  const TILE = CONFIG.tileSize;
  const TORCH_RADIUS = 7.5;
  const FURNACE_RADIUS = 5.5;

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  // Pure helper used by the renderer and the tests.
  function lightLevel(depth, day, torchDistances) {
    const sky = depth <= 0 ? 1 : Math.max(0, 1 - depth / 8) * 0.18;
    let light = 0.08 + sky * (0.14 + 0.78 * clamp(day, 0, 1));
    if (torchDistances) {
      for (const entry of torchDistances) {
        const distance = entry.distance;
        const radius = entry.radius || TORCH_RADIUS;
        if (distance < radius) {
          const falloff = 1 - distance / radius;
          light += (entry.strength || 1.15) * falloff * falloff;
        }
      }
    }
    return clamp(light, 0, 1.15);
  }

  function lightSources(world, x0, x1, y0, y1, furnaces) {
    const sources = [];
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        const block = world.data[y * world.width + x];
        if (block === B.torch) {
          sources.push({ x: x + 0.5, y: y + 0.5, radius: TORCH_RADIUS, strength: 1.15, type: "torch" });
        }
      }
    }
    if (furnaces) {
      Object.keys(furnaces).forEach(function (key) {
        const state = furnaces[key];
        if (!state || state.burnTime <= 0) {
          return;
        }
        const parts = key.split(",");
        sources.push({
          x: Number(parts[0]) + 0.5,
          y: Number(parts[1]) + 0.5,
          radius: FURNACE_RADIUS,
          strength: 0.8,
          type: "furnace"
        });
      });
    }
    return sources;
  }

  function createLighting() {
    let canvas = null;
    let context = null;

    function ensure(width, height) {
      if (!canvas) {
        canvas = document.createElement("canvas");
        context = canvas.getContext("2d");
      }
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
    }

    function render(target, state, offsets) {
      const world = state.world;
      if (!world) {
        return;
      }
      const camera = state.camera;
      const time = state.time == null ? 0.3 : state.time;
      const day = 1 - RENDER.nightAmount(time);
      const firstColumn = Math.max(0, Math.floor(camera.x / TILE) - 1);
      const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + CONFIG.viewWidth) / TILE) + 1);
      const firstRow = Math.max(0, Math.floor(camera.y / TILE) - 1);
      const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + CONFIG.viewHeight) / TILE) + 1);
      const columns = lastColumn - firstColumn + 1;
      const rows = lastRow - firstRow + 1;
      if (columns <= 0 || rows <= 0) {
        return;
      }
      ensure(columns, rows);
      const sources = lightSources(
        world,
        Math.max(0, firstColumn - 8),
        Math.min(world.width - 1, lastColumn + 8),
        Math.max(0, firstRow - 8),
        Math.min(world.height - 1, lastRow + 8),
        state.furnaces
      );
      const image = context.createImageData(columns, rows);
      for (let row = 0; row < rows; row += 1) {
        const y = firstRow + row;
        for (let column = 0; column < columns; column += 1) {
          const x = firstColumn + column;
          const surface = world.surface[x] || 0;
          const depth = y - surface;
          const distances = [];
          for (const source of sources) {
            const dx = source.x - (x + 0.5);
            const dy = source.y - (y + 0.5);
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < source.radius) {
              distances.push({ distance: distance, radius: source.radius, strength: source.strength });
            }
          }
          const light = lightLevel(depth, day, distances);
          const index = (row * columns + column) * 4;
          image.data[index] = 5;
          image.data[index + 1] = 8;
          image.data[index + 2] = 16;
          image.data[index + 3] = Math.round((1 - Math.min(1, light)) * 0.82 * 255);
        }
      }
      context.putImageData(image, 0, 0);
      const offsetX = offsets.shakeX || 0;
      const offsetY = offsets.shakeY || 0;
      const screenX = firstColumn * TILE - camera.x - offsetX;
      const screenY = firstRow * TILE - camera.y - offsetY;
      target.save();
      target.imageSmoothingEnabled = true;
      target.drawImage(canvas, screenX, screenY, columns * TILE, rows * TILE);
      target.globalCompositeOperation = "lighter";
      for (const source of sources) {
        const sx = source.x * TILE - camera.x - offsetX;
        const sy = source.y * TILE - camera.y - offsetY;
        if (sx < -80 || sy < -80 || sx > CONFIG.viewWidth + 80 || sy > CONFIG.viewHeight + 80) {
          continue;
        }
        const radius = source.radius * TILE;
        const glow = target.createRadialGradient(sx, sy, 2, sx, sy, radius);
        const alpha = source.type === "torch" ? 0.16 : 0.1;
        glow.addColorStop(0, "rgba(255, 190, 92, " + alpha + ")");
        glow.addColorStop(0.45, "rgba(255, 150, 55, " + (alpha * 0.45) + ")");
        glow.addColorStop(1, "rgba(255, 120, 30, 0)");
        target.fillStyle = glow;
        target.fillRect(sx - radius, sy - radius, radius * 2, radius * 2);
      }
      target.restore();
    }

    return { render: render };
  }

  return {
    lightLevel: lightLevel,
    lightSources: lightSources,
    createLighting: createLighting,
    torchRadius: TORCH_RADIUS
  };
});
