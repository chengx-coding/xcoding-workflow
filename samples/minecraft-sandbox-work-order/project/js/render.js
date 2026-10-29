(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  const TILE = CONFIG.tileSize;
  const BLOCK = CONFIG.blocks;
  const AIR = BLOCK.air;
  const textureCache = new Map();
  let cavePattern = null;

  const BLOCK_COLORS = Object.freeze({
    1: CONFIG.blockInfo[1].swatch,
    2: CONFIG.blockInfo[2].swatch,
    3: CONFIG.blockInfo[3].swatch,
    4: CONFIG.blockInfo[4].swatch,
    5: CONFIG.blockInfo[5].swatch,
    6: CONFIG.blockInfo[6].swatch,
    7: CONFIG.blockInfo[7].swatch,
    8: CONFIG.blockInfo[8].swatch
  });

  const FLOWER_COLORS = ["#ffd166", "#ff9db1", "#f6f1de", "#c3a6ff", "#ffb26b"];

  const CLOUDS = [
    { x: 0.08, y: 0.12, scale: 1.15, speed: 0.006, alpha: 0.2 },
    { x: 0.32, y: 0.22, scale: 0.72, speed: 0.004, alpha: 0.15 },
    { x: 0.58, y: 0.08, scale: 1.3, speed: 0.005, alpha: 0.18 },
    { x: 0.82, y: 0.28, scale: 0.9, speed: 0.0035, alpha: 0.14 },
    { x: 0.95, y: 0.15, scale: 1.05, speed: 0.0045, alpha: 0.16 }
  ];

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function random() {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeCanvas(size) {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    return canvas;
  }

  function getCavePattern(ctx) {
    if (cavePattern) {
      return cavePattern;
    }
    const size = 64;
    const canvas = makeCanvas(size);
    const g = canvas.getContext("2d");
    g.fillStyle = "#22303a";
    g.fillRect(0, 0, size, size);
    const random = mulberry32(0xc0ffee);
    for (let index = 0; index < 74; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      const w = 1 + Math.floor(random() * 4);
      const h = 1 + Math.floor(random() * 3);
      g.fillStyle = random() > 0.5 ? "#2b3c47" : "#18232b";
      g.fillRect(x, y, w, h);
    }
    g.strokeStyle = "rgba(164, 198, 212, 0.16)";
    g.lineWidth = 1;
    for (let index = 0; index < 7; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x + 4 + Math.floor(random() * 10), y + 3 + Math.floor(random() * 8));
      g.stroke();
    }
    cavePattern = ctx.createPattern(canvas, "repeat");
    return cavePattern;
  }

  function fill(g, color, x, y, width, height) {
    g.fillStyle = color;
    g.fillRect(x, y, width, height);
  }

  function drawDirt(g, size, random) {
    fill(g, "#7b5438", 0, 0, size, size);
    for (let index = 0; index < 34; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      const w = 1 + Math.floor(random() * 3);
      const h = 1 + Math.floor(random() * 2);
      fill(g, random() > 0.55 ? "#684429" : "#8d6243", x, y, w, h);
    }
    for (let index = 0; index < 7; index += 1) {
      const x = Math.floor(random() * (size - 3));
      const y = Math.floor(random() * (size - 2));
      fill(g, "#a2825f", x, y, 2, 1);
    }
    for (let index = 0; index < 3; index += 1) {
      if (random() > 0.55) {
        const x = Math.floor(random() * size);
        const y = Math.floor(random() * (size - 6));
        fill(g, "#5a3c24", x, y, 1, 3 + Math.floor(random() * 4));
        fill(g, "#5a3c24", x + 1, y + 2, 1, 2);
      }
    }
  }

  function drawGrass(g, size, random) {
    drawDirt(g, size, random);
    for (let x = 0; x < size; x += 2) {
      const depth = 7 + Math.floor(random() * 4);
      fill(g, "#5fae45", x, 0, 2, depth);
    }
    for (let x = 0; x < size; x += 1) {
      const shade = random() > 0.62 ? "#7fd15b" : "#6cc24a";
      const top = Math.floor(random() * 4);
      fill(g, shade, x, top, 1, 2);
    }
    fill(g, "#4f973c", 0, 11, size, 2);
    for (let index = 0; index < 9; index += 1) {
      const x = Math.floor(random() * size);
      const y = 10 + Math.floor(random() * 5);
      fill(g, "#8fe06d", x, y, 1, 2);
    }
  }

  function drawStone(g, size, random) {
    fill(g, "#747f8a", 0, 0, size, size);
    for (let index = 0; index < 26; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      const w = 2 + Math.floor(random() * 5);
      const h = 1 + Math.floor(random() * 3);
      fill(g, random() > 0.5 ? "#68737e" : "#828d99", x, y, w, h);
    }
    g.strokeStyle = "#545e69";
    g.lineWidth = 1;
    for (let index = 0; index < 4; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x + 3 + Math.floor(random() * 6), y + 2 + Math.floor(random() * 5));
      g.stroke();
    }
    for (let index = 0; index < 5; index += 1) {
      fill(g, "#9aa5b1", Math.floor(random() * size), Math.floor(random() * size), 2, 1);
    }
    if (random() > 0.42) {
      const oreColor = random() > 0.55 ? "#bf8b52" : "#c8c078";
      const oreX = 4 + Math.floor(random() * (size - 9));
      const oreY = 5 + Math.floor(random() * (size - 11));
      fill(g, oreColor, oreX, oreY, 2, 2);
      fill(g, "#efe7b0", oreX, oreY, 1, 1);
      fill(g, oreColor, oreX + 3, oreY + 4, 1, 2);
      fill(g, "#6a5236", oreX + 2, oreY + 5, 1, 1);
    }
  }

  function drawWood(g, size, random) {
    fill(g, "#6f4a2b", 0, 0, size, size);
    for (let index = 0; index < 6; index += 1) {
      const x = 2 + index * 5 + Math.floor(random() * 2);
      fill(g, index % 2 === 0 ? "#5d3c22" : "#835a36", x, 0, 1, size);
    }
    for (let index = 0; index < 10; index += 1) {
      fill(g, "#8e6239", Math.floor(random() * size), Math.floor(random() * size), 1, 2 + Math.floor(random() * 3));
    }
    g.strokeStyle = "#4c3019";
    g.lineWidth = 1;
    g.beginPath();
    g.ellipse(21, 12, 4, 6, 0, 0, Math.PI * 2);
    g.stroke();
    fill(g, "#9c6c40", 20, 11, 2, 2);
    fill(g, "#4f321d", 0, 0, 2, size);
    fill(g, "#4f321d", size - 1, 0, 1, size);
  }

  function drawLeaves(g, size, random) {
    fill(g, "#357c3c", 0, 0, size, size);
    for (let index = 0; index < 40; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      const w = 2 + Math.floor(random() * 4);
      const h = 2 + Math.floor(random() * 3);
      const tone = random();
      fill(g, tone > 0.72 ? "#63b866" : tone > 0.36 ? "#479b4c" : "#2c6c34", x, y, w, h);
    }
    for (let index = 0; index < 7; index += 1) {
      fill(g, "#7ed07d", Math.floor(random() * size), Math.floor(random() * size), 1, 2);
    }
  }

  function drawSand(g, size, random) {
    fill(g, "#d8bd78", 0, 0, size, size);
    for (let index = 0; index < 46; index += 1) {
      const x = Math.floor(random() * size);
      const y = Math.floor(random() * size);
      fill(g, random() > 0.5 ? "#c6a962" : "#eedba3", x, y, 1 + Math.floor(random() * 2), 1);
    }
    for (let index = 0; index < 4; index += 1) {
      fill(g, "#b99b57", Math.floor(random() * size), Math.floor(random() * size), 2, 2);
    }
  }

  function drawPlanks(g, size, random) {
    for (let row = 0; row < 4; row += 1) {
      const top = row * 8;
      fill(g, row % 2 === 0 ? "#ad7642" : "#a26c3b", 0, top, size, 8);
      fill(g, "#7c5229", 0, top + 7, size, 1);
      fill(g, "#c99359", 0, top, size, 1);
      const seam = row % 2 === 0 ? 10 : 22;
      fill(g, "#7c5229", seam, top, 1, 7);
      fill(g, "#5f3d1f", 4, top + 3, 1, 1);
      fill(g, "#5f3d1f", 26, top + 3, 1, 1);
    }
    for (let index = 0; index < 12; index += 1) {
      fill(g, "#c28b50", Math.floor(random() * size), Math.floor(random() * size), 1, 1);
    }
  }

  function drawGlass(g, size) {
    fill(g, "rgba(160, 216, 232, 0.2)", 0, 0, size, size);
    fill(g, "rgba(226, 250, 255, 0.5)", 0, 0, size, 2);
    fill(g, "rgba(226, 250, 255, 0.35)", 0, 0, 2, size);
    fill(g, "rgba(30, 74, 88, 0.28)", 0, size - 2, size, 2);
    fill(g, "rgba(30, 74, 88, 0.22)", size - 2, 0, 2, size);
    g.save();
    g.globalAlpha = 0.3;
    g.fillStyle = "#ffffff";
    g.beginPath();
    g.moveTo(6, size - 5);
    g.lineTo(size - 5, 6);
    g.lineTo(size - 10, 6);
    g.lineTo(6, size - 10);
    g.closePath();
    g.fill();
    g.restore();
    fill(g, "rgba(255, 255, 255, 0.75)", 21, 7, 2, 2);
    fill(g, "rgba(255, 255, 255, 0.45)", 25, 11, 1, 1);
    fill(g, "rgba(255, 255, 255, 0.45)", 8, 23, 1, 1);
  }

  function drawBlockTexture(g, block, variant, size) {
    const random = mulberry32((block * 7919 + variant * 104729 + 17) >>> 0);
    switch (block) {
      case BLOCK.grass:
        drawGrass(g, size, random);
        break;
      case BLOCK.dirt:
        drawDirt(g, size, random);
        break;
      case BLOCK.stone:
        drawStone(g, size, random);
        break;
      case BLOCK.wood:
        drawWood(g, size, random);
        break;
      case BLOCK.leaves:
        drawLeaves(g, size, random);
        break;
      case BLOCK.sand:
        drawSand(g, size, random);
        break;
      case BLOCK.planks:
        drawPlanks(g, size, random);
        break;
      case BLOCK.glass:
        drawGlass(g, size);
        break;
      default:
        fill(g, "#9e9e9e", 0, 0, size, size);
    }
  }

  function getTexture(block, variant) {
    const key = block + ":" + variant;
    if (textureCache.has(key)) {
      return textureCache.get(key);
    }
    const canvas = makeCanvas(TILE);
    const g = canvas.getContext("2d");
    const scale = TILE / 32;
    g.setTransform(scale, 0, 0, scale, 0, 0);
    drawBlockTexture(g, block, variant, 32);
    textureCache.set(key, canvas);
    return canvas;
  }

  function drawSky(ctx, viewWidth, viewHeight) {
    const sky = ctx.createLinearGradient(0, 0, 0, viewHeight);
    sky.addColorStop(0, "#22577e");
    sky.addColorStop(0.32, "#4f9bbd");
    sky.addColorStop(0.58, "#93cddd");
    sky.addColorStop(0.82, "#ecd6a6");
    sky.addColorStop(1, "#f4c98a");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, viewWidth, viewHeight);

    const sunX = viewWidth * 0.78;
    const sunY = viewHeight * 0.18;
    const glow = ctx.createRadialGradient(sunX, sunY, 8, sunX, sunY, Math.max(viewWidth, viewHeight) * 0.34);
    glow.addColorStop(0, "rgba(255, 246, 201, 0.9)");
    glow.addColorStop(0.18, "rgba(255, 232, 160, 0.35)");
    glow.addColorStop(0.5, "rgba(255, 214, 138, 0.1)");
    glow.addColorStop(1, "rgba(255, 214, 138, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, viewWidth, viewHeight);
    ctx.fillStyle = "#fff7d6";
    ctx.beginPath();
    ctx.arc(sunX, sunY, Math.max(22, viewWidth * 0.026), 0, Math.PI * 2);
    ctx.fill();
  }

  function drawCloud(ctx, x, y, scale, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "#f6fbff";
    const puffs = [
      [0, 0, 42, 16],
      [14, -8, 30, 16],
      [30, -2, 26, 14],
      [50, 3, 34, 12]
    ];
    for (let index = 0; index < puffs.length; index += 1) {
      const puff = puffs[index];
      ctx.beginPath();
      ctx.ellipse(x + puff[0] * scale, y + puff[1] * scale, puff[2] * scale, puff[3] * scale, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawClouds(ctx, viewWidth, viewHeight, time, reducedMotion) {
    for (let index = 0; index < CLOUDS.length; index += 1) {
      const cloud = CLOUDS[index];
      const drift = reducedMotion ? 0 : time * cloud.speed * viewWidth * 0.12;
      const span = viewWidth + 280;
      const x = ((cloud.x * span + drift) % span) - 140;
      drawCloud(ctx, x, cloud.y * viewHeight, cloud.scale, cloud.alpha);
    }
  }

  function drawRidge(ctx, viewWidth, viewHeight, camera, time, color, baseY, amplitude, frequency, parallax, drift) {
    ctx.beginPath();
    ctx.moveTo(-20, viewHeight + 20);
    for (let sx = -20; sx <= viewWidth + 20; sx += 14) {
      const worldX = sx + camera.x * parallax + time * drift;
      const y =
        baseY +
        Math.sin(worldX * frequency) * amplitude +
        Math.sin(worldX * frequency * 2.37 + 1.4) * amplitude * 0.34;
      ctx.lineTo(sx, y);
    }
    ctx.lineTo(viewWidth + 20, viewHeight + 20);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawRidges(ctx, viewWidth, viewHeight, camera, time, reducedMotion) {
    const drift = reducedMotion ? 0 : 6;
    ctx.save();
    drawRidge(ctx, viewWidth, viewHeight, camera, time, "rgba(178, 210, 221, 0.62)", viewHeight * 0.5, 30, 0.0055, 0.05, drift * 0.1);
    drawRidge(ctx, viewWidth, viewHeight, camera, time, "rgba(112, 160, 172, 0.68)", viewHeight * 0.59, 38, 0.0085, 0.1, drift * 0.18);
    drawRidge(ctx, viewWidth, viewHeight, camera, time, "rgba(63, 112, 110, 0.76)", viewHeight * 0.68, 34, 0.0125, 0.18, drift * 0.26);
    ctx.restore();
  }

  function drawBirds(ctx, viewWidth, viewHeight, time, reducedMotion) {
    if (reducedMotion) {
      return;
    }
    ctx.save();
    ctx.strokeStyle = "rgba(30, 52, 66, 0.45)";
    ctx.lineWidth = 1.6;
    ctx.lineCap = "round";
    for (let index = 0; index < 3; index += 1) {
      const x = ((time * (9 + index * 2) + index * 190) % (viewWidth + 160)) - 80;
      const y = viewHeight * (0.16 + index * 0.035) + Math.sin(time * 0.9 + index * 1.7) * 5;
      const size = 4.5 + index * 1.4;
      ctx.beginPath();
      ctx.moveTo(x - size, y);
      ctx.lineTo(x, y - size * 0.55);
      ctx.lineTo(x + size, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawHaze(ctx, viewWidth, viewHeight) {
    const haze = ctx.createLinearGradient(0, viewHeight * 0.34, 0, viewHeight * 0.64);
    haze.addColorStop(0, "rgba(255, 233, 190, 0)");
    haze.addColorStop(0.55, "rgba(255, 233, 190, 0.13)");
    haze.addColorStop(1, "rgba(255, 233, 190, 0)");
    ctx.fillStyle = haze;
    ctx.fillRect(0, viewHeight * 0.34, viewWidth, viewHeight * 0.3);
  }

  function drawUnderground(ctx, world, camera, viewWidth, viewHeight, firstColumn, lastColumn) {
    const path = new Path2D();
    let hasArea = false;
    for (let x = firstColumn; x <= lastColumn; x += 1) {
      const surfaceY = WORLD.surfaceHeightAt(world, x) * TILE - camera.y;
      const top = surfaceY > viewHeight ? 0 : Math.max(0, surfaceY);
      const screenX = x * TILE - camera.x;
      path.rect(screenX, top, TILE + 1, viewHeight - top + 40);
      hasArea = true;
    }
    if (!hasArea) {
      return;
    }
    ctx.save();
    ctx.clip(path);
    const pattern = getCavePattern(ctx);
    if (pattern) {
      ctx.save();
      ctx.translate(-Math.round(camera.x) % 64, -Math.round(camera.y) % 64);
      ctx.fillStyle = pattern;
      ctx.fillRect(-64, -64, viewWidth + 256, viewHeight + 256);
      ctx.restore();
    } else {
      ctx.fillStyle = "#121b22";
      ctx.fillRect(0, 0, viewWidth, viewHeight);
    }
    const depth = ctx.createLinearGradient(0, 0, 0, viewHeight);
    depth.addColorStop(0, "rgba(34, 50, 60, 0.04)");
    depth.addColorStop(0.55, "rgba(14, 22, 30, 0.1)");
    depth.addColorStop(1, "rgba(7, 13, 19, 0.22)");
    ctx.fillStyle = depth;
    ctx.fillRect(0, 0, viewWidth, viewHeight);
    ctx.restore();
  }

  function drawCliffWalls(ctx, world, camera, viewWidth, viewHeight, firstColumn, lastColumn) {
    for (let x = firstColumn; x <= lastColumn; x += 1) {
      const surface = WORLD.surfaceHeightAt(world, x);
      const left = WORLD.surfaceHeightAt(world, x - 1);
      const right = WORLD.surfaceHeightAt(world, x + 1);
      const top = Math.min(left, right);
      if (top >= surface) {
        continue;
      }
      const screenX = x * TILE - camera.x;
      const y0 = top * TILE - camera.y;
      const y1 = surface * TILE - camera.y;
      if (y1 < 0 || y0 > viewHeight) {
        continue;
      }
      const wall = ctx.createLinearGradient(0, y0, 0, y1);
      wall.addColorStop(0, "rgba(24, 16, 10, 0.1)");
      wall.addColorStop(1, "rgba(18, 12, 8, 0.46)");
      const wallTexture = getTexture(BLOCK.dirt, (x * 5) % 3);
      for (let row = top; row < surface; row += 1) {
        ctx.drawImage(wallTexture, screenX, Math.round(row * TILE - camera.y));
      }
      ctx.fillStyle = wall;
      ctx.fillRect(screenX, y0, TILE + 1, y1 - y0);
      ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
      for (let line = y0 + 10; line < y1; line += 14) {
        ctx.fillRect(screenX + 3, line, TILE - 6, 2);
      }
      if (left < surface) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.24)";
        ctx.fillRect(screenX, y0, 4, y1 - y0);
      }
      if (right < surface) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.24)";
        ctx.fillRect(screenX + TILE - 4, y0, 4, y1 - y0);
      }
    }
  }

  function drawOcclusion(ctx, screenX, screenY, world, x, y) {
    const shade = "rgba(8, 13, 17, 0.18)";
    if (!WORLD.isSolid(world, x, y - 1)) {
      ctx.fillStyle = shade;
      ctx.fillRect(screenX, screenY, TILE, 4);
      ctx.fillStyle = "rgba(8, 13, 17, 0.1)";
      ctx.fillRect(screenX, screenY + 4, TILE, 3);
    }
    if (!WORLD.isSolid(world, x - 1, y)) {
      ctx.fillStyle = shade;
      ctx.fillRect(screenX, screenY, 3, TILE);
    }
    if (!WORLD.isSolid(world, x + 1, y)) {
      ctx.fillStyle = shade;
      ctx.fillRect(screenX + TILE - 3, screenY, 3, TILE);
    }
  }

  function drawDecoration(ctx, world, x, y, screenX, screenY, time, reducedMotion) {
    if (WORLD.getBlock(world, x, y) !== BLOCK.grass) {
      return;
    }
    if (WORLD.isSolid(world, x, y - 1)) {
      return;
    }
    const noise = WORLD.hash2(x, y, world.seed, 137);
    const scale = TILE / 32;
    const sway = reducedMotion ? 0 : Math.sin(time * 1.5 + x * 0.7) * 1.2;
    ctx.save();
    ctx.translate(screenX, screenY);
    ctx.scale(scale, scale);
    if (noise > 0.9) {
      const color =
        FLOWER_COLORS[Math.floor(WORLD.hash2(x, y, world.seed, 149) * FLOWER_COLORS.length) % FLOWER_COLORS.length];
      const cx = 32 * (0.28 + WORLD.hash2(x, y, world.seed, 151) * 0.44) + sway;
      ctx.fillStyle = "#3f7f3a";
      ctx.fillRect(cx, -9, 1, 9);
      ctx.fillRect(cx - 3, -4, 3, 1);
      ctx.fillRect(cx + 1, -6, 3, 1);
      ctx.fillStyle = color;
      ctx.fillRect(cx - 3, -14, 7, 4);
      ctx.fillRect(cx - 2, -15, 5, 6);
      ctx.fillStyle = "rgba(255,255,255,0.6)";
      ctx.fillRect(cx - 1, -14, 2, 2);
      ctx.fillStyle = "#ffe9a8";
      ctx.fillRect(cx + 1, -13, 1, 1);
    } else if (noise > 0.7) {
      ctx.fillStyle = "rgba(70, 145, 62, 0.92)";
      const baseX = 4;
      ctx.fillRect(baseX + sway, -6, 1, 6);
      ctx.fillRect(baseX + 5 - sway, -9, 1, 9);
      ctx.fillRect(baseX + 10 + sway * 0.5, -5, 1, 5);
      ctx.fillStyle = "rgba(116, 196, 96, 0.85)";
      ctx.fillRect(baseX + 2, -4, 1, 4);
      ctx.fillRect(baseX + 8 - sway * 0.5, -6, 1, 6);
    } else if (noise > 0.63) {
      ctx.fillStyle = "#f2ddb5";
      ctx.fillRect(18, -5, 2, 5);
      ctx.fillStyle = "#b4553f";
      ctx.fillRect(16, -8, 6, 3);
      ctx.fillStyle = "#d9785f";
      ctx.fillRect(17, -9, 4, 2);
    }
    ctx.restore();
  }

  function drawWorld(ctx, state) {
    const world = state.world;
    const camera = state.camera;
    const viewWidth = state.viewWidth;
    const viewHeight = state.viewHeight;
    const firstColumn = Math.max(0, Math.floor(camera.x / TILE) - 1);
    const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + viewWidth) / TILE) + 1);
    const firstRow = Math.max(0, Math.floor(camera.y / TILE) - 1);
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + viewHeight) / TILE) + 1);

    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const block = world.data[y * world.width + x];
        if (block === AIR) {
          continue;
        }
        const screenX = Math.round(x * TILE - camera.x);
        const screenY = Math.round(y * TILE - camera.y);
        const variant = Math.floor(WORLD.hash2(x, y, world.seed, 211) * 3);
        const texture = getTexture(block, variant);
        const sway =
          block === BLOCK.leaves && !state.reducedMotion
            ? Math.sin(state.time * 1.35 + x * 0.34 + y * 0.11) * 1.2
            : 0;
        if (block === BLOCK.glass) {
          ctx.save();
          ctx.globalAlpha = 0.82;
          ctx.drawImage(texture, screenX, screenY);
          ctx.restore();
        } else {
          ctx.drawImage(texture, screenX + sway, screenY);
        }
        drawOcclusion(ctx, screenX, screenY, world, x, y);
      }
    }

    for (let x = firstColumn; x <= lastColumn; x += 1) {
      for (let y = firstRow; y <= lastRow; y += 1) {
        drawDecoration(
          ctx,
          world,
          x,
          y,
          Math.round(x * TILE - camera.x),
          Math.round(y * TILE - camera.y),
          state.time,
          state.reducedMotion
        );
      }
    }
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const camera = state.camera;
    const time = state.time;
    const sx = player.x * TILE - camera.x;
    const feet = player.y * TILE - camera.y;
    const height = player.height * TILE;
    const width = player.width * TILE;
    const direction = player.facing < 0 ? -1 : 1;
    const characterScale = TILE / 32;
    const moving = Boolean(player.moving);
    const phase = player.animTime;
    const swing = moving ? Math.sin(phase) * 4.5 : Math.sin(time * 2.1) * 0.8;
    const bob = moving ? Math.abs(Math.sin(phase)) * 1.6 : Math.sin(time * 2.1) * 0.7;

    ctx.save();
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = "#04130d";
    ctx.beginPath();
    ctx.ellipse(sx, feet + 3 * characterScale, width * 0.72, 5.5 * characterScale, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    const lanternX = sx + direction * 13 * characterScale;
    const lanternY = feet - height * 0.42;
    const glow = ctx.createRadialGradient(lanternX, lanternY, 2, lanternX, lanternY, 44 * characterScale);
    glow.addColorStop(0, "rgba(255, 206, 112, 0.28)");
    glow.addColorStop(1, "rgba(255, 206, 112, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(lanternX - 46 * characterScale, lanternY - 46 * characterScale, 92 * characterScale, 92 * characterScale);

    ctx.save();
    ctx.translate(sx, feet - bob * characterScale);
    ctx.scale(direction * characterScale, characterScale);

    // Backpack
    ctx.fillStyle = "#5a3d28";
    ctx.fillRect(-14, -36, 8, 17);
    ctx.fillStyle = "#452d1c";
    ctx.fillRect(-14, -30, 8, 2);
    ctx.fillRect(-14, -24, 8, 2);
    ctx.fillStyle = "#7a5636";
    ctx.fillRect(-13, -35, 2, 15);

    // Legs
    const leftLift = moving ? Math.max(0, Math.sin(phase) * 4.5) : 0;
    const rightLift = moving ? Math.max(0, -Math.sin(phase) * 4.5) : 0;
    ctx.fillStyle = "#33546b";
    ctx.fillRect(-8, -18 - leftLift, 6, 16);
    ctx.fillRect(2, -18 - rightLift, 6, 16);
    ctx.fillStyle = "#243b4d";
    ctx.fillRect(-8, -4 - leftLift, 6, 4);
    ctx.fillRect(2, -4 - rightLift, 6, 4);
    ctx.fillStyle = "rgba(255,255,255,0.16)";
    ctx.fillRect(-7, -17 - leftLift, 1, 12);
    ctx.fillRect(3, -17 - rightLift, 1, 12);

    // Body
    ctx.fillStyle = "#2f8f9d";
    ctx.fillRect(-9, -38, 18, 22);
    ctx.fillStyle = "#257886";
    ctx.fillRect(-9, -22, 18, 4);
    ctx.fillStyle = "#3fa8b6";
    ctx.fillRect(-8, -36, 4, 13);
    ctx.fillStyle = "#e1b45c";
    ctx.fillRect(-9, -26, 18, 2);
    ctx.fillStyle = "#f2d38a";
    ctx.fillRect(-1, -26, 3, 2);

    // Scarf
    ctx.fillStyle = "#e8743b";
    ctx.fillRect(-7, -42, 14, 5);
    ctx.fillStyle = "#ff9a5a";
    ctx.fillRect(-7, -42, 14, 2);
    ctx.beginPath();
    ctx.moveTo(-6, -40);
    ctx.lineTo(-14 - swing * 0.8, -35 + swing * 0.5);
    ctx.lineTo(-13 - swing * 0.8, -31 + swing * 0.5);
    ctx.lineTo(-5, -37);
    ctx.closePath();
    ctx.fillStyle = "#d9612c";
    ctx.fill();

    // Head
    ctx.fillStyle = "#f2c9a3";
    ctx.fillRect(-7, -55, 14, 14);
    ctx.fillStyle = "#e3b78e";
    ctx.fillRect(-7, -44, 14, 3);
    ctx.fillStyle = "#2a2019";
    ctx.fillRect(1, -50, 2, 3);
    ctx.fillStyle = "#c98c65";
    ctx.fillRect(3, -45, 3, 1);

    // Helmet
    ctx.fillStyle = "#3d6ea8";
    ctx.fillRect(-8, -58, 16, 9);
    ctx.fillStyle = "#2f5a8c";
    ctx.fillRect(-8, -51, 16, 2);
    ctx.fillStyle = "#5b8fc9";
    ctx.fillRect(-6, -57, 11, 2);
    ctx.fillStyle = "#3d6ea8";
    ctx.fillRect(-6, -50, 17, 2);
    ctx.fillStyle = "#f6d878";
    ctx.fillRect(7, -54, 3, 3);
    ctx.fillStyle = "#fff1b8";
    ctx.fillRect(8, -53, 1, 1);

    // Front arm and lantern
    ctx.fillStyle = "#f2c9a3";
    ctx.fillRect(6, -34 + swing * 0.5, 4, 12);
    ctx.fillStyle = "#2a4e63";
    ctx.fillRect(6, -32 + swing * 0.5, 4, 4);
    ctx.fillStyle = "#e1b45c";
    ctx.fillRect(8, -24 + swing * 0.5, 2, 2);
    ctx.fillStyle = "#6b4b2a";
    ctx.fillRect(9, -22 + swing * 0.5, 1, 6);
    ctx.fillStyle = "#ffcf6b";
    ctx.fillRect(8, -17 + swing * 0.5, 5, 6);
    ctx.fillStyle = "#fff3c4";
    ctx.fillRect(9, -16 + swing * 0.5, 3, 3);
    ctx.fillStyle = "#b8802f";
    ctx.fillRect(7, -18 + swing * 0.5, 7, 1);
    ctx.fillRect(7, -11 + swing * 0.5, 7, 1);

    ctx.restore();
  }

  function drawHover(ctx, state) {
    const hover = state.hover;
    if (!hover) {
      return;
    }
    const camera = state.camera;
    const player = state.player;
    const time = state.time;

    if (hover.reason === "reach") {
      const px = player.x * TILE - camera.x;
      const py = (player.y - player.height / 2) * TILE - camera.y;
      ctx.save();
      ctx.strokeStyle = "rgba(255, 199, 96, 0.35)";
      ctx.setLineDash([5, 6]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(px, py, CONFIG.reach * TILE, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    if (hover.mine && hover.mine.ok) {
      const screenX = hover.cell.x * TILE - camera.x;
      const screenY = hover.cell.y * TILE - camera.y;
      const pulse = 0.68 + Math.sin(time * 7) * 0.2;
      ctx.save();
      ctx.fillStyle = "rgba(255, 213, 128, 0.11)";
      ctx.fillRect(screenX + 2, screenY + 2, TILE - 4, TILE - 4);
      ctx.strokeStyle = "rgba(255, 210, 120, " + pulse.toFixed(3) + ")";
      ctx.lineWidth = 2.5;
      ctx.strokeRect(screenX + 1, screenY + 1, TILE - 2, TILE - 2);
      ctx.strokeStyle = "rgba(255, 244, 205, 0.95)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(screenX + 3.5, screenY + 3.5, TILE - 7, TILE - 7);
      ctx.strokeStyle = "rgba(255, 250, 226, 1)";
      ctx.lineWidth = 2;
      const corner = 7;
      ctx.beginPath();
      ctx.moveTo(screenX + 1, screenY + corner);
      ctx.lineTo(screenX + 1, screenY + 1);
      ctx.lineTo(screenX + corner, screenY + 1);
      ctx.moveTo(screenX + TILE - corner, screenY + 1);
      ctx.lineTo(screenX + TILE - 1, screenY + 1);
      ctx.lineTo(screenX + TILE - 1, screenY + corner);
      ctx.moveTo(screenX + 1, screenY + TILE - corner);
      ctx.lineTo(screenX + 1, screenY + TILE - 1);
      ctx.lineTo(screenX + corner, screenY + TILE - 1);
      ctx.moveTo(screenX + TILE - corner, screenY + TILE - 1);
      ctx.lineTo(screenX + TILE - 1, screenY + TILE - 1);
      ctx.lineTo(screenX + TILE - 1, screenY + TILE - corner);
      ctx.stroke();
      ctx.restore();
    }

    if (hover.placeCell && hover.place) {
      const screenX = hover.placeCell.x * TILE - camera.x;
      const screenY = hover.placeCell.y * TILE - camera.y;
      if (hover.place.ok) {
        const texture = getTexture(state.selectedBlock, 0);
        ctx.save();
        ctx.globalAlpha = 0.58;
        ctx.drawImage(texture, screenX, screenY);
        ctx.globalAlpha = 1;
        ctx.fillStyle = "rgba(198, 244, 255, 0.12)";
        ctx.fillRect(screenX + 1, screenY + 1, TILE - 2, TILE - 2);
        ctx.strokeStyle = "rgba(160, 246, 160, 0.95)";
        ctx.setLineDash([5, 4]);
        ctx.lineWidth = 2.5;
        ctx.strokeRect(screenX + 1, screenY + 1, TILE - 2, TILE - 2);
        ctx.restore();
      } else if (hover.place.reason === "player") {
        ctx.save();
        ctx.strokeStyle = "rgba(255, 116, 116, 0.8)";
        ctx.lineWidth = 2;
        ctx.strokeRect(screenX + 2, screenY + 2, TILE - 4, TILE - 4);
        ctx.restore();
      } else {
        ctx.save();
        ctx.strokeStyle = "rgba(255, 196, 140, 0.38)";
        ctx.setLineDash([3, 4]);
        ctx.lineWidth = 1.5;
        ctx.strokeRect(screenX + 2, screenY + 2, TILE - 4, TILE - 4);
        ctx.restore();
      }
    }
  }

  function drawParticles(ctx, state) {
    const particles = state.particles || [];
    const camera = state.camera;
    for (let index = 0; index < particles.length; index += 1) {
      const particle = particles[index];
      if (particle.life <= 0) {
        continue;
      }
      const alpha = clamp(particle.life / particle.maxLife, 0, 1);
      const size = Math.max(1, particle.size * alpha);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = particle.color;
      ctx.fillRect(
        Math.round(particle.x * TILE - camera.x),
        Math.round(particle.y * TILE - camera.y),
        size,
        size
      );
      ctx.restore();
    }
  }

  function drawVignette(ctx, viewWidth, viewHeight, paused) {
    const vignette = ctx.createRadialGradient(
      viewWidth * 0.5,
      viewHeight * 0.42,
      Math.min(viewWidth, viewHeight) * 0.32,
      viewWidth * 0.5,
      viewHeight * 0.42,
      Math.max(viewWidth, viewHeight) * 0.78
    );
    vignette.addColorStop(0, "rgba(4, 10, 14, 0)");
    vignette.addColorStop(1, "rgba(4, 10, 14, 0.34)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, viewWidth, viewHeight);
    if (paused) {
      ctx.fillStyle = "rgba(3, 8, 12, 0.42)";
      ctx.fillRect(0, 0, viewWidth, viewHeight);
    }
  }

  function createCamera(world, player, viewWidth, viewHeight) {
    const camera = { x: 0, y: 0 };
    updateCamera(camera, world, player, viewWidth, viewHeight, 1, true);
    return camera;
  }

  function updateCamera(camera, world, player, viewWidth, viewHeight, dt, instant) {
    const lookAhead = (player.facing || 1) * 34;
    const targetX = player.x * TILE - viewWidth / 2 + lookAhead;
    const targetY = player.y * TILE - viewHeight * 0.5;
    const maxX = Math.max(0, world.width * TILE - viewWidth);
    const maxY = Math.max(0, world.height * TILE - viewHeight);
    const smooth = instant ? 1 : Math.min(1, Math.max(0, dt) * 6.5);
    camera.x += (clamp(targetX, 0, maxX) - camera.x) * smooth;
    camera.y += (clamp(targetY, 0, maxY) - camera.y) * smooth;
    camera.x = clamp(camera.x, 0, maxX);
    camera.y = clamp(camera.y, 0, maxY);
    return camera;
  }

  function renderFrame(ctx, state) {
    const viewWidth = state.viewWidth;
    const viewHeight = state.viewHeight;
    const world = state.world;

    ctx.setTransform(state.pixelRatio || 1, 0, 0, state.pixelRatio || 1, 0, 0);
    ctx.clearRect(0, 0, viewWidth, viewHeight);

    drawSky(ctx, viewWidth, viewHeight);
    drawClouds(ctx, viewWidth, viewHeight, state.time, state.reducedMotion);
    drawBirds(ctx, viewWidth, viewHeight, state.time, state.reducedMotion);
    drawRidges(ctx, viewWidth, viewHeight, state.camera, state.time, state.reducedMotion);
    drawHaze(ctx, viewWidth, viewHeight);

    const firstColumn = Math.max(0, Math.floor(state.camera.x / TILE) - 1);
    const lastColumn = Math.min(world.width - 1, Math.ceil((state.camera.x + viewWidth) / TILE) + 1);
    drawUnderground(ctx, world, state.camera, viewWidth, viewHeight, firstColumn, lastColumn);
    drawCliffWalls(ctx, world, state.camera, viewWidth, viewHeight, firstColumn, lastColumn);
    drawWorld(ctx, state);
    drawParticles(ctx, state);
    drawPlayer(ctx, state);
    drawHover(ctx, state);
    drawVignette(ctx, viewWidth, viewHeight, state.paused);
  }

  return {
    renderFrame: renderFrame,
    createCamera: createCamera,
    updateCamera: updateCamera,
    getTexture: getTexture,
    drawBlockTexture: drawBlockTexture,
    BLOCK_COLORS: BLOCK_COLORS
  };
});
