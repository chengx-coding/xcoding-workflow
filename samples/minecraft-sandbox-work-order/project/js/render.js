(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./camera.js"), require("./rng.js"), require("./daynight.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxCamera, root.SandboxRng, root.SandboxDayNight);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, CAMERA, RNG, DAYNIGHT) {
  "use strict";

  const BLOCK_COLORS = Object.freeze({
    1: "#5da34d",
    2: "#8a5f3c",
    3: "#7f8a94",
    4: "#6d4a2f",
    5: "#3f8f4f",
    6: "#d9c68a",
    7: "#a9773f",
    8: "#8b9299",
    9: "#a9d8e8"
  });

  const TILE_VARIANTS = 4;
  const tileCache = { tile: 0, variants: null };
  const surfaceCache = typeof WeakMap === "function" ? new WeakMap() : null;

  function hasDocument() {
    return typeof document !== "undefined" && typeof document.createElement === "function";
  }

  function applyPixel(ctx, x, y, color, size) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, size || 1, size || 1);
  }

  function speckle(ctx, random, tile, colors) {
    const count = 10 + Math.floor(random.range(0, 8));
    for (let index = 0; index < count; index += 1) {
      const x = Math.floor(random.range(1, tile - 2));
      const y = Math.floor(random.range(1, tile - 2));
      applyPixel(ctx, x, y, colors[Math.floor(random.range(0, colors.length))], random.range(0, 1) > 0.6 ? 2 : 1);
    }
  }

  function paintGrass(ctx, tile, random) {
    ctx.fillStyle = "#8a5f3c";
    ctx.fillRect(0, 0, tile, tile);
    speckle(ctx, random, tile, ["#7a5230", "#986a44", "#6e4a2b"]);
    const top = Math.max(5, Math.round(tile * 0.3));
    ctx.fillStyle = "#57a24a";
    ctx.fillRect(0, 0, tile, top);
    for (let x = 0; x < tile; x += 1) {
      const depth = 1 + Math.floor(random.next() * 4);
      ctx.fillStyle = random.next() > 0.5 ? "#63b055" : "#4a9140";
      ctx.fillRect(x, top - 1, 1, depth);
    }
    ctx.fillStyle = "#6fc45f";
    ctx.fillRect(0, 0, tile, 2);
  }

  function paintDirt(ctx, tile, random) {
    ctx.fillStyle = "#8a5f3c";
    ctx.fillRect(0, 0, tile, tile);
    speckle(ctx, random, tile, ["#754d2e", "#9c6d47", "#5f3f25"]);
  }

  function paintStone(ctx, tile, random) {
    ctx.fillStyle = "#7f8a94";
    ctx.fillRect(0, 0, tile, tile);
    speckle(ctx, random, tile, ["#737d87", "#8b959f", "#69737d"]);
    ctx.strokeStyle = "rgba(40, 48, 56, 0.35)";
    ctx.lineWidth = 1;
    const splitY = Math.floor(random.range(tile * 0.3, tile * 0.7));
    ctx.beginPath();
    ctx.moveTo(0, splitY);
    ctx.lineTo(tile, splitY + Math.floor(random.range(-3, 3)));
    ctx.stroke();
    applyPixel(ctx, Math.floor(random.range(2, tile - 3)), splitY + 2, "rgba(220, 228, 234, 0.4)", 2);
  }

  function paintSand(ctx, tile, random) {
    ctx.fillStyle = "#d9c68a";
    ctx.fillRect(0, 0, tile, tile);
    speckle(ctx, random, tile, ["#cdb878", "#e6d59b", "#bfa96a"]);
  }

  function paintWood(ctx, tile, random) {
    ctx.fillStyle = "#6d4a2f";
    ctx.fillRect(0, 0, tile, tile);
    for (let x = 3; x < tile; x += 5) {
      ctx.fillStyle = "rgba(58, 38, 22, 0.55)";
      ctx.fillRect(x, 0, 1, tile);
      ctx.fillStyle = "rgba(150, 108, 68, 0.4)";
      ctx.fillRect(x + 1, 0, 1, tile);
    }
    ctx.strokeStyle = "rgba(46, 30, 18, 0.6)";
    ctx.beginPath();
    ctx.ellipse(tile / 2, tile / 2, 4, 6, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  function paintLeaves(ctx, tile, random) {
    ctx.fillStyle = "#2f7a3c";
    ctx.fillRect(0, 0, tile, tile);
    for (let index = 0; index < 26; index += 1) {
      const x = random.range(0, tile - 3);
      const y = random.range(0, tile - 3);
      ctx.fillStyle = random.next() > 0.5 ? "#479b4f" : "#256a31";
      ctx.fillRect(Math.floor(x), Math.floor(y), 3, 2);
    }
    for (let index = 0; index < 5; index += 1) {
      ctx.fillStyle = "rgba(12, 34, 18, 0.5)";
      ctx.fillRect(Math.floor(random.range(2, tile - 3)), Math.floor(random.range(2, tile - 3)), 2, 2);
    }
  }

  function paintPlanks(ctx, tile, random) {
    ctx.fillStyle = "#a9773f";
    ctx.fillRect(0, 0, tile, tile);
    for (let y = 0; y < tile; y += 6) {
      ctx.fillStyle = "rgba(70, 44, 20, 0.5)";
      ctx.fillRect(0, y, tile, 1);
      ctx.fillStyle = "rgba(214, 168, 105, 0.35)";
      ctx.fillRect(0, y + 1, tile, 1);
    }
    for (let index = 0; index < 6; index += 1) {
      applyPixel(
        ctx,
        Math.floor(random.range(1, tile - 2)),
        Math.floor(random.range(1, tile - 2)),
        "rgba(84, 54, 24, 0.45)",
        2
      );
    }
  }

  function paintCobblestone(ctx, tile, random) {
    ctx.fillStyle = "#7d848b";
    ctx.fillRect(0, 0, tile, tile);
    const stones = 6;
    for (let index = 0; index < stones; index += 1) {
      const width = Math.floor(random.range(6, 11));
      const height = Math.floor(random.range(5, 9));
      const x = Math.floor(random.range(0, tile - width));
      const y = Math.floor(random.range(0, tile - height));
      ctx.fillStyle = ["#9aa1a8", "#8d949b", "#767d84"][index % 3];
      ctx.fillRect(x, y, width, height);
      ctx.fillStyle = "rgba(235, 240, 244, 0.22)";
      ctx.fillRect(x, y, width, 1);
      ctx.fillStyle = "rgba(38, 44, 50, 0.35)";
      ctx.fillRect(x, y + height - 1, width, 1);
    }
  }

  function paintGlass(ctx, tile) {
    ctx.fillStyle = "rgba(168, 216, 232, 0.22)";
    ctx.fillRect(0, 0, tile, tile);
    ctx.strokeStyle = "rgba(214, 244, 255, 0.75)";
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, tile - 2, tile - 2);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
    ctx.beginPath();
    ctx.moveTo(3, tile - 4);
    ctx.lineTo(tile - 4, 3);
    ctx.stroke();
  }

  const PAINTERS = {
    1: paintGrass,
    2: paintDirt,
    3: paintStone,
    4: paintWood,
    5: paintLeaves,
    6: paintSand,
    7: paintPlanks,
    8: paintCobblestone,
    9: paintGlass
  };

  function buildTileCache(tile) {
    if (!hasDocument() || tile <= 0) {
      return null;
    }
    const variants = {};
    Object.keys(PAINTERS).forEach(function (key) {
      const block = Number(key);
      const list = [];
      for (let variant = 0; variant < TILE_VARIANTS; variant += 1) {
        const canvas = document.createElement("canvas");
        canvas.width = tile;
        canvas.height = tile;
        const ctx = canvas.getContext("2d");
        const random = RNG.createRandom((block * 977 + variant * 131 + 7) >>> 0);
        PAINTERS[key](ctx, tile, random);
        list.push(canvas);
      }
      variants[block] = list;
    });
    return variants;
  }

  function ensureTileCache(tile) {
    if (!hasDocument()) {
      return null;
    }
    if (!tileCache.variants || tileCache.tile !== tile) {
      tileCache.tile = tile;
      tileCache.variants = buildTileCache(tile);
    }
    return tileCache.variants;
  }

  function tileVariant(x, y, seed) {
    return Math.floor(RNG.hash2(x, y, seed) * TILE_VARIANTS) % TILE_VARIANTS;
  }

  function depthShade(depth) {
    const value = Number(depth);
    if (!Number.isFinite(value) || value <= 0) {
      return 0;
    }
    return Math.min(0.42, value * 0.055);
  }

  function crackStages(progress) {
    const value = Math.min(1, Math.max(0, Number(progress) || 0));
    if (value <= 0) {
      return 0;
    }
    return Math.min(4, Math.ceil(value * 4));
  }

  function surfaceFor(world) {
    if (!surfaceCache) {
      return null;
    }
    let surface = surfaceCache.get(world);
    if (!surface) {
      // Lazy import avoids a hard dependency at module load time.
      surface = null;
      if (typeof require === "function") {
        try {
          surface = require("./world.js").surfaceMap(world);
        } catch (error) {
          surface = null;
        }
      }
      if (!surface) {
        const map = new Uint8Array(world.width);
        for (let x = 0; x < world.width; x += 1) {
          map[x] = world.height;
          for (let y = 0; y < world.height; y += 1) {
            const block = world.data[y * world.width + x];
            if (block === 1 || block === 2 || block === 3 || block === 6) {
              map[x] = y;
              break;
            }
          }
        }
        surface = map;
      }
      surfaceCache.set(world, surface);
    }
    return surface;
  }

  function drawSky(ctx, state) {
    const view = { width: CONFIG.viewWidth, height: CONFIG.viewHeight };
    const palette = DAYNIGHT.skyColors(state.time);
    const gradient = ctx.createLinearGradient(0, 0, 0, view.height);
    gradient.addColorStop(0, palette.top);
    gradient.addColorStop(0.55, palette.mid);
    gradient.addColorStop(1, palette.bottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, view.width, view.height);

    const light = palette.light;
    const stars = 44;
    if (light < 0.55) {
      for (let index = 0; index < stars; index += 1) {
        const x = RNG.hash2(index, 3, state.seed) * view.width;
        const y = RNG.hash2(index, 9, state.seed) * view.height * 0.55;
        const alpha = (1 - light) * (0.25 + RNG.hash2(index, 17, state.seed) * 0.6);
        ctx.fillStyle = "rgba(235, 244, 255, " + alpha.toFixed(3) + ")";
        ctx.fillRect(x, y, 2, 2);
      }
    }

    const bodies = DAYNIGHT.celestial(state.time);
    function disc(position, radius, inner, outer) {
      const x = position.x * view.width;
      const y = view.height * 0.62 - position.y * view.height * 0.45;
      const glow = ctx.createRadialGradient(x, y, radius * 0.4, x, y, radius * 2.6);
      glow.addColorStop(0, inner);
      glow.addColorStop(1, outer);
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, radius * 2.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = inner;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    disc(bodies.sun, 16, "rgba(255, 236, 168, 0.95)", "rgba(255, 214, 120, 0)");
    disc(bodies.moon, 13, "rgba(222, 235, 255, 0.9)", "rgba(150, 190, 255, 0)");

    drawClouds(ctx, state, view);
    drawHills(ctx, state, view);
  }

  function drawClouds(ctx, state, view) {
    const drift = state.time * 140 + state.camera.x * 0.18;
    for (let index = 0; index < 5; index += 1) {
      const span = view.width + 320;
      const x = ((index * 231 + drift) % span) - 160;
      const y = 42 + index * 27 + RNG.hash2(index, 5, state.seed) * 24;
      const scale = 0.7 + RNG.hash2(index, 11, state.seed) * 0.7;
      ctx.fillStyle = "rgba(255, 255, 255, 0.34)";
      ctx.beginPath();
      ctx.ellipse(x, y, 62 * scale, 16 * scale, 0, 0, Math.PI * 2);
      ctx.ellipse(x + 38 * scale, y + 4, 40 * scale, 12 * scale, 0, 0, Math.PI * 2);
      ctx.ellipse(x - 42 * scale, y + 5, 36 * scale, 11 * scale, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawHills(ctx, state, view) {
    const layers = [
      { parallax: 0.22, base: 0.62, amplitude: 46, frequency: 0.006, color: "rgba(84, 118, 132, 0.45)" },
      { parallax: 0.42, base: 0.72, amplitude: 34, frequency: 0.011, color: "rgba(58, 92, 88, 0.55)" }
    ];
    layers.forEach(function (layer, index) {
      const offset = state.camera.x * layer.parallax;
      const phase = RNG.hash2(index, 2, state.seed) * Math.PI * 2;
      ctx.fillStyle = layer.color;
      ctx.beginPath();
      ctx.moveTo(0, view.height);
      for (let x = 0; x <= view.width; x += 12) {
        const worldX = x + offset;
        const y =
          view.height * layer.base -
          layer.amplitude * (Math.sin(worldX * layer.frequency + phase) * 0.6 + 0.4) -
          layer.amplitude * 0.5 * Math.sin(worldX * layer.frequency * 2.7 + phase * 1.6);
        ctx.lineTo(x, y);
      }
      ctx.lineTo(view.width, view.height);
      ctx.closePath();
      ctx.fill();
    });
  }

  function drawTiles(ctx, state, surface) {
    const world = state.world;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const view = { width: CONFIG.viewWidth, height: CONFIG.viewHeight };
    const range = CAMERA.visibleRange(camera, world, view, tile);
    const variants = ensureTileCache(tile);
    for (let y = range.firstY; y <= range.lastY; y += 1) {
      for (let x = range.firstX; x <= range.lastX; x += 1) {
        const block = world.data[y * world.width + x];
        const px = Math.round(x * tile - camera.x);
        const py = Math.round(y * tile - camera.y);
        if (!block) {
          const depth = surface ? y - surface[x] : 0;
          if (depth > 0) {
            const darkness = Math.min(0.78, 0.42 + depth * 0.035);
            ctx.fillStyle = "rgba(9, 13, 20, " + darkness.toFixed(3) + ")";
            ctx.fillRect(px, py, tile, tile);
          }
          continue;
        }
        if (variants && variants[block]) {
          const list = variants[block];
          ctx.drawImage(list[tileVariant(x, y, world.seed)], px, py, tile, tile);
        } else {
          ctx.fillStyle = BLOCK_COLORS[block] || "#9e9e9e";
          ctx.fillRect(px, py, tile, tile);
        }
        const shade = surface ? depthShade(y - surface[x]) : 0;
        if (shade > 0) {
          ctx.fillStyle = "rgba(6, 10, 18, " + shade.toFixed(3) + ")";
          ctx.fillRect(px, py, tile, tile);
        }
      }
    }
  }

  function drawHover(ctx, state) {
    if (!state.hovered) {
      return;
    }
    const tile = CONFIG.tileSize;
    const camera = state.camera;
    const px = Math.round(state.hovered.x * tile - camera.x);
    const py = Math.round(state.hovered.y * tile - camera.y);
    ctx.lineWidth = 2;
    ctx.strokeStyle = state.hoverValid ? "rgba(255, 255, 255, 0.9)" : "rgba(255, 116, 96, 0.9)";
    ctx.strokeRect(px + 1, py + 1, tile - 2, tile - 2);
    if (state.mining && state.mining.cell) {
      const stages = crackStages(state.mining.progress);
      if (stages > 0) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(px, py, tile, tile);
        ctx.clip();
        ctx.strokeStyle = "rgba(16, 18, 22, 0.75)";
        ctx.lineWidth = 1.5;
        const random = RNG.createRandom((state.hovered.x * 31 + state.hovered.y * 17 + stages) >>> 0);
        for (let index = 0; index < stages * 2; index += 1) {
          const startX = px + random.range(2, tile - 2);
          const startY = py + random.range(2, tile - 2);
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(startX + random.range(-7, 7), startY + random.range(-7, 7));
          ctx.stroke();
        }
        ctx.restore();
      }
    }
  }

  function drawParticles(ctx, state) {
    if (!state.particles) {
      return;
    }
    const camera = state.camera;
    state.particles.forEach(function (particle) {
      const alpha = Math.max(0, Math.min(1, particle.life / particle.maxLife));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = particle.color;
      ctx.fillRect(Math.round(particle.x - camera.x), Math.round(particle.y - camera.y), particle.size, particle.size);
    });
    ctx.globalAlpha = 1;
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const tile = CONFIG.tileSize;
    const camera = state.camera;
    const reduced = Boolean(state.reducedMotion);
    const baseX = player.x * tile - camera.x;
    const feetY = player.y * tile - camera.y;
    const width = Math.max(12, player.width * tile);
    const height = player.height * tile;
    const moving = Math.abs(player.vx) > 0.2 && player.onGround;
    const swing = reduced ? 0 : Math.sin(player.walkTime * 9) * (moving ? 1 : 0);
    const bob = reduced ? 0 : Math.abs(Math.sin(player.walkTime * 9)) * (moving ? 1.5 : 0);
    const facing = player.facing || 1;
    const mining = state.mining && state.mining.progress > 0;
    const armSwing = mining ? Math.sin(state.time * 26) * 0.7 : swing * 0.8;

    ctx.save();
    ctx.translate(Math.round(baseX), Math.round(feetY + bob));

    // Ground shadow.
    ctx.fillStyle = "rgba(6, 12, 18, 0.28)";
    ctx.beginPath();
    ctx.ellipse(0, 1, width * 0.62, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    const headSize = width * 0.78;
    const bodyHeight = height * 0.42;
    const legHeight = height * 0.36;

    // Legs.
    ctx.fillStyle = "#2f3b56";
    const legWidth = width * 0.34;
    ctx.save();
    ctx.translate(-width * 0.2, -legHeight);
    ctx.rotate(swing * 0.35);
    ctx.fillRect(-legWidth / 2, 0, legWidth, legHeight);
    ctx.restore();
    ctx.save();
    ctx.translate(width * 0.2, -legHeight);
    ctx.rotate(-swing * 0.35);
    ctx.fillRect(-legWidth / 2, 0, legWidth, legHeight);
    ctx.restore();

    // Body.
    ctx.fillStyle = "#3f7fb8";
    ctx.fillRect(-width * 0.44, -legHeight - bodyHeight, width * 0.88, bodyHeight);
    ctx.fillStyle = "rgba(255, 255, 255, 0.16)";
    ctx.fillRect(-width * 0.44, -legHeight - bodyHeight, width * 0.88, 3);

    // Arms.
    ctx.strokeStyle = "#e0a878";
    ctx.lineCap = "round";
    ctx.lineWidth = Math.max(3, width * 0.22);
    ctx.beginPath();
    ctx.moveTo(-width * 0.4, -legHeight - bodyHeight * 0.82);
    ctx.lineTo(-width * 0.52, -legHeight - bodyHeight * 0.2 + armSwing * 6);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(width * 0.4, -legHeight - bodyHeight * 0.82);
    ctx.lineTo(width * 0.55 * facing + width * 0.4 * (facing > 0 ? 0 : 0), -legHeight - bodyHeight * 0.2 - armSwing * 8);
    ctx.stroke();

    // Head.
    const headX = -headSize / 2 + facing * width * 0.04;
    const headY = -legHeight - bodyHeight - headSize * 0.92;
    ctx.fillStyle = "#e6b58a";
    ctx.fillRect(headX, headY, headSize, headSize);
    ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
    ctx.fillRect(headX, headY, headSize, 3);
    ctx.fillStyle = "#3b2a22";
    ctx.fillRect(headX + (facing > 0 ? headSize * 0.52 : headSize * 0.2), headY + headSize * 0.36, 2, 3);
    ctx.fillRect(headX + (facing > 0 ? headSize * 0.78 : headSize * 0.46), headY + headSize * 0.36, 2, 3);

    // Tool nub while mining, so the action reads as intentional.
    if (mining) {
      ctx.fillStyle = "#c9d4dc";
      ctx.fillRect(width * 0.62 * facing, -legHeight - bodyHeight * 0.5, 8, 3);
    }

    ctx.restore();
  }

  function drawCrosshair(ctx, state) {
    if (!state.hovered) {
      return;
    }
    const tile = CONFIG.tileSize;
    const x = Math.round((state.hovered.x + 0.5) * tile - state.camera.x);
    const y = Math.round((state.hovered.y + 0.5) * tile - state.camera.y);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x - 5, y);
    ctx.lineTo(x + 5, y);
    ctx.moveTo(x, y - 5);
    ctx.lineTo(x, y + 5);
    ctx.stroke();
  }

  function drawNight(ctx, state) {
    const tint = DAYNIGHT.nightTint(state.time);
    if (tint <= 0.01) {
      return;
    }
    ctx.fillStyle = "rgba(8, 12, 34, " + tint.toFixed(3) + ")";
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
  }

  function drawEdges(ctx, state) {
    const world = state.world;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const range = CAMERA.visibleRange(camera, world, { width: CONFIG.viewWidth, height: CONFIG.viewHeight }, tile);
    for (let y = range.firstY; y <= range.lastY; y += 1) {
      for (let x = range.firstX; x <= range.lastX; x += 1) {
        const block = world.data[y * world.width + x];
        if (!block) {
          continue;
        }
        const px = Math.round(x * tile - camera.x);
        const py = Math.round(y * tile - camera.y);
        const airAbove = y === 0 || world.data[(y - 1) * world.width + x] === 0;
        const airBelow = y === world.height - 1 || world.data[(y + 1) * world.width + x] === 0;
        const airLeft = x === 0 || world.data[y * world.width + x - 1] === 0;
        const airRight = x === world.width - 1 || world.data[y * world.width + x + 1] === 0;
        if (airAbove) {
          ctx.fillStyle = "rgba(255, 255, 255, 0.14)";
          ctx.fillRect(px, py, tile, 2);
        }
        if (airBelow) {
          ctx.fillStyle = "rgba(0, 0, 0, 0.24)";
          ctx.fillRect(px, py + tile - 2, tile, 2);
        }
        if (airLeft) {
          ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
          ctx.fillRect(px, py, 2, tile);
        }
        if (airRight) {
          ctx.fillStyle = "rgba(0, 0, 0, 0.14)";
          ctx.fillRect(px + tile - 2, py, 2, tile);
        }
      }
    }
  }

  function drawDecor(ctx, state, surface) {
    if (!surface) {
      return;
    }
    const world = state.world;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const range = CAMERA.visibleRange(camera, world, { width: CONFIG.viewWidth, height: CONFIG.viewHeight }, tile);
    for (let x = range.firstX; x <= range.lastX; x += 1) {
      const surfaceY = surface[x];
      if (surfaceY < range.firstY - 1 || surfaceY > range.lastY + 1) {
        continue;
      }
      if (world.data[surfaceY * world.width + x] !== 1) {
        continue;
      }
      const px = x * tile - camera.x;
      const py = surfaceY * tile - camera.y;
      const roll = RNG.hash2(x, 31, state.seed);
      if (roll < 0.16) {
        const bloom = RNG.hash2(x, 47, state.seed);
        const flowerX = px + 6 + bloom * 12;
        const flowerY = py - 4 - bloom * 3;
        ctx.strokeStyle = "rgba(38, 92, 44, 0.9)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(flowerX, py);
        ctx.lineTo(flowerX, flowerY);
        ctx.stroke();
        ctx.fillStyle = bloom > 0.6 ? "#ffd166" : bloom > 0.3 ? "#ff8f6b" : "#f5f0e6";
        ctx.fillRect(flowerX - 1.5, flowerY - 2, 3, 3);
      } else if (roll < 0.55) {
        ctx.strokeStyle = "rgba(28, 74, 34, 0.75)";
        ctx.lineWidth = 1;
        for (let blade = 0; blade < 3; blade += 1) {
          const bladeX = px + 5 + blade * 5 + RNG.hash2(x, blade, state.seed) * 3;
          ctx.beginPath();
          ctx.moveTo(bladeX, py);
          ctx.lineTo(bladeX + (blade - 1) * 1.5, py - 3 - RNG.hash2(x, blade + 9, state.seed) * 3);
          ctx.stroke();
        }
      }
    }
  }

  function drawVignette(ctx) {
    const gradient = ctx.createRadialGradient(
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      CONFIG.viewHeight * 0.35,
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      CONFIG.viewWidth * 0.72
    );
    gradient.addColorStop(0, "rgba(4, 8, 14, 0)");
    gradient.addColorStop(1, "rgba(4, 8, 14, 0.26)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
  }

  function drawFireflies(ctx, state, surface) {
    if (!surface) {
      return;
    }
    const light = DAYNIGHT.daylight(state.time);
    if (light > 0.36) {
      return;
    }
    const strength = Math.min(0.95, (0.36 - light) * 2.4);
    const tile = CONFIG.tileSize;
    const camera = state.camera;
    const firstX = Math.floor(camera.x / tile);
    const span = Math.ceil(CONFIG.viewWidth / tile) + 1;
    for (let index = 0; index < 22; index += 1) {
      const offset = RNG.hash2(index, 23, state.seed) * span;
      const worldX = Math.min(state.world.width - 1, Math.max(0, firstX + Math.floor(offset)));
      const surfaceY = surface[worldX];
      if (surfaceY >= state.world.height) {
        continue;
      }
      const drift = Math.sin(state.time * 5 + index * 1.7);
      const sx = worldX * tile - camera.x + offset % 1 * tile + drift * 7;
      const sy =
        surfaceY * tile -
        camera.y -
        8 -
        (0.5 + RNG.hash2(index, 41, state.seed) * 0.5) * 26 -
        Math.sin(state.time * 2.2 + index) * 12;
      if (sy < 0 || sy > CONFIG.viewHeight || sx < 0 || sx > CONFIG.viewWidth) {
        continue;
      }
      ctx.fillStyle = "rgba(255, 220, 130, " + (strength * 0.18).toFixed(3) + ")";
      ctx.beginPath();
      ctx.arc(sx, sy, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255, 238, 168, " + strength.toFixed(3) + ")";
      ctx.beginPath();
      ctx.arc(sx, sy, 1.7, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function renderFrame(ctx, state) {
    const surface = surfaceFor(state.world);
    drawSky(ctx, state);
    drawTiles(ctx, state, surface);
    drawEdges(ctx, state);
    drawDecor(ctx, state, surface);
    drawHover(ctx, state);
    drawParticles(ctx, state);
    drawPlayer(ctx, state);
    drawNight(ctx, state);
    drawFireflies(ctx, state, surface);
    drawCrosshair(ctx, state);
    drawVignette(ctx);
  }

  return {
    renderFrame: renderFrame,
    BLOCK_COLORS: BLOCK_COLORS,
    TILE_VARIANTS: TILE_VARIANTS,
    tileVariant: tileVariant,
    depthShade: depthShade,
    crackStages: crackStages,
    surfaceFor: surfaceFor
  };
});
