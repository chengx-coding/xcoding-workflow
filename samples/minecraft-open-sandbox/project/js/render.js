(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"), require("./light.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxBlocks, root.SandboxLight);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS, LIGHT) {
  "use strict";

  if (!CONFIG || !BLOCKS || !LIGHT) {
    throw new Error("SandboxConfig, SandboxBlocks and SandboxLight are required before SandboxRender");
  }

  const TS = CONFIG.tileSize;
  const B = CONFIG.blocks;
  const I = CONFIG.items;
  const VIEW_W = CONFIG.viewWidth;
  const VIEW_H = CONFIG.viewHeight;
  const VARIANTS = 3;

  let textures = null;
  let iconCache = null;
  let lightCanvas = null;
  let lightCtx = null;

  function hash(px, py, seed) {
    let h = Math.imul(px | 0, 374761393) ^ Math.imul(py | 0, 668265263) ^ Math.imul(seed | 0, 2654435761);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function shade(hex, amount) {
    const value = parseInt(hex.slice(1), 16);
    const r = Math.max(0, Math.min(255, ((value >> 16) & 255) + amount));
    const g = Math.max(0, Math.min(255, ((value >> 8) & 255) + amount));
    const b = Math.max(0, Math.min(255, (value & 255) + amount));
    return "rgb(" + r + "," + g + "," + b + ")";
  }

  function speckle(ctx, palette, seed, count, size) {
    for (let i = 0; i < count; i += 1) {
      const x = Math.floor(hash(i, seed, 11) * TS);
      const y = Math.floor(hash(i, seed, 29) * TS);
      const tone = hash(i, seed, 47) > 0.55 ? palette.light : palette.dark;
      ctx.fillStyle = tone;
      ctx.globalAlpha = 0.25 + hash(i, seed, 71) * 0.3;
      const s = size || 2;
      ctx.fillRect(x, y, s, s);
    }
    ctx.globalAlpha = 1;
  }

  function drawGrass(ctx, palette, seed) {
    ctx.fillStyle = palette.accent;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 22, 2);
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 5, TS, TS - 5);
    speckle(ctx, palette, seed + 3, 12, 2);
    ctx.fillStyle = palette.light;
    ctx.fillRect(0, 5, TS, 2);
    for (let x = 0; x < TS; x += 3) {
      if (hash(x, seed, 5) > 0.45) {
        ctx.fillStyle = palette.light;
        ctx.fillRect(x, 3 + Math.floor(hash(x, seed, 9) * 3), 2, 4);
      }
    }
    ctx.fillStyle = shade(palette.dark, -10);
    for (let x = 0; x < TS; x += 5) {
      ctx.fillRect(x + 1, 7, 2, 2);
    }
  }

  function drawStone(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 26, 2);
    ctx.strokeStyle = palette.dark;
    ctx.globalAlpha = 0.55;
    ctx.lineWidth = 1;
    for (let i = 0; i < 3; i += 1) {
      const x = Math.floor(hash(i, seed, 13) * TS);
      const y = Math.floor(hash(i, seed, 17) * TS);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 4, y + 3);
      ctx.lineTo(x + 6, y + 7);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.light;
    ctx.globalAlpha = 0.35;
    ctx.fillRect(1, 1, TS - 2, 2);
    ctx.globalAlpha = 1;
  }

  function drawOre(ctx, palette, seed, colors) {
    drawStone(ctx, { base: palette.base, light: palette.light, dark: palette.dark }, seed);
    for (let i = 0; i < 4; i += 1) {
      const x = 3 + Math.floor(hash(i, seed, 23) * (TS - 8));
      const y = 3 + Math.floor(hash(i, seed, 31) * (TS - 8));
      const size = 3 + Math.floor(hash(i, seed, 41) * 3);
      ctx.fillStyle = colors.dark;
      ctx.fillRect(x - 1, y - 1, size + 2, size + 2);
      ctx.fillStyle = colors.base;
      ctx.fillRect(x, y, size, size);
      ctx.fillStyle = colors.light;
      ctx.fillRect(x, y, Math.max(1, size - 2), 1);
    }
  }

  function drawWood(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let x = 0; x < TS; x += 4) {
      ctx.fillStyle = x % 8 === 0 ? palette.dark : palette.light;
      ctx.globalAlpha = 0.5;
      ctx.fillRect(x, 0, 1, TS);
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.dark;
    ctx.fillRect(2, 4, 5, 6);
    ctx.fillStyle = shade(palette.light, 18);
    ctx.fillRect(3, 5, 3, 4);
    ctx.fillStyle = palette.accent;
    ctx.fillRect(TS - 7, 12, 4, 8);
  }

  function drawLeaves(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 36, 3);
    ctx.fillStyle = palette.light;
    for (let i = 0; i < 7; i += 1) {
      const x = Math.floor(hash(i, seed, 53) * TS);
      const y = Math.floor(hash(i, seed, 59) * TS);
      ctx.fillRect(x, y, 2, 2);
    }
    ctx.fillStyle = palette.dark;
    for (let i = 0; i < 5; i += 1) {
      const x = Math.floor(hash(i, seed, 61) * TS);
      const y = Math.floor(hash(i, seed, 67) * TS);
      ctx.fillRect(x, y, 3, 2);
    }
  }

  function drawPlanks(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let y = 0; y < TS; y += 6) {
      ctx.fillStyle = shade(palette.base, y % 12 === 0 ? 8 : -6);
      ctx.fillRect(0, y, TS, 5);
      ctx.fillStyle = palette.dark;
      ctx.fillRect(0, y + 5, TS, 1);
      for (let x = 2; x < TS; x += 7) {
        ctx.fillStyle = palette.accent;
        ctx.globalAlpha = 0.4;
        ctx.fillRect(x, y + 2, 3, 1);
        ctx.globalAlpha = 1;
      }
    }
    ctx.fillStyle = palette.dark;
    ctx.fillRect(TS - 3, 0, 1, TS);
  }

  function drawCobble(ctx, palette, seed) {
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 0, TS, TS);
    const cells = [
      [1, 1, 10, 8],
      [13, 1, 9, 6],
      [2, 11, 8, 6],
      [12, 10, 10, 8],
      [1, 19, 8, 4],
      [11, 20, 11, 3]
    ];
    for (let i = 0; i < cells.length; i += 1) {
      const cell = cells[i];
      ctx.fillStyle = i % 2 === 0 ? palette.base : shade(palette.base, -8);
      ctx.fillRect(cell[0], cell[1], cell[2] - 1, cell[3] - 1);
      ctx.fillStyle = palette.light;
      ctx.globalAlpha = 0.4;
      ctx.fillRect(cell[0], cell[1], cell[2] - 2, 1);
      ctx.globalAlpha = 1;
    }
    speckle(ctx, palette, seed, 8, 1);
  }

  function drawBricks(ctx, palette, seed) {
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 0, TS, TS);
    for (let row = 0; row < 3; row += 1) {
      const offset = row % 2 === 0 ? 0 : -5;
      for (let col = -1; col < 4; col += 1) {
        const x = offset + col * 12 + 1;
        const y = row * 8 + 1;
        ctx.fillStyle = palette.base;
        ctx.fillRect(x, y, 10, 6);
        ctx.fillStyle = palette.light;
        ctx.globalAlpha = 0.35;
        ctx.fillRect(x, y, 10, 1);
        ctx.globalAlpha = 1;
      }
    }
    speckle(ctx, palette, seed, 6, 1);
  }

  function drawTable(ctx, palette, seed) {
    drawWood(ctx, palette, seed);
    ctx.fillStyle = palette.light;
    ctx.fillRect(0, 0, TS, 5);
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 5, TS, 2);
    ctx.strokeStyle = palette.accent;
    ctx.lineWidth = 1;
    ctx.strokeRect(4, 9, 7, 7);
    ctx.beginPath();
    ctx.moveTo(16, 9);
    ctx.lineTo(20, 16);
    ctx.moveTo(20, 9);
    ctx.lineTo(16, 16);
    ctx.stroke();
    ctx.fillStyle = shade(palette.light, 25);
    ctx.fillRect(2, 3, 3, 1);
  }

  function drawFurnace(ctx, palette, seed) {
    drawStone(ctx, palette, seed);
    ctx.fillStyle = "#1b1d22";
    ctx.fillRect(5, 9, TS - 10, TS - 12);
    ctx.fillStyle = "#3a2a20";
    ctx.fillRect(7, 11, TS - 14, TS - 16);
    ctx.fillStyle = "#ff9c4a";
    ctx.globalAlpha = 0.9;
    ctx.fillRect(8, 13, TS - 16, 3);
    ctx.globalAlpha = 0.45;
    ctx.fillRect(9, 17, TS - 18, 2);
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.light;
    ctx.fillRect(3, 3, TS - 6, 2);
  }

  function drawBeacon(ctx, palette, seed) {
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 0, TS, TS);
    ctx.fillStyle = palette.base;
    ctx.fillRect(2, 2, TS - 4, TS - 4);
    const gradient = ctx.createRadialGradient(TS / 2, TS / 2, 1, TS / 2, TS / 2, TS / 2);
    gradient.addColorStop(0, "#ffe8a3");
    gradient.addColorStop(0.4, palette.light);
    gradient.addColorStop(0.8, palette.accent);
    gradient.addColorStop(1, "rgba(255,138,76,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(2, 2, TS - 4, TS - 4);
    ctx.fillStyle = "#ffe9b0";
    ctx.fillRect(TS / 2 - 1, TS / 2 - 1, 2, 2);
    ctx.strokeStyle = palette.accent;
    ctx.globalAlpha = 0.55;
    ctx.strokeRect(4, 4, TS - 8, TS - 8);
    ctx.globalAlpha = 1;
  }

  function drawSand(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 30, 2);
    ctx.fillStyle = palette.light;
    for (let i = 0; i < 6; i += 1) {
      const x = Math.floor(hash(i, seed, 73) * TS);
      const y = Math.floor(hash(i, seed, 79) * TS);
      ctx.fillRect(x, y, 2, 1);
    }
  }

  function paintTexture(ctx, blockId, seed) {
    const def = BLOCKS.get(blockId);
    if (!def) {
      ctx.fillStyle = "#ff00ff";
      ctx.fillRect(0, 0, TS, TS);
      return;
    }
    const palette = def.palette;
    switch (def.key) {
      case "grass":
        drawGrass(ctx, palette, seed);
        break;
      case "dirt":
        ctx.fillStyle = palette.base;
        ctx.fillRect(0, 0, TS, TS);
        speckle(ctx, palette, seed, 30, 2);
        break;
      case "stone":
        drawStone(ctx, palette, seed);
        break;
      case "wood":
        drawWood(ctx, palette, seed);
        break;
      case "leaves":
        drawLeaves(ctx, palette, seed);
        break;
      case "sand":
        drawSand(ctx, palette, seed);
        break;
      case "planks":
        drawPlanks(ctx, palette, seed);
        break;
      case "cobble":
        drawCobble(ctx, palette, seed);
        break;
      case "coal_ore":
        drawOre(ctx, palette, seed, { base: "#2b2f36", light: "#4a5059", dark: "#14171b" });
        break;
      case "iron_ore":
        drawOre(ctx, palette, seed, { base: "#c98a63", light: "#e8c3a2", dark: "#8a5a3c" });
        break;
      case "ember_ore":
        drawOre(ctx, palette, seed, { base: "#ff8a4c", light: "#ffd27a", dark: "#b34a1f" });
        break;
      case "workbench":
        drawTable(ctx, palette, seed);
        break;
      case "furnace":
        drawFurnace(ctx, palette, seed);
        break;
      case "stone_bricks":
        drawBricks(ctx, palette, seed);
        break;
      case "beacon":
        drawBeacon(ctx, palette, seed);
        break;
      default:
        ctx.fillStyle = palette.base;
        ctx.fillRect(0, 0, TS, TS);
        speckle(ctx, palette, seed, 12, 2);
    }
  }

  function buildTextures() {
    const map = {};
    const ids = Object.keys(BLOCKS.DEFS).map(Number);
    for (let index = 0; index < ids.length; index += 1) {
      const id = ids[index];
      if (id === B.air || id === B.torch) {
        continue;
      }
      const variants = [];
      for (let v = 0; v < VARIANTS; v += 1) {
        const canvas = makeCanvas(TS, TS);
        paintTexture(canvas.getContext("2d"), id, id * 977 + v * 131);
        variants.push(canvas);
      }
      map[id] = variants;
    }
    return map;
  }

  function initTextures() {
    if (!textures) {
      textures = buildTextures();
    }
    if (!lightCanvas) {
      lightCanvas = makeCanvas(96, 64);
      lightCtx = lightCanvas.getContext("2d");
    }
    if (!iconCache) {
      iconCache = {};
    }
    return textures;
  }

  function tileVariant(x, y) {
    return Math.abs((x * 31 + y * 17) % VARIANTS);
  }

  function drawTorch(ctx, px, py, scale) {
    const s = scale || 1;
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.fillRect(px + 3 * s, py + TS - 4 * s, TS - 6 * s, 3 * s);
    ctx.fillStyle = "#6d4522";
    ctx.fillRect(px + TS / 2 - 2 * s, py + 8 * s, 4 * s, TS - 9 * s);
    ctx.fillStyle = "#3f2a14";
    ctx.fillRect(px + TS / 2 - 1 * s, py + 9 * s, 2 * s, TS - 11 * s);
    const glow = ctx.createRadialGradient(
      px + TS / 2,
      py + 7 * s,
      1,
      px + TS / 2,
      py + 7 * s,
      10 * s
    );
    glow.addColorStop(0, "rgba(255,226,150,0.95)");
    glow.addColorStop(0.4, "rgba(255,160,70,0.6)");
    glow.addColorStop(1, "rgba(255,120,40,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px, py - 4 * s, TS, TS);
    ctx.fillStyle = "#ffd88a";
    ctx.fillRect(px + TS / 2 - 2 * s, py + 5 * s, 4 * s, 4 * s);
    ctx.fillStyle = "#ff9c4a";
    ctx.fillRect(px + TS / 2 - 1 * s, py + 4 * s, 2 * s, 2 * s);
  }

  function drawTileAt(ctx, id, x, y, px, py) {
    if (id === B.air) {
      return;
    }
    if (id === B.torch) {
      drawTorch(ctx, px, py, 1);
      return;
    }
    const set = textures && textures[id];
    if (set) {
      ctx.drawImage(set[tileVariant(x, y)], px, py);
    } else {
      const def = BLOCKS.get(id);
      ctx.fillStyle = def ? def.palette.base : "#9e9e9e";
      ctx.fillRect(px, py, TS, TS);
    }
  }

  function drawItemIcon(ctx, id, size) {
    initTextures();
    const def = BLOCKS.itemDef(id);
    if (!def) {
      ctx.fillStyle = "#ff00ff";
      ctx.fillRect(0, 0, size, size);
      return;
    }
    if (def.kind === "block") {
      if (id === B.torch) {
        ctx.save();
        ctx.scale(size / TS, size / TS);
        drawTorch(ctx, 0, 0, 1);
        ctx.restore();
        return;
      }
      const set = textures[id];
      if (set) {
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(set[0], 0, 0, size, size);
        return;
      }
    }
    const pad = size * 0.14;
    const inner = size - pad * 2;
    ctx.save();
    ctx.translate(pad, pad);
    const key = def.key;
    if (key === "stick") {
      ctx.strokeStyle = "#8a6239";
      ctx.lineWidth = Math.max(2, size * 0.1);
      ctx.beginPath();
      ctx.moveTo(inner * 0.2, inner * 0.85);
      ctx.lineTo(inner * 0.8, inner * 0.15);
      ctx.stroke();
      ctx.strokeStyle = "#b98a52";
      ctx.lineWidth = Math.max(1, size * 0.05);
      ctx.beginPath();
      ctx.moveTo(inner * 0.26, inner * 0.82);
      ctx.lineTo(inner * 0.82, inner * 0.2);
      ctx.stroke();
    } else if (key === "coal") {
      ctx.fillStyle = "#1c1f24";
      ctx.beginPath();
      ctx.ellipse(inner * 0.5, inner * 0.55, inner * 0.34, inner * 0.3, 0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#3b4048";
      ctx.fillRect(inner * 0.36, inner * 0.38, inner * 0.2, inner * 0.08);
    } else if (key === "iron_ingot") {
      ctx.fillStyle = "#8f99a3";
      ctx.fillRect(inner * 0.12, inner * 0.45, inner * 0.76, inner * 0.3);
      ctx.fillStyle = "#d6dde3";
      ctx.fillRect(inner * 0.18, inner * 0.47, inner * 0.64, inner * 0.08);
      ctx.fillStyle = "#5c6771";
      ctx.fillRect(inner * 0.16, inner * 0.7, inner * 0.68, inner * 0.06);
    } else if (key === "ember_shard") {
      ctx.fillStyle = "#ff8a4c";
      ctx.beginPath();
      ctx.moveTo(inner * 0.5, inner * 0.05);
      ctx.lineTo(inner * 0.82, inner * 0.5);
      ctx.lineTo(inner * 0.55, inner * 0.95);
      ctx.lineTo(inner * 0.22, inner * 0.55);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#ffd27a";
      ctx.beginPath();
      ctx.moveTo(inner * 0.5, inner * 0.18);
      ctx.lineTo(inner * 0.65, inner * 0.5);
      ctx.lineTo(inner * 0.5, inner * 0.72);
      ctx.lineTo(inner * 0.36, inner * 0.48);
      ctx.closePath();
      ctx.fill();
    } else if (key.indexOf("pick") === 0) {
      const tier = def.tool.tier;
      const headColor = tier === 1 ? "#b98a52" : tier === 2 ? "#97a1aa" : "#e4e9ee";
      ctx.strokeStyle = "#7d5730";
      ctx.lineWidth = Math.max(2, size * 0.1);
      ctx.beginPath();
      ctx.moveTo(inner * 0.3, inner * 0.9);
      ctx.lineTo(inner * 0.7, inner * 0.3);
      ctx.stroke();
      ctx.strokeStyle = headColor;
      ctx.lineWidth = Math.max(3, size * 0.12);
      ctx.beginPath();
      ctx.moveTo(inner * 0.2, inner * 0.35);
      ctx.quadraticCurveTo(inner * 0.55, inner * 0.05, inner * 0.9, inner * 0.3);
      ctx.stroke();
    } else if (key.indexOf("sword") === 0) {
      const tier = def.tool.tier;
      const blade = tier === 1 ? "#b98a52" : tier === 2 ? "#97a1aa" : "#e4e9ee";
      ctx.strokeStyle = blade;
      ctx.lineWidth = Math.max(3, size * 0.12);
      ctx.beginPath();
      ctx.moveTo(inner * 0.3, inner * 0.8);
      ctx.lineTo(inner * 0.75, inner * 0.18);
      ctx.stroke();
      ctx.strokeStyle = "#8a6239";
      ctx.lineWidth = Math.max(2, size * 0.09);
      ctx.beginPath();
      ctx.moveTo(inner * 0.22, inner * 0.62);
      ctx.lineTo(inner * 0.46, inner * 0.86);
      ctx.stroke();
    } else {
      ctx.fillStyle = "#9e9e9e";
      ctx.fillRect(0, 0, inner, inner);
    }
    ctx.restore();
  }

  const SKY_KEYS = [
    { t: 0.0, top: [22, 30, 54], bottom: [247, 178, 103] },
    { t: 0.07, top: [110, 176, 216], bottom: [245, 230, 200] },
    { t: 0.46, top: [94, 180, 219], bottom: [216, 240, 250] },
    { t: 0.56, top: [136, 120, 168], bottom: [244, 162, 97] },
    { t: 0.64, top: [16, 22, 44], bottom: [58, 62, 105] },
    { t: 0.9, top: [8, 12, 26], bottom: [30, 42, 71] },
    { t: 0.965, top: [30, 38, 66], bottom: [224, 138, 92] },
    { t: 1.0, top: [22, 30, 54], bottom: [247, 178, 103] }
  ];

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function colorAt(time) {
    const value = ((time % 1) + 1) % 1;
    let a = SKY_KEYS[0];
    let b = SKY_KEYS[1];
    for (let i = 0; i < SKY_KEYS.length - 1; i += 1) {
      if (value >= SKY_KEYS[i].t && value <= SKY_KEYS[i + 1].t) {
        a = SKY_KEYS[i];
        b = SKY_KEYS[i + 1];
        break;
      }
    }
    const span = b.t - a.t;
    const t = span <= 0 ? 0 : (value - a.t) / span;
    const top = [
      Math.round(lerp(a.top[0], b.top[0], t)),
      Math.round(lerp(a.top[1], b.top[1], t)),
      Math.round(lerp(a.top[2], b.top[2], t))
    ];
    const bottom = [
      Math.round(lerp(a.bottom[0], b.bottom[0], t)),
      Math.round(lerp(a.bottom[1], b.bottom[1], t)),
      Math.round(lerp(a.bottom[2], b.bottom[2], t))
    ];
    return { top: top, bottom: bottom };
  }

  function rgb(arr, alpha) {
    if (alpha === undefined) {
      return "rgb(" + arr[0] + "," + arr[1] + "," + arr[2] + ")";
    }
    return "rgba(" + arr[0] + "," + arr[1] + "," + arr[2] + "," + alpha + ")";
  }

  function drawSky(ctx, state) {
    const colors = colorAt(state.time);
    const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
    gradient.addColorStop(0, rgb(colors.top));
    gradient.addColorStop(1, rgb(colors.bottom));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    const night = 1 - LIGHT.dayFactor(state.time);
    ctx.globalAlpha = Math.min(1, night * 1.4);
    for (let i = 0; i < 70; i += 1) {
      const x = (hash(i, 3, 7) * VIEW_W + state.time * 18 * (1 + (i % 3))) % VIEW_W;
      const y = hash(i, 5, 11) * VIEW_H * 0.6;
      const twinkle = 0.35 + 0.65 * Math.abs(Math.sin(state.time * 40 + i));
      ctx.fillStyle = "rgba(232,238,245," + (0.25 + twinkle * 0.5) + ")";
      const size = i % 9 === 0 ? 2 : 1;
      ctx.fillRect(Math.round(x), Math.round(y), size, size);
    }
    ctx.globalAlpha = 1;

    const angle = (state.time - 0.02) / 0.58;
    if (angle >= 0 && angle <= 1) {
      const sunX = VIEW_W * (0.08 + angle * 0.84);
      const sunY = VIEW_H * 0.58 - Math.sin(angle * Math.PI) * VIEW_H * 0.34;
      const glow = ctx.createRadialGradient(sunX, sunY, 4, sunX, sunY, 90);
      glow.addColorStop(0, "rgba(255,244,190,0.9)");
      glow.addColorStop(0.25, "rgba(255,214,120,0.35)");
      glow.addColorStop(1, "rgba(255,200,90,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(sunX - 100, sunY - 100, 200, 200);
      ctx.fillStyle = "#fff3c4";
      ctx.fillRect(sunX - 15, sunY - 15, 30, 30);
      ctx.fillStyle = "#ffe28a";
      ctx.fillRect(sunX - 10, sunY - 10, 20, 20);
    }
    const moonAngle = (state.time - 0.58) / 0.44;
    if (moonAngle >= 0 && moonAngle <= 1) {
      const moonX = VIEW_W * (0.1 + moonAngle * 0.8);
      const moonY = VIEW_H * 0.5 - Math.sin(moonAngle * Math.PI) * VIEW_H * 0.28;
      const glow = ctx.createRadialGradient(moonX, moonY, 6, moonX, moonY, 90);
      glow.addColorStop(0, "rgba(214,228,248,0.35)");
      glow.addColorStop(1, "rgba(180,200,230,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(moonX - 100, moonY - 100, 200, 200);
      ctx.fillStyle = "rgba(224,232,246,0.95)";
      ctx.fillRect(moonX - 13, moonY - 13, 26, 26);
      ctx.fillStyle = "rgba(180,192,210,0.9)";
      ctx.fillRect(moonX - 6, moonY - 4, 5, 5);
      ctx.fillRect(moonX + 2, moonY + 4, 7, 4);
    }

    // Clouds.
    const cloudAlpha = 0.35 + 0.35 * LIGHT.dayFactor(state.time);
    for (let i = 0; i < 6; i += 1) {
      const speed = 8 + (i % 3) * 4;
      const x = ((hash(i, 9, 5) * VIEW_W + state.time * speed * 60) % (VIEW_W + 260)) - 130;
      const y = 40 + hash(i, 11, 7) * VIEW_H * 0.28;
      ctx.globalAlpha = cloudAlpha;
      ctx.fillStyle = i % 2 === 0 ? "#f4fbff" : "#dcecf7";
      ctx.beginPath();
      ctx.ellipse(x, y, 64, 16, 0, 0, Math.PI * 2);
      ctx.ellipse(x + 46, y - 8, 40, 14, 0, 0, Math.PI * 2);
      ctx.ellipse(x - 42, y + 3, 34, 12, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawParallax(ctx, state) {
    const day = LIGHT.dayFactor(state.time);
    const layers = [
      { factor: 0.18, base: 0.62, height: 130, color: [36, 54, 74], step: 90 },
      { factor: 0.32, base: 0.7, height: 170, color: [30, 46, 62], step: 70 },
      { factor: 0.46, base: 0.8, height: 210, color: [24, 38, 52], step: 52 }
    ];
    for (let l = 0; l < layers.length; l += 1) {
      const layer = layers[l];
      const offset = state.camera.x * layer.factor;
      const color = layer.color;
      const tint = 0.55 + day * 0.45;
      ctx.fillStyle =
        "rgba(" +
        Math.round(color[0] * tint) +
        "," +
        Math.round(color[1] * tint) +
        "," +
        Math.round(color[2] * tint) +
        ",0.95)";
      ctx.beginPath();
      ctx.moveTo(0, VIEW_H);
      const width = VIEW_W + 200;
      for (let x = 0; x <= width; x += 8) {
        const worldX = x + offset;
        const wobble =
          Math.sin(worldX / layer.step) * 24 +
          Math.sin(worldX / (layer.step * 0.37) + l) * 14 +
          Math.sin(worldX / 19 + l * 2) * 4;
        const y = VIEW_H * layer.base - layer.height * 0.35 - wobble;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(width, VIEW_H);
      ctx.closePath();
      ctx.fill();
    }
  }

  function drawCaveBackdrop(ctx, state, firstCol, lastCol) {
    const ts = TS;
    const camera = state.camera;
    const world = state.world;
    for (let x = firstCol; x <= lastCol; x += 1) {
      // Fill below the terrain surface, not below the first solid tile: a tree
      // canopy or trunk must not turn the open air beneath it into cave wall.
      let top = world.height;
      for (let y = 0; y < world.height; y += 1) {
        const id = world.data[y * world.width + x];
        if (id !== B.air && id !== B.leaves && id !== B.wood) {
          top = y;
          break;
        }
      }
      const px = Math.round(x * ts - camera.x);
      const py = Math.round(top * ts - camera.y);
      if (py > VIEW_H) {
        continue;
      }
      const gradient = ctx.createLinearGradient(0, py, 0, VIEW_H);
      gradient.addColorStop(0, "rgba(24,26,32,0.96)");
      gradient.addColorStop(0.5, "rgba(14,15,20,0.98)");
      gradient.addColorStop(1, "rgba(6,7,10,1)");
      ctx.fillStyle = gradient;
      ctx.fillRect(px, Math.max(py, 0), ts + 1, VIEW_H - Math.max(py, 0));
    }
  }

  function drawWorld(ctx, state) {
    initTextures();
    const camera = state.camera;
    const world = state.world;
    const ts = TS;
    const firstCol = Math.max(0, Math.floor(camera.x / ts) - 1);
    const lastCol = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / ts) + 1);
    const firstRow = Math.max(0, Math.floor(camera.y / ts) - 1);
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + VIEW_H) / ts) + 1);

    drawCaveBackdrop(ctx, state, firstCol, lastCol);

    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstCol; x <= lastCol; x += 1) {
        const id = world.data[y * world.width + x];
        if (id === B.air) {
          // A block the player removed gets a dark back wall, so a dug pocket
          // reads as a hole rather than as sky seen through a glass tile.
          if (state.dug && state.dug.has(x + "," + y)) {
            const px = Math.round(x * ts - camera.x);
            const py = Math.round(y * ts - camera.y);
            ctx.fillStyle = "#15171d";
            ctx.fillRect(px, py, ts, ts);
          }
          continue;
        }
        const px = Math.round(x * ts - camera.x);
        const py = Math.round(y * ts - camera.y);
        drawTileAt(ctx, id, x, y, px, py);
      }
    }
  }

  function drawLight(ctx, state, firstCol, lastCol, firstRow, lastRow) {
    if (!state.light) {
      return;
    }
    const light = state.light;
    const width = Math.max(1, light.width);
    const height = Math.max(1, light.height);
    if (!lightCtx) {
      return;
    }
    if (lightCanvas.width !== width || lightCanvas.height !== height) {
      lightCanvas.width = width;
      lightCanvas.height = height;
      lightCtx = lightCanvas.getContext("2d");
    }
    const image = lightCtx.createImageData(width, height);
    const topByColumn = new Int16Array(width);
    for (let gx = 0; gx < width; gx += 1) {
      const x = light.x0 + gx;
      let top = light.y1 + 1;
      for (let y = 0; y <= light.y1; y += 1) {
        const block = state.world.data[y * state.world.width + x];
        if (block !== B.air && block !== B.wood && block !== B.leaves) {
          top = y;
          break;
        }
      }
      topByColumn[gx] = top;
    }
    for (let gy = 0; gy < height; gy += 1) {
      for (let gx = 0; gx < width; gx += 1) {
        const index = (gy * width + gx) * 4;
        const worldY = light.y0 + gy;
        const openSky = worldY < topByColumn[gx];
        if (openSky) {
          image.data[index + 3] = 0;
          continue;
        }
        const value = light.data[gy * width + gx];
        const darkness = Math.max(0, Math.min(1, 1 - value / LIGHT.MAX_LIGHT));
        image.data[index] = 4;
        image.data[index + 1] = 6;
        image.data[index + 2] = 12;
        image.data[index + 3] = Math.round(6 + darkness * 228);
      }
    }
    lightCtx.putImageData(image, 0, 0);
    const ts = TS;
    const px = Math.round(light.x0 * ts - state.camera.x);
    const py = Math.round(light.y0 * ts - state.camera.y);
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(lightCanvas, px, py, width * ts, height * ts);
    ctx.restore();
  }

  function drawTorchGlow(ctx, state, firstCol, lastCol, firstRow, lastRow) {
    const world = state.world;
    const ts = TS;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let y = Math.max(0, firstRow - 1); y <= Math.min(world.height - 1, lastRow + 1); y += 1) {
      for (let x = Math.max(0, firstCol - 1); x <= Math.min(world.width - 1, lastCol + 1); x += 1) {
        const id = world.data[y * world.width + x];
        if (id !== B.torch && id !== B.beacon) {
          continue;
        }
        const px = x * ts - state.camera.x + ts / 2;
        const py = y * ts - state.camera.y + ts / 2;
        const radius = id === B.beacon ? 150 : 80;
        const gradient = ctx.createRadialGradient(px, py, 1, px, py, radius);
        gradient.addColorStop(0, id === B.beacon ? "rgba(255,190,110,0.35)" : "rgba(255,170,80,0.22)");
        gradient.addColorStop(1, "rgba(255,140,40,0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(px - radius, py - radius, radius * 2, radius * 2);
      }
    }
    ctx.restore();
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const ts = TS;
    const px = player.x * ts - state.camera.x;
    const py = player.y * ts - state.camera.y;
    const width = player.width * ts;
    const height = player.height * ts;
    const facing = player.facing >= 0 ? 1 : -1;
    const walk = Math.sin(player.walkPhase || 0) * 4;
    const flash = player.invuln > 0 && Math.floor(player.invuln * 18) % 2 === 0;

    ctx.save();
    ctx.globalAlpha = 0.28;
    ctx.fillStyle = "#000";
    ctx.beginPath();
    ctx.ellipse(px, py + 2, width * 0.55, 4, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(px, py);
    ctx.scale(facing, 1);
    if (flash) {
      ctx.globalAlpha = 0.55;
    }
    const legY = -height * 0.34;
    ctx.fillStyle = "#2c3e50";
    ctx.fillRect(-width * 0.42 + walk, legY, width * 0.32, height * 0.34);
    ctx.fillRect(width * 0.1 - walk, legY, width * 0.32, height * 0.34);
    ctx.fillStyle = "#1a252f";
    ctx.fillRect(-width * 0.42 + walk, -height * 0.06, width * 0.34, height * 0.06);
    ctx.fillRect(width * 0.1 - walk, -height * 0.06, width * 0.34, height * 0.06);

    ctx.fillStyle = "#3f5f7d";
    ctx.fillRect(-width * 0.44, -height * 0.72, width * 0.88, height * 0.4);
    ctx.fillStyle = "#4f7392";
    ctx.fillRect(-width * 0.44, -height * 0.72, width * 0.88, height * 0.08);
    ctx.fillStyle = "#2f4a63";
    ctx.fillRect(-width * 0.44, -height * 0.36, width * 0.88, height * 0.05);

    const headY = -height * 0.94;
    const headSize = width * 0.78;
    ctx.fillStyle = "#f0c090";
    ctx.fillRect(-headSize / 2, headY, headSize, height * 0.24);
    ctx.fillStyle = "#3b2a1e";
    ctx.fillRect(-headSize / 2, headY - 3, headSize, 5);
    ctx.fillRect(-headSize / 2, headY, 3, height * 0.16);
    ctx.fillStyle = "#1d1b1a";
    ctx.fillRect(headSize * 0.08, headY + height * 0.09, 3, 3);
    ctx.fillStyle = "#c98a63";
    ctx.fillRect(headSize * 0.16, headY + height * 0.16, 4, 2);

    // Arm and held tool.
    ctx.fillStyle = "#e2b083";
    ctx.fillRect(width * 0.3, -height * 0.66, width * 0.18, height * 0.24);
    if (state.heldItem) {
      ctx.save();
      ctx.translate(width * 0.5, -height * 0.6);
      ctx.rotate(-0.32);
      drawItemIcon(ctx, state.heldItem, 16);
      ctx.restore();
    }
    ctx.restore();
  }

  function drawMobs(ctx, state) {
    const ts = TS;
    const mobs = state.mobs ? state.mobs.list : [];
    for (let i = 0; i < mobs.length; i += 1) {
      const mob = mobs[i];
      const px = mob.x * ts - state.camera.x;
      const py = mob.y * ts - state.camera.y;
      const width = mob.width * ts;
      const height = mob.height * ts;
      const bob = Math.sin((state.clockSeconds || 0) * 3 + i) * 2;
      ctx.save();
      ctx.globalAlpha = 0.3;
      ctx.fillStyle = "#000";
      ctx.beginPath();
      ctx.ellipse(px, py + 1, width * 0.5, 3, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.translate(px, py + bob);
      if (mob.hurt > 0) {
        ctx.globalAlpha = 0.85;
      }
      ctx.fillStyle = mob.hurt > 0 ? "#f5e9d8" : "#1a1d27";
      ctx.beginPath();
      ctx.moveTo(-width * 0.4, 0);
      ctx.quadraticCurveTo(-width * 0.55, -height * 0.75, 0, -height);
      ctx.quadraticCurveTo(width * 0.55, -height * 0.75, width * 0.4, 0);
      ctx.quadraticCurveTo(0, -height * 0.12, -width * 0.4, 0);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = mob.hurt > 0 ? "#ffd27a" : "#ff8a4c";
      ctx.fillRect(-width * 0.22, -height * 0.76, 5, 5);
      ctx.fillRect(width * 0.08, -height * 0.76, 5, 5);
      ctx.fillStyle = "rgba(255,138,76,0.25)";
      ctx.fillRect(-width * 0.3, -height * 0.6, width * 0.6, 3);
      ctx.restore();
    }
  }

  function drawParticles(ctx, state) {
    const ts = TS;
    const particles = state.particles || [];
    for (let i = 0; i < particles.length; i += 1) {
      const particle = particles[i];
      const px = particle.x * ts - state.camera.x;
      const py = particle.y * ts - state.camera.y;
      const alpha = Math.max(0, particle.life / particle.maxLife);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = particle.color;
      const size = particle.size || 3;
      ctx.fillRect(Math.round(px), Math.round(py), size, size);
    }
    ctx.globalAlpha = 1;
  }

  function drawTarget(ctx, state) {
    if (!state.pointer || !state.pointer.valid) {
      return;
    }
    const ts = TS;
    const tile = state.pointer;
    const px = tile.tx * ts - state.camera.x;
    const py = tile.ty * ts - state.camera.y;
    if (px < -ts || py < -ts || px > VIEW_W || py > VIEW_H) {
      return;
    }
    const mining = state.mining;
    if (state.placeValid) {
      const ghostId = state.placeBlockId;
      ctx.save();
      ctx.globalAlpha = 0.45;
      drawTileAt(ctx, ghostId, tile.tx, tile.ty, px, py);
      ctx.restore();
      ctx.strokeStyle = "rgba(126,224,164,0.9)";
    } else {
      ctx.strokeStyle = "rgba(232,182,98,0.75)";
    }
    ctx.lineWidth = 2;
    ctx.strokeRect(px + 1, py + 1, ts - 2, ts - 2);

    if (mining && mining.tx === tile.tx && mining.ty === tile.ty && mining.fraction > 0) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(px, py, ts, ts);
      ctx.clip();
      ctx.strokeStyle = "rgba(10,12,16,0.85)";
      ctx.lineWidth = 2;
      const cracks = Math.max(1, Math.floor(mining.fraction * 5));
      for (let i = 0; i < cracks; i += 1) {
        const startX = px + hash(i, tile.tx, 3) * ts;
        const startY = py + hash(i, tile.ty, 7) * ts;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(startX + (hash(i, 5, 9) - 0.5) * 18, startY + (hash(i, 11, 13) - 0.5) * 18);
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  function drawVignette(ctx, state) {
    const gradient = ctx.createRadialGradient(
      VIEW_W / 2,
      VIEW_H / 2,
      VIEW_H * 0.32,
      VIEW_W / 2,
      VIEW_H / 2,
      VIEW_H * 0.85
    );
    gradient.addColorStop(0, "rgba(0,0,0,0)");
    gradient.addColorStop(1, "rgba(2,4,8,0.55)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    if (state.hurtFlash > 0) {
      ctx.fillStyle = "rgba(180,30,30," + Math.min(0.5, state.hurtFlash * 0.5) + ")";
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }
    if (state.pausedTint) {
      ctx.fillStyle = "rgba(4,7,12,0.55)";
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }
  }

  function drawFog(ctx, state) {
    const day = LIGHT.dayFactor(state.time);
    const alpha = 0.12 + (1 - day) * 0.1;
    const gradient = ctx.createLinearGradient(0, VIEW_H * 0.45, 0, VIEW_H);
    gradient.addColorStop(0, "rgba(180,210,230,0)");
    gradient.addColorStop(1, "rgba(180,210,230," + alpha + ")");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, VIEW_H * 0.45, VIEW_W, VIEW_H * 0.55);
  }

  function renderFrame(ctx, state) {
    initTextures();
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, VIEW_W, VIEW_H);
    drawSky(ctx, state);
    drawParallax(ctx, state);
    drawFog(ctx, state);
    drawWorld(ctx, state);

    const ts = TS;
    const firstCol = Math.max(0, Math.floor(state.camera.x / ts) - 1);
    const lastCol = Math.min(state.world.width - 1, Math.ceil((state.camera.x + VIEW_W) / ts) + 1);
    const firstRow = Math.max(0, Math.floor(state.camera.y / ts) - 1);
    const lastRow = Math.min(state.world.height - 1, Math.ceil((state.camera.y + VIEW_H) / ts) + 1);

    drawLight(ctx, state, firstCol, lastCol, firstRow, lastRow);
    drawTorchGlow(ctx, state, firstCol, lastCol, firstRow, lastRow);
    drawMobs(ctx, state);
    if (!state.player.dead) {
      drawPlayer(ctx, state);
    }
    drawParticles(ctx, state);
    drawTarget(ctx, state);
    drawVignette(ctx, state);

    const beacon = state.beaconGlow;
    if (beacon) {
      const px = beacon.x * ts - state.camera.x;
      const py = beacon.y * ts - state.camera.y;
      const glow = ctx.createRadialGradient(px, py, 2, px, py, 220);
      glow.addColorStop(0, "rgba(255,214,140,0.35)");
      glow.addColorStop(1, "rgba(255,150,70,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(px - 220, py - 220, 440, 440);
    }
  }

  function createParticles() {
    return [];
  }

  function spawnParticles(particles, tileX, tileY, color, count) {
    const total = count || 8;
    for (let i = 0; i < total; i += 1) {
      particles.push({
        x: tileX + 0.1 + Math.random() * 0.8,
        y: tileY + 0.1 + Math.random() * 0.8,
        vx: (Math.random() - 0.5) * 3.5,
        vy: -Math.random() * 3.2 - 0.6,
        life: 0.4 + Math.random() * 0.5,
        maxLife: 0.9,
        color: color || "#c9b47a",
        size: 2 + Math.floor(Math.random() * 3)
      });
    }
  }

  function spawnStep(particles, x, y, facing) {
    particles.push({
      x: x + 0.2 * facing,
      y: y - 0.05,
      vx: -facing * 0.6 + (Math.random() - 0.5) * 0.4,
      vy: -0.4 - Math.random() * 0.5,
      life: 0.35,
      maxLife: 0.35,
      color: "rgba(200,190,160,0.85)",
      size: 2
    });
  }

  function updateParticles(particles, dt) {
    for (let i = particles.length - 1; i >= 0; i -= 1) {
      const particle = particles[i];
      particle.life -= dt;
      if (particle.life <= 0) {
        particles.splice(i, 1);
        continue;
      }
      particle.vy += 14 * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      if (particle.y > CONFIG.worldHeight) {
        particles.splice(i, 1);
      }
    }
  }

  return {
    initTextures: initTextures,
    drawItemIcon: drawItemIcon,
    drawTileAt: drawTileAt,
    renderFrame: renderFrame,
    createParticles: createParticles,
    spawnParticles: spawnParticles,
    spawnStep: spawnStep,
    updateParticles: updateParticles
  };
});
