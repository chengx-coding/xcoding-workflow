(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./lighting.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxLighting);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, LIGHTING) {
  "use strict";

  if (!CONFIG || !LIGHTING) {
    throw new Error("SandboxConfig and SandboxLighting are required before SandboxRender");
  }

  const TILE = CONFIG.tileSize;
  const VIEW_W = CONFIG.viewWidth;
  const VIEW_H = CONFIG.viewHeight;

  const SKY_KEYS = [
    { t: 0.0, top: [247, 178, 103], bottom: [255, 225, 168] },
    { t: 0.1, top: [110, 198, 255], bottom: [217, 242, 255] },
    { t: 0.42, top: [104, 194, 255], bottom: [214, 241, 255] },
    { t: 0.5, top: [255, 138, 91], bottom: [91, 58, 112] },
    { t: 0.62, top: [11, 16, 38], bottom: [27, 42, 74] },
    { t: 0.9, top: [11, 16, 38], bottom: [27, 42, 74] },
    { t: 1.0, top: [247, 178, 103], bottom: [255, 225, 168] }
  ];

  function createRng(seed) {
    let state = seed >>> 0;
    return function random() {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function speckle(ctx, rng, colors, count, minSize, maxSize) {
    for (let i = 0; i < count; i += 1) {
      const size = minSize + Math.floor(rng() * (maxSize - minSize + 1));
      ctx.fillStyle = colors[Math.floor(rng() * colors.length)];
      ctx.fillRect(Math.floor(rng() * (TILE - size)), Math.floor(rng() * (TILE - size)), size, size);
    }
  }

  function paintBlock(block, variant) {
    const canvas = makeCanvas(TILE, TILE);
    const ctx = canvas.getContext("2d");
    const colors = CONFIG.palette[block];
    const rng = createRng(block * 977 + variant * 131 + 7);
    ctx.fillStyle = colors.base;
    ctx.fillRect(0, 0, TILE, TILE);
    const id = block;

    if (id === CONFIG.blocks.grass) {
      ctx.fillStyle = colors.light;
      ctx.fillRect(0, 0, TILE, 6);
      ctx.fillStyle = colors.dark;
      ctx.fillRect(0, 5, TILE, 2);
      for (let x = 0; x < TILE; x += 3) {
        const height = 2 + Math.floor(rng() * 3);
        ctx.fillStyle = rng() > 0.5 ? colors.light : colors.dark;
        ctx.fillRect(x, 6, 1, height);
      }
      speckle(ctx, rng, [colors.dark], 8, 1, 2);
    } else if (id === CONFIG.blocks.dirt) {
      speckle(ctx, rng, [colors.light, colors.dark], 14, 1, 3);
    } else if (id === CONFIG.blocks.stone) {
      speckle(ctx, rng, [colors.light, colors.dark], 12, 1, 2);
      ctx.strokeStyle = colors.dark;
      ctx.lineWidth = 1;
      for (let i = 0; i < 2; i += 1) {
        ctx.beginPath();
        ctx.moveTo(Math.floor(rng() * TILE), 0);
        ctx.lineTo(Math.floor(rng() * TILE), TILE);
        ctx.stroke();
      }
    } else if (id === CONFIG.blocks.wood) {
      for (let x = 3; x < TILE; x += 6) {
        ctx.fillStyle = colors.dark;
        ctx.fillRect(x, 0, 2, TILE);
        ctx.fillStyle = colors.light;
        ctx.fillRect(x + 2, 0, 1, TILE);
      }
      ctx.fillStyle = colors.dark;
      ctx.fillRect(0, Math.floor(TILE / 2), TILE, 1);
    } else if (id === CONFIG.blocks.leaves) {
      for (let i = 0; i < 12; i += 1) {
        ctx.fillStyle = rng() > 0.5 ? colors.light : colors.dark;
        const size = 3 + Math.floor(rng() * 4);
        ctx.fillRect(Math.floor(rng() * (TILE - size)), Math.floor(rng() * (TILE - size)), size, size);
      }
      ctx.fillStyle = "rgba(0, 0, 0, 0.16)";
      ctx.fillRect(0, TILE - 2, TILE, 2);
    } else if (id === CONFIG.blocks.sand) {
      speckle(ctx, rng, [colors.light, colors.dark], 16, 1, 2);
    } else if (id === CONFIG.blocks.coal) {
      speckle(ctx, rng, [colors.light, colors.dark], 10, 1, 2);
      for (let i = 0; i < 3; i += 1) {
        ctx.fillStyle = "#1d2024";
        const size = 3 + Math.floor(rng() * 3);
        ctx.fillRect(Math.floor(rng() * (TILE - size)), Math.floor(rng() * (TILE - size)), size, size);
      }
    } else if (id === CONFIG.blocks.crystal) {
      speckle(ctx, rng, [colors.dark], 8, 1, 2);
      for (let i = 0; i < 3; i += 1) {
        const cx = 5 + Math.floor(rng() * 14);
        const cy = 5 + Math.floor(rng() * 14);
        ctx.fillStyle = colors.light;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 5);
        ctx.lineTo(cx + 4, cy);
        ctx.lineTo(cx, cy + 5);
        ctx.lineTo(cx - 4, cy);
        ctx.closePath();
        ctx.fill();
      }
    } else if (id === CONFIG.blocks.planks) {
      ctx.fillStyle = colors.dark;
      ctx.fillRect(0, 7, TILE, 1);
      ctx.fillRect(0, 15, TILE, 1);
      ctx.fillStyle = colors.light;
      ctx.fillRect(0, 6, TILE, 1);
      ctx.fillRect(0, 14, TILE, 1);
      for (let i = 0; i < 3; i += 1) {
        ctx.fillStyle = colors.dark;
        ctx.fillRect(Math.floor(rng() * TILE), 1 + i * 8, 1, 6);
      }
      speckle(ctx, rng, [colors.light], 5, 1, 2);
    } else {
      speckle(ctx, rng, [colors.light, colors.dark], 8, 1, 2);
    }

    ctx.strokeStyle = "rgba(0, 0, 0, 0.18)";
    ctx.strokeRect(0.5, 0.5, TILE - 1, TILE - 1);
    return canvas;
  }

  function createTextures() {
    const textures = {};
    const ids = [
      CONFIG.blocks.grass,
      CONFIG.blocks.dirt,
      CONFIG.blocks.stone,
      CONFIG.blocks.wood,
      CONFIG.blocks.leaves,
      CONFIG.blocks.sand,
      CONFIG.blocks.coal,
      CONFIG.blocks.crystal,
      CONFIG.blocks.planks
    ];
    for (let i = 0; i < ids.length; i += 1) {
      const variants = [];
      for (let v = 0; v < 3; v += 1) {
        variants.push(paintBlock(ids[i], v));
      }
      textures[ids[i]] = variants;
    }
    return textures;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function mixColor(a, b, t) {
    return [
      Math.round(lerp(a[0], b[0], t)),
      Math.round(lerp(a[1], b[1], t)),
      Math.round(lerp(a[2], b[2], t))
    ];
  }

  function skyColors(time) {
    const t = ((time % 1) + 1) % 1;
    let index = SKY_KEYS.length - 1;
    for (let i = 0; i < SKY_KEYS.length - 1; i += 1) {
      if (t >= SKY_KEYS[i].t && t <= SKY_KEYS[i + 1].t) {
        index = i;
        break;
      }
    }
    const current = SKY_KEYS[index];
    const next = SKY_KEYS[Math.min(SKY_KEYS.length - 1, index + 1)];
    const span = Math.max(0.0001, next.t - current.t);
    const mix = Math.max(0, Math.min(1, (t - current.t) / span));
    return {
      top: mixColor(current.top, next.top, mix),
      bottom: mixColor(current.bottom, next.bottom, mix)
    };
  }

  function rgb(color) {
    return "rgb(" + color[0] + "," + color[1] + "," + color[2] + ")";
  }

  function drawSky(ctx, state) {
    const colors = skyColors(state.time.tick / CONFIG.dayLengthSeconds);
    const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
    gradient.addColorStop(0, rgb(colors.top));
    gradient.addColorStop(1, rgb(colors.bottom));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    const t = ((state.time.tick / CONFIG.dayLengthSeconds) % 1 + 1) % 1;
    const nightAlpha = t > 0.52 && t < 0.98 ? 1 : t >= 0.98 ? 1 - (t - 0.98) / 0.02 : t < 0.04 ? 1 - t / 0.04 : 0;
    if (nightAlpha > 0.05) {
      ctx.fillStyle = "rgba(255, 255, 255, " + (0.75 * nightAlpha) + ")";
      const rng = createRng(4242);
      for (let i = 0; i < 70; i += 1) {
        const x = Math.floor(rng() * VIEW_W);
        const y = Math.floor(rng() * VIEW_H * 0.55);
        const size = rng() > 0.8 ? 2 : 1;
        ctx.fillRect(x, y, size, size);
      }
    }

    if (t < 0.5) {
      const progress = t / 0.5;
      const x = progress * (VIEW_W + 160) - 80;
      const y = VIEW_H * 0.72 - Math.sin(progress * Math.PI) * VIEW_H * 0.58;
      ctx.fillStyle = "#fff3b0";
      ctx.beginPath();
      ctx.arc(x, y, 26, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255, 243, 176, 0.25)";
      ctx.beginPath();
      ctx.arc(x, y, 44, 0, Math.PI * 2);
      ctx.fill();
    } else {
      const progress = (t - 0.5) / 0.5;
      const x = progress * (VIEW_W + 160) - 80;
      const y = VIEW_H * 0.72 - Math.sin(progress * Math.PI) * VIEW_H * 0.58;
      ctx.fillStyle = "#e8eef7";
      ctx.beginPath();
      ctx.arc(x, y, 20, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(20, 26, 40, 0.22)";
      ctx.beginPath();
      ctx.arc(x + 7, y - 4, 17, 0, Math.PI * 2);
      ctx.fill();
    }

    drawClouds(ctx, state, t);
  }

  function drawClouds(ctx, state, t) {
    const camera = state.camera;
    const drift = t * 90;
    const clouds = [
      { x: 120, y: 80, scale: 1.2 },
      { x: 430, y: 140, scale: 0.8 },
      { x: 740, y: 60, scale: 1.4 },
      { x: 980, y: 170, scale: 0.9 }
    ];
    ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
    for (let i = 0; i < clouds.length; i += 1) {
      const cloud = clouds[i];
      const x = ((cloud.x + drift + camera.x * 0.06) % (VIEW_W + 260)) - 130;
      const y = cloud.y;
      const scale = cloud.scale;
      ctx.beginPath();
      ctx.arc(x, y, 26 * scale, 0, Math.PI * 2);
      ctx.arc(x + 30 * scale, y + 4 * scale, 20 * scale, 0, Math.PI * 2);
      ctx.arc(x - 28 * scale, y + 6 * scale, 18 * scale, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawParallax(ctx, state) {
    const camera = state.camera;
    const horizon = VIEW_H * 0.66;
    const farOffset = camera.x * 0.12;
    ctx.fillStyle = "rgba(24, 48, 58, 0.55)";
    ctx.beginPath();
    ctx.moveTo(0, VIEW_H);
    for (let x = 0; x <= VIEW_W; x += 24) {
      const wave = Math.sin((x + farOffset) * 0.008) * 34 + Math.sin((x + farOffset) * 0.021) * 14;
      ctx.lineTo(x, horizon - 40 + wave);
    }
    ctx.lineTo(VIEW_W, VIEW_H);
    ctx.closePath();
    ctx.fill();

    const nearOffset = camera.x * 0.28;
    ctx.fillStyle = "rgba(16, 34, 30, 0.7)";
    ctx.beginPath();
    ctx.moveTo(0, VIEW_H);
    for (let x = 0; x <= VIEW_W; x += 20) {
      const wave = Math.sin((x + nearOffset) * 0.012 + 1.7) * 26 + Math.sin((x + nearOffset) * 0.03) * 9;
      ctx.lineTo(x, horizon + 12 + wave);
    }
    ctx.lineTo(VIEW_W, VIEW_H);
    ctx.closePath();
    ctx.fill();
  }

  function drawWater(ctx, state, x, y) {
    const tile = TILE;
    const px = Math.round(x * tile - state.camera.x);
    const py = Math.round(y * tile - state.camera.y);
    const t = state.time.tick;
    const gradient = ctx.createLinearGradient(px, py, px, py + tile);
    gradient.addColorStop(0, "rgba(79, 151, 209, 0.86)");
    gradient.addColorStop(1, "rgba(31, 79, 125, 0.92)");
    ctx.fillStyle = gradient;
    ctx.fillRect(px, py, tile, tile);
    ctx.fillStyle = "rgba(255, 255, 255, 0.16)";
    for (let i = 0; i < 2; i += 1) {
      const wave = Math.sin((x + i * 3) * 0.6 + t * 1.6) * 2;
      ctx.fillRect(px + 2, py + 5 + i * 8 + wave, tile - 4, 1);
    }
    if (state.world.data[(y - 1) * state.world.width + x] !== CONFIG.blocks.water) {
      ctx.fillStyle = "rgba(226, 246, 255, 0.5)";
      ctx.fillRect(px, py, tile, 2);
    }
  }

  function drawTorch(ctx, state, x, y) {
    const tile = TILE;
    const px = Math.round(x * tile - state.camera.x);
    const py = Math.round(y * tile - state.camera.y);
    const flicker = Math.sin(state.time.tick * 9 + x * 3.1) * 1.5;
    ctx.fillStyle = "#6b4a28";
    ctx.fillRect(px + 10, py + 9, 4, 15);
    ctx.fillStyle = "#ffcf6b";
    ctx.beginPath();
    ctx.arc(px + 12, py + 8 + flicker, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#fff1b8";
    ctx.beginPath();
    ctx.arc(px + 12, py + 7 + flicker, 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 190, 90, 0.16)";
    ctx.beginPath();
    ctx.arc(px + 12, py + 8, 16 + flicker, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawTiles(ctx, state) {
    const world = state.world;
    const camera = state.camera;
    const tile = TILE;
    const firstColumn = Math.max(0, Math.floor(camera.x / tile) - 1);
    const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / tile) + 1);
    const firstRow = Math.max(0, Math.floor(camera.y / tile) - 1);
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + VIEW_H) / tile) + 1);

    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const block = world.data[y * world.width + x];
        if (block === CONFIG.blocks.air) {
          continue;
        }
        const px = Math.round(x * tile - camera.x);
        const py = Math.round(y * tile - camera.y);
        if (block === CONFIG.blocks.water) {
          drawWater(ctx, state, x, y);
          continue;
        }
        if (block === CONFIG.blocks.torch) {
          drawTorch(ctx, state, x, y);
          continue;
        }
        const variants = state.textures[block];
        if (!variants) {
          ctx.fillStyle = CONFIG.palette[block] ? CONFIG.palette[block].base : "#888";
          ctx.fillRect(px, py, tile, tile);
          continue;
        }
        const variant = (x * 31 + y * 17) % variants.length;
        ctx.drawImage(variants[variant], px, py);

        if (block === CONFIG.blocks.crystal) {
          ctx.fillStyle = "rgba(168, 240, 255, 0.12)";
          ctx.fillRect(px - 4, py - 4, tile + 8, tile + 8);
        }
      }
    }
  }

  function drawDarkness(ctx, state) {
    const world = state.world;
    const camera = state.camera;
    const light = state.light;
    const tile = TILE;
    const firstColumn = Math.max(0, Math.floor(camera.x / tile));
    const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / tile));
    const firstRow = Math.max(0, Math.floor(camera.y / tile));
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + VIEW_H) / tile));
    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const level = light[y * world.width + x];
        const darkness = LIGHTING.darknessForLevel(level);
        if (darkness <= 0.02) {
          continue;
        }
        ctx.fillStyle = "rgba(3, 6, 14, " + (darkness * 0.88).toFixed(3) + ")";
        ctx.fillRect(
          Math.round(x * tile - camera.x),
          Math.round(y * tile - camera.y),
          tile,
          tile
        );
      }
    }
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const camera = state.camera;
    const tile = TILE;
    const scale = tile / 24;
    const screenX = player.x * tile - camera.x;
    const screenY = player.y * tile - camera.y;
    const bodyW = 18 * scale;
    const bodyH = 44 * scale;
    const left = Math.round(screenX - bodyW / 2);
    const top = Math.round(screenY - bodyH);
    const facing = player.facing >= 0 ? 1 : -1;
    const moving = Math.abs(player.vx) > 0.4 && player.onGround;
    const walkPhase = Math.sin(player.walk * 6) * (moving ? 1 : 0);
    const mining = state.mining && state.mining.active;
    const armSwing = mining ? Math.sin(state.time.tick * 18) * 0.9 : walkPhase * 0.5;

    ctx.fillStyle = "rgba(0, 0, 0, 0.24)";
    ctx.beginPath();
    ctx.ellipse(screenX, screenY - 1, bodyW * 0.55, 4 * scale, 0, 0, Math.PI * 2);
    ctx.fill();

    const legSwing = walkPhase * 4 * scale;
    ctx.fillStyle = "#2f3e50";
    ctx.fillRect(left + 3 * scale, top + 30 * scale, 5 * scale, 14 * scale - legSwing);
    ctx.fillRect(left + 10 * scale, top + 30 * scale, 5 * scale, 14 * scale + legSwing);

    ctx.fillStyle = "#2f8fbf";
    ctx.fillRect(left + 2 * scale, top + 16 * scale, 14 * scale, 15 * scale);
    ctx.fillStyle = "#246f96";
    ctx.fillRect(left + 2 * scale, top + 27 * scale, 14 * scale, 4 * scale);

    ctx.fillStyle = "#e0ac69";
    ctx.fillRect(left + 2 * scale, top + 4 * scale, 14 * scale, 13 * scale);
    ctx.fillStyle = "#3b2417";
    ctx.fillRect(left + 2 * scale, top + 2 * scale, 14 * scale, 4 * scale);
    ctx.fillRect(left + 1 * scale, top + 4 * scale, 2 * scale, 5 * scale);
    ctx.fillStyle = "#1b1b1b";
    const eyeX = facing > 0 ? left + 11 * scale : left + 4 * scale;
    ctx.fillRect(eyeX, top + 8 * scale, 2 * scale, 2 * scale);

    const armX = facing > 0 ? left + 14 * scale : left - 4 * scale;
    ctx.fillStyle = "#e0ac69";
    ctx.save();
    ctx.translate(armX + 2 * scale, top + 18 * scale);
    ctx.rotate(armSwing * 0.7);
    ctx.fillRect(-2 * scale, 0, 4 * scale, 12 * scale);
    ctx.restore();
  }

  function drawParticles(ctx, state) {
    const camera = state.camera;
    const tile = TILE;
    const particles = state.particles;
    for (let i = 0; i < particles.length; i += 1) {
      const particle = particles[i];
      const alpha = Math.max(0, particle.life / particle.maxLife);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = particle.color;
      ctx.fillRect(
        Math.round(particle.x * tile - camera.x),
        Math.round(particle.y * tile - camera.y),
        Math.max(1, particle.size),
        Math.max(1, particle.size)
      );
    }
    ctx.globalAlpha = 1;
  }

  function drawTarget(ctx, state) {
    const tile = TILE;
    const target = state.mouseTile;
    if (!target) {
      return;
    }
    const px = Math.round(target.x * tile - state.camera.x);
    const py = Math.round(target.y * tile - state.camera.y);
    const reachable = target.reachable;
    ctx.strokeStyle = reachable ? "rgba(255, 255, 255, 0.85)" : "rgba(240, 138, 122, 0.8)";
    ctx.lineWidth = 1;
    ctx.strokeRect(px + 0.5, py + 0.5, tile - 1, tile - 1);

    const mining = state.mining;
    if (mining && mining.active && mining.x === target.x && mining.y === target.y) {
      const progress = Math.min(1, mining.progress);
      const rng = createRng(target.x * 97 + target.y * 31 + 5);
      ctx.strokeStyle = "rgba(0, 0, 0, " + (0.25 + progress * 0.55) + ")";
      ctx.lineWidth = 1;
      const lines = 2 + Math.floor(progress * 4);
      for (let i = 0; i < lines; i += 1) {
        const sx = px + Math.floor(rng() * tile);
        const sy = py + Math.floor(rng() * tile);
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + (rng() > 0.5 ? 4 : -4), sy + (rng() > 0.5 ? 5 : -5));
        ctx.stroke();
      }
    }
  }

  function drawVignette(ctx) {
    const gradient = ctx.createRadialGradient(
      VIEW_W / 2,
      VIEW_H / 2,
      VIEW_H * 0.35,
      VIEW_W / 2,
      VIEW_H / 2,
      VIEW_H * 0.85
    );
    gradient.addColorStop(0, "rgba(0, 0, 0, 0)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0.16)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);
  }

  function renderFrame(ctx, state) {
    drawSky(ctx, state);
    drawParallax(ctx, state);
    drawTiles(ctx, state);
    drawDarkness(ctx, state);
    drawPlayer(ctx, state);
    drawParticles(ctx, state);
    drawTarget(ctx, state);
    drawVignette(ctx);
  }

  return {
    createTextures: createTextures,
    renderFrame: renderFrame,
    skyColors: skyColors
  };
});
