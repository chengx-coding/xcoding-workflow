/* Canvas renderer: sky, parallax, tiles, characters, selection and particles. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"), require("./textures.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig, root.SandboxRng, root.SandboxTextures);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG, TEX) {
  "use strict";

  const B = CONFIG.blocks;
  const TILE = CONFIG.tileSize;

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function mix(a, b, t) {
    return a + (b - a) * t;
  }

  function hexToRgb(hex) {
    const value = hex.replace("#", "");
    return [
      parseInt(value.slice(0, 2), 16),
      parseInt(value.slice(2, 4), 16),
      parseInt(value.slice(4, 6), 16)
    ];
  }

  function mixColor(a, b, t) {
    const ca = hexToRgb(a);
    const cb = hexToRgb(b);
    return "rgb(" + Math.round(mix(ca[0], cb[0], t)) + "," + Math.round(mix(ca[1], cb[1], t)) + "," + Math.round(mix(ca[2], cb[2], t)) + ")";
  }

  const SKY_KEYS = [
    { t: 0.0, top: "#ef9a63", bottom: "#ffe1b0" },
    { t: 0.1, top: "#72bbe8", bottom: "#cdeeff" },
    { t: 0.25, top: "#56a8df", bottom: "#bde7fa" },
    { t: 0.42, top: "#6ab1df", bottom: "#ffd39b" },
    { t: 0.5, top: "#e8765f", bottom: "#71406e" },
    { t: 0.58, top: "#20264a", bottom: "#11172d" },
    { t: 0.75, top: "#070c1c", bottom: "#101a34" },
    { t: 0.9, top: "#1b2142", bottom: "#3a2b48" },
    { t: 1.0, top: "#ef9a63", bottom: "#ffe1b0" }
  ];

  function skyColors(time) {
    const t = ((time % 1) + 1) % 1;
    for (let i = 0; i < SKY_KEYS.length - 1; i += 1) {
      const a = SKY_KEYS[i];
      const b = SKY_KEYS[i + 1];
      if (t >= a.t && t <= b.t) {
        const local = (t - a.t) / (b.t - a.t || 1);
        return {
          top: mixColor(a.top, b.top, local),
          bottom: mixColor(a.bottom, b.bottom, local),
          phase: local
        };
      }
    }
    return { top: SKY_KEYS[0].top, bottom: SKY_KEYS[0].bottom, phase: 0 };
  }

  function nightAmount(time) {
    const t = ((time % 1) + 1) % 1;
    const angle = (t - 0.25) * Math.PI * 2;
    return clamp((1 - Math.cos(angle)) / 2, 0, 1);
  }

  function drawSky(ctx, time, viewWidth, viewHeight, shakeX, shakeY) {
    const colors = skyColors(time);
    const gradient = ctx.createLinearGradient(0, -shakeY, 0, viewHeight - shakeY);
    gradient.addColorStop(0, colors.top);
    gradient.addColorStop(1, colors.bottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(-shakeX, -shakeY, viewWidth + Math.abs(shakeX) * 2, viewHeight + Math.abs(shakeY) * 2);
    return colors;
  }

  function drawStars(ctx, time, viewWidth, viewHeight) {
    const night = nightAmount(time);
    if (night <= 0.05) {
      return;
    }
    const random = RNG.mulberry32(918273);
    ctx.save();
    ctx.globalAlpha = night * 0.9;
    for (let i = 0; i < 110; i += 1) {
      const x = Math.floor(random() * viewWidth);
      const y = Math.floor(random() * viewHeight * 0.62);
      const size = random() < 0.12 ? 2 : 1;
      ctx.fillStyle = random() < 0.2 ? "#ffe9b0" : "#dbe8ff";
      ctx.fillRect(x, y, size, size);
    }
    ctx.restore();
  }

  function drawCelestial(ctx, time, viewWidth, viewHeight, shakeX, shakeY) {
    const t = ((time % 1) + 1) % 1;
    const horizon = viewHeight * 0.62;
    const isDay = t < 0.5;
    const local = isDay ? t / 0.5 : (t - 0.5) / 0.5;
    const x = 70 + local * (viewWidth - 140);
    const y = horizon - Math.sin(local * Math.PI) * horizon * 0.82;
    ctx.save();
    ctx.translate(-shakeX, -shakeY);
    if (isDay) {
      const glow = ctx.createRadialGradient(x, y, 4, x, y, 70);
      glow.addColorStop(0, "rgba(255, 240, 170, 0.75)");
      glow.addColorStop(1, "rgba(255, 220, 120, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - 70, y - 70, 140, 140);
      ctx.fillStyle = "#ffe27a";
      ctx.fillRect(x - 14, y - 14, 28, 28);
      ctx.fillStyle = "#fff2b0";
      ctx.fillRect(x - 10, y - 10, 20, 20);
    } else {
      const glow = ctx.createRadialGradient(x, y, 4, x, y, 60);
      glow.addColorStop(0, "rgba(200, 220, 255, 0.35)");
      glow.addColorStop(1, "rgba(160, 190, 255, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - 60, y - 60, 120, 120);
      ctx.fillStyle = "#dce7ff";
      ctx.fillRect(x - 15, y - 15, 30, 30);
      ctx.fillStyle = "#0d1426";
      ctx.fillRect(x - 4, y - 16, 20, 20);
    }
    ctx.restore();
  }

  function drawClouds(ctx, time, camera, viewWidth, viewHeight, shakeX, shakeY) {
    const night = nightAmount(time);
    const random = RNG.mulberry32(4411);
    ctx.save();
    ctx.translate(-shakeX, -shakeY);
    ctx.globalAlpha = 0.34 + (1 - night) * 0.34;
    for (let i = 0; i < 11; i += 1) {
      const baseX = random() * 2200;
      const baseY = 40 + random() * 190;
      const scale = 0.7 + random() * 1.1;
      const drift = time * 160 + i * 37;
      let x = ((baseX - camera.x * 0.18 + drift) % (viewWidth + 360)) - 180;
      if (x < -220) {
        x += viewWidth + 360;
      }
      const y = baseY - camera.y * 0.08;
      ctx.fillStyle = night > 0.45 ? "#5a6382" : "#ffffff";
      ctx.fillRect(x, y, 86 * scale, 12 * scale);
      ctx.fillRect(x + 12 * scale, y - 8 * scale, 52 * scale, 12 * scale);
      ctx.fillRect(x + 26 * scale, y + 10 * scale, 38 * scale, 8 * scale);
      ctx.fillStyle = night > 0.45 ? "#6d7698" : "#e8f3fb";
      ctx.fillRect(x + 6 * scale, y + 4 * scale, 62 * scale, 4 * scale);
    }
    ctx.restore();
  }

  function drawHills(ctx, time, camera, viewWidth, viewHeight, shakeX, shakeY) {
    const colors = skyColors(time);
    const night = nightAmount(time);
    const horizon = viewHeight * 0.68 - camera.y * 0.12;
    ctx.save();
    ctx.translate(-shakeX, -shakeY);
    for (let layer = 0; layer < 2; layer += 1) {
      ctx.beginPath();
      ctx.moveTo(0, viewHeight);
      const parallax = layer === 0 ? 0.08 : 0.17;
      const base = horizon + layer * 44;
      for (let x = 0; x <= viewWidth + 40; x += 40) {
        const worldX = x + camera.x * parallax;
        const wave = Math.sin(worldX * (layer === 0 ? 0.006 : 0.009) + layer * 2.1) * (layer === 0 ? 34 : 24);
        const wave2 = RNG.noise1(worldX * 0.01, 71 + layer) * 18;
        ctx.lineTo(x, base + wave + wave2);
      }
      ctx.lineTo(viewWidth, viewHeight);
      ctx.closePath();
      const dark = layer === 0 ? 0.18 : 0.1;
      const baseColor = mixColor(colors.bottom, "#20303a", 0.42 + dark + night * 0.32);
      ctx.fillStyle = baseColor;
      ctx.fill();
    }
    ctx.restore();
  }

  function updateCamera(camera, player, world, viewWidth, viewHeight, dt, lookX, lookY) {
    const targetX = player.x * TILE - viewWidth / 2 + clamp(lookX || 0, -70, 70);
    const targetY = (player.y - player.height * 0.55) * TILE - viewHeight / 2 + clamp(lookY || 0, -45, 45);
    const smooth = Math.min(1, (dt || 1 / 60) * 9);
    camera.x += (targetX - camera.x) * smooth;
    camera.y += (targetY - camera.y) * smooth;
    camera.x = clamp(camera.x, 0, Math.max(0, world.width * TILE - viewWidth));
    camera.y = clamp(camera.y, 0, Math.max(0, world.height * TILE - viewHeight));
    return camera;
  }

  function screenX(worldX, camera) {
    return worldX * TILE - camera.x;
  }

  function screenY(worldY, camera) {
    return worldY * TILE - camera.y;
  }

  function drawCaveWall(ctx, x, y, world, screen) {
    const depth = y - (world.surface[x] || 0);
    const hash = RNG.hash2(x, y, world.seed);
    if (depth < 5) {
      ctx.fillStyle = hash % 3 === 0 ? "#3a2a1d" : "#2f2318";
    } else {
      ctx.fillStyle = hash % 3 === 0 ? "#2a2b2d" : "#232426";
    }
    ctx.fillRect(screen.x, screen.y, TILE, TILE);
    if (hash % 7 === 0) {
      ctx.fillStyle = "rgba(255,255,255,0.035)";
      ctx.fillRect(screen.x + (hash % 20), screen.y + (hash % 16), 3, 3);
    }
  }

  function drawWorld(ctx, world, camera, viewWidth, viewHeight, time, shakeX, shakeY) {
    const firstColumn = Math.max(0, Math.floor(camera.x / TILE) - 1);
    const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + viewWidth) / TILE) + 1);
    const firstRow = Math.max(0, Math.floor(camera.y / TILE) - 1);
    const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + viewHeight) / TILE) + 1);
    const waterOffset = Math.floor((time * 24) % TILE);

    ctx.save();
    ctx.translate(-shakeX, -shakeY);
    for (let y = firstRow; y <= lastRow; y += 1) {
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const block = world.data[y * world.width + x];
        const sx = Math.round(x * TILE - camera.x);
        const sy = Math.round(y * TILE - camera.y);
        const screen = { x: sx, y: sy };
        if (block === B.air) {
          if (y > (world.surface[x] || 0) + 1) {
            drawCaveWall(ctx, x, y, world, screen);
          }
          continue;
        }
        if (block === B.water) {
          if (y > (world.surface[x] || 0) + 1) {
            drawCaveWall(ctx, x, y, world, screen);
          }
          const variants = TEX.blockVariants(B.water);
          const image = variants ? variants[0] : null;
          if (image) {
            ctx.save();
            ctx.globalAlpha = 0.82;
            ctx.drawImage(image, sx, sy + (waterOffset % 4), TILE, TILE);
            ctx.restore();
          } else {
            ctx.fillStyle = "#2b6ca6";
            ctx.fillRect(sx, sy, TILE, TILE);
          }
          if (y === firstRow || world.data[(y - 1) * world.width + x] !== B.water) {
            ctx.fillStyle = "rgba(180, 230, 255, 0.35)";
            ctx.fillRect(sx, sy, TILE, 2);
          }
          continue;
        }
        if ((block === B.flower || block === B.tallGrass || block === B.torch) && y > (world.surface[x] || 0) + 1) {
          drawCaveWall(ctx, x, y, world, screen);
        }
        const variants = TEX.blockVariants(block);
        const image = variants ? variants[RNG.hash2(x, y, world.seed) % variants.length] : null;
        if (image) {
          ctx.drawImage(image, sx, sy, TILE, TILE);
        } else {
          ctx.fillStyle = "#9e9e9e";
          ctx.fillRect(sx, sy, TILE, TILE);
        }
        if (block === B.grass) {
          ctx.fillStyle = "rgba(255,255,255,0.06)";
          ctx.fillRect(sx, sy, TILE, 2);
        }
      }
    }
    ctx.restore();
  }

  function drawSelection(ctx, target, camera, progress, valid, shakeX, shakeY) {
    if (!target) {
      return;
    }
    const x = Math.round(target.x * TILE - camera.x) - shakeX;
    const y = Math.round(target.y * TILE - camera.y) - shakeY;
    ctx.save();
    ctx.lineWidth = 2;
    ctx.strokeStyle = valid === false ? "rgba(255, 96, 96, 0.95)" : "rgba(255, 255, 255, 0.85)";
    ctx.strokeRect(x + 1, y + 1, TILE - 2, TILE - 2);
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, TILE - 1, TILE - 1);
    if (progress > 0 && progress < 1) {
      ctx.strokeStyle = "rgba(20, 14, 10, 0.85)";
      ctx.lineWidth = 1;
      const stage = Math.floor(progress * 5);
      for (let i = 0; i <= stage; i += 1) {
        const offset = (i * 5) % 20;
        ctx.beginPath();
        ctx.moveTo(x + 2 + offset * 0.4, y + 3);
        ctx.lineTo(x + 6 + offset * 0.3, y + 10 + (i % 3) * 3);
        ctx.lineTo(x + 3 + offset * 0.2, y + 19);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawPlayer(ctx, player, camera, time, shakeX, shakeY) {
    const sx = Math.round(player.x * TILE - camera.x) - shakeX;
    const sy = Math.round(player.y * TILE - camera.y) - shakeY;
    const w = Math.round(player.width * TILE);
    const h = Math.round(player.height * TILE);
    const walk = Math.sin(player.walkTime) * (player.moving ? 1 : 0);
    const hurt = player.hurtCooldown > 0 && Math.floor(time * 30) % 2 === 0;

    ctx.save();
    ctx.translate(sx, sy);
    ctx.scale(player.facing >= 0 ? 1 : -1, 1);
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.beginPath();
    ctx.ellipse(0, 1, w * 0.62, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    const bodyTop = -h + 4;
    const skin = hurt ? "#ff9a9a" : "#e3b07a";
    const shirt = hurt ? "#f2b2b2" : "#2f8f83";
    const pants = hurt ? "#e0a0a0" : "#3b4a7a";
    const hair = "#4a2f1b";

    // Legs
    ctx.fillStyle = pants;
    ctx.fillRect(-7, -12, 6, 11 + walk * 2);
    ctx.fillRect(1, -12, 6, 11 - walk * 2);
    ctx.fillStyle = "#2b2b33";
    ctx.fillRect(-7, -2 + walk * 2, 6, 2);
    ctx.fillRect(1, -2 - walk * 2, 6, 2);

    // Body
    ctx.fillStyle = shirt;
    ctx.fillRect(-8, bodyTop + 15, 16, 16);
    ctx.fillStyle = "rgba(255,255,255,0.13)";
    ctx.fillRect(-8, bodyTop + 15, 3, 16);

    // Arms
    const swing = player.swing > 0 ? Math.sin(player.swing * Math.PI) : 0;
    ctx.fillStyle = shirt;
    ctx.fillRect(-11, bodyTop + 16 - swing * 4, 3, 13);
    ctx.fillStyle = skin;
    ctx.fillRect(-11, bodyTop + 27 - swing * 4, 3, 4);
    ctx.fillStyle = shirt;
    ctx.fillRect(8, bodyTop + 16 + swing * 4, 3, 13);
    ctx.fillStyle = skin;
    ctx.fillRect(8, bodyTop + 27 + swing * 4, 3, 4);

    // Head
    ctx.fillStyle = skin;
    ctx.fillRect(-8, bodyTop, 16, 15);
    ctx.fillStyle = hair;
    ctx.fillRect(-9, bodyTop - 2, 18, 6);
    ctx.fillRect(-9, bodyTop - 2, 5, 11);
    ctx.fillStyle = "#2b2b33";
    ctx.fillRect(2, bodyTop + 6, 2, 2);
    ctx.fillRect(-4, bodyTop + 6, 2, 2);
    ctx.fillStyle = "rgba(120, 70, 40, 0.55)";
    ctx.fillRect(-1, bodyTop + 10, 4, 1);

    // Hand item (a small tool silhouette so the selected slot reads in-world)
    if (player.heldItem && player.heldItem.kind === "tool") {
      ctx.fillStyle = "#c9ced4";
      ctx.fillRect(11, bodyTop + 12 + swing * 4, 2, 10);
    } else if (player.heldItem && player.heldItem.kind === "block") {
      ctx.fillStyle = "#b07a43";
      ctx.fillRect(10, bodyTop + 18 + swing * 4, 5, 5);
    }
    ctx.restore();
  }

  function drawEntities(ctx, entities, camera, time, shakeX, shakeY) {
    if (!entities || !entities.length) {
      return;
    }
    for (const entity of entities) {
      const sx = Math.round(entity.x * TILE - camera.x) - shakeX;
      const sy = Math.round(entity.y * TILE - camera.y) - shakeY;
      const w = Math.round((entity.width || 0.8) * TILE);
      const h = Math.round((entity.height || 0.9) * TILE);
      ctx.save();
      ctx.translate(sx, sy);
      const hurt = entity.hurt > 0 && Math.floor(time * 24) % 2 === 0;
      ctx.fillStyle = "rgba(0,0,0,0.2)";
      ctx.beginPath();
      ctx.ellipse(0, 1, w * 0.55, 3, 0, 0, Math.PI * 2);
      ctx.fill();
      if (entity.type === "slime") {
        const squash = 1 + Math.sin(time * 6 + entity.phase) * 0.12;
        ctx.fillStyle = hurt ? "#ffb3b3" : "#5fc46a";
        ctx.fillRect(-w / 2, -h * squash, w, h * squash);
        ctx.fillStyle = "#2f7d39";
        ctx.fillRect(-w / 2 + 3, -h * squash + 4, 3, 3);
        ctx.fillRect(w / 2 - 6, -h * squash + 4, 3, 3);
        ctx.fillStyle = "rgba(255,255,255,0.25)";
        ctx.fillRect(-w / 2 + 4, -h * squash + 6, 5, 4);
      } else if (entity.type === "zombie") {
        ctx.fillStyle = hurt ? "#ffb3b3" : "#4e7a4e";
        ctx.fillRect(-6, -h + 14, 12, 12);
        ctx.fillStyle = "#3d5f3d";
        ctx.fillRect(-6, -h + 14, 12, 4);
        ctx.fillStyle = "#5d8f5d";
        ctx.fillRect(-6, -h + 4, 5, 7);
        ctx.fillRect(1, -h + 4, 5, 7);
        ctx.fillStyle = "#d94b4b";
        ctx.fillRect(-4, -h + 7, 2, 2);
        ctx.fillRect(2, -h + 7, 2, 2);
        ctx.fillStyle = "#3a4a6a";
        ctx.fillRect(-6, -h + 24, 5, 7);
        ctx.fillRect(1, -h + 24, 5, 7);
      } else if (entity.type === "pig") {
        ctx.fillStyle = hurt ? "#ffb3b3" : "#e79a9a";
        ctx.fillRect(-w / 2, -h, w, h * 0.7);
        ctx.fillStyle = "#c97a7a";
        ctx.fillRect(-w / 2 + 2, -h + 4, 3, 3);
        ctx.fillRect(w / 2 - 5, -h + 4, 3, 3);
        ctx.fillStyle = "#d98a8a";
        ctx.fillRect(w / 2 - 2, -h + 7, 4, 4);
        ctx.fillStyle = "#8a4c4c";
        ctx.fillRect(-w / 2 + 3, -h + h * 0.7 - 2, 3, 4);
        ctx.fillRect(w / 2 - 6, -h + h * 0.7 - 2, 3, 4);
      } else if (entity.type === "chicken") {
        ctx.fillStyle = hurt ? "#ffb3b3" : "#f2f0e6";
        ctx.fillRect(-6, -h, 12, 9);
        ctx.fillStyle = "#e8c34a";
        ctx.fillRect(4, -h + 2, 4, 3);
        ctx.fillStyle = "#d94b4b";
        ctx.fillRect(-2, -h - 2, 4, 3);
        ctx.fillStyle = "#c9a23a";
        ctx.fillRect(-3, -2, 2, 3);
        ctx.fillRect(1, -2, 2, 3);
      }
      if (entity.health < entity.maxHealth) {
        const ratio = Math.max(0, entity.health / entity.maxHealth);
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        ctx.fillRect(-12, -h - 8, 24, 3);
        ctx.fillStyle = "#e74c4c";
        ctx.fillRect(-12, -h - 8, 24 * ratio, 3);
      }
      ctx.restore();
    }
  }

  function drawParticles(ctx, particles, camera, shakeX, shakeY) {
    if (!particles || !particles.length) {
      return;
    }
    ctx.save();
    for (const p of particles) {
      const x = p.x * TILE - camera.x - shakeX;
      const y = p.y * TILE - camera.y - shakeY;
      const alpha = Math.max(0, Math.min(1, p.life / p.maxLife));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      ctx.fillRect(Math.round(x), Math.round(y), p.size, p.size);
    }
    ctx.restore();
  }

  function drawNightTint(ctx, time, viewWidth, viewHeight, shakeX, shakeY) {
    const night = nightAmount(time);
    if (night <= 0.02) {
      return;
    }
    ctx.save();
    ctx.fillStyle = "rgba(8, 12, 30, " + (night * 0.38).toFixed(3) + ")";
    ctx.fillRect(-shakeX, -shakeY, viewWidth + Math.abs(shakeX) * 2, viewHeight + Math.abs(shakeY) * 2);
    ctx.restore();
  }

  function drawCrosshair(ctx, mouseX, mouseY) {
    ctx.save();
    ctx.fillStyle = "rgba(255,255,255,0.72)";
    ctx.fillRect(mouseX - 5, mouseY, 4, 1);
    ctx.fillRect(mouseX + 2, mouseY, 4, 1);
    ctx.fillRect(mouseX, mouseY - 5, 1, 4);
    ctx.fillRect(mouseX, mouseY + 2, 1, 4);
    ctx.restore();
  }

  function renderFrame(ctx, state) {
    const viewWidth = CONFIG.viewWidth;
    const viewHeight = CONFIG.viewHeight;
    const shake = state.shake || { x: 0, y: 0 };
    const shakeX = shake.x || 0;
    const shakeY = shake.y || 0;
    const time = state.time == null ? 0.3 : state.time;

    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, viewWidth, viewHeight);

    drawSky(ctx, time, viewWidth, viewHeight, shakeX, shakeY);
    drawStars(ctx, time, viewWidth, viewHeight);
    drawCelestial(ctx, time, viewWidth, viewHeight, shakeX, shakeY);
    drawClouds(ctx, time, state.camera, viewWidth, viewHeight, shakeX, shakeY);
    drawHills(ctx, time, state.camera, viewWidth, viewHeight, shakeX, shakeY);
    drawWorld(ctx, state.world, state.camera, viewWidth, viewHeight, time, shakeX, shakeY);
    drawEntities(ctx, state.entities, state.camera, time, shakeX, shakeY);
    drawPlayer(ctx, state.player, state.camera, time, shakeX, shakeY);
    drawParticles(ctx, state.particles, state.camera, shakeX, shakeY);
    if (state.lighting) {
      state.lighting(ctx, state, { shakeX: shakeX, shakeY: shakeY });
    } else {
      drawNightTint(ctx, time, viewWidth, viewHeight, shakeX, shakeY);
    }
    drawSelection(ctx, state.target, state.camera, state.miningProgress || 0, state.targetValid, shakeX, shakeY);
    if (state.showCrosshair !== false) {
      drawCrosshair(ctx, state.mouseX || viewWidth / 2, state.mouseY || viewHeight / 2);
    }
    ctx.restore();
  }

  return {
    renderFrame: renderFrame,
    updateCamera: updateCamera,
    screenX: screenX,
    screenY: screenY,
    skyColors: skyColors,
    nightAmount: nightAmount,
    drawNightTint: drawNightTint,
    drawSky: drawSky,
    drawWorld: drawWorld,
    drawPlayer: drawPlayer,
    TILE: TILE
  };
});
