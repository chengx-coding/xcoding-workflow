(function () {
  "use strict";

  const CONFIG = window.SandboxConfig;
  const WORLD = window.SandboxWorld;
  const TEXTURES = window.SandboxTextures;
  const RNG = window.SandboxRng;
  const TILE = CONFIG.tileSize;
  const VIEW_W = CONFIG.viewWidth;
  const VIEW_H = CONFIG.viewHeight;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function mix(a, b, t) {
    return [
      Math.round(a[0] + (b[0] - a[0]) * t),
      Math.round(a[1] + (b[1] - a[1]) * t),
      Math.round(a[2] + (b[2] - a[2]) * t)
    ];
  }

  function css(color, alpha) {
    if (alpha === undefined) {
      return "rgb(" + color[0] + "," + color[1] + "," + color[2] + ")";
    }
    return "rgba(" + color[0] + "," + color[1] + "," + color[2] + "," + alpha + ")";
  }

  function skyPalette(timeOfDay, dayFactor) {
    const sunHeight = Math.sin((timeOfDay - 0.25) * Math.PI * 2);
    const dayness = clamp(sunHeight * 2.3 + 0.38, 0, 1);
    const dusk = clamp(1 - Math.abs(sunHeight) * 3.7, 0, 1) * 0.9;
    const nightTop = [7, 13, 32];
    const nightBottom = [28, 42, 68];
    const dayTop = [91, 157, 202];
    const dayBottom = [203, 232, 235];
    const duskTop = [78, 49, 84];
    const duskBottom = [232, 133, 86];
    let top = mix(nightTop, dayTop, dayness);
    let bottom = mix(nightBottom, dayBottom, dayness);
    if (dusk > 0) {
      top = mix(top, duskTop, dusk);
      bottom = mix(bottom, duskBottom, dusk);
    }
    return {
      top: top,
      bottom: bottom,
      dayness: dayness,
      dusk: dusk,
      sunHeight: sunHeight
    };
  }

  function createRenderer(canvas) {
    const ctx = canvas.getContext("2d");
    canvas.width = VIEW_W;
    canvas.height = VIEW_H;
    ctx.imageSmoothingEnabled = false;
    const lightCanvas = document.createElement("canvas");
    const lightCtx = lightCanvas.getContext("2d");
    const stars = [];
    const clouds = [];
    const hillLayers = [];
    const starRand = RNG.sampleRng(CONFIG.seed, 12345);
    for (let index = 0; index < 90; index += 1) {
      stars.push({
        x: starRand() * VIEW_W,
        y: starRand() * VIEW_H * 0.7,
        r: starRand() < 0.15 ? 1.7 : 1,
        a: 0.35 + starRand() * 0.6
      });
    }
    const cloudRand = RNG.sampleRng(CONFIG.seed, 54321);
    for (let index = 0; index < 7; index += 1) {
      clouds.push({
        x: cloudRand() * VIEW_W,
        y: 40 + cloudRand() * 170,
        w: 80 + cloudRand() * 130,
        h: 16 + cloudRand() * 18,
        speed: 4 + cloudRand() * 8,
        alpha: 0.18 + cloudRand() * 0.22
      });
    }
    for (let layer = 0; layer < 3; layer += 1) {
      const rand = RNG.sampleRng(CONFIG.seed + 90 + layer, 707);
      const points = [];
      const step = 18 - layer * 3;
      for (let x = 0; x <= VIEW_W * 2 + step; x += step) {
        const wave = Math.sin(x * (0.012 + layer * 0.003) + layer * 2.1) * (22 - layer * 4);
        const detail = (rand() - 0.5) * (18 - layer * 4);
        points.push({ x: x, y: 120 + wave + detail + layer * 18 });
      }
      hillLayers.push({
        points: points,
        base: 395 + layer * 34,
        parallax: 0.08 + layer * 0.06,
        color: layer === 0 ? [68, 92, 92] : layer === 1 ? [48, 74, 64] : [31, 53, 46]
      });
    }

    function screenToWorld(clientX, clientY, camera) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = VIEW_W / rect.width;
      const scaleY = VIEW_H / rect.height;
      return {
        x: ((clientX - rect.left) * scaleX + camera.x) / TILE,
        y: ((clientY - rect.top) * scaleY + camera.y) / TILE
      };
    }

    function drawSky(state) {
      const palette = skyPalette(state.timeOfDay, state.dayFactor);
      const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
      gradient.addColorStop(0, css(palette.top));
      gradient.addColorStop(0.72, css(palette.bottom));
      gradient.addColorStop(1, css(mix(palette.bottom, [45, 51, 54], 0.3)));
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);

      const starAlpha = Math.pow(1 - palette.dayness, 2.1);
      if (starAlpha > 0.02) {
        for (let index = 0; index < stars.length; index += 1) {
          const star = stars[index];
          ctx.fillStyle = "rgba(246, 242, 220, " + (star.a * starAlpha) + ")";
          ctx.fillRect(Math.round(star.x), Math.round(star.y), star.r, star.r);
        }
      }

      const horizon = 424;
      if (palette.sunHeight > -0.08) {
        const dayT = clamp((state.timeOfDay - 0.25) / 0.5, 0, 1);
        const sunX = dayT * VIEW_W;
        const sunY = horizon - Math.sin(dayT * Math.PI) * 285;
        const glow = ctx.createRadialGradient(sunX, sunY, 4, sunX, sunY, 90);
        glow.addColorStop(0, "rgba(255, 238, 175, 0.9)");
        glow.addColorStop(0.18, "rgba(255, 205, 125, 0.45)");
        glow.addColorStop(1, "rgba(255, 164, 86, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(sunX - 100, sunY - 100, 200, 200);
        ctx.fillStyle = "#fff2b8";
        ctx.beginPath();
        ctx.arc(sunX, sunY, 22, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        ctx.beginPath();
        ctx.arc(sunX - 6, sunY - 6, 8, 0, Math.PI * 2);
        ctx.fill();
      } else {
        const nightT = clamp(((state.timeOfDay + 1) % 1 - 0.75) / 0.5, 0, 1);
        const moonX = nightT * VIEW_W;
        const moonY = horizon - Math.sin(nightT * Math.PI) * 265;
        ctx.fillStyle = "rgba(229, 237, 224, 0.9)";
        ctx.beginPath();
        ctx.arc(moonX, moonY, 19, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "rgba(35, 48, 65, 0.25)";
        ctx.beginPath();
        ctx.arc(moonX + 7, moonY - 5, 16, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "rgba(229,237,224,0.08)";
        ctx.beginPath();
        ctx.arc(moonX, moonY, 48, 0, Math.PI * 2);
        ctx.fill();
      }

      for (let index = 0; index < clouds.length; index += 1) {
        const cloud = clouds[index];
        const x = ((cloud.x + state.timeOfDay * 1800 * (cloud.speed / 8) - state.camera.x * 0.035) % (VIEW_W + 320)) - 160;
        const y = cloud.y - state.camera.y * 0.02;
        const alpha = cloud.alpha * (0.45 + palette.dayness * 0.55);
        ctx.fillStyle = "rgba(238, 244, 242, " + alpha + ")";
        const puffs = 4;
        for (let puff = 0; puff < puffs; puff += 1) {
          const offset = (puff - 1.5) * (cloud.w / 5);
          const radius = cloud.h * (0.6 + (puff % 2) * 0.45);
          ctx.beginPath();
          ctx.arc(x + offset, y + Math.sin(puff) * 3, radius, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillRect(x - cloud.w * 0.22, y, cloud.w * 0.55, cloud.h * 0.5);
      }
    }

    function drawHills(state) {
      const palette = skyPalette(state.timeOfDay, state.dayFactor);
      for (let layer = 0; layer < hillLayers.length; layer += 1) {
        const data = hillLayers[layer];
        const offset = -(state.camera.x * data.parallax) % (VIEW_W * 2);
        const tint = mix(data.color, palette.bottom, layer === 0 ? 0.35 : 0.12);
        const darkness = 1 - palette.dayness;
        const color = mix(tint, [11, 20, 24], darkness * 0.55);
        ctx.fillStyle = css(color);
        ctx.beginPath();
        ctx.moveTo(-VIEW_W, VIEW_H);
        for (let index = 0; index < data.points.length; index += 1) {
          const point = data.points[index];
          const x = point.x + offset - VIEW_W * 0.5;
          const y = data.base - point.y + state.camera.y * (1 - data.parallax) * 0.2;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(VIEW_W * 2, VIEW_H);
        ctx.closePath();
        ctx.fill();
      }
    }

    function drawCaveBackdrop(state) {
      const world = state.world;
      const camera = state.camera;
      const firstColumn = Math.max(0, Math.floor(camera.x / TILE) - 1);
      const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / TILE) + 1);
      const gradient = ctx.createLinearGradient(0, 0, 0, VIEW_H);
      gradient.addColorStop(0, "#241a16");
      gradient.addColorStop(0.55, "#171210");
      gradient.addColorStop(1, "#0d0b0c");
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const surfaceY = world.surface ? world.surface[x] : WORLD.findSurfaceY(world, x);
        const screenY = surfaceY * TILE - camera.y;
        if (screenY >= VIEW_H) {
          continue;
        }
        const left = Math.round(x * TILE - camera.x);
        ctx.fillStyle = gradient;
        ctx.fillRect(left, Math.max(0, Math.round(screenY)), TILE + 1, VIEW_H - Math.max(0, screenY));
      }
      ctx.fillStyle = "rgba(255, 232, 196, 0.03)";
      for (let x = firstColumn; x <= lastColumn; x += 1) {
        const surfaceY = world.surface ? world.surface[x] : WORLD.findSurfaceY(world, x);
        const screenY = Math.max(0, Math.round(surfaceY * TILE - camera.y));
        if (screenY < VIEW_H) {
          const left = Math.round(x * TILE - camera.x);
          for (let y = screenY + 22; y < VIEW_H; y += 34) {
            ctx.fillRect(left + 3, y, TILE - 6, 1);
          }
        }
      }
    }

    function drawWorld(state) {
      const world = state.world;
      const camera = state.camera;
      const firstColumn = Math.max(0, Math.floor(camera.x / TILE) - 1);
      const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / TILE) + 1);
      const firstRow = Math.max(0, Math.floor(camera.y / TILE) - 1);
      const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + VIEW_H) / TILE) + 1);
      for (let y = firstRow; y <= lastRow; y += 1) {
        for (let x = firstColumn; x <= lastColumn; x += 1) {
          const block = world.data[y * world.width + x];
          if (block === CONFIG.blocks.air) {
            continue;
          }
          const variant = Math.floor(RNG.hash2(x, y, world.seed + 44) * TEXTURES.VARIANTS);
          const sx = Math.round(x * TILE - camera.x);
          const sy = Math.round(y * TILE - camera.y);
          TEXTURES.drawBlock(ctx, block, sx, sy, TILE, variant);
          const definition = CONFIG.blockDefs[block];
          if (definition && definition.solid && block !== CONFIG.blocks.torch) {
            const above = y > 0 ? world.data[(y - 1) * world.width + x] : CONFIG.blocks.air;
            if (above === CONFIG.blocks.air || CONFIG.blockDefs[above].transparent) {
              ctx.fillStyle = "rgba(255, 242, 204, 0.16)";
              ctx.fillRect(sx, sy, TILE, 1);
            }
            ctx.fillStyle = "rgba(0, 0, 0, 0.16)";
            ctx.fillRect(sx, sy + TILE - 1, TILE, 1);
            ctx.fillRect(sx + TILE - 1, sy, 1, TILE);
          }
        }
      }
    }

    function drawLighting(state) {
      const world = state.world;
      const camera = state.camera;
      const firstColumn = Math.max(0, Math.floor(camera.x / TILE));
      const lastColumn = Math.min(world.width - 1, Math.ceil((camera.x + VIEW_W) / TILE));
      const firstRow = Math.max(0, Math.floor(camera.y / TILE));
      const lastRow = Math.min(world.height - 1, Math.ceil((camera.y + VIEW_H) / TILE));
      const cols = lastColumn - firstColumn + 1;
      const rows = lastRow - firstRow + 1;
      if (cols <= 0 || rows <= 0) {
        return;
      }
      if (lightCanvas.width !== cols || lightCanvas.height !== rows) {
        lightCanvas.width = cols;
        lightCanvas.height = rows;
      }
      const image = lightCtx.createImageData(cols, rows);
      const data = image.data;
      const day = state.dayFactor;
      for (let row = 0; row < rows; row += 1) {
        const worldY = firstRow + row;
        for (let col = 0; col < cols; col += 1) {
          const worldX = firstColumn + col;
          const index = (row * cols + col) * 4;
          const block = world.data[worldY * world.width + worldX];
          const surfaceY = world.surface ? world.surface[worldX] : WORLD.findSurfaceY(world, worldX);
          if (block === CONFIG.blocks.air && worldY < surfaceY) {
            data[index + 3] = 0;
            continue;
          }
          let light = WORLD.lightAt(world, worldX, worldY, day);
          light = Math.max(light, 2.8);
          const depth = Math.max(0, worldY - surfaceY);
          const ambient = Math.max(0, 4.9 - depth * 0.13) * (0.45 + day * 0.55);
          light = Math.max(light, ambient);
          if (block !== CONFIG.blocks.air) {
            const neighbors = [
              worldX > 0 ? WORLD.lightAt(world, worldX - 1, worldY, day) : 0,
              worldX < world.width - 1 ? WORLD.lightAt(world, worldX + 1, worldY, day) : 0,
              worldY > 0 ? WORLD.lightAt(world, worldX, worldY - 1, day) : 0,
              worldY < world.height - 1 ? WORLD.lightAt(world, worldX, worldY + 1, day) : 0
            ];
            light = Math.max(light, Math.max(neighbors[0], neighbors[1], neighbors[2], neighbors[3]) - 1);
          }
          const darkness = Math.pow(1 - clamp(light / 15, 0, 1), 1.15);
          data[index] = 7;
          data[index + 1] = 11;
          data[index + 2] = 24;
          data[index + 3] = Math.round(darkness * (block === CONFIG.blocks.air ? 238 : 205));
        }
      }
      lightCtx.putImageData(image, 0, 0);
      ctx.save();
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(
        lightCanvas,
        Math.round(firstColumn * TILE - camera.x),
        Math.round(firstRow * TILE - camera.y),
        cols * TILE,
        rows * TILE
      );
      ctx.restore();
      ctx.imageSmoothingEnabled = false;

      const lightRadius = 5.4 * TILE;
      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
          const worldX = firstColumn + col;
          const worldY = firstRow + row;
          if (world.data[worldY * world.width + worldX] !== CONFIG.blocks.torch) {
            continue;
          }
          const x = worldX * TILE - camera.x + TILE / 2;
          const y = worldY * TILE - camera.y + TILE / 2;
          const glow = ctx.createRadialGradient(x, y, 2, x, y, lightRadius);
          glow.addColorStop(0, "rgba(255, 195, 91, 0.24)");
          glow.addColorStop(0.35, "rgba(255, 133, 49, 0.11)");
          glow.addColorStop(1, "rgba(255, 110, 36, 0)");
          ctx.save();
          ctx.globalCompositeOperation = "lighter";
          ctx.fillStyle = glow;
          ctx.fillRect(x - lightRadius, y - lightRadius, lightRadius * 2, lightRadius * 2);
          ctx.restore();
        }
      }
    }

    function drawTarget(state) {
      const hover = state.hover;
      if (!hover || !hover.visible) {
        return;
      }
      const camera = state.camera;
      const sx = Math.round(hover.x * TILE - camera.x);
      const sy = Math.round(hover.y * TILE - camera.y);
      const valid = hover.valid;
      ctx.save();
      ctx.strokeStyle = valid ? "rgba(255,255,255,0.88)" : "rgba(239,110,93,0.9)";
      ctx.lineWidth = 2;
      ctx.strokeRect(sx + 1, sy + 1, TILE - 2, TILE - 2);
      ctx.strokeStyle = valid ? "rgba(30,30,30,0.55)" : "rgba(80,20,18,0.6)";
      ctx.lineWidth = 1;
      ctx.strokeRect(sx + 3, sy + 3, TILE - 6, TILE - 6);
      const corner = 5;
      ctx.strokeStyle = valid ? "rgba(255, 226, 153, 0.95)" : "rgba(255, 140, 120, 0.95)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx, sy + corner);
      ctx.lineTo(sx, sy);
      ctx.lineTo(sx + corner, sy);
      ctx.moveTo(sx + TILE - corner, sy);
      ctx.lineTo(sx + TILE, sy);
      ctx.lineTo(sx + TILE, sy + corner);
      ctx.moveTo(sx, sy + TILE - corner);
      ctx.lineTo(sx, sy + TILE);
      ctx.lineTo(sx + corner, sy + TILE);
      ctx.moveTo(sx + TILE - corner, sy + TILE);
      ctx.lineTo(sx + TILE, sy + TILE);
      ctx.lineTo(sx + TILE, sy + TILE - corner);
      ctx.stroke();
      ctx.restore();

      if (state.mining && state.mining.x === hover.x && state.mining.y === hover.y && state.mining.progress > 0) {
        drawCracks(sx, sy, state.mining.progress);
      }
    }

    function drawCracks(sx, sy, progress) {
      const stage = clamp(progress, 0, 1);
      const lines = [
        [[8, 1], [9, 7], [5, 11]],
        [[15, 1], [13, 7], [16, 12]],
        [[1, 13], [7, 15], [10, 22]],
        [[22, 10], [17, 13], [20, 19]],
        [[11, 8], [7, 13], [12, 17]],
        [[3, 4], [8, 6], [11, 3]]
      ];
      ctx.save();
      ctx.strokeStyle = "rgba(16, 12, 9, 0.75)";
      ctx.lineWidth = 1.4;
      const count = Math.max(1, Math.ceil(stage * lines.length));
      for (let index = 0; index < count; index += 1) {
        const line = lines[index];
        ctx.beginPath();
        ctx.moveTo(sx + line[0][0], sy + line[0][1]);
        for (let point = 1; point < line.length; point += 1) {
          ctx.lineTo(sx + line[point][0], sy + line[point][1]);
        }
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
      ctx.fillRect(sx + 6, sy + 4, Math.round(3 * stage), 1);
      ctx.restore();
    }

    function drawParticles(state) {
      const particles = state.particles || [];
      const camera = state.camera;
      for (let index = 0; index < particles.length; index += 1) {
        const particle = particles[index];
        const alpha = clamp(particle.life / particle.maxLife, 0, 1);
        ctx.fillStyle = "rgba(" + particle.color[0] + "," + particle.color[1] + "," + particle.color[2] + "," + alpha + ")";
        const size = particle.size * TILE;
        ctx.fillRect(
          Math.round(particle.x * TILE - camera.x),
          Math.round(particle.y * TILE - camera.y),
          Math.max(2, Math.round(size)),
          Math.max(2, Math.round(size))
        );
      }
    }

    function drawPlayer(state) {
      const player = state.player;
      const camera = state.camera;
      const px = Math.round(player.x * TILE - camera.x);
      const feetY = Math.round(player.y * TILE - camera.y);
      const width = Math.round(player.width * TILE);
      const height = Math.round(player.height * TILE);
      const bob = player.onGround ? Math.sin(player.walkTime * 12) * Math.min(1.4, Math.abs(player.vx) * 0.18) : 0;
      const facing = player.facing < 0 ? -1 : 1;
      const swing = state.swing || 0;
      const armAngle = Math.sin(swing * Math.PI) * 0.8;

      ctx.save();
      if (player.onGround) {
        ctx.fillStyle = "rgba(0,0,0,0.22)";
        ctx.beginPath();
        ctx.ellipse(px, feetY + 1, width * 0.6, 4, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.translate(px, feetY + bob);
      ctx.scale(facing, 1);

      const legSwing = player.onGround ? Math.sin(player.walkTime * 12) * Math.min(3, Math.abs(player.vx)) : 1.5;
      const skin = "#ddb087";
      const skinShade = "#b98561";
      const shirt = "#2f6a61";
      const shirtLight = "#3f8b79";
      const pantsDark = "#263249";
      const hair = "#4a2c20";

      ctx.fillStyle = "rgba(0,0,0,0.24)";
      ctx.fillRect(-width / 2 + 1, -height + 1, width, height);
      ctx.fillStyle = pantsDark;
      ctx.fillRect(-width / 2 + 1, -14, 6, 14 + legSwing);
      ctx.fillRect(width / 2 - 7, -14, 6, 14 - legSwing);
      ctx.fillStyle = "#1c1716";
      ctx.fillRect(-width / 2, -3 + legSwing, 7, 3);
      ctx.fillRect(width / 2 - 7, -3 - legSwing, 7, 3);

      ctx.fillStyle = shirt;
      ctx.fillRect(-width / 2 + 1, -28, width - 2, 16);
      ctx.fillStyle = shirtLight;
      ctx.fillRect(-width / 2 + 1, -28, width - 2, 3);
      ctx.fillStyle = "#d7b24d";
      ctx.fillRect(-2, -27, 3, 2);

      ctx.fillStyle = skinShade;
      ctx.fillRect(-width / 2 - 1, -26, 4, 12);
      ctx.fillStyle = skin;
      ctx.fillRect(width / 2 - 3, -26, 4, 12);
      const handY = -16 - Math.round(armAngle * 6);
      ctx.fillStyle = skin;
      ctx.fillRect(width / 2 - 3, handY, 5, 5);

      const item = state.heldItem;
      if (item) {
        ctx.save();
        ctx.translate(width / 2 + 1, handY - 2);
        ctx.rotate(-0.55 - armAngle * 0.5);
        TEXTURES.drawItem(ctx, item, -8, -12, 18);
        ctx.restore();
      }

      ctx.fillStyle = skin;
      ctx.fillRect(-6, -41, 12, 12);
      ctx.fillStyle = skinShade;
      ctx.fillRect(2, -38, 5, 3);
      ctx.fillStyle = "#2c201d";
      ctx.fillRect(3, -36, 2, 2);
      ctx.fillStyle = hair;
      ctx.fillRect(-7, -43, 14, 5);
      ctx.fillRect(-7, -40, 3, 6);
      ctx.fillStyle = "#5c3626";
      ctx.fillRect(-4, -44, 8, 2);

      if (player.hurtCooldown > 0.25) {
        ctx.fillStyle = "rgba(255, 80, 58, 0.32)";
        ctx.fillRect(-width / 2 - 1, -height, width + 2, height);
      }
      ctx.restore();
    }

    function drawVignette() {
      const gradient = ctx.createRadialGradient(VIEW_W / 2, VIEW_H / 2, VIEW_H * 0.32, VIEW_W / 2, VIEW_H / 2, VIEW_W * 0.7);
      gradient.addColorStop(0, "rgba(0,0,0,0)");
      gradient.addColorStop(1, "rgba(3,7,10,0.34)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, VIEW_W, VIEW_H);
    }

    function draw(state) {
      const palette = skyPalette(state.timeOfDay, state.dayFactor);
      drawSky(state);
      drawHills(state);
      drawCaveBackdrop(state);
      drawWorld(state);
      drawLighting(state);
      drawParticles(state);
      drawPlayer(state);
      drawTarget(state);
      ctx.save();
      if (palette.dusk > 0.4 && state.dayFactor > 0.25) {
        ctx.globalCompositeOperation = "soft-light";
        ctx.fillStyle = "rgba(255, 130, 69, " + (palette.dusk * 0.08) + ")";
        ctx.fillRect(0, 0, VIEW_W, VIEW_H);
      }
      drawVignette();
      ctx.restore();
    }

    function drawMinimap(targetCanvas, state) {
      const minimapCtx = targetCanvas.getContext("2d");
      const width = targetCanvas.width;
      const height = targetCanvas.height;
      const world = state.world;
      minimapCtx.clearRect(0, 0, width, height);
      minimapCtx.fillStyle = "rgba(8, 13, 18, 0.78)";
      minimapCtx.fillRect(0, 0, width, height);
      const top = 24;
      const bottom = height - 8;
      const span = world.height - 30;
      for (let x = 0; x < width; x += 1) {
        const worldX = Math.floor((x / width) * world.width);
        const surfaceY = WORLD.findSurfaceY(world, worldX);
        const screenY = top + clamp((surfaceY - 30) / span, 0, 1) * (bottom - top);
        const block = world.data[surfaceY * world.width + worldX];
        let color = "#668a55";
        if (block === CONFIG.blocks.sand) {
          color = "#c9b070";
        } else if (block === CONFIG.blocks.stone || block === CONFIG.blocks.cobblestone) {
          color = "#737d7e";
        } else if (block === CONFIG.blocks.wood || block === CONFIG.blocks.leaves) {
          color = "#4e7444";
        }
        minimapCtx.fillStyle = color;
        minimapCtx.fillRect(x, screenY, 1, height - screenY);
        minimapCtx.fillStyle = "rgba(255,255,255,0.06)";
        minimapCtx.fillRect(x, screenY, 1, 1);
      }
      const playerX = clamp((state.player.x / world.width) * width, 2, width - 2);
      const playerY = top + clamp((state.player.y - 30) / span, 0, 1) * (bottom - top);
      minimapCtx.fillStyle = "#ffcc70";
      minimapCtx.beginPath();
      minimapCtx.moveTo(playerX, playerY - 4);
      minimapCtx.lineTo(playerX - 4, playerY + 3);
      minimapCtx.lineTo(playerX + 4, playerY + 3);
      minimapCtx.closePath();
      minimapCtx.fill();
      minimapCtx.strokeStyle = "rgba(255, 220, 147, 0.75)";
      minimapCtx.strokeRect(playerX - 5, playerY - 5, 10, 10);
      minimapCtx.fillStyle = "rgba(239, 238, 222, 0.8)";
      minimapCtx.font = "9px monospace";
      minimapCtx.fillText("SURFACE", 5, 13);
      minimapCtx.fillStyle = "rgba(175, 196, 190, 0.68)";
      minimapCtx.fillText(Math.floor(state.player.x) + ", " + Math.floor(state.player.y), width - 52, 13);
    }

    return {
      draw: draw,
      drawMinimap: drawMinimap,
      screenToWorld: screenToWorld,
      canvas: canvas
    };
  }

  window.SandboxRender = {
    createRenderer: createRenderer,
    skyPalette: skyPalette
  };
})();
