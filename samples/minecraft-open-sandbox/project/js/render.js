(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"), require("./rng.js"), require("./time.js"), require("./world.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxBlocks, root.SandboxRng, root.SandboxTime, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS, RNG, TIME, WORLD) {
  "use strict";

  if (!CONFIG || !BLOCKS || !RNG || !TIME) {
    throw new Error("SandboxConfig, SandboxBlocks, SandboxRng and SandboxTime are required before SandboxRender");
  }

  const TEXTURE_SIZE = 32;
  const VARIANTS = 3;

  function hexToRgb(hex) {
    const value = hex.replace("#", "");
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16)
    };
  }

  function rgba(hex, alpha) {
    const color = hexToRgb(hex);
    return "rgba(" + color.r + ", " + color.g + ", " + color.b + ", " + alpha + ")";
  }

  function shade(hex, amount) {
    const color = hexToRgb(hex);
    const clamp = function (value) {
      return Math.max(0, Math.min(255, Math.round(value)));
    };
    return "rgb(" + clamp(color.r + amount) + ", " + clamp(color.g + amount) + ", " + clamp(color.b + amount) + ")";
  }

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  const textureCache = Object.create(null);
  const iconCache = Object.create(null);

  function textureFor(id, variant) {
    const key = id + ":" + variant;
    if (textureCache[key]) {
      return textureCache[key];
    }
    const canvas = makeCanvas(TEXTURE_SIZE, TEXTURE_SIZE);
    const ctx = canvas.getContext("2d");
    const definition = BLOCKS.block(id) || BLOCKS.block(0);
    const colors = definition.colors;
    const rng = RNG.createRng((id + 1) * 7919 + variant * 104729 + 17);
    const size = TEXTURE_SIZE;
    const px = function (x, y, w, h, color) {
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h)));
    };

    if (id === CONFIG.blocks.air) {
      return canvas;
    }

    ctx.fillStyle = colors.base;
    ctx.fillRect(0, 0, size, size);

    if (id === CONFIG.blocks.grass) {
      px(0, 0, size, size * 0.32, colors.accent);
      for (let index = 0; index < 14; index += 1) {
        const x = rng() * size;
        const y = rng() * size * 0.34;
        px(x, y, 2, 4 + rng() * 5, colors.detail);
      }
      for (let index = 0; index < 10; index += 1) {
        px(rng() * size, size * 0.38 + rng() * size * 0.58, 2 + rng() * 3, 2, colors.detail);
      }
    } else if (id === CONFIG.blocks.dirt) {
      for (let index = 0; index < 16; index += 1) {
        px(rng() * size, rng() * size, 2 + rng() * 4, 2, index % 2 ? colors.accent : colors.detail);
      }
    } else if (id === CONFIG.blocks.stone) {
      for (let index = 0; index < 7; index += 1) {
        px(rng() * size, rng() * size, 5 + rng() * 8, 3 + rng() * 4, colors.accent);
      }
      for (let index = 0; index < 6; index += 1) {
        px(rng() * size, rng() * size, 3 + rng() * 5, 2 + rng() * 3, colors.detail);
      }
    } else if (id === CONFIG.blocks.cobblestone) {
      for (let index = 0; index < 6; index += 1) {
        const x = rng() * (size - 10);
        const y = rng() * (size - 8);
        px(x, y, 8 + rng() * 6, 5 + rng() * 4, colors.accent);
        px(x + 1, y + 1, 6, 2, shade(colors.accent, -14));
      }
      for (let index = 0; index < 5; index += 1) {
        px(rng() * size, rng() * size, 3, 3, colors.detail);
      }
    } else if (id === CONFIG.blocks.wood) {
      px(0, 0, 4, size, colors.detail);
      px(size - 4, 0, 4, size, colors.detail);
      for (let index = 0; index < 4; index += 1) {
        px(5 + index * 6, 0, 2, size, index % 2 ? colors.accent : colors.base);
      }
      px(9, 7, 5, 3, colors.detail);
      px(18, 22, 6, 3, colors.detail);
    } else if (id === CONFIG.blocks.leaves) {
      for (let index = 0; index < 22; index += 1) {
        px(rng() * size, rng() * size, 3 + rng() * 4, 3 + rng() * 4, index % 3 ? colors.accent : colors.detail);
      }
      px(2, 2, size - 4, 2, shade(colors.base, 18));
    } else if (id === CONFIG.blocks.planks) {
      for (let index = 0; index < 4; index += 1) {
        px(0, index * 8, size, 1, colors.detail);
      }
      px(0, 3, size, 2, colors.accent);
      px(0, 19, size, 2, colors.accent);
      px(6, 10, 2, 12, colors.detail);
      px(22, 26, 2, 6, colors.detail);
    } else if (id === CONFIG.blocks.coalOre) {
      for (let index = 0; index < 6; index += 1) {
        px(rng() * size, rng() * size, 4 + rng() * 5, 4 + rng() * 5, colors.detail);
      }
      for (let index = 0; index < 4; index += 1) {
        px(rng() * size, rng() * size, 4, 4, colors.accent);
      }
    } else if (id === CONFIG.blocks.ironOre) {
      for (let index = 0; index < 5; index += 1) {
        px(rng() * size, rng() * size, 4 + rng() * 4, 4 + rng() * 4, colors.accent);
      }
      for (let index = 0; index < 4; index += 1) {
        px(rng() * size, rng() * size, 3, 3, colors.detail);
      }
    } else if (id === CONFIG.blocks.sand) {
      for (let index = 0; index < 18; index += 1) {
        px(rng() * size, rng() * size, 2, 2, index % 2 ? colors.accent : colors.detail);
      }
    } else if (id === CONFIG.blocks.sandstone) {
      px(0, 0, size, 6, colors.accent);
      px(0, 10, size, 2, colors.detail);
      px(0, 24, size, 2, colors.detail);
      for (let index = 0; index < 8; index += 1) {
        px(rng() * size, 12 + rng() * 10, 4, 2, colors.accent);
      }
    } else if (id === CONFIG.blocks.glass) {
      ctx.clearRect(0, 0, size, size);
      ctx.fillStyle = "rgba(191, 232, 242, 0.22)";
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = "rgba(226, 247, 251, 0.7)";
      ctx.lineWidth = 2;
      ctx.strokeRect(1, 1, size - 2, size - 2);
      ctx.beginPath();
      ctx.moveTo(6, 26);
      ctx.lineTo(26, 6);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
      ctx.lineWidth = 2;
      ctx.stroke();
    } else if (id === CONFIG.blocks.bedrock) {
      for (let index = 0; index < 10; index += 1) {
        px(rng() * size, rng() * size, 4 + rng() * 8, 3 + rng() * 6, index % 2 ? colors.accent : colors.detail);
      }
    } else if (id === CONFIG.blocks.torch) {
      ctx.clearRect(0, 0, size, size);
      px(size / 2 - 2, 12, 4, 20, colors.base);
      px(size / 2 - 3, 8, 6, 6, colors.detail);
      px(size / 2 - 2, 6, 4, 4, "#fff3b0");
    } else if (id === CONFIG.blocks.flower) {
      ctx.clearRect(0, 0, size, size);
      px(size / 2 - 1, 16, 2, 16, colors.base);
      px(size / 2 - 5, 10, 4, 4, colors.accent);
      px(size / 2 + 1, 10, 4, 4, colors.accent);
      px(size / 2 - 2, 7, 4, 4, colors.accent);
      px(size / 2 - 2, 12, 4, 4, colors.detail);
    } else {
      for (let index = 0; index < 12; index += 1) {
        px(rng() * size, rng() * size, 3, 3, index % 2 ? colors.accent : colors.detail);
      }
    }

    // A soft top highlight keeps tiles readable without outlines everywhere.
    if (definition.solid) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.05)";
      ctx.fillRect(0, 0, size, 1);
    }
    textureCache[key] = canvas;
    return canvas;
  }

  const caveCache = Object.create(null);

  function caveTexture(variant) {
    const key = "cave" + variant;
    if (caveCache[key]) {
      return caveCache[key];
    }
    const canvas = makeCanvas(TEXTURE_SIZE, TEXTURE_SIZE);
    const ctx = canvas.getContext("2d");
    const size = TEXTURE_SIZE;
    const rng = RNG.createRng(4099 + variant * 977);
    ctx.fillStyle = "#3a3128";
    ctx.fillRect(0, 0, size, size);
    for (let index = 0; index < 9; index += 1) {
      ctx.fillStyle = index % 2 ? "#2e261e" : "#463b2e";
      ctx.fillRect(rng() * size, rng() * size, 2 + rng() * 5, 2 + rng() * 3);
    }
    ctx.fillStyle = "rgba(0, 0, 0, 0.28)";
    ctx.fillRect(0, 0, size, 2);
    caveCache[key] = canvas;
    return canvas;
  }

  function paintItemIcon(canvas, itemId, options) {
    const settings = options || {};
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.imageSmoothingEnabled = false;

    if (itemId === 0 || itemId === undefined) {
      const size = 8;
      for (let y = 0; y < height; y += size) {
        for (let x = 0; x < width; x += size) {
          ctx.fillStyle = (x / size + y / size) % 2 === 0 ? "#18232f" : "#131c26";
          ctx.fillRect(x, y, size, size);
        }
      }
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(width * 0.24, height * 0.24);
      ctx.lineTo(width * 0.76, height * 0.76);
      ctx.stroke();
      return;
    }

    const definition = BLOCKS.item(itemId);
    if (!definition) {
      return;
    }

    if (definition.kind === "block") {
      const source = textureFor(itemId, 0);
      const inset = Math.round(width * 0.1);
      ctx.drawImage(source, inset, inset, width - inset * 2, height - inset * 2);
      ctx.strokeStyle = "rgba(0,0,0,0.28)";
      ctx.lineWidth = 2;
      ctx.strokeRect(inset, inset, width - inset * 2, height - inset * 2);
      return;
    }

    // Materials and tools are simple pixel glyphs drawn from the item colour.
    const color = definition.color || "#c9d4e0";
    ctx.fillStyle = color;
    if (definition.key === "stick") {
      ctx.save();
      ctx.translate(width / 2, height / 2);
      ctx.rotate(-0.6);
      ctx.fillRect(-4, -height * 0.34, 8, height * 0.68);
      ctx.restore();
    } else if (definition.key === "coal") {
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, width * 0.26, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#5b5b5b";
      ctx.fillRect(width * 0.4, height * 0.42, 8, 6);
    } else if (definition.key === "iron") {
      ctx.fillRect(width * 0.24, height * 0.38, width * 0.52, height * 0.26);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(width * 0.34, height * 0.44, width * 0.2, 4);
    } else if (definition.kind === "tool") {
      ctx.save();
      ctx.translate(width / 2, height / 2);
      ctx.rotate(-0.5);
      ctx.fillStyle = "#7a5230";
      ctx.fillRect(-3, -4, 6, height * 0.42);
      ctx.fillStyle = color;
      if (definition.tool === "pickaxe") {
        ctx.fillRect(-width * 0.3, -height * 0.3, width * 0.6, 6);
        ctx.fillRect(-width * 0.34, -height * 0.3, 6, 10);
        ctx.fillRect(width * 0.3, -height * 0.3, 6, 10);
      } else if (definition.tool === "axe") {
        ctx.fillRect(-width * 0.16, -height * 0.32, width * 0.32, height * 0.22);
        ctx.fillRect(-width * 0.02, -height * 0.32, 5, height * 0.22);
      } else {
        ctx.fillRect(-width * 0.16, -height * 0.3, width * 0.32, height * 0.16);
      }
      ctx.restore();
    } else {
      ctx.fillRect(width * 0.3, height * 0.3, width * 0.4, height * 0.4);
    }
  }

  function skylineAt(x, seed, base, amplitude, frequency) {
    const noise = RNG.unitFromHash(RNG.hashInts(seed, Math.floor(x * frequency), 0));
    const noise2 = RNG.unitFromHash(RNG.hashInts(seed + 17, Math.floor(x * frequency * 2.7), 0));
    return base - (noise * 0.7 + noise2 * 0.3) * amplitude;
  }

  function drawSky(ctx, view) {
    const sky = view.sky || TIME.sky(view.clock ? view.clock.t : 0.3);
    const gradient = ctx.createLinearGradient(0, 0, 0, view.height);
    gradient.addColorStop(0, sky.top);
    gradient.addColorStop(1, sky.bottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, view.width, view.height);

    const night = 1 - (sky.daylight || 1);
    if (night > 0.05) {
      ctx.save();
      ctx.globalAlpha = Math.min(1, night * 1.1);
      for (let index = 0; index < 70; index += 1) {
        const x = RNG.unitFromHash(RNG.hashInts(991, index, 3)) * view.width;
        const y = RNG.unitFromHash(RNG.hashInts(992, index, 7)) * view.height * 0.7;
        const size = 1 + (index % 3) * 0.6;
        ctx.fillStyle = index % 5 === 0 ? "#ffe9b8" : "#dce6ff";
        ctx.fillRect(x, y, size, size);
      }
      ctx.restore();
    }

    // Slow parallax clouds.
    const drift = (view.clock ? view.clock.t : 0) * 46 + (view.camera.x * 0.04);
    for (let index = 0; index < 5; index += 1) {
      const cloudWidth = 90 + index * 26;
      const x = ((index * 317 + drift) % (view.width + 240)) - 180;
      const y = 44 + (index % 3) * 34;
      ctx.fillStyle = "rgba(255, 255, 255, " + (0.16 - night * 0.1) + ")";
      ctx.beginPath();
      ctx.ellipse(x, y, cloudWidth / 2, 15, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(x + cloudWidth * 0.3, y + 4, cloudWidth / 3, 12, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    const sun = TIME.sunPosition(view.clock ? view.clock.t : 0.3);
    const bodyY = view.height * 0.62;
    if (sun.sun.visible) {
      const x = 40 + sun.sun.x * (view.width - 80);
      const y = bodyY * sun.sun.y + 30;
      const glow = ctx.createRadialGradient(x, y, 4, x, y, 90);
      glow.addColorStop(0, "rgba(255, 236, 168, 0.55)");
      glow.addColorStop(1, "rgba(255, 236, 168, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - 100, y - 100, 200, 200);
      ctx.fillStyle = "#fff2bd";
      ctx.beginPath();
      ctx.arc(x, y, 18, 0, Math.PI * 2);
      ctx.fill();
    }
    if (sun.moon.visible) {
      const x = 40 + sun.moon.x * (view.width - 80);
      const y = bodyY * sun.moon.y + 30;
      ctx.fillStyle = "#e8edf7";
      ctx.beginPath();
      ctx.arc(x, y, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = sky.top;
      ctx.beginPath();
      ctx.arc(x + 6, y - 4, 12, 0, Math.PI * 2);
      ctx.fill();
    }

  }

  function drawParallax(ctx, view) {
    const camera = view.camera;
    const layers = [
      { seed: 31, base: 0.62, amplitude: 88, frequency: 0.0016, factor: 0.12, color: "rgba(52, 78, 96, 0.45)" },
      { seed: 57, base: 0.72, amplitude: 70, frequency: 0.0022, factor: 0.24, color: "rgba(38, 58, 72, 0.55)" },
      { seed: 73, base: 0.82, amplitude: 52, frequency: 0.0031, factor: 0.4, color: "rgba(26, 42, 54, 0.65)" }
    ];
    layers.forEach(function (layer) {
      ctx.fillStyle = layer.color;
      ctx.beginPath();
      ctx.moveTo(0, view.height);
      for (let x = 0; x <= view.width + 40; x += 40) {
        const worldX = x + camera.x * layer.factor;
        const y = skylineAt(worldX, layer.seed, view.height * layer.base, layer.amplitude, layer.frequency);
        ctx.lineTo(x, y);
      }
      ctx.lineTo(view.width, view.height);
      ctx.closePath();
      ctx.fill();
    });
  }

  function drawTile(ctx, view, x, y, screenX, screenY) {
    const id = view.world.data[y * view.world.width + x];
    if (id === CONFIG.blocks.air) {
      const surface = view.world.surface;
      if (surface && surface[x] !== undefined && y > surface[x]) {
        const variant = RNG.hashInts(x, y, 31) % 3;
        ctx.drawImage(caveTexture(variant), screenX, screenY, Math.ceil(view.tile), Math.ceil(view.tile));
      }
      return;
    }
    const size = view.tile;
    const variant = RNG.hashInts(x, y, 13) % VARIANTS;
    const definition = BLOCKS.block(id);
    if (!definition) {
      return;
    }
    if (definition.transparent) {
      ctx.globalAlpha = 0.9;
    }
    ctx.drawImage(textureFor(id, variant), screenX, screenY, Math.ceil(size), Math.ceil(size));
    ctx.globalAlpha = 1;

    // Neighbour seams: a subtle inner edge only where the tile meets air.
    const above = y > 0 ? view.world.data[(y - 1) * view.world.width + x] : 0;
    if (above === CONFIG.blocks.air && definition.solid) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.12)";
      ctx.fillRect(screenX, screenY, size, Math.max(1, size * 0.05));
    }
  }

  function drawUnderground(ctx, view) {
    const tile = view.tile;
    const camera = view.camera;
    const world = view.world;
    const firstX = Math.max(0, Math.floor(camera.x / tile));
    const lastX = Math.min(world.width - 1, Math.ceil((camera.x + view.width) / tile));
    ctx.fillStyle = "#211b16";
    for (let x = firstX; x <= lastX; x += 1) {
      const top = world.surface && world.surface[x] !== undefined
        ? world.surface[x]
        : (WORLD.terrainHeightAt ? WORLD.terrainHeightAt(world, x) : world.height);
      const screenTop = top * tile - camera.y;
      if (screenTop < view.height) {
        const start = Math.max(0, screenTop);
        ctx.fillRect(Math.floor(x * tile - camera.x), Math.floor(start), Math.ceil(tile) + 1, Math.ceil(view.height - start + 2));
      }
    }
  }

  function drawTiles(ctx, view) {
    const world = view.world;
    const tile = view.tile;
    const camera = view.camera;
    const firstX = Math.max(0, Math.floor(camera.x / tile));
    const lastX = Math.min(world.width - 1, Math.ceil((camera.x + view.width) / tile));
    const firstY = Math.max(0, Math.floor(camera.y / tile));
    const lastY = Math.min(world.height - 1, Math.ceil((camera.y + view.height) / tile));
    ctx.imageSmoothingEnabled = false;
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        const screenX = Math.round(x * tile - camera.x);
        const screenY = Math.round(y * tile - camera.y);
        drawTile(ctx, view, x, y, screenX, screenY);
      }
    }
  }

  function drawLighting(ctx, view) {
    const light = view.light;
    if (!light) {
      return;
    }
    const tile = view.tile;
    const camera = view.camera;
    const day = view.daylight === undefined ? 1 : view.daylight;
    const world = view.world;
    const firstX = Math.max(0, Math.floor(camera.x / tile));
    const lastX = Math.min(world.width - 1, Math.ceil((camera.x + view.width) / tile));
    const firstY = Math.max(0, Math.floor(camera.y / tile));
    const lastY = Math.min(world.height - 1, Math.ceil((camera.y + view.height) / tile));
    const width = world.width;
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        const solidTile = world.data[y * width + x] !== CONFIG.blocks.air;
        const surface = world.surface;
        const belowSurface = surface && surface[x] !== undefined && y > surface[x];
        if (!solidTile && !belowSurface) {
          continue;
        }
        const index = y * width + x;
        const level = Math.max(light.sky[index] * day, light.block[index]);
        const darkness = 1 - level / 15;
        if (darkness <= 0.04) {
          continue;
        }
        ctx.fillStyle = "rgba(4, 7, 14, " + (darkness * 0.64).toFixed(3) + ")";
        ctx.fillRect(Math.floor(x * tile - camera.x), Math.floor(y * tile - camera.y), Math.ceil(tile), Math.ceil(tile));
      }
    }
  }

  function drawTorchGlow(ctx, view) {
    const tile = view.tile;
    const camera = view.camera;
    const world = view.world;
    const firstX = Math.max(0, Math.floor(camera.x / tile) - 2);
    const lastX = Math.min(world.width - 1, Math.ceil((camera.x + view.width) / tile) + 2);
    const firstY = Math.max(0, Math.floor(camera.y / tile) - 2);
    const lastY = Math.min(world.height - 1, Math.ceil((camera.y + view.height) / tile) + 2);
    const night = 1 - (view.daylight === undefined ? 1 : view.daylight);
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        if (world.data[y * world.width + x] !== CONFIG.blocks.torch) {
          continue;
        }
        const cx = (x + 0.5) * tile - camera.x;
        const cy = (y + 0.5) * tile - camera.y;
        const radius = tile * 3.4;
        const glow = ctx.createRadialGradient(cx, cy, tile * 0.2, cx, cy, radius);
        glow.addColorStop(0, "rgba(255, 190, 105, " + (0.2 + night * 0.22).toFixed(3) + ")");
        glow.addColorStop(0.5, "rgba(255, 160, 70, " + (0.08 + night * 0.1).toFixed(3) + ")");
        glow.addColorStop(1, "rgba(255, 140, 40, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
      }
    }
  }

  function drawBackdropVeil(ctx, view) {
    if (view.mode !== "backdrop") {
      return;
    }
    ctx.fillStyle = "rgba(8, 14, 26, 0.2)";
    ctx.fillRect(0, 0, view.width, view.height);
  }

  function drawGhosts(ctx, view) {
    if (view.mode !== "backdrop") {
      return;
    }
    const tile = view.tile;
    const camera = view.camera;
    const edits = view.edits || [];
    ctx.save();
    for (let index = edits.length - 1; index >= 0 && index >= edits.length - 46; index -= 1) {
      const edit = edits[index];
      const screenX = Math.round(edit.x * tile - camera.x);
      const screenY = Math.round(edit.y * tile - camera.y);
      if (screenX < -tile || screenY < -tile || screenX > view.width || screenY > view.height) {
        continue;
      }
      if (edit.before && edit.before !== CONFIG.blocks.air) {
        ctx.globalAlpha = 0.55;
        ctx.drawImage(textureFor(edit.before, 0), screenX, screenY, Math.ceil(tile), Math.ceil(tile));
        ctx.globalAlpha = 1;
        ctx.strokeStyle = "rgba(240, 179, 92, 0.9)";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(screenX + 1, screenY + 1, tile - 2, tile - 2);
        ctx.setLineDash([]);
      } else {
        ctx.strokeStyle = "rgba(111, 209, 138, 0.85)";
        ctx.lineWidth = 2;
        ctx.setLineDash([3, 4]);
        ctx.strokeRect(screenX + 2, screenY + 2, tile - 4, tile - 4);
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(111, 209, 138, 0.12)";
        ctx.fillRect(screenX, screenY, tile, tile);
      }
    }
    ctx.restore();
  }

  function drawHover(ctx, view) {
    const hover = view.hover;
    const tile = view.tile;
    const camera = view.camera;
    if (!hover || !hover.visible) {
      return;
    }
    const screenX = Math.round(hover.x * tile - camera.x);
    const screenY = Math.round(hover.y * tile - camera.y);
    ctx.save();
    if (hover.mode === "place" && hover.block) {
      ctx.globalAlpha = 0.55;
      ctx.drawImage(textureFor(hover.block, 0), screenX, screenY, Math.ceil(tile), Math.ceil(tile));
      ctx.globalAlpha = 1;
      ctx.strokeStyle = hover.valid ? "rgba(111, 209, 138, 0.95)" : "rgba(226, 113, 106, 0.95)";
      ctx.lineWidth = 2;
      ctx.strokeRect(screenX + 1, screenY + 1, tile - 2, tile - 2);
    } else {
      ctx.strokeStyle = hover.valid ? "rgba(255, 255, 255, 0.85)" : "rgba(226, 113, 106, 0.9)";
      ctx.lineWidth = 2;
      ctx.strokeRect(screenX + 1, screenY + 1, tile - 2, tile - 2);
      ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
      ctx.fillRect(screenX, screenY, tile, tile);
    }
    ctx.restore();
  }

  function drawMining(ctx, view) {
    const mining = view.mining;
    if (!mining || mining.progress <= 0) {
      return;
    }
    const tile = view.tile;
    const screenX = mining.x * tile - view.camera.x;
    const screenY = mining.y * tile - view.camera.y;
    const progress = Math.min(1, mining.progress);
    ctx.save();
    ctx.strokeStyle = "rgba(10, 10, 12, " + (0.35 + progress * 0.5).toFixed(2) + ")";
    ctx.lineWidth = Math.max(1.5, tile * 0.055);
    const lines = 5;
    for (let index = 0; index < lines; index += 1) {
      if (index / lines > progress) {
        break;
      }
      const rng = RNG.createRng(RNG.hashInts(mining.x, mining.y, index));
      ctx.beginPath();
      ctx.moveTo(screenX + rng() * tile, screenY + rng() * tile);
      ctx.lineTo(screenX + rng() * tile, screenY + rng() * tile);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(240, 179, 92, 0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(screenX + tile / 2, screenY + tile / 2, Math.max(4, tile - 10), -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function drawPlayer(ctx, view) {
    const player = view.player;
    const tile = view.tile;
    const camera = view.camera;
    const width = player.width * tile;
    const height = player.height * tile;
    const centerX = player.x * tile - camera.x;
    const feetY = player.y * tile - camera.y;
    const swing = player.walkPhase || 0;
    const moving = Math.abs(player.vx) > 0.2 && player.onGround;
    const legOffset = moving ? Math.sin(swing) * tile * 0.18 : 0;
    const armOffset = Math.sin(swing + Math.PI) * tile * 0.12;
    const facing = player.facing === -1 ? -1 : 1;

    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.28)";
    ctx.beginPath();
    ctx.ellipse(centerX, feetY, width * 0.62, tile * 0.12, 0, 0, Math.PI * 2);
    ctx.fill();

    const bodyTop = feetY - height;
    const headSize = tile * 0.52;
    const bodyWidth = width * 0.82;
    const bodyHeight = height * 0.46;
    const bodyY = bodyTop + headSize;
    const legHeight = feetY - (bodyY + bodyHeight);

    // Legs
    ctx.fillStyle = "#3b4a63";
    ctx.fillRect(centerX - bodyWidth * 0.38, bodyY + bodyHeight, bodyWidth * 0.32, legHeight + legOffset * 0.4);
    ctx.fillStyle = "#2f3b50";
    ctx.fillRect(centerX + bodyWidth * 0.06, bodyY + bodyHeight, bodyWidth * 0.32, legHeight - legOffset * 0.4);

    // Torso
    ctx.fillStyle = "#4f7f9c";
    ctx.fillRect(centerX - bodyWidth / 2, bodyY, bodyWidth, bodyHeight);
    ctx.fillStyle = "#6ea3bd";
    ctx.fillRect(centerX - bodyWidth / 2, bodyY, bodyWidth, Math.max(2, bodyHeight * 0.16));

    // Arm
    ctx.fillStyle = "#3f6a84";
    const armX = centerX + facing * (bodyWidth * 0.42);
    ctx.fillRect(armX, bodyY + bodyHeight * 0.08 + armOffset, bodyWidth * 0.26, bodyHeight * 0.72);

    // Head
    const headX = centerX - headSize / 2 + facing * tile * 0.04;
    ctx.fillStyle = "#e8b98c";
    ctx.fillRect(headX, bodyTop, headSize, headSize);
    ctx.fillStyle = "#2a2118";
    ctx.fillRect(headX, bodyTop, headSize, headSize * 0.28);
    ctx.fillStyle = "#1c2630";
    ctx.fillRect(headX + (facing === 1 ? headSize * 0.56 : headSize * 0.18), bodyTop + headSize * 0.46, headSize * 0.16, headSize * 0.14);
    ctx.fillRect(headX + (facing === 1 ? headSize * 0.26 : headSize * 0.52), bodyTop + headSize * 0.46, headSize * 0.16, headSize * 0.14);
    ctx.restore();
  }

  function drawParticles(ctx, view) {
    const particles = view.particles || [];
    const tile = view.tile;
    const camera = view.camera;
    ctx.save();
    for (let index = 0; index < particles.length; index += 1) {
      const particle = particles[index];
      const alpha = Math.max(0, particle.life / particle.maxLife);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = particle.color;
      const size = Math.max(2, particle.size * tile / 32);
      ctx.fillRect(particle.x * tile - camera.x, particle.y * tile - camera.y, size, size);
    }
    ctx.restore();
  }

  function drawVignette(ctx, view) {
    const gradient = ctx.createRadialGradient(
      view.width / 2, view.height / 2, Math.min(view.width, view.height) * 0.3,
      view.width / 2, view.height / 2, Math.max(view.width, view.height) * 0.72
    );
    gradient.addColorStop(0, "rgba(0, 0, 0, 0)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0.2)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, view.width, view.height);
  }

  function render(ctx, view) {
    ctx.save();
    drawSky(ctx, view);
    drawParallax(ctx, view);
    drawUnderground(ctx, view);
    drawTiles(ctx, view);
    drawLighting(ctx, view);
    drawTorchGlow(ctx, view);
    drawBackdropVeil(ctx, view);
    drawGhosts(ctx, view);
    drawMining(ctx, view);
    drawHover(ctx, view);
    drawPlayer(ctx, view);
    drawParticles(ctx, view);
    drawVignette(ctx, view);
    ctx.restore();
  }

  function renderMinimap(canvas, view) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const world = view.world;
    const scaleX = width / world.width;
    const scaleY = height / world.height;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, width, height);
    const sky = view.sky || TIME.sky(view.clock ? view.clock.t : 0.3);
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, sky.top);
    gradient.addColorStop(1, sky.bottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    for (let x = 0; x < world.width; x += 1) {
      let top = 0;
      for (let y = 0; y < world.height; y += 1) {
        if (BLOCKS.isSolid(world.data[y * world.width + x])) {
          top = y;
          break;
        }
      }
      const surfaceId = world.data[top * world.width + x];
      ctx.fillStyle = BLOCKS.colorOf(surfaceId);
      ctx.fillRect(Math.floor(x * scaleX), Math.floor(top * scaleY), Math.ceil(scaleX) + 0.5, Math.max(1, height - top * scaleY));
      ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
      ctx.fillRect(Math.floor(x * scaleX), Math.floor((top + 6) * scaleY), Math.ceil(scaleX) + 0.5, Math.max(0, height - (top + 6) * scaleY));
    }

    const tile = view.tile;
    const camera = view.camera;
    const viewportX = (camera.x / tile) * scaleX;
    const viewportY = (camera.y / tile) * scaleY;
    const viewportW = (view.width / tile) * scaleX;
    const viewportH = (view.height / tile) * scaleY;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
    ctx.lineWidth = 1.6;
    ctx.strokeRect(viewportX, viewportY, viewportW, viewportH);
    ctx.fillStyle = "rgba(255, 255, 255, 0.1)";
    ctx.fillRect(viewportX, viewportY, viewportW, viewportH);

    if (view.minimapPrevious) {
      const previous = view.minimapPrevious;
      const age = (Date.now() - previous.at) / 1000;
      if (age < 5) {
        ctx.globalAlpha = Math.max(0.15, 1 - age / 5);
        ctx.strokeStyle = "rgba(240, 179, 92, 0.95)";
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1.4;
        ctx.strokeRect(previous.x * scaleX, previous.y * scaleY, previous.w * scaleX, previous.h * scaleY);
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }
    }

    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc((view.player.x) * scaleX, (view.player.y) * scaleY, 2.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.6)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  return {
    render: render,
    renderMinimap: renderMinimap,
    paintItemIcon: paintItemIcon,
    textureFor: textureFor,
    shade: shade,
    rgba: rgba
  };
});

