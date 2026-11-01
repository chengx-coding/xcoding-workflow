(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"), require("./timecycle.js"), require("./world.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxRng, root.SandboxTime, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG, Time, World) {
  "use strict";

  const TAU = Math.PI * 2;

  function hexToRgb(hex) {
    const value = hex.replace("#", "");
    return [
      parseInt(value.slice(0, 2), 16),
      parseInt(value.slice(2, 4), 16),
      parseInt(value.slice(4, 6), 16)
    ];
  }

  function rgb(c) {
    return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")";
  }

  function rgba(c, alpha) {
    return "rgba(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + "," + alpha + ")";
  }

  function shade(c, factor) {
    return [
      Math.max(0, Math.min(255, c[0] * factor)),
      Math.max(0, Math.min(255, c[1] * factor)),
      Math.max(0, Math.min(255, c[2] * factor))
    ];
  }

  const BLOCK_RGB = {};
  Object.keys(CONFIG.blockInfo).forEach(function (key) {
    const info = CONFIG.blockInfo[key];
    BLOCK_RGB[key] = { base: hexToRgb(info.color), accent: hexToRgb(info.accent) };
  });

  function blockPalette(blockId, light) {
    const entry = BLOCK_RGB[blockId];
    const factor = 0.5 + 0.5 * light;
    return {
      base: shade(entry.base, factor),
      accent: shade(entry.accent, factor)
    };
  }

  function drawSky(ctx, state) {
    const sky = Time.sky(state.time);
    const light = sky.light;
    const gradient = ctx.createLinearGradient(0, 0, 0, CONFIG.viewHeight);
    gradient.addColorStop(0, sky.topCss);
    gradient.addColorStop(0.72, sky.bottomCss);
    gradient.addColorStop(1, rgb(shade(sky.bottom, 0.92)));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);

    if (light < 0.55) {
      const starAlpha = Math.min(0.9, (0.55 - light) * 2.2);
      const phase = state.reducedMotion ? 0 : Math.floor(state.time * 900);
      for (let index = 0; index < 48; index += 1) {
        const sx = Math.floor(RNG.unitHash(index, 11, 7) * CONFIG.viewWidth);
        const sy = Math.floor(RNG.unitHash(index, 23, 3) * CONFIG.viewHeight * 0.62);
        const twinkle = 0.55 + 0.45 * RNG.unitHash(index + phase, 5, 1);
        ctx.fillStyle = "rgba(232,242,255," + (starAlpha * twinkle).toFixed(3) + ")";
        const size = 1 + Math.round(RNG.unitHash(index, 3, 9));
        ctx.fillRect(sx, sy, size, size);
      }
    }

    drawSunAndMoon(ctx, state.time, light);
    drawClouds(ctx, state);
    drawHills(ctx, state, light);
  }

  function drawSunAndMoon(ctx, time, light) {
    const t = Time.normalize(time);
    const isDay = t >= 0.25 && t <= 0.75;
    const p = isDay ? (t - 0.25) / 0.5 : ((t > 0.75 ? t - 0.75 : t + 0.25) / 0.5);
    const x = 92 + p * 776;
    const y = 388 - Math.sin(p * Math.PI) * 306;
    const radius = isDay ? 26 : 20;
    const glow = ctx.createRadialGradient(x, y, 2, x, y, radius * 3.4);
    if (isDay) {
      glow.addColorStop(0, "rgba(255,236,176,0.95)");
      glow.addColorStop(0.35, "rgba(255,206,110,0.35)");
      glow.addColorStop(1, "rgba(255,196,90,0)");
    } else {
      glow.addColorStop(0, "rgba(226,238,255,0.9)");
      glow.addColorStop(0.35, "rgba(176,206,255,0.28)");
      glow.addColorStop(1, "rgba(140,170,255,0)");
    }
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, radius * 3.4, 0, TAU);
    ctx.fill();
    ctx.fillStyle = isDay ? "rgba(255,246,206,1)" : "rgba(232,240,255,1)";
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, TAU);
    ctx.fill();
    if (!isDay) {
      ctx.fillStyle = "rgba(176,192,220,0.55)";
      ctx.beginPath();
      ctx.arc(x - 6, y - 4, 4, 0, TAU);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x + 7, y + 5, 3, 0, TAU);
      ctx.fill();
    }
    // A soft horizon haze keeps the sun from looking pasted on.
    if (isDay && light > 0.8) {
      const haze = ctx.createLinearGradient(0, 330, 0, 470);
      haze.addColorStop(0, "rgba(255,240,205,0)");
      haze.addColorStop(1, "rgba(255,240,205,0.16)");
      ctx.fillStyle = haze;
      ctx.fillRect(0, 330, CONFIG.viewWidth, 140);
    }
  }

  function drawClouds(ctx, state) {
    const drift = state.reducedMotion ? 0 : state.time * 180;
    const cameraShift = state.camera.x * 0.05;
    for (let index = 0; index < 6; index += 1) {
      const baseX = RNG.unitHash(index, 31, 4) * (CONFIG.viewWidth + 320);
      const x = ((baseX + drift - cameraShift) % (CONFIG.viewWidth + 320) + CONFIG.viewWidth + 320) % (CONFIG.viewWidth + 320) - 160;
      const y = 44 + RNG.unitHash(index, 37, 8) * 150;
      const scale = 0.7 + RNG.unitHash(index, 41, 2) * 0.9;
      const alpha = 0.16 + RNG.unitHash(index, 43, 6) * 0.14;
      ctx.fillStyle = "rgba(255,255,255," + alpha.toFixed(3) + ")";
      ctx.beginPath();
      ctx.arc(x, y, 26 * scale, 0, TAU);
      ctx.arc(x + 30 * scale, y - 8 * scale, 20 * scale, 0, TAU);
      ctx.arc(x + 58 * scale, y + 2 * scale, 24 * scale, 0, TAU);
      ctx.fill();
    }
  }

  function drawHills(ctx, state, light) {
    const camera = state.camera;
    const factor = 0.55 + 0.35 * light;
    const near = [86, 112, 140].map(function (value) { return Math.round(value * factor); });
    const far = [116, 142, 170].map(function (value) { return Math.round(value * factor); });
    // Anchor the parallax range to the world's base surface line so hills sit behind
    // the terrain silhouette instead of floating in front of it as the camera moves.
    const horizon = CONFIG.baseSurfaceRow * CONFIG.tileSize - camera.y;

    ctx.save();
    ctx.globalAlpha = 0.42;
    ctx.fillStyle = rgb(far);
    const farOffset = -(camera.x * 0.1) % 200;
    for (let index = -1; index < 7; index += 1) {
      const x = farOffset + index * 200;
      ctx.beginPath();
      ctx.arc(x + 100, horizon + 40, 120, Math.PI, 0);
      ctx.fill();
    }

    ctx.globalAlpha = 0.58;
    ctx.fillStyle = rgb(near);
    const nearOffset = -(camera.x * 0.24) % 160;
    for (let index = -1; index < 9; index += 1) {
      const x = nearOffset + index * 160;
      ctx.beginPath();
      ctx.arc(x + 80, horizon + 80, 90, Math.PI, 0);
      ctx.fill();
    }
    ctx.restore();

    const mist = ctx.createLinearGradient(0, horizon + 20, 0, CONFIG.viewHeight);
    mist.addColorStop(0, "rgba(255,255,255,0)");
    mist.addColorStop(1, "rgba(210,230,245," + (0.05 + light * 0.06).toFixed(3) + ")");
    ctx.fillStyle = mist;
    ctx.fillRect(0, Math.max(0, horizon + 20), CONFIG.viewWidth, CONFIG.viewHeight - Math.max(0, horizon + 20));
  }

  function visibleRange(camera, world) {
    const tile = CONFIG.tileSize;
    return {
      x0: Math.max(0, Math.floor(camera.x / tile)),
      x1: Math.min(world.width - 1, Math.ceil((camera.x + CONFIG.viewWidth) / tile)),
      y0: Math.max(0, Math.floor(camera.y / tile)),
      y1: Math.min(world.height - 1, Math.ceil((camera.y + CONFIG.viewHeight) / tile))
    };
  }

  function drawBlockFace(ctx, blockId, x, y, size, palette, seed) {
    const base = palette.base;
    const accent = palette.accent;
    ctx.fillStyle = rgb(base);
    ctx.fillRect(x, y, size, size);

    const detail = function (salt) {
      return RNG.unitHash(x, y, (seed + salt) >>> 0);
    };

    if (blockId === CONFIG.blocks.grass) {
      ctx.fillStyle = rgb(accent);
      ctx.fillRect(x, y, size, 7);
      const offset = Math.floor(detail(3) * (size - 14)) + 3;
      ctx.fillStyle = "rgba(24,52,24,0.35)";
      ctx.fillRect(x + offset, y + 1, 2, 5);
      ctx.fillRect(x + offset + 9, y + 2, 2, 4);
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      ctx.fillRect(x, y + 7, size, 1);
      if (detail(53) > 0.82) {
        const flowerX = x + 5 + Math.floor(detail(57) * (size - 10));
        const flowerY = y + 8;
        ctx.fillStyle = "rgba(46,86,40,0.8)";
        ctx.fillRect(flowerX, flowerY, 1, 5);
        ctx.fillStyle = detail(59) > 0.5 ? "rgba(255,214,120,0.95)" : "rgba(240,240,255,0.9)";
        ctx.fillRect(flowerX - 2, flowerY - 1, 5, 3);
        ctx.fillStyle = "rgba(255,170,90,0.9)";
        ctx.fillRect(flowerX, flowerY, 1, 1);
      }
    } else if (blockId === CONFIG.blocks.dirt) {
      ctx.fillStyle = rgb(accent);
      for (let index = 0; index < 3; index += 1) {
        const px = x + 3 + Math.floor(detail(11 + index) * (size - 8));
        const py = y + 3 + Math.floor(detail(21 + index) * (size - 8));
        ctx.fillRect(px, py, 3, 2);
      }
    } else if (blockId === CONFIG.blocks.stone) {
      ctx.fillStyle = "rgba(255,255,255,0.16)";
      ctx.fillRect(x + 3, y + 3, size - 6, 2);
      ctx.strokeStyle = "rgba(24,28,33,0.32)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + 4, y + size - 8);
      ctx.lineTo(x + size - 7, y + size - 14);
      ctx.lineTo(x + size - 3, y + size - 10);
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.1)";
      ctx.fillRect(x + 6, y + 9, 4, 2);
      if (detail(67) > 0.86) {
        ctx.fillStyle = "rgba(32,36,42,0.55)";
        ctx.fillRect(x + 12, y + 16, 5, 3);
        ctx.fillRect(x + 14, y + 18, 3, 2);
        ctx.fillStyle = "rgba(255,255,255,0.12)";
        ctx.fillRect(x + 13, y + 15, 2, 1);
      }
    } else if (blockId === CONFIG.blocks.wood) {
      ctx.fillStyle = "rgba(50,30,12,0.3)";
      ctx.fillRect(x + 4, y + 2, 2, size - 4);
      ctx.fillRect(x + size - 7, y + 2, 2, size - 4);
      ctx.fillStyle = rgb(accent);
      ctx.fillRect(x + 8, y + 3, 2, size - 6);
      ctx.fillStyle = "rgba(50,30,12,0.22)";
      ctx.fillRect(x + size / 2 - 1, y + 6, 2, size - 12);
    } else if (blockId === CONFIG.blocks.leaves) {
      ctx.fillStyle = "rgba(10,40,16,0.24)";
      ctx.beginPath();
      ctx.arc(x + 9, y + 11, 5, 0, TAU);
      ctx.arc(x + size - 10, y + size - 12, 4, 0, TAU);
      ctx.fill();
      ctx.fillStyle = rgb(accent);
      ctx.fillRect(x + 5, y + size - 12, 4, 3);
      ctx.fillRect(x + size - 12, y + 8, 4, 3);
    } else if (blockId === CONFIG.blocks.sand) {
      ctx.fillStyle = "rgba(120,90,40,0.2)";
      for (let index = 0; index < 4; index += 1) {
        const px = x + 3 + Math.floor(detail(31 + index) * (size - 6));
        const py = y + 3 + Math.floor(detail(41 + index) * (size - 6));
        ctx.fillRect(px, py, 2, 1);
      }
      ctx.fillStyle = "rgba(255,255,255,0.18)";
      ctx.fillRect(x, y, size, 2);
    } else if (blockId === CONFIG.blocks.planks) {
      ctx.fillStyle = "rgba(70,40,12,0.34)";
      ctx.fillRect(x, y + size / 2 - 1, size, 2);
      ctx.fillRect(x, y + size - 3, size, 2);
      ctx.fillStyle = rgb(accent);
      ctx.fillRect(x, y + 1, size, 2);
      ctx.fillStyle = "rgba(50,30,10,0.5)";
      ctx.fillRect(x + 6, y + 6, 2, 2);
      ctx.fillRect(x + size - 9, y + size - 8, 2, 2);
    } else if (blockId === CONFIG.blocks.glass) {
      ctx.fillStyle = "rgba(180,232,238,0.24)";
      ctx.fillRect(x, y, size, size);
      ctx.strokeStyle = "rgba(226,250,252,0.72)";
      ctx.lineWidth = 2;
      ctx.strokeRect(x + 1, y + 1, size - 2, size - 2);
      ctx.strokeStyle = "rgba(255,255,255,0.55)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x + 5, y + size - 7);
      ctx.lineTo(x + size - 7, y + 5);
      ctx.stroke();
    } else if (blockId === CONFIG.blocks.brick) {
      ctx.strokeStyle = "rgba(40,16,12,0.42)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y + size / 2);
      ctx.lineTo(x + size, y + size / 2);
      ctx.moveTo(x + size / 2, y);
      ctx.lineTo(x + size / 2, y + size / 2);
      ctx.moveTo(x + size / 4, y + size / 2);
      ctx.lineTo(x + size / 4, y + size);
      ctx.moveTo(x + (size * 3) / 4, y + size / 2);
      ctx.lineTo(x + (size * 3) / 4, y + size);
      ctx.stroke();
    }

    ctx.strokeStyle = "rgba(0,0,0,0.12)";
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
  }

  function drawBedrockFace(ctx, x, y, size, seed) {
    ctx.fillStyle = "rgb(56,60,68)";
    ctx.fillRect(x, y, size, size);
    ctx.fillStyle = "rgb(38,41,47)";
    ctx.fillRect(x, y, size, 4);
    ctx.fillRect(x, y + size - 4, size, 4);
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.fillRect(x + 4, y + 6, size - 14, 2);
    ctx.fillRect(x + 9, y + size - 10, size - 18, 2);
    ctx.strokeStyle = "rgba(18,20,24,0.6)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 5, y + 8);
    ctx.lineTo(x + size - 8, y + size / 2);
    ctx.lineTo(x + 7, y + size - 7);
    ctx.stroke();
    ctx.fillStyle = "rgba(150,158,170,0.18)";
    ctx.fillRect(x + Math.floor(RNG.unitHash(x, y, seed + 5) * (size - 10)) + 3, y + 13, 4, 2);
    ctx.strokeStyle = "rgba(0,0,0,0.22)";
    ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
  }

  function drawWorld(ctx, state) {
    const world = state.world;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const light = Time.lightLevel(state.time);
    const range = visibleRange(camera, world);
    const caveFill = "rgba(30,26,26," + (0.78 + 0.12 * light).toFixed(3) + ")";
    const bedrockTop = world.height - CONFIG.bedrockRows;

    for (let y = range.y0; y <= range.y1; y += 1) {
      for (let x = range.x0; x <= range.x1; x += 1) {
        const block = world.data[y * world.width + x];
        const sx = Math.round(x * tile - camera.x);
        const sy = Math.round(y * tile - camera.y);
        if (y >= bedrockTop) {
          drawBedrockFace(ctx, sx, sy, tile, world.seed);
          continue;
        }
        if (block === CONFIG.blocks.air) {
          // Air below the generated surface is a cave, not a window to the sky.
          if (y > World.surfaceHeightAt(world.seed, x)) {
            ctx.fillStyle = caveFill;
            ctx.fillRect(sx, sy, tile, tile);
            ctx.fillStyle = "rgba(255,255,255,0.035)";
            ctx.fillRect(sx + 4, sy + 6, tile - 12, 2);
          }
          continue;
        }
        drawBlockFace(ctx, block, sx, sy, tile, blockPalette(block, light), world.seed);
      }
    }
  }

  function drawMining(ctx, state) {
    const mining = state.mining;
    if (!mining || !mining.active || !mining.tile) {
      return;
    }
    const tile = CONFIG.tileSize;
    const x = Math.round(mining.tile.x * tile - state.camera.x);
    const y = Math.round(mining.tile.y * tile - state.camera.y);
    const progress = Math.max(0, Math.min(1, mining.progress || 0));

    ctx.fillStyle = "rgba(0,0,0," + (0.16 + 0.16 * progress).toFixed(3) + ")";
    ctx.fillRect(x, y, tile, tile);

    const cracks = [
      [0.02, [[0.16, 0.14], [0.44, 0.38], [0.36, 0.62], [0.52, 0.82]]],
      [0.35, [[0.82, 0.08], [0.58, 0.34], [0.76, 0.58], [0.62, 0.78]]],
      [0.62, [[0.1, 0.68], [0.34, 0.76], [0.24, 0.96]]],
      [0.85, [[0.72, 0.88], [0.9, 0.72], [0.82, 0.98]]]
    ];
    ctx.strokeStyle = "rgba(14,10,8,0.88)";
    ctx.lineWidth = 3;
    for (let index = 0; index < cracks.length; index += 1) {
      if (progress < cracks[index][0]) {
        continue;
      }
      const points = cracks[index][1];
      for (let pass = 0; pass < 2; pass += 1) {
        ctx.strokeStyle = pass === 0 ? "rgba(14,10,8,0.88)" : "rgba(255,255,255,0.32)";
        ctx.lineWidth = pass === 0 ? 4 : 1;
        ctx.beginPath();
        for (let point = 0; point < points.length; point += 1) {
          const px = x + points[point][0] * tile;
          const py = y + points[point][1] * tile + (pass === 1 ? 1 : 0);
          if (point === 0) {
            ctx.moveTo(px, py);
          } else {
            ctx.lineTo(px, py);
          }
        }
        ctx.stroke();
      }
    }
  }

  function drawSelection(ctx, state) {
    if (!state.hover) {
      return;
    }
    const tile = CONFIG.tileSize;
    const x = Math.round(state.hover.x * tile - state.camera.x);
    const y = Math.round(state.hover.y * tile - state.camera.y);
    const reachable = state.hover.reachable !== false;
    const color = reachable ? "rgba(255,196,107,0.95)" : "rgba(255,122,107,0.95)";

    ctx.fillStyle = reachable ? "rgba(255,196,107,0.09)" : "rgba(255,122,107,0.08)";
    ctx.fillRect(x, y, tile, tile);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, tile - 1, tile - 1);
    ctx.lineWidth = 3;
    const corner = 8;
    const corners = [
      [x + 1, y + 1, 1, 1],
      [x + tile - 1, y + 1, -1, 1],
      [x + 1, y + tile - 1, 1, -1],
      [x + tile - 1, y + tile - 1, -1, -1]
    ];
    ctx.beginPath();
    for (let index = 0; index < corners.length; index += 1) {
      const cx = corners[index][0];
      const cy = corners[index][1];
      const dx = corners[index][2] * corner;
      const dy = corners[index][3] * corner;
      ctx.moveTo(cx + dx, cy);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx, cy + dy);
    }
    ctx.stroke();
  }

  function drawParticles(ctx, state) {
    const particles = state.particles || [];
    for (let index = 0; index < particles.length; index += 1) {
      const particle = particles[index];
      const alpha = Math.max(0, Math.min(1, particle.life / particle.maxLife));
      const x = particle.x * CONFIG.tileSize - state.camera.x;
      const y = particle.y * CONFIG.tileSize - state.camera.y;
      ctx.fillStyle = "rgba(" + particle.color[0] + "," + particle.color[1] + "," + particle.color[2] + "," + alpha.toFixed(3) + ")";
      ctx.fillRect(Math.round(x), Math.round(y), particle.size, particle.size);
    }
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const feetX = player.x * tile - camera.x;
    const feetY = player.y * tile - camera.y;
    const w = player.width * tile;
    const h = player.height * tile;
    const bob = player.onGround && Math.abs(player.vx) > 0.1 ? Math.sin(player.walkTime * 14) * 1.4 : 0;
    const swing = player.onGround && Math.abs(player.vx) > 0.1 ? Math.sin(player.walkTime * 14) * 4 : 0;
    const left = feetX - w / 2;
    const top = feetY - h + bob;
    const facing = player.facing < 0 ? -1 : 1;

    ctx.fillStyle = "rgba(0,0,0,0.22)";
    ctx.beginPath();
    ctx.arc(feetX, feetY + 2, w * 0.62, 0, TAU);
    ctx.fill();

    // legs
    ctx.fillStyle = "#33506b";
    if (player.onGround) {
      ctx.fillRect(left + 3, top + h * 0.62 + swing, w * 0.36, h * 0.38 - swing);
      ctx.fillRect(left + w - 3 - w * 0.36, top + h * 0.62 - swing, w * 0.36, h * 0.38 + swing);
    } else {
      ctx.fillRect(left + 3, top + h * 0.64, w * 0.36, h * 0.3);
      ctx.fillRect(left + w - 3 - w * 0.36, top + h * 0.6, w * 0.36, h * 0.34);
    }

    // torso
    ctx.fillStyle = "#e9a13c";
    ctx.fillRect(left + 2, top + h * 0.34, w - 4, h * 0.3);
    ctx.fillStyle = "rgba(255,255,255,0.2)";
    ctx.fillRect(left + 2, top + h * 0.34, w - 4, 3);

    // arm
    ctx.fillStyle = "#c9862c";
    if (facing > 0) {
      ctx.fillRect(left + w - 5, top + h * 0.36, 5, h * 0.24);
    } else {
      ctx.fillRect(left, top + h * 0.36, 5, h * 0.24);
    }

    // pickaxe swing while a break is in progress
    if (state.mining && state.mining.active) {
      const swing = Math.sin(Math.min(1, state.mining.progress || 0) * Math.PI);
      const handX = facing > 0 ? left + w - 2 : left + 2;
      const handY = top + h * 0.48;
      const tipX = handX + facing * (12 + swing * 15);
      const tipY = handY - 9 + swing * 14;
      ctx.strokeStyle = "rgba(255,255,255,0.4)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(handX, handY, 21, -1.1, -1.1 + swing * 1.4);
      ctx.stroke();
      ctx.strokeStyle = "#5d3417";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(handX, handY);
      ctx.lineTo(tipX, tipY);
      ctx.stroke();
      ctx.fillStyle = "#2a2f36";
      ctx.fillRect(tipX - 6, tipY - 5, 14, 9);
      ctx.fillStyle = "#d7e0e8";
      ctx.fillRect(tipX - 5, tipY - 4, 12, 7);
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillRect(tipX + 2, tipY - 3, 3, 2);
    }

    // head
    ctx.fillStyle = "#f2c49b";
    ctx.fillRect(left + 2, top, w - 4, h * 0.34);
    ctx.fillStyle = "#3a2a20";
    ctx.fillRect(left + 1, top - 2, w - 2, 6);
    ctx.fillRect(left + 1, top, 3, h * 0.12);
    // face
    ctx.fillStyle = "#2a2320";
    const eyeX = facing > 0 ? left + w - 8 : left + 5;
    ctx.fillRect(eyeX, top + 9, 2, 3);
    ctx.fillRect(eyeX + (facing > 0 ? -6 : 6), top + 9, 2, 3);
  }

  function drawNight(ctx, state) {
    const light = Time.lightLevel(state.time);
    const darkness = Math.min(0.72, Math.max(0, (1 - light) * 0.78));
    if (darkness > 0.02) {
      ctx.fillStyle = "rgba(8,14,34," + darkness.toFixed(3) + ")";
      ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);

      const px = state.player.x * CONFIG.tileSize - state.camera.x;
      const py = state.player.y * CONFIG.tileSize - state.camera.y - CONFIG.tileSize;
      const glow = ctx.createRadialGradient(px, py, 8, px, py, 190);
      glow.addColorStop(0, "rgba(255,214,150," + (0.26 * (1 - light)).toFixed(3) + ")");
      glow.addColorStop(0.5, "rgba(255,190,120," + (0.08 * (1 - light)).toFixed(3) + ")");
      glow.addColorStop(1, "rgba(255,180,110,0)");
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(px, py, 190, 0, TAU);
      ctx.fill();
      ctx.restore();
    }
    const vignette = ctx.createRadialGradient(
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      180,
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      620
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(1, "rgba(0,0,0,0.3)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
  }

  function renderMinimap(ctx, world, player, camera, size) {
    const width = size && size.width ? size.width : 180;
    const height = size && size.height ? size.height : 64;
    const worldPixelsW = world.width * CONFIG.tileSize;
    const worldPixelsH = world.height * CONFIG.tileSize;

    ctx.fillStyle = "#0a1422";
    ctx.fillRect(0, 0, width, height);
    for (let px = 0; px < width; px += 1) {
      const worldX = Math.min(world.width - 1, Math.floor((px / width) * world.width));
      const surface = World.surfaceHeightAt(world.seed, worldX);
      const sy = Math.round((surface / world.height) * height);
      ctx.fillStyle = "rgba(74,96,88,0.65)";
      ctx.fillRect(px, sy, 1, Math.max(0, height - sy));
      ctx.fillStyle = surface <= CONFIG.sandMaxSurfaceRow ? "#d7c088" : "#5c9e4a";
      ctx.fillRect(px, sy, 1, 2);
    }

    const viewX = (camera.x / worldPixelsW) * width;
    const viewY = (camera.y / worldPixelsH) * height;
    const viewW = (CONFIG.viewWidth / worldPixelsW) * width;
    const viewH = (CONFIG.viewHeight / worldPixelsH) * height;
    ctx.strokeStyle = "rgba(255,255,255,0.65)";
    ctx.lineWidth = 1;
    ctx.strokeRect(
      Math.round(viewX) + 0.5,
      Math.round(viewY) + 0.5,
      Math.max(3, Math.round(viewW) - 1),
      Math.max(2, Math.round(viewH) - 1)
    );

    const playerX = Math.round((player.x / world.width) * width);
    const playerY = Math.round((player.y / world.height) * height);
    ctx.fillStyle = "rgba(255,196,107,0.3)";
    ctx.fillRect(playerX - 3, playerY - 3, 7, 7);
    ctx.fillStyle = "#ffc46b";
    ctx.fillRect(playerX - 1, playerY - 1, 3, 3);

    ctx.strokeStyle = "rgba(255,255,255,0.18)";
    ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
  }

  function renderFrame(ctx, state) {
    const normalized = {
      world: state.world,
      player: state.player,
      camera: state.camera,
      time: typeof state.time === "number" ? state.time : CONFIG.time.startFraction,
      hover: state.hover || null,
      mining: state.mining || null,
      particles: state.particles || [],
      reducedMotion: state.reducedMotion === true
    };
    drawSky(ctx, normalized);
    drawWorld(ctx, normalized);
    drawMining(ctx, normalized);
    drawSelection(ctx, normalized);
    drawParticles(ctx, normalized);
    drawPlayer(ctx, normalized);
    drawNight(ctx, normalized);
  }

  return {
    renderFrame: renderFrame,
    renderMinimap: renderMinimap,
    drawSky: drawSky,
    drawWorld: drawWorld,
    drawPlayer: drawPlayer,
    drawSelection: drawSelection,
    drawMining: drawMining,
    drawParticles: drawParticles,
    drawNight: drawNight,
    visibleRange: visibleRange,
    hexToRgb: hexToRgb
  };
});
