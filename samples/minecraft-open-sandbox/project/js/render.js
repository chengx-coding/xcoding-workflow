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
  let VIEW_W = CONFIG.viewWidth;
  let VIEW_H = CONFIG.viewHeight;
  const VARIANTS = 4;
  const MAX_LIGHT = LIGHT.MAX_LIGHT;

  let textures = null;
  let edges = null;
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

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function shade(hex, amount) {
    const value = parseInt(hex.slice(1), 16);
    const r = clamp(((value >> 16) & 255) + amount, 0, 255);
    const g = clamp(((value >> 8) & 255) + amount, 0, 255);
    const b = clamp((value & 255) + amount, 0, 255);
    return "rgb(" + r + "," + g + "," + b + ")";
  }

  function speckle(ctx, palette, seed, count, size) {
    for (let i = 0; i < count; i += 1) {
      const x = Math.floor(hash(i, seed, 11) * TS);
      const y = Math.floor(hash(i, seed, 29) * TS);
      const tone = hash(i, seed, 47) > 0.5 ? palette.light : palette.dark;
      ctx.fillStyle = tone;
      ctx.globalAlpha = 0.24 + hash(i, seed, 71) * 0.4;
      const s = size || 2;
      ctx.fillRect(x, y, s, s);
    }
    ctx.globalAlpha = 1;
  }

  /* ------------------------------------------------------------------ */
  /* Block textures                                                      */
  /* ------------------------------------------------------------------ */

  function drawGrass(ctx, palette, seed) {
    const soil = palette.accent;
    ctx.fillStyle = soil;
    ctx.fillRect(0, 0, TS, TS);
    // Soil grit under the green cap.
    for (let i = 0; i < 16; i += 1) {
      const x = Math.floor(hash(i, seed, 131) * TS);
      const y = 7 + Math.floor(hash(i, seed, 137) * (TS - 8));
      ctx.fillStyle = hash(i, seed, 139) > 0.5 ? shade(soil, 14) : shade(soil, -16);
      ctx.globalAlpha = 0.55;
      ctx.fillRect(x, y, 2 + (i % 2), 1 + (i % 2));
    }
    ctx.globalAlpha = 1;

    // A jagged grass cap, so the top edge is not a ruler line.
    for (let x = 0; x < TS; x += 2) {
      const depth = 4 + Math.floor(hash(x, seed, 143) * 4);
      ctx.fillStyle = palette.base;
      ctx.fillRect(x, 0, 2, depth);
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.45;
      ctx.fillRect(x, depth, 2, 2);
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = palette.light;
    ctx.fillRect(0, 0, TS, 2);
    ctx.globalAlpha = 0.55;
    ctx.fillRect(0, 2, TS, 1);
    ctx.globalAlpha = 1;

    // Blades and clumps.
    for (let x = 1; x < TS; x += 3) {
      if (hash(x, seed, 151) > 0.52) {
        const h = 2 + Math.floor(hash(x, seed, 157) * 3);
        ctx.fillStyle = palette.light;
        ctx.fillRect(x, 2 - h + 2, 1, h);
      }
    }
    for (let i = 0; i < 7; i += 1) {
      const x = Math.floor(hash(i, seed, 163) * TS);
      const y = 3 + Math.floor(hash(i, seed, 167) * 3);
      ctx.fillStyle = hash(i, seed, 173) > 0.4 ? palette.light : palette.dark;
      ctx.globalAlpha = 0.4;
      ctx.fillRect(x, y, 2, 1);
    }
    ctx.globalAlpha = 1;

    // A rare flower keeps a meadow tile from reading as a green stamp.
    if (hash(seed, 7, 181) > 0.72) {
      const fx = 4 + Math.floor(hash(seed, 9, 191) * (TS - 9));
      const fy = 2 + Math.floor(hash(seed, 11, 193) * 3);
      ctx.fillStyle = palette.dark;
      ctx.fillRect(fx, fy + 2, 1, 4);
      ctx.fillStyle = hash(seed, 13, 197) > 0.5 ? "#f6f0cf" : "#f2d277";
      ctx.fillRect(fx - 1, fy, 3, 2);
      ctx.fillStyle = "#e0a64d";
      ctx.fillRect(fx, fy, 1, 1);
    }
  }

  function drawDirt(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 26, 2);
    for (let i = 0; i < 5; i += 1) {
      const x = 2 + Math.floor(hash(i, seed, 211) * (TS - 8));
      const y = 2 + Math.floor(hash(i, seed, 217) * (TS - 8));
      const w = 3 + Math.floor(hash(i, seed, 223) * 3);
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.7;
      ctx.fillRect(x, y, w, 2);
      ctx.fillStyle = palette.light;
      ctx.globalAlpha = 0.4;
      ctx.fillRect(x + 1, y - 1, w - 2, 1);
    }
    ctx.globalAlpha = 1;
  }

  function drawStone(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    // Broad mottling first, grit second.
    for (let i = 0; i < 5; i += 1) {
      const x = Math.floor(hash(i, seed, 231) * TS) - 4;
      const y = Math.floor(hash(i, seed, 233) * TS) - 3;
      ctx.fillStyle = hash(i, seed, 237) > 0.5 ? palette.light : palette.dark;
      ctx.globalAlpha = 0.22;
      ctx.fillRect(x, y, 7 + (i % 3) * 3, 4 + (i % 2) * 2);
    }
    ctx.globalAlpha = 1;
    speckle(ctx, palette, seed, 22, 2);

    // Bedding lines.
    ctx.strokeStyle = palette.dark;
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = 1;
    for (let i = 0; i < 3; i += 1) {
      const y = 3 + Math.floor(hash(i, seed, 241) * (TS - 6));
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(TS, y + (hash(i, seed, 247) > 0.5 ? 1 : -1));
      ctx.stroke();
    }
    // Cracks.
    for (let i = 0; i < 2; i += 1) {
      const x = Math.floor(hash(i, seed, 251) * TS);
      const y = Math.floor(hash(i, seed, 257) * TS);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 3, y + 2);
      ctx.lineTo(x + 5, y + 6);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.light;
    ctx.globalAlpha = 0.3;
    ctx.fillRect(1, 1, TS - 2, 1);
    ctx.globalAlpha = 1;
  }

  function drawOreHost(ctx, palette, seed) {
    // A quieter host: broad mineral mottles and two fissures, not the dense
    // grit of the plain stone tile, so the ore cells own the silhouette.
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let i = 0; i < 5; i += 1) {
      const x = -2 + Math.floor(hash(i, seed, 521) * TS);
      const y = -2 + Math.floor(hash(i, seed, 523) * TS);
      const w = 5 + Math.floor(hash(i, seed, 527) * 6);
      const h = 4 + Math.floor(hash(i, seed, 529) * 5);
      ctx.fillStyle = i % 2 === 0 ? palette.light : palette.dark;
      ctx.globalAlpha = 0.1 + hash(i, seed, 531) * 0.07;
      ctx.fillRect(x, y, w, h);
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = palette.dark;
    ctx.globalAlpha = 0.28;
    ctx.lineWidth = 1;
    for (let i = 0; i < 2; i += 1) {
      const x = 2 + Math.floor(hash(i, seed, 533) * (TS - 8));
      const y = 2 + Math.floor(hash(i, seed, 535) * (TS - 8));
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 4, y + 2);
      ctx.lineTo(x + 6, y + 7);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.light;
    ctx.globalAlpha = 0.18;
    ctx.fillRect(0, 0, TS, 1);
    ctx.globalAlpha = 1;
  }

  function oreCells(seed) {
    const slots = [
      [3, 3],
      [13, 2],
      [2, 12],
      [12, 12],
      [7, 8]
    ];
    const start = Math.floor(hash(seed, 5, 541) * slots.length);
    const count = 4 + (hash(seed, 7, 547) > 0.52 ? 1 : 0);
    const cells = [];
    for (let i = 0; i < count; i += 1) {
      const slot = slots[(start + i) % slots.length];
      const x = slot[0] + Math.floor(hash(seed, i, 551) * 2);
      const y = slot[1] + Math.floor(hash(seed, i, 557) * 2);
      const w = 5 + Math.floor(hash(seed, i, 559) * 3);
      const h = 4 + Math.floor(hash(seed, i, 563) * 3);
      // A second overlapping lobe makes a chunky nugget silhouette; an offset
      // tail would read as a keyhole at 24 px.
      const extra = i % 2 === 0
        ? [x - 1, y + 1, 3 + Math.floor(hash(seed, i, 569) * 2), 2 + Math.floor(hash(seed, i, 573) * 2)]
        : [x + w - 2, y - 1, 2 + Math.floor(hash(seed, i, 571) * 2), 3 + Math.floor(hash(seed, i, 575) * 2)];
      cells.push({
        rects: [[x, y, w, h], extra],
        cx: x + w / 2,
        cy: y + h / 2
      });
    }
    return cells;
  }

  function drawOre(ctx, palette, seed, colors) {
    const cells = oreCells(seed);
    drawOreHost(ctx, palette, seed);

    // A small warm halo only around ember cells; never a full-tile bloom, so
    // hollows stay the darkest thing in a cave.
    if (colors.glow) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (let i = 0; i < cells.length; i += 1) {
        const cell = cells[i];
        const glow = ctx.createRadialGradient(cell.cx, cell.cy, 1, cell.cx, cell.cy, 10);
        glow.addColorStop(0, "rgba(255, 122, 46, 0.2)");
        glow.addColorStop(1, "rgba(255, 100, 30, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(cell.cx - 10, cell.cy - 10, 20, 20);
      }
      ctx.restore();
    }

    for (let i = 0; i < cells.length; i += 1) {
      const cell = cells[i];
      const rects = cell.rects;

      // 1 px dark encasement around the union of both cell rectangles.
      ctx.fillStyle = colors.dark;
      ctx.beginPath();
      for (let r = 0; r < rects.length; r += 1) {
        const rect = rects[r];
        ctx.rect(rect[0] - 1, rect[1] - 1, rect[2] + 2, rect[3] + 2);
      }
      ctx.fill();

      // Mineral body.
      ctx.fillStyle = colors.base;
      ctx.beginPath();
      for (let r = 0; r < rects.length; r += 1) {
        const rect = rects[r];
        ctx.rect(rect[0], rect[1], rect[2], rect[3]);
      }
      ctx.fill();

      // 1 px top/left glint traces the outer silhouette, including whichever
      // lobe is highest or leftmost.
      ctx.fillStyle = colors.light;
      const first = rects[0];
      const second = rects[1];
      const top = second[1] < first[1] ? second : first;
      const left = second[0] < first[0] ? second : first;
      ctx.fillRect(top[0] + 1, top[1] + 1, Math.max(1, top[2] - 2), 1);
      ctx.fillRect(left[0] + 1, left[1] + 1, 1, Math.max(1, left[3] - 2));
      if (hash(seed, i, 577) > 0.4) {
        ctx.fillRect(first[0] + first[2] - 2, first[1] + 1, 1, 1);
      }
    }

    if (colors.glow) {
      ctx.fillStyle = "rgba(255, 247, 214, 0.95)";
      for (let i = 0; i < 2; i += 1) {
        const cell = cells[i];
        ctx.fillRect(Math.floor(cell.cx), Math.floor(cell.cy), 1, 1);
      }
    }
  }

  function drawWood(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let x = 0; x < TS; x += 4) {
      ctx.fillStyle = x % 8 === 0 ? palette.dark : palette.light;
      ctx.globalAlpha = 0.38;
      ctx.fillRect(x, 0, 1, TS);
    }
    ctx.globalAlpha = 1;
    // Bark ridges.
    for (let i = 0; i < 4; i += 1) {
      const x = 2 + Math.floor(hash(i, seed, 263) * (TS - 5));
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.55;
      ctx.fillRect(x, 2 + (i % 2) * 2, 2, TS - 5 - (i % 2) * 3);
    }
    ctx.globalAlpha = 1;
    // A knot.
    const kx = 4 + Math.floor(hash(seed, 3, 269) * 8);
    const ky = 5 + Math.floor(hash(seed, 5, 271) * 9);
    ctx.fillStyle = palette.dark;
    ctx.fillRect(kx, ky, 6, 7);
    ctx.fillStyle = shade(palette.light, 18);
    ctx.fillRect(kx + 1, ky + 1, 4, 5);
    ctx.fillStyle = palette.accent;
    ctx.fillRect(kx + 2, ky + 2, 2, 3);
    ctx.fillStyle = palette.light;
    ctx.globalAlpha = 0.35;
    ctx.fillRect(0, 0, 1, TS);
    ctx.globalAlpha = 1;
  }

  function drawLeaves(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let i = 0; i < 8; i += 1) {
      const x = Math.floor(hash(i, seed, 277) * (TS - 4));
      const y = Math.floor(hash(i, seed, 281) * (TS - 4));
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.45;
      ctx.fillRect(x, y, 3 + (i % 2), 2 + (i % 2));
    }
    ctx.globalAlpha = 1;
    speckle(ctx, palette, seed, 30, 2);
    for (let i = 0; i < 9; i += 1) {
      const x = Math.floor(hash(i, seed, 283) * (TS - 3));
      const y = Math.floor(hash(i, seed, 293) * (TS - 3));
      ctx.fillStyle = hash(i, seed, 307) > 0.75 ? shade(palette.light, 14) : palette.light;
      ctx.fillRect(x, y, 2, 2);
    }
    // Leaf-scale leaf shapes.
    for (let i = 0; i < 4; i += 1) {
      const x = 3 + Math.floor(hash(i, seed, 311) * (TS - 8));
      const y = 3 + Math.floor(hash(i, seed, 313) * (TS - 8));
      ctx.strokeStyle = palette.dark;
      ctx.globalAlpha = 0.55;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + 3, y + 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function drawSand(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    speckle(ctx, palette, seed, 28, 2);
    for (let band = 0; band < 3; band += 1) {
      const y = 5 + band * 7 + Math.floor(hash(band, seed, 317) * 3);
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.22;
      for (let x = 0; x < TS; x += 4) {
        const yy = y + Math.round(Math.sin((x + seed * 0.3) / 4) * 1);
        ctx.fillRect(x, yy, 3, 1);
      }
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.light;
    for (let i = 0; i < 7; i += 1) {
      const x = Math.floor(hash(i, seed, 331) * TS);
      const y = Math.floor(hash(i, seed, 337) * TS);
      ctx.fillRect(x, y, 2, 1);
    }
  }

  function drawPlanks(ctx, palette, seed) {
    ctx.fillStyle = palette.base;
    ctx.fillRect(0, 0, TS, TS);
    for (let row = 0; row < 4; row += 1) {
      const y = row * 6;
      ctx.fillStyle = shade(palette.base, row % 2 === 0 ? 7 : -5);
      ctx.fillRect(0, y, TS, 5);
      ctx.fillStyle = palette.dark;
      ctx.fillRect(0, y + 5, TS, 1);
      // Grain.
      for (let x = 2; x < TS; x += 5) {
        ctx.fillStyle = palette.accent;
        ctx.globalAlpha = 0.35;
        ctx.fillRect(x, y + 2, 2 + (x % 3), 1);
      }
      ctx.globalAlpha = 1;
      // Board seam, staggered per row.
      const seam = 4 + ((row * 9) % (TS - 8));
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.7;
      ctx.fillRect(seam, y, 1, 5);
      ctx.globalAlpha = 1;
      // Nails.
      ctx.fillStyle = palette.dark;
      ctx.fillRect(1, y + 1, 1, 1);
      ctx.fillRect(TS - 2, y + 3, 1, 1);
      ctx.fillStyle = palette.light;
      ctx.fillRect(2, y + 1, 1, 1);
    }
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
      const jx = Math.floor(hash(i, seed, 347) * 2);
      const jy = Math.floor(hash(i, seed, 349) * 2);
      ctx.fillStyle = i % 2 === 0 ? palette.base : shade(palette.base, -10);
      ctx.fillRect(cell[0] + jx, cell[1] + jy, cell[2] - 1, cell[3] - 1);
      ctx.fillStyle = palette.light;
      ctx.globalAlpha = 0.34;
      ctx.fillRect(cell[0] + jx, cell[1] + jy, cell[2] - 2, 1);
      ctx.globalAlpha = 1;
      ctx.fillStyle = palette.dark;
      ctx.globalAlpha = 0.5;
      ctx.fillRect(cell[0] + jx, cell[1] + jy + cell[3] - 2, cell[2] - 2, 1);
      ctx.globalAlpha = 1;
    }
    speckle(ctx, palette, seed, 10, 1);
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
        ctx.globalAlpha = 0.38;
        ctx.fillRect(x, y, 10, 1);
        ctx.globalAlpha = 1;
        ctx.fillStyle = palette.dark;
        ctx.globalAlpha = 0.55;
        ctx.fillRect(x, y + 5, 10, 1);
        ctx.globalAlpha = 1;
        if (hash(row, col + 2, seed) > 0.7) {
          ctx.fillStyle = palette.accent;
          ctx.fillRect(x + 4, y + 3, 2, 1);
        }
      }
    }
    speckle(ctx, palette, seed, 6, 1);
  }

  function drawTable(ctx, palette, seed) {
    drawPlanks(ctx, palette, seed);
    ctx.fillStyle = palette.light;
    ctx.fillRect(0, 0, TS, 5);
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 5, TS, 2);
    ctx.fillStyle = palette.accent;
    ctx.fillRect(0, 7, TS, 1);
    // A saw and a square on the bench top.
    ctx.fillStyle = "#d7dde2";
    ctx.fillRect(3, 9, 7, 2);
    ctx.fillStyle = "#8f99a3";
    ctx.fillRect(4, 11, 5, 1);
    ctx.fillStyle = "#f0d9a2";
    ctx.fillRect(15, 9, 5, 5);
    ctx.fillStyle = "#8a6239";
    ctx.fillRect(15, 14, 5, 1);
    ctx.fillStyle = shade(palette.light, 22);
    ctx.fillRect(2, 3, 3, 1);
  }

  function drawFurnace(ctx, palette, seed) {
    drawStone(ctx, palette, seed);
    ctx.fillStyle = "#20232a";
    ctx.fillRect(4, 8, TS - 8, TS - 11);
    ctx.fillStyle = "#3b2d24";
    ctx.fillRect(6, 10, TS - 12, TS - 15);
    // Grate.
    ctx.fillStyle = "#171a20";
    for (let x = 7; x < TS - 6; x += 3) {
      ctx.fillRect(x, 11, 1, TS - 19);
    }
    const glow = ctx.createRadialGradient(TS / 2, 17, 1, TS / 2, 17, 12);
    glow.addColorStop(0, "rgba(255, 238, 170, 0.95)");
    glow.addColorStop(0.45, "rgba(255, 150, 60, 0.75)");
    glow.addColorStop(1, "rgba(255, 100, 30, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(3, 8, TS - 6, TS - 10);
    ctx.fillStyle = "#ffcb6a";
    ctx.fillRect(8, 14, TS - 16, 2);
    ctx.fillStyle = "#ff8a3c";
    ctx.fillRect(10, 16, TS - 20, 2);
    ctx.fillStyle = palette.light;
    ctx.fillRect(3, 3, TS - 6, 2);
    ctx.fillStyle = palette.dark;
    ctx.fillRect(3, 6, TS - 6, 1);
  }

  function drawBeacon(ctx, palette, seed) {
    ctx.fillStyle = palette.dark;
    ctx.fillRect(0, 0, TS, TS);
    ctx.fillStyle = palette.base;
    ctx.fillRect(2, 2, TS - 4, TS - 4);
    const gradient = ctx.createRadialGradient(TS / 2, TS / 2, 1, TS / 2, TS / 2, TS / 2);
    gradient.addColorStop(0, "#fff3c2");
    gradient.addColorStop(0.32, palette.light);
    gradient.addColorStop(0.7, palette.accent);
    gradient.addColorStop(1, "rgba(255,138,76,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(2, 2, TS - 4, TS - 4);
    // Runed frame.
    ctx.strokeStyle = palette.accent;
    ctx.globalAlpha = 0.6;
    ctx.strokeRect(4, 4, TS - 8, TS - 8);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#ffe9b0";
    ctx.fillRect(TS / 2 - 2, TS / 2 - 2, 4, 4);
    ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
    ctx.fillRect(TS / 2 - 1, TS / 2 - 1, 2, 2);
    ctx.fillStyle = "rgba(255, 205, 130, 0.55)";
    ctx.fillRect(4, TS / 2 - 1, 2, 2);
    ctx.fillRect(TS - 6, TS / 2 - 1, 2, 2);
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
        drawDirt(ctx, palette, seed);
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
        drawOre(ctx, palette, seed, { base: "#414b56", light: "#c7d3df", dark: "#05070a", glow: false });
        break;
      case "iron_ore":
        drawOre(ctx, palette, seed, { base: "#e0a987", light: "#fff6e8", dark: "#4b2f20", glow: false });
        break;
      case "ember_ore":
        drawOre(ctx, palette, seed, { base: "#f25c24", light: "#ffecad", dark: "#3d0f04", glow: true });
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

  function buildEdges() {
    const top = makeCanvas(TS, 4);
    const topCtx = top.getContext("2d");
    const topGradient = topCtx.createLinearGradient(0, 0, 0, 4);
    topGradient.addColorStop(0, "rgba(255, 240, 200, 0.17)");
    topGradient.addColorStop(1, "rgba(255, 240, 200, 0)");
    topCtx.fillStyle = topGradient;
    topCtx.fillRect(0, 0, TS, 4);

    const bottom = makeCanvas(TS, 5);
    const bottomCtx = bottom.getContext("2d");
    const bottomGradient = bottomCtx.createLinearGradient(0, 0, 0, 5);
    bottomGradient.addColorStop(0, "rgba(0, 0, 0, 0)");
    bottomGradient.addColorStop(1, "rgba(0, 0, 0, 0.36)");
    bottomCtx.fillStyle = bottomGradient;
    bottomCtx.fillRect(0, 0, TS, 5);

    const side = makeCanvas(3, TS);
    const sideCtx = side.getContext("2d");
    const sideGradient = sideCtx.createLinearGradient(0, 0, 3, 0);
    sideGradient.addColorStop(0, "rgba(0, 0, 0, 0.26)");
    sideGradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    sideCtx.fillStyle = sideGradient;
    sideCtx.fillRect(0, 0, 3, TS);

    // Sparse mineral grain for the air-backed cave wall.
    const cave = makeCanvas(TS, TS);
    const caveCtx = cave.getContext("2d");
    for (let i = 0; i < 16; i += 1) {
      const x = Math.floor(hash(i, 3, 501) * TS);
      const y = Math.floor(hash(i, 5, 503) * TS);
      caveCtx.fillStyle = i % 3 === 0 ? "rgba(180, 202, 226, 0.045)" : "rgba(0, 0, 0, 0.12)";
      caveCtx.fillRect(x, y, i % 4 === 0 ? 2 : 1, 1);
    }

    return { top: top, bottom: bottom, side: side, cave: cave };
  }

  function initTextures() {
    if (!textures) {
      textures = buildTextures();
    }
    if (!edges) {
      edges = buildEdges();
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
    return Math.abs((x * 31 + y * 17 + ((x * y) % 7)) % VARIANTS);
  }

  function drawTorch(ctx, px, py, scale) {
    const s = scale || 1;
    const cx = px + TS / 2;
    // Bracket and shadow.
    ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
    ctx.fillRect(px + 3 * s, py + TS - 4 * s, TS - 6 * s, 3 * s);
    ctx.fillStyle = "#3c2a18";
    ctx.fillRect(cx - 4 * s, py + TS - 7 * s, 8 * s, 3 * s);
    // Handle.
    ctx.fillStyle = "#7a4a22";
    ctx.fillRect(cx - 2 * s, py + 9 * s, 4 * s, TS - 13 * s);
    ctx.fillStyle = "#5a3518";
    ctx.fillRect(cx - 1 * s, py + 10 * s, 2 * s, TS - 15 * s);
    ctx.fillStyle = "#a9713c";
    ctx.fillRect(cx - 2 * s, py + 10 * s, 1 * s, TS - 15 * s);

    // Flame glow.
    const glow = ctx.createRadialGradient(cx, py + 7 * s, 1, cx, py + 7 * s, 14 * s);
    glow.addColorStop(0, "rgba(255, 236, 166, 0.95)");
    glow.addColorStop(0.35, "rgba(255, 166, 74, 0.55)");
    glow.addColorStop(1, "rgba(255, 120, 40, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px - 6 * s, py - 10 * s, TS + 12 * s, TS + 6 * s);

    // Layered flame.
    ctx.fillStyle = "#ff8a3c";
    ctx.fillRect(cx - 2.5 * s, py + 3 * s, 5 * s, 8 * s);
    ctx.fillStyle = "#ffc46a";
    ctx.fillRect(cx - 1.5 * s, py + 2 * s, 3 * s, 6 * s);
    ctx.fillStyle = "#fff1bb";
    ctx.fillRect(cx - 1 * s, py + 2 * s, 2 * s, 4 * s);

    // Ember specks.
    ctx.fillStyle = "rgba(255, 180, 90, 0.7)";
    ctx.fillRect(cx - 4 * s, py + 1 * s, 1 * s, 1 * s);
    ctx.fillRect(cx + 4 * s, py + 3 * s, 1 * s, 1 * s);
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

  /* ------------------------------------------------------------------ */
  /* Item icons                                                          */
  /* ------------------------------------------------------------------ */

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
      ctx.strokeStyle = "#4d3016";
      ctx.lineWidth = Math.max(3, size * 0.13);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(inner * 0.22, inner * 0.86);
      ctx.lineTo(inner * 0.8, inner * 0.16);
      ctx.stroke();
      ctx.strokeStyle = "#a9713c";
      ctx.lineWidth = Math.max(2, size * 0.08);
      ctx.beginPath();
      ctx.moveTo(inner * 0.26, inner * 0.8);
      ctx.lineTo(inner * 0.78, inner * 0.2);
      ctx.stroke();
      ctx.strokeStyle = "#c89a63";
      ctx.lineWidth = Math.max(1, size * 0.03);
      ctx.beginPath();
      ctx.moveTo(inner * 0.3, inner * 0.74);
      ctx.lineTo(inner * 0.55, inner * 0.44);
      ctx.stroke();
    } else if (key === "coal") {
      ctx.fillStyle = "#5c6672";
      ctx.beginPath();
      ctx.ellipse(inner * 0.5, inner * 0.56, inner * 0.39, inner * 0.35, 0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#101318";
      ctx.beginPath();
      ctx.ellipse(inner * 0.5, inner * 0.56, inner * 0.35, inner * 0.31, 0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#2a2f37";
      ctx.beginPath();
      ctx.ellipse(inner * 0.46, inner * 0.5, inner * 0.24, inner * 0.2, 0.3, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#4b535d";
      ctx.fillRect(inner * 0.32, inner * 0.35, inner * 0.2, inner * 0.07);
      ctx.fillStyle = "#78828e";
      ctx.fillRect(inner * 0.34, inner * 0.34, inner * 0.1, inner * 0.03);
      ctx.fillStyle = "#39414a";
      ctx.fillRect(inner * 0.56, inner * 0.6, inner * 0.14, inner * 0.06);
    } else if (key === "iron_ingot") {
      const x0 = inner * 0.08;
      const y0 = inner * 0.46;
      const w = inner * 0.84;
      const h = inner * 0.36;
      ctx.fillStyle = "#3f4954";
      ctx.beginPath();
      ctx.moveTo(x0, y0 + h * 0.48);
      ctx.lineTo(x0 + w * 0.12, y0);
      ctx.lineTo(x0 + w * 0.88, y0);
      ctx.lineTo(x0 + w, y0 + h * 0.52);
      ctx.lineTo(x0 + w * 0.86, y0 + h * 0.72);
      ctx.lineTo(x0 + w * 0.14, y0 + h * 0.72);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#9aa6b1";
      ctx.beginPath();
      ctx.moveTo(x0 + w * 0.14, y0 + h * 0.44);
      ctx.lineTo(x0 + w * 0.22, y0 + h * 0.08);
      ctx.lineTo(x0 + w * 0.78, y0 + h * 0.08);
      ctx.lineTo(x0 + w * 0.88, y0 + h * 0.46);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#d8e0e7";
      ctx.fillRect(x0 + w * 0.24, y0 + h * 0.08, w * 0.52, h * 0.1);
      ctx.fillStyle = "#66717c";
      ctx.fillRect(x0 + w * 0.2, y0 + h * 0.6, w * 0.62, h * 0.07);
      ctx.fillStyle = "#eef4f8";
      ctx.fillRect(x0 + w * 0.3, y0 + h * 0.16, w * 0.18, h * 0.05);
    } else if (key === "ember_shard") {
      const glow = ctx.createRadialGradient(inner * 0.5, inner * 0.5, 1, inner * 0.5, inner * 0.5, inner * 0.6);
      glow.addColorStop(0, "rgba(255, 150, 70, 0.55)");
      glow.addColorStop(1, "rgba(255, 120, 40, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, inner, inner);
      ctx.fillStyle = "#a9421b";
      ctx.beginPath();
      ctx.moveTo(inner * 0.5, inner * 0.04);
      ctx.lineTo(inner * 0.86, inner * 0.5);
      ctx.lineTo(inner * 0.56, inner * 0.96);
      ctx.lineTo(inner * 0.16, inner * 0.54);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#ff8a4c";
      ctx.beginPath();
      ctx.moveTo(inner * 0.5, inner * 0.12);
      ctx.lineTo(inner * 0.78, inner * 0.5);
      ctx.lineTo(inner * 0.54, inner * 0.88);
      ctx.lineTo(inner * 0.24, inner * 0.53);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#ffd27a";
      ctx.beginPath();
      ctx.moveTo(inner * 0.5, inner * 0.22);
      ctx.lineTo(inner * 0.64, inner * 0.48);
      ctx.lineTo(inner * 0.5, inner * 0.68);
      ctx.lineTo(inner * 0.36, inner * 0.47);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#fff3c8";
      ctx.fillRect(inner * 0.48, inner * 0.3, inner * 0.06, inner * 0.16);
    } else if (key.indexOf("pick") === 0) {
      const tier = def.tool.tier;
      const head = tier === 1 ? "#c08f55" : tier === 2 ? "#a7b2bc" : "#e8edf2";
      const dark = tier === 1 ? "#6f4c26" : tier === 2 ? "#59636d" : "#98a4b1";
      const handle = inner * 0.11;
      // Thick handle first, so the silhouette reads at 30 px as well as 64 px.
      ctx.strokeStyle = "#3f2814";
      ctx.lineWidth = handle + Math.max(2, inner * 0.05);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(inner * 0.24, inner * 0.9);
      ctx.lineTo(inner * 0.68, inner * 0.26);
      ctx.stroke();
      ctx.strokeStyle = "#8a6239";
      ctx.lineWidth = handle;
      ctx.beginPath();
      ctx.moveTo(inner * 0.24, inner * 0.88);
      ctx.lineTo(inner * 0.66, inner * 0.28);
      ctx.stroke();
      ctx.strokeStyle = "#c2935b";
      ctx.lineWidth = Math.max(1, inner * 0.03);
      ctx.beginPath();
      ctx.moveTo(inner * 0.29, inner * 0.82);
      ctx.lineTo(inner * 0.63, inner * 0.32);
      ctx.stroke();

      // Crescent head.
      ctx.fillStyle = dark;
      ctx.beginPath();
      ctx.moveTo(inner * 0.08, inner * 0.5);
      ctx.quadraticCurveTo(inner * 0.5, inner * 0.0, inner * 0.94, inner * 0.42);
      ctx.quadraticCurveTo(inner * 0.53, inner * 0.23, inner * 0.2, inner * 0.58);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = head;
      ctx.beginPath();
      ctx.moveTo(inner * 0.11, inner * 0.48);
      ctx.quadraticCurveTo(inner * 0.5, inner * 0.045, inner * 0.9, inner * 0.4);
      ctx.quadraticCurveTo(inner * 0.53, inner * 0.25, inner * 0.2, inner * 0.54);
      ctx.closePath();
      ctx.fill();
      // Pointed tips.
      ctx.fillStyle = head;
      ctx.beginPath();
      ctx.moveTo(inner * 0.06, inner * 0.56);
      ctx.lineTo(inner * 0.1, inner * 0.4);
      ctx.lineTo(inner * 0.19, inner * 0.53);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(inner * 0.92, inner * 0.5);
      ctx.lineTo(inner * 0.95, inner * 0.34);
      ctx.lineTo(inner * 0.84, inner * 0.42);
      ctx.closePath();
      ctx.fill();
      // Glint along the top of the crescent.
      ctx.strokeStyle = "rgba(255, 255, 255, 0.6)";
      ctx.lineWidth = Math.max(1, inner * 0.025);
      ctx.beginPath();
      ctx.moveTo(inner * 0.19, inner * 0.4);
      ctx.quadraticCurveTo(inner * 0.5, inner * 0.09, inner * 0.82, inner * 0.36);
      ctx.stroke();
    } else if (key.indexOf("sword") === 0) {
      const tier = def.tool.tier;
      const blade = tier === 1 ? "#c08f55" : tier === 2 ? "#a7b2bc" : "#e8edf2";
      const edge = tier === 1 ? "#6f4c26" : tier === 2 ? "#59636d" : "#98a4b1";
      const len = inner * 0.34;
      const half = inner * 0.075;
      ctx.save();
      ctx.translate(inner * 0.53, inner * 0.53);
      // Rotate so the blade runs from lower-left (grip) to upper-right (tip).
      ctx.rotate(Math.PI / 4);

      // Blade with a pointed tip.
      ctx.fillStyle = edge;
      ctx.beginPath();
      ctx.moveTo(-half - 1, len);
      ctx.lineTo(-half - 1, -len + inner * 0.02);
      ctx.lineTo(0, -len - inner * 0.1);
      ctx.lineTo(half + 1, -len + inner * 0.02);
      ctx.lineTo(half + 1, len);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = blade;
      ctx.beginPath();
      ctx.moveTo(-half, len);
      ctx.lineTo(-half, -len + inner * 0.02);
      ctx.lineTo(0, -len - inner * 0.07);
      ctx.lineTo(half, -len + inner * 0.02);
      ctx.lineTo(half, len);
      ctx.closePath();
      ctx.fill();
      // Fuller and a hard highlight down the centre.
      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      ctx.fillRect(-half * 0.22, -len + inner * 0.06, half * 0.2, len * 0.82);
      ctx.fillStyle = "rgba(0, 0, 0, 0.14)";
      ctx.fillRect(half * 0.22, -len + inner * 0.08, half * 0.12, len * 0.78);

      // Crossguard.
      ctx.fillStyle = "#3f2814";
      ctx.fillRect(-inner * 0.2, len - inner * 0.025, inner * 0.4, inner * 0.075);
      ctx.fillStyle = "#b98a52";
      ctx.fillRect(-inner * 0.18, len - inner * 0.012, inner * 0.36, inner * 0.048);
      ctx.fillStyle = "#e0b878";
      ctx.fillRect(-inner * 0.18, len - inner * 0.012, inner * 0.36, inner * 0.015);

      // Grip and pommel.
      ctx.fillStyle = "#3f2814";
      ctx.fillRect(-inner * 0.055, len + inner * 0.04, inner * 0.11, inner * 0.2);
      ctx.fillStyle = "#7d5730";
      ctx.fillRect(-inner * 0.035, len + inner * 0.04, inner * 0.03, inner * 0.2);
      ctx.fillStyle = "#b98a52";
      ctx.beginPath();
      ctx.arc(0, len + inner * 0.27, inner * 0.06, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    } else {
      ctx.fillStyle = "#9e9e9e";
      ctx.fillRect(0, 0, inner, inner);
    }
    ctx.restore();
  }

  /* ------------------------------------------------------------------ */
  /* Sky, distance and horizon                                           */
  /* ------------------------------------------------------------------ */

  const SKY_KEYS = [
    { t: 0.0, top: [22, 30, 54], bottom: [244, 166, 100] },
    { t: 0.06, top: [86, 140, 190], bottom: [250, 204, 151] },
    { t: 0.16, top: [77, 143, 201], bottom: [216, 237, 246] },
    { t: 0.46, top: [64, 137, 203], bottom: [199, 230, 245] },
    { t: 0.56, top: [116, 108, 165], bottom: [242, 158, 92] },
    { t: 0.64, top: [30, 40, 74], bottom: [86, 82, 126] },
    { t: 0.74, top: [8, 13, 30], bottom: [25, 34, 61] },
    { t: 0.92, top: [8, 12, 28], bottom: [21, 30, 55] },
    { t: 0.965, top: [44, 46, 84], bottom: [225, 139, 92] },
    { t: 1.0, top: [22, 30, 54], bottom: [244, 166, 100] }
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

  function mix(a, b, t) {
    return [
      Math.round(lerp(a[0], b[0], t)),
      Math.round(lerp(a[1], b[1], t)),
      Math.round(lerp(a[2], b[2], t))
    ];
  }

  function drawSun(ctx, x, y) {
    const glow = ctx.createRadialGradient(x, y, 2, x, y, 86);
    glow.addColorStop(0, "rgba(255, 247, 205, 0.9)");
    glow.addColorStop(0.22, "rgba(255, 216, 128, 0.36)");
    glow.addColorStop(0.6, "rgba(255, 188, 100, 0.1)");
    glow.addColorStop(1, "rgba(255, 180, 90, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(x - 92, y - 92, 184, 184);
    // A square sun is the Minecraft read, but the layered disc gives it depth.
    ctx.fillStyle = "rgba(255, 224, 138, 0.95)";
    ctx.fillRect(x - 13, y - 13, 26, 26);
    ctx.fillStyle = "#fff4c9";
    ctx.fillRect(x - 10, y - 10, 20, 20);
    ctx.fillStyle = "#fffbe8";
    ctx.fillRect(x - 5, y - 5, 10, 10);
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    ctx.fillRect(x - 13, y - 13, 26, 2);
  }

  function drawMoon(ctx, x, y) {
    const glow = ctx.createRadialGradient(x, y, 3, x, y, 84);
    glow.addColorStop(0, "rgba(214, 230, 252, 0.32)");
    glow.addColorStop(1, "rgba(170, 196, 232, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(x - 90, y - 90, 180, 180);
    ctx.fillStyle = "rgba(231, 238, 250, 0.97)";
    ctx.fillRect(x - 11, y - 11, 22, 22);
    ctx.fillStyle = "rgba(197, 208, 226, 0.9)";
    ctx.fillRect(x - 5, y - 7, 5, 4);
    ctx.fillRect(x + 2, y + 2, 6, 4);
    ctx.fillRect(x - 7, y + 4, 3, 3);
    ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
    ctx.fillRect(x - 11, y - 11, 22, 2);
  }

  function drawCloud(ctx, x, y, scale, color, alpha) {
    const blocks = [
      [0, 0, 74, 14],
      [12, -9, 46, 12],
      [48, 4, 32, 10],
      [-20, 5, 30, 9],
      [26, -16, 20, 9]
    ];
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    for (let i = 0; i < blocks.length; i += 1) {
      const block = blocks[i];
      ctx.fillRect(
        Math.round(x + block[0] * scale),
        Math.round(y + block[1] * scale),
        Math.round(block[2] * scale),
        Math.round(block[3] * scale)
      );
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
    ctx.fillRect(Math.round(x + 4 * scale), Math.round(y + 1 * scale), Math.round(56 * scale), Math.round(2 * scale));
    ctx.globalAlpha = 1;
  }

  function drawSky(ctx, state) {
    const colors = colorAt(state.time);
    const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
    gradient.addColorStop(0, rgb(colors.top));
    gradient.addColorStop(0.58, rgb(mix(colors.top, colors.bottom, 0.55)));
    gradient.addColorStop(1, rgb(colors.bottom));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    const day = LIGHT.dayFactor(state.time);
    const night = 1 - day;

    // Stars: denser and slightly larger above the horizon.
    ctx.globalAlpha = Math.min(1, night * 1.5);
    for (let i = 0; i < 120; i += 1) {
      const x = (hash(i, 3, 7) * VIEW_W + state.time * 9 * (1 + (i % 3))) % VIEW_W;
      const y = hash(i, 5, 11) * VIEW_H * 0.62;
      const twinkle = 0.4 + 0.6 * Math.abs(Math.sin(state.time * 26 + i));
      ctx.fillStyle = "rgba(232, 240, 252," + (0.2 + twinkle * 0.58) + ")";
      const size = i % 17 === 0 ? 2 : 1;
      ctx.fillRect(Math.round(x), Math.round(y), size, size);
    }
    ctx.globalAlpha = 1;

    // Horizon warmth (dawn/dusk) and a quiet daytime glow.
    const dusk = Math.max(
      Math.max(0, 1 - Math.abs(state.time - 0.56) / 0.12),
      Math.max(0, 1 - Math.abs(state.time - 0.965) / 0.05)
    );
    const horizon = ctx.createLinearGradient(0, VIEW_H * 0.42, 0, VIEW_H);
    horizon.addColorStop(0, "rgba(255, 255, 255, 0)");
    horizon.addColorStop(0.7, "rgba(255, 222, 176," + (0.07 + dusk * 0.16).toFixed(3) + ")");
    horizon.addColorStop(1, "rgba(255, 200, 150," + (0.1 + dusk * 0.12).toFixed(3) + ")");
    ctx.fillStyle = horizon;
    ctx.fillRect(0, VIEW_H * 0.42, VIEW_W, VIEW_H * 0.58);

    const angle = (state.time - 0.02) / 0.58;
    if (angle >= 0 && angle <= 1) {
      const sunX = VIEW_W * (0.08 + angle * 0.84);
      const sunY = VIEW_H * 0.58 - Math.sin(angle * Math.PI) * VIEW_H * 0.34;
      drawSun(ctx, sunX, sunY);
    }
    const moonAngle = (state.time - 0.58) / 0.44;
    if (moonAngle >= 0 && moonAngle <= 1) {
      const moonX = VIEW_W * (0.1 + moonAngle * 0.8);
      const moonY = VIEW_H * 0.5 - Math.sin(moonAngle * Math.PI) * VIEW_H * 0.28;
      drawMoon(ctx, moonX, moonY);
    }

    // Block-built clouds with a flat, wind-drifted silhouette.
    const cloudAlpha = 0.28 + 0.4 * day;
    for (let i = 0; i < 7; i += 1) {
      const speed = 7 + (i % 3) * 5;
      const x = ((hash(i, 9, 5) * VIEW_W + state.time * speed * 55) % (VIEW_W + 280)) - 140;
      const y = 38 + hash(i, 11, 7) * VIEW_H * 0.24;
      const scale = 0.7 + hash(i, 13, 9) * 0.55;
      const color = i % 2 === 0 ? "#f2f8fb" : "#d8e8f2";
      const warm = dusk > 0.15 ? "#ffe0c2" : color;
      drawCloud(ctx, x, y, scale, warm, cloudAlpha * (0.75 + hash(i, 15, 3) * 0.3));
    }
  }

  function ridgeY(worldX, layer, index) {
    return (
      Math.sin(worldX / layer.step) * 22 +
      Math.sin(worldX / (layer.step * 0.42) + index) * 13 +
      Math.sin(worldX / 19 + index * 2) * 4
    );
  }

  function drawParallax(ctx, state) {
    const day = LIGHT.dayFactor(state.time);
    const colors = colorAt(state.time);
    const layers = [
      { factor: 0.14, base: 0.59, height: 118, color: [94, 126, 154], step: 118, haze: 0.5 },
      { factor: 0.25, base: 0.65, height: 155, color: [62, 92, 118], step: 84, haze: 0.32 },
      { factor: 0.38, base: 0.73, height: 196, color: [38, 62, 84], step: 60, haze: 0.16 },
      { factor: 0.52, base: 0.83, height: 232, color: [20, 36, 52], step: 44, haze: 0.04 }
    ];
    for (let l = 0; l < layers.length; l += 1) {
      const layer = layers[l];
      const offset = state.camera.x * layer.factor;
      const tint = 0.34 + day * 0.66;
      const lit = [
        Math.round(layer.color[0] * tint + colors.bottom[0] * layer.haze * 0.35),
        Math.round(layer.color[1] * tint + colors.bottom[1] * layer.haze * 0.35),
        Math.round(layer.color[2] * tint + colors.bottom[2] * layer.haze * 0.35)
      ];
      ctx.fillStyle = rgb(lit, 0.96);
      ctx.beginPath();
      ctx.moveTo(0, VIEW_H);
      const width = VIEW_W + 200;
      for (let x = 0; x <= width; x += 8) {
        const worldX = x + offset;
        const y = VIEW_H * layer.base - layer.height * 0.35 - ridgeY(worldX, layer, l);
        ctx.lineTo(x, y);
      }
      ctx.lineTo(width, VIEW_H);
      ctx.closePath();
      ctx.fill();

      // A far treeline on the second layer gives the hills a sense of scale.
      if (l === 1) {
        const ridgeBase = VIEW_H * layer.base - layer.height * 0.35;
        const trunk = rgb(mix(lit, [10, 16, 22], 0.42), 0.85);
        ctx.fillStyle = trunk;
        for (let i = 0; i < 15; i += 1) {
          const worldX = i * 46 + (offset % 46) + hash(i, 3, 17) * 28;
          if (worldX < -30 || worldX > VIEW_W + 30) {
            continue;
          }
          const y = ridgeBase - ridgeY(worldX + offset, layer, l) + 2;
          if (hash(i, 5, 19) < 0.2) {
            continue;
          }
          const h = 10 + Math.floor(hash(i, 7, 23) * 9);
          ctx.fillRect(Math.round(worldX), Math.round(y - h), 2, h);
          ctx.fillRect(Math.round(worldX - 4), Math.round(y - h - 3), 10, 4);
          ctx.fillRect(Math.round(worldX - 3), Math.round(y - h - 7), 8, 4);
          ctx.fillRect(Math.round(worldX - 2), Math.round(y - h - 10), 5, 4);
        }
      }
    }
  }

  function drawFog(ctx, state) {
    const day = LIGHT.dayFactor(state.time);
    const dusk = Math.max(0, 1 - Math.abs(state.time - 0.56) / 0.12);
    const color = dusk > 0.2 ? [255, 196, 148] : [190, 218, 236];
    const alpha = 0.08 + (1 - day) * 0.06 + dusk * 0.05;
    const gradient = ctx.createLinearGradient(0, VIEW_H * 0.4, 0, VIEW_H);
    gradient.addColorStop(0, rgb(color, 0));
    gradient.addColorStop(0.55, rgb(color, alpha * 0.55));
    gradient.addColorStop(1, rgb(color, alpha));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, VIEW_H * 0.4, VIEW_W, VIEW_H * 0.6);
  }

  /* ------------------------------------------------------------------ */
  /* World                                                               */
  /* ------------------------------------------------------------------ */

  function drawCaveBackdrop(ctx, state, firstCol, lastCol) {
    const ts = TS;
    const camera = state.camera;
    const world = state.world;
    const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
    gradient.addColorStop(0, "rgba(35, 39, 48, 0.97)");
    gradient.addColorStop(0.3, "rgba(23, 27, 35, 0.985)");
    gradient.addColorStop(0.7, "rgba(12, 15, 21, 0.995)");
    gradient.addColorStop(1, "rgba(7, 9, 14, 1)");
    for (let x = firstCol; x <= lastCol; x += 1) {
      // Fill below the terrain surface, not below the first solid tile: a tree
      // canopy or trunk must not turn the open air beneath it into cave wall.
      let top = world.height;
      for (let y = 0; y < world.height; y += 1) {
        const id = world.data[y * world.width + x];
        if (id !== B.air && id !== B.leaves && id !== B.wood && id !== B.torch) {
          top = y;
          break;
        }
      }
      const px = Math.round(x * ts - camera.x);
      const py = Math.round(top * ts - camera.y);
      if (py > VIEW_H) {
        continue;
      }
      ctx.fillStyle = gradient;
      ctx.fillRect(px, Math.max(py, 0), ts + 1, VIEW_H - Math.max(py, 0));

      // Rock grain in the air-backed wall so a cave pocket reads as rock in
      // shadow, not as a missing rectangle.
      for (let ty = Math.max(py, 0); ty < VIEW_H; ty += ts) {
        ctx.drawImage(edges.cave, px, ty);
      }

      // Strata bands in the air-backed cave wall; only visible in open pockets.
      ctx.fillStyle = "rgba(255, 236, 200, 0.028)";
      for (let band = 0; band < 3; band += 1) {
        const by = py + 26 + band * 34 + Math.floor(hash(x, band, 401) * 10);
        if (by > 0 && by < VIEW_H) {
          ctx.fillRect(px, by, ts + 1, 1);
        }
      }
      // A damp, slightly lighter lip under the surface.
      if (py > -ts && py < VIEW_H) {
        ctx.fillStyle = "rgba(100, 120, 125, 0.05)";
        ctx.fillRect(px, Math.max(py, 0), ts + 1, 8);
      }
    }
  }

  function isOpenBlock(id) {
    return id === B.air || id === B.torch;
  }

  function drawEdgeShading(ctx, world, x, y, px, py, id) {
    if (id === B.torch) {
      return;
    }
    const above = y > 0 ? world.data[(y - 1) * world.width + x] : B.air;
    const below = y < world.height - 1 ? world.data[(y + 1) * world.width + x] : B.air;
    const left = x > 0 ? world.data[y * world.width + (x - 1)] : B.air;
    const right = x < world.width - 1 ? world.data[y * world.width + (x + 1)] : B.air;
    const leaf = id === B.leaves;

    if (leaf) {
      ctx.fillStyle = "rgba(8, 14, 10, 0.22)";
      if (isOpenBlock(above)) {
        ctx.fillRect(px, py, TS, 3);
      }
      if (isOpenBlock(below)) {
        ctx.fillRect(px, py + TS - 3, TS, 3);
      }
      if (isOpenBlock(left)) {
        ctx.fillRect(px, py, 3, TS);
      }
      if (isOpenBlock(right)) {
        ctx.fillRect(px + TS - 3, py, 3, TS);
      }
      return;
    }

    if (isOpenBlock(above)) {
      ctx.drawImage(edges.top, px, py);
    }
    if (isOpenBlock(below)) {
      ctx.drawImage(edges.bottom, px, py + TS - 5);
    }
    if (isOpenBlock(left)) {
      ctx.drawImage(edges.side, px, py);
    }
    if (isOpenBlock(right)) {
      ctx.save();
      ctx.translate(px + TS, py);
      ctx.scale(-1, 1);
      ctx.drawImage(edges.side, 0, 0);
      ctx.restore();
    }
  }

  function drawGrassDetail(ctx, world, x, y, px, py, id, time) {
    if (id !== B.grass) {
      return;
    }
    const above = y > 0 ? world.data[(y - 1) * world.width + x] : B.air;
    if (!isOpenBlock(above)) {
      return;
    }
    const def = BLOCKS.get(B.grass);
    const palette = def.palette;

    // Blades stand proud of the tile edge so the meadow has a silhouette.
    const blades = 2 + Math.floor(hash(x, y, 419) * 3);
    for (let i = 0; i < blades; i += 1) {
      const bx = px + 1 + Math.floor(hash(x, y + i, 421) * (TS - 2));
      const bh = 2 + Math.floor(hash(x, y + i, 431) * 3);
      ctx.fillStyle = i % 2 === 0 ? palette.light : palette.base;
      ctx.fillRect(bx, py - bh, 1, bh);
    }
    if (hash(x, y, 433) > 0.9) {
      const fx = px + 3 + Math.floor(hash(x, y, 439) * (TS - 8));
      const flower = hash(x, y, 443) > 0.5 ? "#f6f0cf" : "#f0cd78";
      ctx.fillStyle = palette.dark;
      ctx.fillRect(fx + 1, py - 3, 1, 3);
      ctx.fillStyle = flower;
      ctx.fillRect(fx, py - 5, 3, 2);
      ctx.fillStyle = "#d7a24a";
      ctx.fillRect(fx + 1, py - 4, 1, 1);
    }
  }

  function drawDugTile(ctx, px, py) {
    ctx.fillStyle = "#161a21";
    ctx.fillRect(px, py, TS, TS);
    ctx.fillStyle = "rgba(0, 0, 0, 0.28)";
    ctx.fillRect(px, py, TS, 4);
    ctx.fillRect(px, py, 3, TS);
    ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
    for (let i = 0; i < 3; i += 1) {
      ctx.fillRect(px + 5 + i * 6, py + 7 + (i % 2) * 5, 3, 2);
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
        const px = Math.round(x * ts - camera.x);
        const py = Math.round(y * ts - camera.y);
        if (id === B.air) {
          // A block the player removed gets a dark back wall, so a dug pocket
          // reads as a hole rather than as sky seen through a glass tile.
          if (state.dug && state.dug.has(x + "," + y)) {
            drawDugTile(ctx, px, py);
          }
          continue;
        }
        drawTileAt(ctx, id, x, y, px, py);
        drawEdgeShading(ctx, world, x, y, px, py, id);
        drawGrassDetail(ctx, world, x, y, px, py, id, state.time);
      }
    }
  }

  /* ------------------------------------------------------------------ */
  /* Light                                                               */
  /* ------------------------------------------------------------------ */

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
        if (block !== B.air && block !== B.wood && block !== B.leaves && block !== B.torch) {
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
        const darkness = Math.max(0, Math.min(1, 1 - value / MAX_LIGHT));
        const block = state.world.data[(light.y0 + gy) * state.world.width + (light.x0 + gx)];
        const solid = block !== B.air && block !== B.torch;
        // Solid ground keeps a little more of its material in the dark; cave
        // air stays void-dark, so depth reads as terrain rather than a band.
        const maxAlpha = solid ? 186 : 212;
        image.data[index] = 5;
        image.data[index + 1] = 8;
        image.data[index + 2] = 15;
        image.data[index + 3] = Math.round(8 + Math.pow(darkness, 1.05) * (maxAlpha - 8));
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
        const py = y * ts - state.camera.y + ts * 0.35;
        const beacon = id === B.beacon;
        const radius = beacon ? 210 : 120;
        const wide = ctx.createRadialGradient(px, py, 2, px, py, radius);
        wide.addColorStop(0, beacon ? "rgba(255, 196, 116, 0.3)" : "rgba(255, 172, 88, 0.13)");
        wide.addColorStop(0.45, beacon ? "rgba(255, 160, 80, 0.14)" : "rgba(255, 150, 70, 0.05)");
        wide.addColorStop(1, "rgba(255, 130, 40, 0)");
        ctx.fillStyle = wide;
        ctx.fillRect(px - radius, py - radius, radius * 2, radius * 2);

        const core = ctx.createRadialGradient(px, py, 1, px, py, beacon ? 54 : 34);
        core.addColorStop(0, beacon ? "rgba(255, 236, 176, 0.42)" : "rgba(255, 210, 140, 0.3)");
        core.addColorStop(1, "rgba(255, 160, 70, 0)");
        ctx.fillStyle = core;
        ctx.fillRect(px - 54, py - 54, 108, 108);
      }
    }
    ctx.restore();
  }

  function drawBeaconGlow(ctx, state) {
    const beacon = state.beaconGlow;
    if (!beacon) {
      return;
    }
    const ts = TS;
    const px = beacon.x * ts - state.camera.x + ts / 2;
    const py = beacon.y * ts - state.camera.y + ts / 2;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const glow = ctx.createRadialGradient(px, py, 2, px, py, 240);
    glow.addColorStop(0, "rgba(255, 224, 156, 0.38)");
    glow.addColorStop(0.4, "rgba(255, 170, 90, 0.16)");
    glow.addColorStop(1, "rgba(255, 140, 60, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px - 240, py - 240, 480, 480);
    ctx.restore();
  }

  /* ------------------------------------------------------------------ */
  /* Characters and props                                                */
  /* ------------------------------------------------------------------ */

  function outlinedRect(ctx, x, y, w, h, color, outline) {
    ctx.fillStyle = outline;
    ctx.fillRect(Math.round(x) - 1, Math.round(y) - 1, Math.round(w) + 2, Math.round(h) + 2);
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
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
    const moving = Math.abs(player.vx || 0) > 0.05;
    const bob = moving && player.onGround ? Math.abs(Math.sin((player.walkPhase || 0) * 2)) * 1.2 : 0;

    ctx.save();
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = "#000";
    ctx.beginPath();
    ctx.ellipse(px + 1, py + 2, width * 0.58, 4, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(px, py - bob);
    ctx.scale(facing, 1);
    if (flash) {
      ctx.globalAlpha = 0.6;
    }

    const legY = -height * 0.35;
    const legW = width * 0.3;
    // Boots and legs, with a warm rim from the ground side.
    outlinedRect(ctx, -width * 0.43 + walk, legY, legW, height * 0.28, "#33445a", "#111823");
    outlinedRect(ctx, width * 0.1 - walk, legY, legW, height * 0.28, "#2c3c50", "#111823");
    ctx.fillStyle = "#1a252f";
    ctx.fillRect(-width * 0.45 + walk, -height * 0.08, width * 0.36, height * 0.08);
    ctx.fillRect(width * 0.08 - walk, -height * 0.08, width * 0.36, height * 0.08);
    ctx.fillStyle = "#4b5f76";
    ctx.fillRect(-width * 0.43 + walk, legY, legW, height * 0.03);
    ctx.fillRect(width * 0.1 - walk, legY, legW, height * 0.03);

    // Tunic.
    outlinedRect(ctx, -width * 0.45, -height * 0.73, width * 0.9, height * 0.38, "#3c6178", "#101720");
    ctx.fillStyle = "#4f7f96";
    ctx.fillRect(-width * 0.43, -height * 0.72, width * 0.86, height * 0.05);
    ctx.fillStyle = "#2c4a5e";
    ctx.fillRect(-width * 0.43, -height * 0.42, width * 0.86, height * 0.05);
    // Ember scarf / belt accent.
    ctx.fillStyle = "#c9673c";
    ctx.fillRect(-width * 0.43, -height * 0.66, width * 0.86, height * 0.035);
    ctx.fillStyle = "#e8955e";
    ctx.fillRect(-width * 0.43, -height * 0.66, width * 0.86, height * 0.012);
    ctx.fillStyle = "#8e4a2c";
    ctx.fillRect(-width * 0.45, -height * 0.5, width * 0.9, height * 0.03);
    // Buckle.
    ctx.fillStyle = "#d9b875";
    ctx.fillRect(-width * 0.05, -height * 0.51, width * 0.1, height * 0.05);

    // Head.
    const headY = -height * 0.95;
    const headSize = width * 0.8;
    outlinedRect(ctx, -headSize / 2, headY, headSize, height * 0.23, "#e8b98c", "#1a1512");
    ctx.fillStyle = "#c98a63";
    ctx.fillRect(-headSize / 2, headY + height * 0.21, headSize, height * 0.025);
    ctx.fillStyle = "#3b2a1e";
    ctx.fillRect(-headSize / 2 - 1, headY - 3, headSize + 2, 6);
    ctx.fillRect(-headSize / 2, headY - 1, 3, height * 0.15);
    ctx.fillRect(headSize / 2 - 2, headY - 1, 2, height * 0.12);
    // A little ember feather on the cap.
    ctx.fillStyle = "#c9673c";
    ctx.fillRect(headSize * 0.12, headY - 6, 4, 4);
    ctx.fillStyle = "#e8955e";
    ctx.fillRect(headSize * 0.18, headY - 7, 3, 2);
    // Eye and brow.
    ctx.fillStyle = "#1d1b1a";
    ctx.fillRect(headSize * 0.12, headY + height * 0.09, 3, 3);
    ctx.fillStyle = "#fff4d8";
    ctx.fillRect(headSize * 0.2, headY + height * 0.09, 1, 1);
    ctx.fillStyle = "#b98360";
    ctx.fillRect(headSize * 0.12, headY + height * 0.165, 4, 1);
    // Rim light.
    ctx.fillStyle = "rgba(255, 232, 190, 0.35)";
    ctx.fillRect(-headSize / 2 + 1, headY - 2, headSize - 2, 1);
    ctx.fillRect(-width * 0.44, -height * 0.72, 1, height * 0.26);

    // Arm and held item.
    ctx.fillStyle = "#e2b083";
    ctx.fillRect(width * 0.32, -height * 0.64, width * 0.16, height * 0.22);
    ctx.fillStyle = "#c98a63";
    ctx.fillRect(width * 0.32, -height * 0.44, width * 0.16, height * 0.04);
    if (state.heldItem) {
      ctx.save();
      ctx.translate(width * 0.54, -height * 0.52);
      ctx.rotate(-0.34);
      drawItemIcon(ctx, state.heldItem, 14);
      ctx.fillStyle = "#e2b083";
      ctx.fillRect(-3, 8, 6, 5);
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
      const width = mob.width * ts * 1.08;
      const height = mob.height * ts * 1.04;
      const bob = Math.sin((state.clockSeconds || 0) * 3 + i) * 2;
      const hurt = mob.hurt > 0;

      // Grounding shadow.
      ctx.save();
      ctx.globalAlpha = 0.34;
      ctx.fillStyle = "#000";
      ctx.beginPath();
      ctx.ellipse(px, py + 1, width * 0.55, 3.5, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.translate(px, py + bob);
      if (hurt) {
        ctx.globalAlpha = 0.9;
      }

      // Cold aura.
      const aura = ctx.createRadialGradient(0, -height * 0.45, 2, 0, -height * 0.45, width * 0.9);
      aura.addColorStop(0, "rgba(120, 92, 180, 0.18)");
      aura.addColorStop(1, "rgba(80, 60, 140, 0)");
      ctx.fillStyle = aura;
      ctx.fillRect(-width, -height * 1.2, width * 2, height * 1.2);

      // Ragged body.
      const body = ctx.createLinearGradient(0, -height, 0, 0);
      if (hurt) {
        body.addColorStop(0, "#f6ead8");
        body.addColorStop(1, "#d9b9a0");
      } else {
        body.addColorStop(0, "#232a3a");
        body.addColorStop(0.55, "#151a26");
        body.addColorStop(1, "#090c12");
      }
      ctx.fillStyle = body;
      ctx.beginPath();
      ctx.moveTo(-width * 0.36, 0);
      ctx.quadraticCurveTo(-width * 0.56, -height * 0.7, -width * 0.2, -height * 0.9);
      ctx.quadraticCurveTo(0, -height * 1.04, width * 0.22, -height * 0.9);
      ctx.quadraticCurveTo(width * 0.56, -height * 0.68, width * 0.38, 0);
      // Ragged hem.
      ctx.lineTo(width * 0.22, -height * 0.1);
      ctx.lineTo(width * 0.12, -height * 0.02);
      ctx.lineTo(width * 0.02, -height * 0.12);
      ctx.lineTo(-width * 0.1, -height * 0.01);
      ctx.lineTo(-width * 0.2, -height * 0.11);
      ctx.closePath();
      ctx.fill();
      // A cold rim keeps the hollow readable against the night sky.
      ctx.strokeStyle = hurt ? "rgba(255, 214, 160, 0.45)" : "rgba(140, 160, 200, 0.2)";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Inner wisp band.
      ctx.fillStyle = hurt ? "rgba(255, 180, 110, 0.5)" : "rgba(255, 138, 76, 0.15)";
      ctx.fillRect(-width * 0.3, -height * 0.5, width * 0.6, 2);

      // Eyes with their own glow.
      const eyeColor = hurt ? "#ffe6b0" : "#ff9450";
      for (let e = 0; e < 2; e += 1) {
        const ex = e === 0 ? -width * 0.2 : width * 0.12;
        const ey = -height * 0.76;
        const glow = ctx.createRadialGradient(ex + 2, ey + 2, 1, ex + 2, ey + 2, 11);
        glow.addColorStop(0, "rgba(255, 160, 80, 0.55)");
        glow.addColorStop(1, "rgba(255, 120, 40, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(ex - 10, ey - 10, 24, 24);
        ctx.fillStyle = eyeColor;
        ctx.fillRect(ex, ey, 5, 5);
        ctx.fillStyle = "#fff3cf";
        ctx.fillRect(ex + 1, ey + 1, 2, 2);
      }
      // Ember mouth.
      ctx.fillStyle = "rgba(255, 120, 50, 0.55)";
      ctx.fillRect(-width * 0.12, -height * 0.6, width * 0.24, 2);
      ctx.fillStyle = "#0a0d13";
      ctx.fillRect(-width * 0.06, -height * 0.62, width * 0.12, 2);
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
      ctx.globalAlpha = 0.42;
      drawTileAt(ctx, ghostId, tile.tx, tile.ty, px, py);
      ctx.restore();
      ctx.strokeStyle = "rgba(143, 227, 176, 0.9)";
      ctx.fillStyle = "rgba(143, 227, 176, 0.08)";
    } else {
      ctx.strokeStyle = "rgba(233, 185, 106, 0.85)";
      ctx.fillStyle = "rgba(233, 185, 106, 0.05)";
    }
    ctx.fillRect(px + 2, py + 2, ts - 4, ts - 4);
    ctx.lineWidth = 1;
    ctx.strokeRect(px + 1.5, py + 1.5, ts - 3, ts - 3);
    // Corner brackets.
    const length = 7;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px + 1, py + 1 + length);
    ctx.lineTo(px + 1, py + 1);
    ctx.lineTo(px + 1 + length, py + 1);
    ctx.moveTo(px + ts - 1 - length, py + 1);
    ctx.lineTo(px + ts - 1, py + 1);
    ctx.lineTo(px + ts - 1, py + 1 + length);
    ctx.moveTo(px + 1, py + ts - 1 - length);
    ctx.lineTo(px + 1, py + ts - 1);
    ctx.lineTo(px + 1 + length, py + ts - 1);
    ctx.moveTo(px + ts - 1 - length, py + ts - 1);
    ctx.lineTo(px + ts - 1, py + ts - 1);
    ctx.lineTo(px + ts - 1, py + ts - 1 - length);
    ctx.stroke();

    if (mining && mining.tx === tile.tx && mining.ty === tile.ty && mining.fraction > 0) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(px, py, ts, ts);
      ctx.clip();
      ctx.strokeStyle = "rgba(8, 10, 14, 0.88)";
      ctx.lineWidth = 2;
      const cracks = Math.max(1, Math.floor(mining.fraction * 6));
      for (let i = 0; i < cracks; i += 1) {
        const startX = px + hash(i, tile.tx, 3) * ts;
        const startY = py + hash(i, tile.ty, 7) * ts;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(startX + (hash(i, 5, 9) - 0.5) * 20, startY + (hash(i, 11, 13) - 0.5) * 20);
        ctx.stroke();
      }
      // Progress ring in the corner bracket colour.
      ctx.strokeStyle = "rgba(255, 210, 122, 0.9)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(px + ts - 6, py + 6, 4, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * mining.fraction);
      ctx.stroke();
      ctx.restore();
    }
  }

  function drawVignette(ctx, state) {
    const gradient = ctx.createRadialGradient(
      VIEW_W / 2,
      VIEW_H * 0.48,
      VIEW_H * 0.3,
      VIEW_W / 2,
      VIEW_H * 0.5,
      VIEW_H * 0.88
    );
    gradient.addColorStop(0, "rgba(0,0,0,0)");
    gradient.addColorStop(1, "rgba(2,4,8,0.58)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, VIEW_W, VIEW_H);

    if (state.hurtFlash > 0) {
      ctx.fillStyle = "rgba(180,30,30," + Math.min(0.5, state.hurtFlash * 0.5) + ")";
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }
    if (state.pausedTint) {
      ctx.fillStyle = "rgba(4,7,12,0.5)";
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }
  }

  function renderFrame(ctx, state) {
    if (state.view && state.view.width > 0 && state.view.height > 0) {
      VIEW_W = Math.floor(state.view.width);
      VIEW_H = Math.floor(state.view.height);
    }
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
    drawMobs(ctx, state);
    if (!state.player.dead) {
      drawPlayer(ctx, state);
    }
    // Drawn after the characters so the warm pool reads as light falling on
    // them, not as a decal behind them.
    drawTorchGlow(ctx, state, firstCol, lastCol, firstRow, lastRow);
    drawParticles(ctx, state);
    drawTarget(ctx, state);
    drawBeaconGlow(ctx, state);
    drawVignette(ctx, state);
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
