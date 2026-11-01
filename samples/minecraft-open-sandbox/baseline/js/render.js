(function (root) {
  "use strict";

  const CONFIG = root.MosswildConfig;
  const CONTENT = root.MosswildContent;
  const TIME = root.MosswildTime;
  const ART = root.MosswildArt;
  const B = CONFIG.block;
  const TILE = CONFIG.tileSize;
  const TAU = Math.PI * 2;

  const SKY = {
    dayTop: [83, 157, 194],
    dayMid: [151, 202, 207],
    dayBottom: [210, 228, 205],
    nightTop: [8, 13, 32],
    nightMid: [18, 29, 51],
    nightBottom: [37, 51, 66],
    duskTop: [196, 112, 100],
    duskMid: [231, 153, 111],
    duskBottom: [247, 194, 132],
    dawnTop: [203, 146, 132],
    dawnMid: [239, 178, 138],
    dawnBottom: [248, 213, 163]
  };

  let stars = null;
  let clouds = null;
  let lightCanvas = null;
  let lightCtx = null;
  let lightSize = { width: 0, height: 0, scale: 0.5 };

  const MOUNTAINS = [
    { seed: 13.1, distance: 0.045, base: -8, amplitude: 0.34, colorDay: [111, 143, 133], colorNight: [23, 32, 43], haze: 0.35 },
    { seed: 47.7, distance: 0.075, base: 10, amplitude: 0.25, colorDay: [72, 106, 92], colorNight: [17, 27, 34], haze: 0.2 },
    { seed: 91.3, distance: 0.12, base: 43, amplitude: 0.14, colorDay: [45, 78, 61], colorNight: [12, 21, 26], haze: 0.08 }
  ];

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function smoothstep(edge0, edge1, value) {
    const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  }

  function mixColor(a, b, t) {
    return [
      Math.round(lerp(a[0], b[0], t)),
      Math.round(lerp(a[1], b[1], t)),
      Math.round(lerp(a[2], b[2], t))
    ];
  }

  function css(color, alpha) {
    return "rgba(" + color[0] + ", " + color[1] + ", " + color[2] + ", " + alpha + ")";
  }

  function colorWithAlpha(color, alpha) {
    if (Array.isArray(color)) {
      return css(color, alpha);
    }
    if (typeof color !== "string") {
      return "rgba(255, 255, 255, " + alpha + ")";
    }
    const value = color.trim();
    if (/^#[0-9a-f]{3}$/i.test(value)) {
      return "rgba("
        + parseInt(value[1] + value[1], 16) + ", "
        + parseInt(value[2] + value[2], 16) + ", "
        + parseInt(value[3] + value[3], 16) + ", " + alpha + ")";
    }
    if (/^#[0-9a-f]{6}$/i.test(value)) {
      return "rgba("
        + parseInt(value.slice(1, 3), 16) + ", "
        + parseInt(value.slice(3, 5), 16) + ", "
        + parseInt(value.slice(5, 7), 16) + ", " + alpha + ")";
    }
    return value;
  }

  function hash01(seed) {
    let value = seed >>> 0;
    value = Math.imul(value ^ (value >>> 16), 0x7feb352d);
    value = Math.imul(value ^ (value >>> 15), 0x846ca68b);
    return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
  }

  function localHash(x, y, seed) {
    return hash01(Math.imul(x | 0, 73856093) ^ Math.imul(y | 0, 19349663) ^ (seed >>> 0));
  }

  function ensureBackgroundDetails() {
    if (stars) {
      return;
    }
    stars = [];
    let state = 0x1badf00d;
    const random = function () {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 4294967296;
    };
    for (let i = 0; i < 92; i += 1) {
      stars.push({
        x: random(),
        y: random() * 0.66,
        size: random() < 0.18 ? 2 : 1,
        phase: random() * TAU,
        speed: 0.35 + random() * 1.4
      });
    }

    clouds = [];
    for (let i = 0; i < 9; i += 1) {
      clouds.push({
        x: random(),
        y: 0.08 + random() * 0.34,
        scale: 0.6 + random() * 1.4,
        speed: 2.2 + random() * 4.6,
        alpha: 0.3 + random() * 0.35
      });
    }
  }

  function getSkyPalette(day) {
    const daylight = day.daylight;
    const twilight = day.twilight;
    const isDawn = day.fraction < 0.5;
    let top = mixColor(SKY.nightTop, SKY.dayTop, daylight);
    let middle = mixColor(SKY.nightMid, SKY.dayMid, daylight);
    let bottom = mixColor(SKY.nightBottom, SKY.dayBottom, daylight);
    const sunsetTop = isDawn ? SKY.dawnTop : SKY.duskTop;
    const sunsetMid = isDawn ? SKY.dawnMid : SKY.duskMid;
    const sunsetBottom = isDawn ? SKY.dawnBottom : SKY.duskBottom;
    top = mixColor(top, sunsetTop, twilight * 0.72);
    middle = mixColor(middle, sunsetMid, twilight * 0.82);
    bottom = mixColor(bottom, sunsetBottom, twilight * 0.9);
    return {
      top,
      middle,
      bottom,
      starAlpha: clamp(1 - daylight * 1.8, 0, 1) * 0.9,
      cloudLight: mixColor([43, 53, 66], [250, 243, 218], daylight),
      cloudShade: mixColor([28, 35, 48], [187, 202, 190], daylight),
      mountainColors: MOUNTAINS.map(function (layer) {
        let color = mixColor(layer.colorNight, layer.colorDay, daylight);
        if (twilight > 0.25) {
          color = mixColor(color, [166, 130, 110], twilight * 0.16);
        }
        return color;
      })
    };
  }

  function drawSky(ctx, game, view, day) {
    const w = view.width;
    const h = view.height;
    const palette = getSkyPalette(day);
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, css(palette.top, 1));
    gradient.addColorStop(0.58, css(palette.middle, 1));
    gradient.addColorStop(1, css(palette.bottom, 1));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    if (palette.starAlpha > 0.02) {
      drawStars(ctx, view, palette, game.elapsed);
    }

    drawSunAndMoon(ctx, game, view, day, palette);
    drawClouds(ctx, game, view, day, palette);
  }

  function drawStars(ctx, view, palette, time) {
    ctx.save();
    for (let i = 0; i < stars.length; i += 1) {
      const star = stars[i];
      const twinkle = 0.55 + 0.45 * Math.sin(time * star.speed + star.phase);
      const alpha = palette.starAlpha * (0.4 + twinkle * 0.6);
      const x = Math.round(star.x * view.width);
      const y = Math.round(star.y * view.height);
      ctx.fillStyle = "rgba(229, 238, 221, " + alpha.toFixed(3) + ")";
      ctx.fillRect(x, y, star.size, star.size);
      if (star.size > 1 && twinkle > 0.75) {
        ctx.fillStyle = "rgba(229, 238, 221, " + (alpha * 0.35).toFixed(3) + ")";
        ctx.fillRect(x - 2, y, 6, 1);
        ctx.fillRect(x, y - 2, 1, 6);
      }
    }
    ctx.restore();
  }

  function drawSunAndMoon(ctx, game, view, day, palette) {
    const w = view.width;
    const h = view.height;
    const horizon = h * 0.63;

    if (day.fraction < 0.53) {
      const progress = clamp(day.fraction / 0.5, 0, 1);
      const x = w * (0.08 + progress * 0.84);
      const y = horizon - Math.sin(progress * Math.PI) * h * 0.44;
      const alpha = clamp(day.sunHeight * 5 + 0.3, 0, 1);
      const glow = ctx.createRadialGradient(x, y, 8, x, y, 140);
      glow.addColorStop(0, "rgba(255, 225, 155, " + (0.22 * alpha).toFixed(3) + ")");
      glow.addColorStop(0.5, "rgba(250, 190, 122, " + (0.07 * alpha).toFixed(3) + ")");
      glow.addColorStop(1, "rgba(250, 190, 122, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - 150, y - 150, 300, 300);

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = "rgba(255, 222, 142, 0.16)";
      ctx.fillRect(x - 32, y - 26, 64, 52);
      ctx.fillStyle = "#ffe8a3";
      ctx.fillRect(x - 18, y - 18, 36, 36);
      ctx.fillStyle = "#ffd377";
      ctx.fillRect(x - 13, y - 13, 26, 26);
      ctx.fillStyle = "rgba(255, 249, 207, 0.75)";
      ctx.fillRect(x - 9, y - 14, 8, 5);
      ctx.fillStyle = "rgba(255, 249, 207, 0.55)";
      ctx.fillRect(x - 28, y - 2, 4, 4);
      ctx.fillRect(x + 24, y - 8, 4, 4);
      ctx.restore();
    }

    if (day.fraction >= 0.47) {
      const progress = clamp((day.fraction - 0.5) / 0.5, 0, 1);
      const x = w * (0.08 + progress * 0.84);
      const y = horizon - Math.sin(progress * Math.PI) * h * 0.44;
      const alpha = clamp(1 - day.daylight * 1.7, 0, 1);
      if (alpha > 0.02) {
        const glow = ctx.createRadialGradient(x, y, 6, x, y, 95);
        glow.addColorStop(0, "rgba(199, 224, 212, " + (0.16 * alpha).toFixed(3) + ")");
        glow.addColorStop(1, "rgba(199, 224, 212, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(x - 100, y - 100, 200, 200);

        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.fillStyle = "rgba(226, 235, 217, 0.18)";
        ctx.fillRect(x - 22, y - 22, 44, 44);
        ctx.fillStyle = "#dce5d6";
        ctx.fillRect(x - 15, y - 15, 30, 30);
        ctx.fillStyle = "#c2d0c5";
        ctx.fillRect(x - 8, y - 10, 8, 7);
        ctx.fillRect(x + 3, y + 1, 9, 7);
        ctx.fillRect(x - 4, y + 6, 5, 4);
        ctx.fillStyle = "rgba(250, 252, 235, 0.45)";
        ctx.fillRect(x - 11, y - 11, 3, 3);
        ctx.restore();
      }
    }
  }

  function drawCloudShape(ctx, x, y, scale, alpha, lightColor, shadeColor) {
    ctx.save();
    ctx.globalAlpha = alpha;
    const pieces = [
      [-32, 2, 42, 13],
      [-11, -6, 34, 21],
      [14, 1, 38, 13],
      [-2, 10, 52, 10],
      [-45, 7, 25, 8]
    ];
    ctx.fillStyle = css(shadeColor, 0.85);
    pieces.forEach(function (piece) {
      ctx.fillRect(Math.round(x + piece[0] * scale), Math.round(y + (piece[1] + 3) * scale), Math.round(piece[2] * scale), Math.round(piece[3] * scale));
    });
    ctx.fillStyle = css(lightColor, 0.9);
    pieces.forEach(function (piece, index) {
      ctx.fillRect(
        Math.round(x + piece[0] * scale),
        Math.round(y + piece[1] * scale),
        Math.round(piece[2] * scale),
        Math.round((piece[3] - (index === 3 ? 3 : 1)) * scale)
      );
    });
    ctx.restore();
  }

  function drawClouds(ctx, game, view, day, palette) {
    if (!clouds) {
      return;
    }
    const w = view.width;
    const h = view.height;
    const camera = game.camera;
    for (let i = 0; i < clouds.length; i += 1) {
      const cloud = clouds[i];
      const span = w + 440;
      let x = (cloud.x * span - game.elapsed * cloud.speed - camera.x * 0.028) % span;
      if (x < -220) {
        x += span;
      }
      x -= 220;
      const y = cloud.y * h - camera.y * 0.012 + Math.sin(game.elapsed * 0.04 + i) * 2.5;
      const alpha = cloud.alpha * (0.22 + day.daylight * 0.7);
      drawCloudShape(ctx, x, y, cloud.scale, alpha, palette.cloudLight, palette.cloudShade);
    }
  }

  function mountainRidge(x, layer, horizon, viewHeight) {
    const p = layer.seed;
    const n = Math.sin(x * 0.006 + p) * 0.54
      + Math.sin(x * 0.016 + p * 1.73) * 0.29
      + Math.sin(x * 0.041 + p * 2.51) * 0.13
      + Math.sin(x * 0.0021 + p * 0.4) * 0.22;
    const normalized = clamp(0.5 + n * 0.55, 0, 1);
    return horizon + layer.base - (normalized * layer.amplitude * viewHeight);
  }

  function drawMountainLayer(ctx, game, view, day, palette, layerIndex) {
    const layer = MOUNTAINS[layerIndex];
    const w = view.width;
    const h = view.height;
    const camera = game.camera;
    const offset = camera.x * layer.distance;
    const centerColumn = clamp(Math.floor((camera.x + w / 2) / TILE), 0, game.world.width - 1);
    const surface = game.world.surface[centerColumn] * TILE - camera.y;
    const horizon = clamp(surface, -h * 0.6, h * 1.2);
    const step = 22;
    const color = palette.mountainColors[layerIndex];
    const warm = day.twilight * 0.16;

    const ctxColor = warm > 0.001 ? mixColor(color, [173, 132, 105], warm) : color;
    ctx.beginPath();
    ctx.moveTo(-step, h + 20);
    for (let screenX = -step; screenX <= w + step; screenX += step) {
      const ridge = mountainRidge(screenX + offset, layer, horizon, h);
      if (screenX === -step) {
        ctx.lineTo(-step, ridge);
      } else {
        ctx.lineTo(screenX, ridge);
      }
    }
    ctx.lineTo(w + step, h + 20);
    ctx.closePath();
    ctx.fillStyle = css(ctxColor, 1);
    ctx.fill();

    // A pale rim on the ridges separates the layers in the morning haze.
    ctx.save();
    ctx.globalAlpha = layerIndex === 0 ? 0.16 + day.daylight * 0.08 : 0.08 + day.daylight * 0.06;
    ctx.strokeStyle = layerIndex === 0 ? "#d3ddc5" : "#9eb39c";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let screenX = -step; screenX <= w + step; screenX += step) {
      const ridge = mountainRidge(screenX + offset, layer, horizon, h);
      if (screenX === -step) {
        ctx.moveTo(screenX, ridge);
      } else {
        ctx.lineTo(screenX, ridge);
      }
    }
    ctx.stroke();
    ctx.restore();

    if (layerIndex === 2) {
      drawHorizonTrees(ctx, w, horizon, layer, offset, day, palette, h);
    }
  }

  function drawHorizonTrees(ctx, w, horizon, layer, offset, day, palette, viewHeight) {
    const baseColor = mixColor([25, 43, 35], [64, 91, 70], day.daylight);
    ctx.save();
    ctx.fillStyle = css(baseColor, 0.92);
    for (let i = 0; i < 25; i += 1) {
      const rawX = i * 76 + (i % 3) * 17;
      const x = ((rawX - offset * 0.3) % (w + 120) + w + 120) % (w + 120) - 60;
      const height = 18 + localHash(i, 7, 91) * 38;
      const ridge = mountainRidge(rawX + offset, layer, horizon, viewHeight) + 2;
      ctx.beginPath();
      ctx.moveTo(x - height * 0.22, ridge);
      ctx.lineTo(x, ridge - height);
      ctx.lineTo(x + height * 0.22, ridge);
      ctx.closePath();
      ctx.fill();
      ctx.fillRect(x - 1, ridge, 2, 4);
    }
    ctx.restore();
  }

  function drawMountains(ctx, game, view, day, palette) {
    for (let i = 0; i < MOUNTAINS.length; i += 1) {
      drawMountainLayer(ctx, game, view, day, palette, i);
    }
    const horizon = clamp(game.player.y * TILE - game.camera.y, -view.height, view.height);
    const fog = ctx.createLinearGradient(0, horizon - 110, 0, horizon + 40);
    fog.addColorStop(0, "rgba(218, 231, 211, 0)");
    fog.addColorStop(0.58, "rgba(218, 231, 211, " + (0.16 * day.daylight).toFixed(3) + ")");
    fog.addColorStop(1, "rgba(218, 231, 211, 0)");
    ctx.fillStyle = fog;
    ctx.fillRect(0, horizon - 110, view.width, 150);
  }

  function drawBirds(ctx, game, view, day) {
    if (day.daylight < 0.3) {
      return;
    }
    const time = game.elapsed;
    const horizon = game.player.y * TILE - game.camera.y;
    ctx.save();
    ctx.strokeStyle = "rgba(38, 52, 43, " + (0.28 * day.daylight).toFixed(3) + ")";
    ctx.lineWidth = 1.4;
    for (let i = 0; i < 5; i += 1) {
      const speed = 8 + i * 1.4;
      const x = ((time * speed + i * 247) % (view.width + 220)) - 110;
      const y = clamp(horizon - 150 - i * 27 + Math.sin(time * 0.23 + i) * 9, 40, view.height * 0.55);
      const flap = Math.sin(time * 3.2 + i) * 4;
      ctx.beginPath();
      ctx.moveTo(x - 7, y + flap);
      ctx.quadraticCurveTo(x - 3, y - 3, x, y);
      ctx.quadraticCurveTo(x + 3, y - 3, x + 7, y + flap);
      ctx.stroke();
    }
    ctx.restore();
  }

  function isSolidBlock(world, x, y) {
    if (x < 0 || x >= world.width || y >= world.height) {
      return true;
    }
    if (y < 0) {
      return false;
    }
    return Boolean(CONTENT.getBlockDef(world.data[y * world.width + x]).solid);
  }

  function getUtilitySupport(world, x, y) {
    if (isSolidBlock(world, x, y + 1)) {
      return "below";
    }
    if (isSolidBlock(world, x - 1, y)) {
      return "left";
    }
    if (isSolidBlock(world, x + 1, y)) {
      return "right";
    }
    if (isSolidBlock(world, x, y - 1)) {
      return "above";
    }
    return null;
  }

  function drawCaveBackground(ctx, world, x, y, screenX, screenY) {
    const surface = world.surface[clamp(x, 0, world.width - 1)];
    const depth = y - surface;
    const bucket = depth < 4 ? 0 : depth < 15 ? 1 : 2;
    const variant = Math.floor(localHash(x, y, world.seed ^ 0x5f3a) * 3);
    ctx.drawImage(ART.getCaveSprite(bucket, variant), screenX, screenY);
  }

  function drawWorld(ctx, game, view, camX, camY, lights) {
    const world = game.world;
    const seed = world.seed;
    const startX = Math.max(0, Math.floor(camX / TILE) - 1);
    const endX = Math.min(world.width - 1, Math.ceil((camX + view.width) / TILE) + 1);
    const startY = Math.max(0, Math.floor(camY / TILE) - 1);
    const endY = Math.min(world.height - 1, Math.ceil((camY + view.height) / TILE) + 1);
    const special = [];

    ctx.save();
    ctx.imageSmoothingEnabled = false;

    for (let y = startY; y <= endY; y += 1) {
      for (let x = startX; x <= endX; x += 1) {
        const block = world.data[y * world.width + x];
        const screenX = x * TILE - camX;
        const screenY = y * TILE - camY;
        if (block === B.AIR) {
          if (y >= world.surface[x]) {
            drawCaveBackground(ctx, world, x, y, screenX, screenY);
            const decorHash = localHash(x, y, seed ^ 0xa32d);
            if (decorHash < 0.045) {
              const hasFloor = isSolidBlock(world, x, y + 1);
              const hasCeiling = isSolidBlock(world, x, y - 1);
              if (hasFloor || hasCeiling) {
                ART.drawCaveDecor(ctx, screenX, screenY, Math.floor(decorHash * 10000), game.elapsed);
              }
            }
          }
          continue;
        }

        const def = CONTENT.getBlockDef(block);
        if (block === B.TORCH || block === B.LANTERN || block === B.CAMPFIRE) {
          const support = getUtilitySupport(world, x, y);
          special.push({ block, x, y, screenX, screenY, support, def });
          continue;
        }

        const sprite = ART.getBlockSprite(block, Math.floor(localHash(x, y, seed ^ 0x81b3) * 3));
        if (sprite) {
          ctx.drawImage(sprite, screenX, screenY);
        }
        if (def.light) {
          lights.push({ x: screenX + TILE / 2, y: screenY + TILE / 2, radius: def.light, flicker: localHash(x, y, 17) * 7 });
        }
      }
    }

    // Surface plants live at the edge of grass and air.
    for (let x = startX; x <= endX; x += 1) {
      const ground = world.surface[x];
      if (ground < startY || ground > endY + 1) {
        continue;
      }
      const groundY = ground * TILE - camY;
      if (ART.hash2(seed ^ 0x92a1, x, 117) % 100 >= 68) {
        continue;
      }
      if (world.data[ground * world.width + x] !== B.GRASS) {
        continue;
      }
      if (world.data[(ground - 1) * world.width + x] !== B.AIR) {
        continue;
      }
      ART.drawSurfacePlant(ctx, x * TILE - camX, groundY, ART.hash2(seed, x, 8) % 997, game.elapsed);
    }

    special.forEach(function (item) {
      const time = game.elapsed;
      if (item.block === B.TORCH) {
        ART.drawTorch(ctx, item.screenX, item.screenY, item.support, item.x * 7 + item.y);
        lights.push({
          x: item.screenX + (item.support === "left" ? 13 : item.support === "right" ? 19 : 16),
          y: item.screenY + 11,
          radius: item.def.light,
          flicker: item.x * 0.17 + item.y * 0.31
        });
      } else if (item.block === B.LANTERN) {
        ART.drawLantern(ctx, item.screenX, item.screenY, item.support, item.x * 3 + item.y);
        lights.push({
          x: item.screenX + TILE / 2,
          y: item.screenY + 18,
          radius: item.def.light,
          flicker: item.x * 0.11
        });
      } else if (item.block === B.CAMPFIRE) {
        ART.drawCampfire(ctx, item.screenX, item.screenY, item.x * 5 + item.y);
        lights.push({
          x: item.screenX + TILE / 2,
          y: item.screenY + 11,
          radius: item.def.light,
          flicker: item.x * 0.27
        });
      }
    });

    // Exposed block-top glints make the foreground terrain feel sunlit.
    if (game.dayInfo.daylight > 0.35) {
      ctx.globalAlpha = 0.12 * game.dayInfo.daylight;
      ctx.fillStyle = "#fff2c2";
      for (let x = startX; x <= endX; x += 1) {
        const ground = world.surface[x];
        if (ground < startY || ground > endY) {
          continue;
        }
        if (world.data[ground * world.width + x] === B.GRASS) {
          ctx.fillRect(x * TILE - camX, ground * TILE - camY, TILE, 1);
        }
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }

  function drawParticles(ctx, game, camX, camY) {
    const particles = game.particles || [];
    ctx.save();
    for (let i = 0; i < particles.length; i += 1) {
      const particle = particles[i];
      const ratio = clamp(particle.life / particle.maxLife, 0, 1);
      const x = particle.x * TILE - camX;
      const y = particle.y * TILE - camY;
      if (x < -20 || y < -20 || x > ctx.canvas.clientWidth + 20 || y > ctx.canvas.clientHeight + 20) {
        continue;
      }
      ctx.globalAlpha = ratio * (particle.alpha === undefined ? 1 : particle.alpha);
      ctx.fillStyle = particle.color;
      if (particle.kind === "spark") {
        ctx.globalCompositeOperation = "lighter";
        ctx.fillRect(Math.round(x), Math.round(y), particle.size + 1, 2);
        ctx.fillStyle = "rgba(255,255,230,0.55)";
        ctx.fillRect(Math.round(x), Math.round(y), 1, 1);
        ctx.globalCompositeOperation = "source-over";
      } else if (particle.kind === "glow") {
        ctx.globalCompositeOperation = "lighter";
        const gradient = ctx.createRadialGradient(x, y, 0, x, y, 9);
        gradient.addColorStop(0, colorWithAlpha(particle.color, 0.7));
        gradient.addColorStop(1, colorWithAlpha(particle.color, 0));
        ctx.fillStyle = gradient;
        ctx.fillRect(x - 9, y - 9, 18, 18);
        ctx.globalCompositeOperation = "source-over";
      } else {
        ctx.fillRect(Math.round(x), Math.round(y), particle.size, particle.size);
      }
    }
    ctx.restore();
  }

  function drawFloatingText(ctx, game, camX, camY) {
    const floaters = game.floaters || [];
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "700 12px 'Trebuchet MS', 'Segoe UI', sans-serif";
    for (let i = 0; i < floaters.length; i += 1) {
      const floater = floaters[i];
      const ratio = clamp(floater.life / floater.maxLife, 0, 1);
      const x = floater.x * TILE - camX;
      const y = floater.y * TILE - camY;
      ctx.globalAlpha = Math.min(1, ratio * 1.7);
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(13, 19, 16, 0.78)";
      ctx.strokeText(floater.text, x, y);
      ctx.fillStyle = floater.color || "#f0e5c4";
      ctx.fillText(floater.text, x, y);
    }
    ctx.restore();
  }

  function drawFireflies(ctx, game, view, camX, camY, day) {
    const world = game.world;
    const time = game.elapsed;
    const darkness = clamp(1 - day.daylight * 2.2, 0, 1);
    if (darkness > 0.02) {
      const firstX = Math.floor(camX / TILE) - 2;
      const lastX = Math.ceil((camX + view.width) / TILE) + 2;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (let x = Math.max(1, firstX); x <= Math.min(world.width - 2, lastX); x += 1) {
        const h = localHash(x, 17, world.seed ^ 0x7712);
        if (h > 0.32) {
          continue;
        }
        const surface = world.surface[x];
        const drift = Math.sin(time * (0.3 + h) + h * 12) * 24;
        const sx = x * TILE - camX + 8 + h * 18 + drift;
        const sy = surface * TILE - camY - 18 - h * 80 + Math.sin(time * 0.6 + x) * 7;
        if (sy < -20 || sy > view.height + 20) {
          continue;
        }
        const pulse = 0.5 + 0.5 * Math.sin(time * 2.5 + x * 0.7);
        const alpha = darkness * pulse * 0.6;
        ctx.fillStyle = "rgba(212, 241, 145, " + alpha.toFixed(3) + ")";
        ctx.fillRect(Math.round(sx), Math.round(sy), 2, 2);
        const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, 7);
        glow.addColorStop(0, "rgba(203, 238, 130, " + (alpha * 0.28).toFixed(3) + ")");
        glow.addColorStop(1, "rgba(203, 238, 130, 0)");
        ctx.fillStyle = glow;
        ctx.fillRect(sx - 8, sy - 8, 16, 16);
      }
      ctx.restore();
    }

    if (day.daylight > 0.35) {
      const firstX = Math.floor(camX / TILE) - 2;
      const lastX = Math.ceil((camX + view.width) / TILE) + 2;
      ctx.save();
      for (let x = Math.max(1, firstX); x <= Math.min(world.width - 2, lastX); x += 2) {
        const h = localHash(x, 31, world.seed ^ 0x11ab);
        if (h > 0.2) {
          continue;
        }
        const surface = world.surface[x];
        const sx = x * TILE - camX + h * 60 + Math.sin(time * 0.18 + x) * 22;
        const sy = surface * TILE - camY - 35 - h * 140 + Math.sin(time * 0.5 + h * 11) * 15;
        if (sy < 0 || sy > view.height) {
          continue;
        }
        ctx.globalAlpha = 0.18 + day.daylight * 0.16;
        ctx.fillStyle = "#f4e6b2";
        ctx.fillRect(Math.round(sx), Math.round(sy), 1, 1);
      }
      ctx.restore();
    }
  }

  function ensureLightCanvas(width, height) {
    const scale = 0.45;
    const nextWidth = Math.max(120, Math.ceil(width * scale));
    const nextHeight = Math.max(90, Math.ceil(height * scale));
    if (!lightCanvas) {
      lightCanvas = document.createElement("canvas");
    }
    if (lightCanvas.width !== nextWidth || lightCanvas.height !== nextHeight) {
      lightCanvas.width = nextWidth;
      lightCanvas.height = nextHeight;
      lightCtx = lightCanvas.getContext("2d");
      lightSize = { width: nextWidth, height: nextHeight, scale: scale };
    }
    if (!lightCtx) {
      lightCtx = lightCanvas.getContext("2d");
    }
    lightCtx.setTransform(scale, 0, 0, scale, 0, 0);
    return lightCtx;
  }

  function drawLighting(ctx, game, view, camX, camY, lights) {
    const w = view.width;
    const h = view.height;
    const world = game.world;
    const day = game.dayInfo;
    const player = game.player;
    const lctx = ensureLightCanvas(w, h);

    lctx.clearRect(0, 0, lightCanvas.width / lightSize.scale, lightCanvas.height / lightSize.scale);
    const nightAlpha = (1 - day.daylight) * 0.56 + day.twilight * 0.025;
    if (nightAlpha > 0.001) {
      lctx.fillStyle = "rgba(5, 10, 20, " + nightAlpha.toFixed(3) + ")";
      lctx.fillRect(0, 0, w, h);
    }

    // A darkening polyline follows the original surface, so excavated caves
    // and ditches feel deep while the sunlit surface stays bright.
    const surfacePoints = [];
    const startWorldX = Math.max(0, Math.floor(camX / TILE) - 1);
    const endWorldX = Math.min(world.width - 1, Math.ceil((camX + w) / TILE) + 1);
    let minSurfaceY = h;
    for (let x = startWorldX; x <= endWorldX; x += 1) {
      const screenX = x * TILE - camX;
      const screenY = world.surface[x] * TILE - camY;
      minSurfaceY = Math.min(minSurfaceY, screenY);
      surfacePoints.push([screenX, screenY]);
    }
    if (surfacePoints.length > 1) {
      const caveGradient = lctx.createLinearGradient(0, Math.max(0, minSurfaceY - 10), 0, h);
      caveGradient.addColorStop(0, "rgba(3, 8, 12, " + (0.05 + (1 - day.daylight) * 0.05).toFixed(3) + ")");
      caveGradient.addColorStop(0.36, "rgba(3, 8, 12, " + (0.17 + (1 - day.daylight) * 0.05).toFixed(3) + ")");
      caveGradient.addColorStop(1, "rgba(2, 6, 10, " + (0.54 + (1 - day.daylight) * 0.06).toFixed(3) + ")");
      lctx.beginPath();
      lctx.moveTo(surfacePoints[0][0], h + 5);
      surfacePoints.forEach(function (point) {
        lctx.lineTo(point[0], point[1] + 2);
      });
      lctx.lineTo(surfacePoints[surfacePoints.length - 1][0], h + 5);
      lctx.closePath();
      lctx.fillStyle = caveGradient;
      lctx.fill();
    }

    lctx.globalCompositeOperation = "destination-out";
    const playerColumn = clamp(Math.floor(player.x), 0, world.width - 1);
    const underGround = player.y > world.surface[playerColumn] + 1.5;
    const playerLight = (underGround ? 4.7 : 3.5) * TILE;
    const px = player.x * TILE - camX;
    const py = (player.y - 0.9) * TILE - camY;
    const playerFlicker = 0.96 + Math.sin(game.elapsed * 2.7) * 0.025;
    punchLight(lctx, px, py, playerLight * playerFlicker, 0.95);
    lights.forEach(function (light) {
      const radius = light.radius * TILE * 1.03;
      const flicker = 0.97 + Math.sin(game.elapsed * 8.3 + light.flicker) * 0.035;
      punchLight(lctx, light.x, light.y, radius * flicker, 0.94);
    });
    lctx.globalCompositeOperation = "source-over";

    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(lightCanvas, 0, 0, w, h);
    ctx.restore();

    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    lights.forEach(function (light) {
      const radius = light.radius * TILE * 1.35;
      const flicker = 0.9 + Math.sin(game.elapsed * 6.1 + light.flicker) * 0.1;
      const gradient = ctx.createRadialGradient(light.x, light.y, 2, light.x, light.y, radius);
      gradient.addColorStop(0, "rgba(255, 190, 98, " + (0.11 * flicker).toFixed(3) + ")");
      gradient.addColorStop(0.5, "rgba(235, 150, 67, " + (0.045 * flicker).toFixed(3) + ")");
      gradient.addColorStop(1, "rgba(235, 150, 67, 0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(light.x - radius, light.y - radius, radius * 2, radius * 2);
    });
    if (underGround || day.daylight < 0.4) {
      const radius = 150;
      const personGlow = ctx.createRadialGradient(px, py, 4, px, py, radius);
      personGlow.addColorStop(0, "rgba(255, 224, 153, 0.045)");
      personGlow.addColorStop(1, "rgba(255, 224, 153, 0)");
      ctx.fillStyle = personGlow;
      ctx.fillRect(px - radius, py - radius, radius * 2, radius * 2);
    }
    ctx.restore();
  }

  function punchLight(ctx, x, y, radius, strength) {
    const gradient = ctx.createRadialGradient(x, y, radius * 0.06, x, y, radius);
    gradient.addColorStop(0, "rgba(0, 0, 0, " + strength.toFixed(3) + ")");
    gradient.addColorStop(0.28, "rgba(0, 0, 0, " + (strength * 0.86).toFixed(3) + ")");
    gradient.addColorStop(0.64, "rgba(0, 0, 0, " + (strength * 0.38).toFixed(3) + ")");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }

  function drawCracks(ctx, screenX, screenY, progress, seedX, seedY) {
    const stage = Math.ceil(progress * 5);
    if (stage <= 0) {
      return;
    }
    const paths = [
      [[6, 2], [13, 11], [10, 18], [16, 24]],
      [[20, 4], [17, 12], [24, 18], [22, 27]],
      [[3, 20], [11, 17], [15, 23], [13, 30]],
      [[24, 10], [19, 9], [16, 14], [8, 8]],
      [[27, 25], [20, 22], [15, 28], [12, 26]]
    ];
    ctx.save();
    ctx.strokeStyle = "rgba(19, 24, 20, 0.72)";
    ctx.lineWidth = 1.5;
    ctx.lineCap = "square";
    for (let i = 0; i < Math.min(stage, paths.length); i += 1) {
      const path = paths[i];
      ctx.beginPath();
      ctx.moveTo(screenX + path[0][0], screenY + path[0][1]);
      for (let j = 1; j < path.length; j += 1) {
        ctx.lineTo(screenX + path[j][0], screenY + path[j][1]);
      }
      ctx.stroke();
    }
    if (progress > 0.05) {
      ctx.fillStyle = "rgba(240, 226, 189, 0.8)";
      ctx.fillRect(screenX + 3, screenY + TILE - 4, Math.round((TILE - 6) * progress), 2);
    }
    ctx.restore();
  }

  function drawPlacementGhost(ctx, game, camX, camY, placement) {
    const itemKey = placement.itemKey;
    const item = CONTENT.ITEMS[itemKey];
    if (!item || item.kind !== "block") {
      return;
    }
    const screenX = placement.x * TILE - camX;
    const screenY = placement.y * TILE - camY;
    const color = placement.valid ? "rgba(197, 226, 145, 0.92)" : "rgba(219, 119, 91, 0.95)";

    ctx.save();
    ctx.globalAlpha = 0.5;
    if (item.block === B.TORCH) {
      ART.drawTorch(ctx, screenX, screenY, "below", 3);
    } else if (item.block === B.LANTERN) {
      ART.drawLantern(ctx, screenX, screenY, "below", 4);
    } else if (item.block === B.CAMPFIRE) {
      ART.drawCampfire(ctx, screenX, screenY, 5);
    } else {
      const sprite = ART.getBlockSprite(item.block, 0);
      if (sprite) {
        ctx.drawImage(sprite, screenX, screenY);
      }
    }
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(screenX + 1.5, screenY + 1.5, TILE - 3, TILE - 3);
    ctx.setLineDash([]);
    ctx.restore();
  }

  function drawHover(ctx, game, view, camX, camY) {
    const hover = game.hover;
    if (!hover) {
      return;
    }
    const inPlaying = game.mode === "playing";
    if (inPlaying && hover.tx !== undefined && hover.inReach && hover.highlight !== false) {
      const x = hover.tx * TILE - camX;
      const y = hover.ty * TILE - camY;
      const color = hover.validMine === false ? "rgba(222, 127, 90, 0.95)" : "rgba(241, 231, 202, 0.9)";
      ctx.save();
      ctx.strokeStyle = "rgba(22, 28, 23, 0.65)";
      ctx.lineWidth = 3;
      ctx.strokeRect(x + 1.5, y + 1.5, TILE - 3, TILE - 3);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.strokeRect(x + 1.5, y + 1.5, TILE - 3, TILE - 3);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      const corner = 7;
      ctx.beginPath();
      ctx.moveTo(x + 2, y + 2 + corner);
      ctx.lineTo(x + 2, y + 2);
      ctx.lineTo(x + 2 + corner, y + 2);
      ctx.moveTo(x + TILE - 2 - corner, y + 2);
      ctx.lineTo(x + TILE - 2, y + 2);
      ctx.lineTo(x + TILE - 2, y + 2 + corner);
      ctx.moveTo(x + 2, y + TILE - 2 - corner);
      ctx.lineTo(x + 2, y + TILE - 2);
      ctx.lineTo(x + 2 + corner, y + TILE - 2);
      ctx.moveTo(x + TILE - 2 - corner, y + TILE - 2);
      ctx.lineTo(x + TILE - 2, y + TILE - 2);
      ctx.lineTo(x + TILE - 2, y + TILE - 2 - corner);
      ctx.stroke();
      ctx.restore();

      if (hover.progress > 0) {
        drawCracks(ctx, x, y, hover.progress, hover.tx, hover.ty);
      }
    }

    if (inPlaying && hover.enemy) {
      const enemy = hover.enemy;
      const ex = enemy.x * TILE - camX;
      const ey = (enemy.y - enemy.height) * TILE - camY;
      const ew = Math.max(14, enemy.width * TILE);
      const eh = enemy.height * TILE;
      ctx.save();
      ctx.strokeStyle = "rgba(23, 26, 24, 0.65)";
      ctx.lineWidth = 3;
      ctx.strokeRect(ex - ew / 2 - 3, ey - 3, ew + 6, eh + 6);
      ctx.strokeStyle = "rgba(235, 184, 112, 0.9)";
      ctx.lineWidth = 1;
      ctx.strokeRect(ex - ew / 2 - 3, ey - 3, ew + 6, eh + 6);
      ctx.fillStyle = "rgba(235, 184, 112, 0.95)";
      ctx.beginPath();
      ctx.moveTo(ex, ey - 9);
      ctx.lineTo(ex - 4, ey - 15);
      ctx.lineTo(ex + 4, ey - 15);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    if (hover.placement) {
      drawPlacementGhost(ctx, game, camX, camY, hover.placement);
    }

    if (inPlaying && game.mouse && game.mouse.inside !== false) {
      drawCrosshair(ctx, game.mouse.x, game.mouse.y, hover);
    }
  }

  function drawCrosshair(ctx, x, y, hover) {
    const color = hover && hover.validMine === false ? "rgba(236, 142, 109, 0.95)" : "rgba(246, 239, 216, 0.92)";
    ctx.save();
    ctx.lineCap = "square";
    ctx.strokeStyle = "rgba(19, 25, 20, 0.82)";
    ctx.lineWidth = 3.4;
    ctx.beginPath();
    ctx.moveTo(x - 8, y);
    ctx.lineTo(x - 3, y);
    ctx.moveTo(x + 3, y);
    ctx.lineTo(x + 8, y);
    ctx.moveTo(x, y - 8);
    ctx.lineTo(x, y - 3);
    ctx.moveTo(x, y + 3);
    ctx.lineTo(x, y + 8);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(x - 8, y);
    ctx.lineTo(x - 3, y);
    ctx.moveTo(x + 3, y);
    ctx.lineTo(x + 8, y);
    ctx.moveTo(x, y - 8);
    ctx.lineTo(x, y - 3);
    ctx.moveTo(x, y + 3);
    ctx.lineTo(x, y + 8);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.fillRect(x - 1, y - 1, 2, 2);
    ctx.restore();
  }

  function render(ctx, game, view) {
    ensureBackgroundDetails();
    const day = game.dayInfo || TIME.getDayInfo(game.state.worldTime, CONFIG.daySeconds);
    game.dayInfo = day;
    const shakeX = game.shake ? (Math.random() - 0.5) * game.shake : 0;
    const shakeY = game.shake ? (Math.random() - 0.5) * game.shake : 0;
    const camX = Math.round(game.camera.x + shakeX);
    const camY = Math.round(game.camera.y + shakeY);
    const lights = [];

    ctx.save();
    ctx.setTransform(game.view.dpr, 0, 0, game.view.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, view.width, view.height);
    drawSky(ctx, game, view, day);
    drawMountains(ctx, game, view, day, getSkyPalette(day));
    drawBirds(ctx, game, view, day);
    drawWorld(ctx, game, view, camX, camY, lights);

    const enemies = game.enemies || [];
    for (let i = 0; i < enemies.length; i += 1) {
      const enemy = enemies[i];
      if (enemy.dead) {
        continue;
      }
      ART.drawHollow(ctx, enemy, camX, camY, game.elapsed, day.daylight);
    }

    ART.drawPlayer(
      ctx,
      game.player,
      game.state,
      camX,
      camY,
      game.elapsed,
      Boolean(game.hover && game.hover.mining)
    );

    drawLighting(ctx, game, view, camX, camY, lights);
    drawParticles(ctx, game, camX, camY);
    drawFloatingText(ctx, game, camX, camY);
    drawFireflies(ctx, game, view, camX, camY, day);
    drawHover(ctx, game, view, camX, camY);

    // A tiny screen-space dust layer keeps the scene from feeling sterile.
    ctx.restore();
  }

  function init() {
    ART.init();
    ensureBackgroundDetails();
    return root.MosswildRender;
  }

  root.MosswildRender = {
    init,
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
