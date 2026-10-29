(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxRender = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const B = CONFIG.blocks;
  const TAU = Math.PI * 2;
  const PALETTE = Object.freeze({
    1: { base: "#7a5439", top: "#4b8b4d", accent: "#86c45b" },
    2: { base: "#8b5b3d", accent: "#6d422c" },
    3: { base: "#5b6673", accent: "#414b58" },
    4: { base: "#80552f", accent: "#5c3a20" },
    5: { base: "#2f7b45", accent: "#67b65f" },
    6: { base: "#c9b173", accent: "#a78e57" },
    7: { base: "#ad7844", accent: "#7f4f2b" },
    8: { base: "#a9e3ee", accent: "#dffbff" },
    9: { base: "#353843", accent: "#ffc95e" },
    10: { base: "#59636f", accent: "#242a33" },
    11: { base: "#47405f", accent: "#71e4d1" },
    12: { base: "#292932", accent: "#1b1b22" }
  });

  const PARTICLE_COLORS = Object.freeze({
    1: ["#4b8b4d", "#86c45b", "#7a5439"],
    2: ["#8b5b3d", "#6d422c", "#b07b53"],
    3: ["#7b8794", "#5b6673", "#414b58"],
    4: ["#80552f", "#a97747", "#5c3a20"],
    5: ["#2f7b45", "#67b65f", "#9bd77a"],
    6: ["#c9b173", "#e1ca8d", "#a78e57"],
    7: ["#ad7844", "#d09a63", "#7f4f2b"],
    8: ["#a9e3ee", "#dffbff", "#72bdcf"],
    9: ["#ffc95e", "#ffe6a1", "#353843"],
    10: ["#59636f", "#242a33", "#8b96a3"],
    11: ["#71e4d1", "#b8fff4", "#7c6bff"],
    12: ["#292932", "#41414e"]
  });

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function hash(x, y, salt) {
    let value = (Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263) ^ Math.imul(salt | 0, 2246822519)) >>> 0;
    value = Math.imul(value ^ (value >>> 13), 1274126177);
    return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
  }

  function hexToRgb(hex) {
    const clean = hex.replace("#", "");
    return [
      parseInt(clean.slice(0, 2), 16),
      parseInt(clean.slice(2, 4), 16),
      parseInt(clean.slice(4, 6), 16)
    ];
  }

  function mixColour(first, second, amount) {
    const a = typeof first === "string" ? hexToRgb(first) : first;
    const b = typeof second === "string" ? hexToRgb(second) : second;
    return [
      Math.round(a[0] + (b[0] - a[0]) * amount),
      Math.round(a[1] + (b[1] - a[1]) * amount),
      Math.round(a[2] + (b[2] - a[2]) * amount)
    ];
  }

  function rgba(colour, alpha) {
    const rgb = typeof colour === "string" ? hexToRgb(colour) : colour;
    return "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + "," + alpha + ")";
  }

  function shade(hex, amount) {
    const rgb = hexToRgb(hex);
    const target = amount >= 0 ? [255, 255, 255] : [0, 0, 0];
    return "rgb(" + mixColour(rgb, target, Math.abs(amount)).join(",") + ")";
  }

  function daylightAt(dayTime) {
    const angle = (dayTime - 0.25) * TAU;
    return clamp(Math.sin(angle) * 1.22, 0, 1);
  }

  function roundedRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }

  function drawSky(ctx, state) {
    const light = daylightAt(state.dayTime);
    const dusk = clamp(1 - Math.abs(light - 0.42) * 3.2, 0, 1);
    const top = mixColour("#0a1228", "#5aa8d6", light);
    const horizon = mixColour("#1a2544", "#d7eee6", light);
    const warm = mixColour(horizon, "#f0a36b", dusk * 0.34);
    const gradient = ctx.createLinearGradient(0, 0, 0, CONFIG.viewHeight);
    gradient.addColorStop(0, rgba(top, 1));
    gradient.addColorStop(0.56, rgba(warm, 1));
    gradient.addColorStop(1, rgba(mixColour(warm, "#ecdfbd", 0.25), 1));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);

    const starAlpha = Math.pow(1 - light, 2.1);
    if (starAlpha > 0.02) {
      for (let index = 0; index < 90; index += 1) {
        const x = hash(index, 3, 91) * CONFIG.viewWidth;
        const y = hash(index, 5, 17) * CONFIG.viewHeight * 0.6;
        const size = 0.7 + hash(index, 7, 31) * 1.8;
        ctx.fillStyle = "rgba(235,245,255," + (starAlpha * (0.35 + hash(index, 9, 12) * 0.65)).toFixed(3) + ")";
        ctx.fillRect(x, y, size, size);
      }
    }

    const solar = (state.dayTime - 0.25) * 2;
    if (solar >= 0 && solar <= 1) {
      const sunX = -80 + solar * (CONFIG.viewWidth + 160);
      const sunY = 425 - Math.sin(solar * Math.PI) * 330;
      const glow = ctx.createRadialGradient(sunX, sunY, 4, sunX, sunY, 120);
      glow.addColorStop(0, "rgba(255,244,190,0.95)");
      glow.addColorStop(0.22, "rgba(255,219,130,0.45)");
      glow.addColorStop(1, "rgba(255,206,112,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(sunX - 130, sunY - 130, 260, 260);
      ctx.fillStyle = "#fff2b3";
      ctx.beginPath();
      ctx.arc(sunX, sunY, 26, 0, TAU);
      ctx.fill();
    }

    const lunar = (state.dayTime - 0.75 + 1) % 1;
    if (lunar < 0.5) {
      const phase = lunar / 0.5;
      const moonX = -80 + phase * (CONFIG.viewWidth + 160);
      const moonY = 390 - Math.sin(phase * Math.PI) * 300;
      const moonGlow = ctx.createRadialGradient(moonX, moonY, 3, moonX, moonY, 85);
      moonGlow.addColorStop(0, "rgba(205,229,255,0.55)");
      moonGlow.addColorStop(1, "rgba(160,200,255,0)");
      ctx.fillStyle = moonGlow;
      ctx.fillRect(moonX - 95, moonY - 95, 190, 190);
      ctx.fillStyle = "#e8f2ff";
      ctx.beginPath();
      ctx.arc(moonX, moonY, 20, 0, TAU);
      ctx.fill();
      ctx.fillStyle = "rgba(118,150,189,0.32)";
      ctx.beginPath();
      ctx.arc(moonX - 7, moonY - 3, 5, 0, TAU);
      ctx.arc(moonX + 6, moonY + 5, 3.5, 0, TAU);
      ctx.fill();
    }

    drawClouds(ctx, state, light);
    drawBirds(ctx, state, light);
    drawDistantRidges(ctx, state, light);
    drawDistantForest(ctx, state, light);
  }

  function drawClouds(ctx, state, light) {
    const cloudAlpha = 0.1 + light * 0.16;
    for (let index = 0; index < 11; index += 1) {
      const drift = state.time * (5 + hash(index, 1, 44) * 7);
      const total = CONFIG.viewWidth + 520;
      const x = ((hash(index, 2, 74) * total + drift - state.camera.x * 0.035) % total + total) % total - 260;
      const y = 55 + hash(index, 3, 24) * 235;
      const scale = 0.55 + hash(index, 5, 61) * 1.1;
      ctx.fillStyle = "rgba(244,249,255," + cloudAlpha.toFixed(3) + ")";
      ctx.beginPath();
      ctx.ellipse(x, y, 74 * scale, 18 * scale, 0, 0, TAU);
      ctx.ellipse(x + 48 * scale, y - 9 * scale, 54 * scale, 20 * scale, 0, 0, TAU);
      ctx.ellipse(x - 44 * scale, y - 2 * scale, 46 * scale, 15 * scale, 0, 0, TAU);
      ctx.fill();
    }
  }

  function drawBirds(ctx, state, light) {
    if (light < 0.25) {
      return;
    }
    ctx.save();
    ctx.strokeStyle = "rgba(34,48,45," + (0.18 + light * 0.2).toFixed(3) + ")";
    ctx.lineWidth = 1.4;
    for (let index = 0; index < 6; index += 1) {
      const span = CONFIG.viewWidth + 200;
      const speed = 9 + hash(index, 3, 21) * 9;
      const x = ((hash(index, 1, 31) * span + state.time * speed - state.camera.x * 0.025) % span + span) % span - 100;
      const y = 115 + hash(index, 2, 43) * 175 + Math.sin(state.time * 0.65 + index) * 5;
      const size = 3 + hash(index, 4, 72) * 3;
      const flap = Math.sin(state.time * 2.8 + index * 1.7) * size * 0.45;
      ctx.beginPath();
      ctx.moveTo(x - size, y + flap);
      ctx.quadraticCurveTo(x - size * 0.35, y - size * 0.35, x, y);
      ctx.quadraticCurveTo(x + size * 0.35, y - size * 0.35, x + size, y + flap);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawDistantForest(ctx, state, light) {
    const colour = mixColour("#0d211c", "#315447", light);
    ctx.save();
    for (let index = 0; index < 42; index += 1) {
      const span = CONFIG.viewWidth + 260;
      const x = ((hash(index, 7, 51) * span - state.camera.x * 0.115) % span + span) % span - 130;
      const base = 470 + Math.sin((x + state.camera.x * 0.115) / 90 + index) * 10;
      const height = 25 + hash(index, 3, 39) * 38;
      const width = 5 + hash(index, 2, 17) * 5;
      ctx.fillStyle = rgba(colour, 0.34 + hash(index, 5, 12) * 0.25);
      ctx.beginPath();
      ctx.moveTo(x, base - height);
      ctx.lineTo(x - width, base);
      ctx.lineTo(x + width, base);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(x, base - height * 0.58);
      ctx.lineTo(x - width * 1.32, base - height * 0.1);
      ctx.lineTo(x + width * 1.32, base - height * 0.1);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  function drawDistantRidges(ctx, state, light) {
    const layers = [
      { factor: 0.05, base: 455, amplitude: 74, colour: mixColour("#223747", "#8cb9b0", light), alpha: 0.8 },
      { factor: 0.09, base: 500, amplitude: 58, colour: mixColour("#1a2c3a", "#659888", light), alpha: 0.9 },
      { factor: 0.15, base: 548, amplitude: 40, colour: mixColour("#14232c", "#497568", light), alpha: 1 }
    ];
    layers.forEach(function (layer, layerIndex) {
      ctx.beginPath();
      ctx.moveTo(-60, CONFIG.viewHeight);
      for (let x = -60; x <= CONFIG.viewWidth + 60; x += 22) {
        const wave =
          Math.sin((x + state.camera.x * layer.factor) / 180 + layerIndex * 1.7) * layer.amplitude +
          Math.sin((x + state.camera.x * layer.factor) / 67 + layerIndex) * layer.amplitude * 0.23;
        ctx.lineTo(x, layer.base + wave);
      }
      ctx.lineTo(CONFIG.viewWidth + 60, CONFIG.viewHeight);
      ctx.closePath();
      ctx.fillStyle = rgba(layer.colour, layer.alpha);
      ctx.fill();
    });

    const mist = ctx.createLinearGradient(0, 430, 0, 590);
    mist.addColorStop(0, "rgba(220,239,229,0)");
    mist.addColorStop(1, "rgba(218,236,225,0.22)");
    ctx.fillStyle = mist;
    ctx.fillRect(0, 430, CONFIG.viewWidth, 160);
  }

  function drawCaveBackground(ctx, state, tile, firstX, lastX, firstY, lastY) {
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        if (state.world.data[y * state.world.width + x] !== B.air) {
          continue;
        }
        if (y <= state.world.ground[x] + 1) {
          continue;
        }
        const screenX = Math.floor(x * tile - state.camera.x - state.camera.shakeX);
        const screenY = Math.floor(y * tile - state.camera.y - state.camera.shakeY);
        const depth = clamp((y - state.world.ground[x]) / 22, 0, 1);
        ctx.fillStyle = rgba(mixColour("#1c1a23", "#0b0b12", depth), 1);
        ctx.fillRect(screenX, screenY, tile + 1, tile + 1);
        if (hash(x, y, 9) > 0.84) {
          ctx.fillStyle = "rgba(116,154,151,0.16)";
          ctx.fillRect(screenX + hash(x, y, 4) * tile, screenY + hash(x, y, 6) * tile, 2, 2);
        }
      }
    }
  }

  function drawBlockTile(ctx, block, px, py, size, worldX, worldY) {
    const palette = PALETTE[block];
    if (!palette) {
      return;
    }
    const wx = worldX == null ? 0 : worldX;
    const wy = worldY == null ? 0 : worldY;
    const jitter = hash(wx, wy, 3);
    const unit = size / 32;
    ctx.save();
    ctx.translate(px, py);

    if (block === B.grass) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.12);
      ctx.fillRect(0, 0, size, size);
      ctx.fillStyle = shade(palette.top, (hash(wx, wy, 12) - 0.5) * 0.1);
      ctx.fillRect(0, 0, size, size * 0.3);
      ctx.fillStyle = "rgba(28,58,35,0.22)";
      for (let index = 0; index < 5; index += 1) {
        ctx.fillRect(hash(wx, index, 41) * size, size * (0.12 + hash(index, wy, 22) * 0.18), 2 * unit, 2 * unit);
      }
      ctx.strokeStyle = palette.accent;
      ctx.lineWidth = Math.max(1, unit);
      for (let index = 0; index < 4; index += 1) {
        const sx = hash(wx, index, 71) * size;
        const sy = size * 0.05 + hash(index, wy, 12) * size * 0.12;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + (index % 2 ? 2 : -2) * unit, sy - 4 * unit);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(30,24,18,0.15)";
      for (let index = 0; index < 4; index += 1) {
        ctx.fillRect(hash(wx, index, 14) * size, size * 0.45 + hash(wx, index, 77) * size * 0.45, 2 * unit, 2 * unit);
      }
    } else if (block === B.dirt) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.1);
      ctx.fillRect(0, 0, size, size);
      for (let index = 0; index < 14; index += 1) {
        const colour = index % 3 === 0 ? palette.accent : index % 2 ? "#b37b54" : "#69442e";
        ctx.fillStyle = rgba(colour, index % 3 === 0 ? 0.5 : 0.62);
        const dot = Math.max(1.2, unit * (0.7 + hash(wx, index, 13) * 2.2));
        ctx.fillRect(hash(wx, index, 1) * size, hash(index, wy, 9) * size, dot, dot);
      }
      ctx.fillStyle = "rgba(52,31,22,0.2)";
      for (let index = 0; index < 4; index += 1) {
        ctx.fillRect(hash(wx, index, 33) * size, hash(index, wy, 27) * size, 1.5 * unit, 3.5 * unit);
      }
    } else if (block === B.stone) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.14);
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = "rgba(37,45,54,0.45)";
      ctx.lineWidth = Math.max(1, unit);
      for (let index = 0; index < 5; index += 1) {
        const startX = hash(wx, index, 6) * size;
        const startY = hash(wx, index, 7) * size;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(startX + (hash(index, wy, 8) - 0.5) * 20 * unit, startY + 8 * unit);
        ctx.lineTo(startX + (hash(wx, index, 9) - 0.5) * 24 * unit, startY + 17 * unit);
        ctx.stroke();
      }
      for (let index = 0; index < 7; index += 1) {
        ctx.fillStyle = index % 2 ? "rgba(196,211,215,0.16)" : "rgba(31,40,48,0.2)";
        const speck = Math.max(1, unit * (0.6 + hash(wx, index, 45) * 1.7));
        ctx.fillRect(hash(wx, index, 53) * size, hash(index, wy, 57) * size, speck, speck);
      }
      ctx.fillStyle = "rgba(217,231,236,0.12)";
      ctx.fillRect(0, 0, size, Math.max(1, unit));
    } else if (block === B.wood) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.08);
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = "rgba(70,40,21,0.55)";
      ctx.lineWidth = Math.max(1, unit);
      for (let index = 0; index < 4; index += 1) {
        const x = (index + 0.5) * (size / 4) + (hash(wx, index, 3) - 0.5) * 3 * unit;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x + (hash(wx, wy, 5) - 0.5) * 3 * unit, size);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(43,26,17,0.35)";
      ctx.fillRect(0, 0, Math.max(1, unit), size);
      ctx.fillRect(size - Math.max(1, unit), 0, Math.max(1, unit), size);
    } else if (block === B.leaves) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.12);
      ctx.fillRect(0, 0, size, size);
      for (let index = 0; index < 10; index += 1) {
        const cx = hash(wx, index, 31) * size;
        const cy = hash(index, wy, 21) * size;
        const radius = (2.1 + hash(wx, index, 12) * 3.1) * unit;
        ctx.fillStyle = index % 3 === 0 ? rgba(palette.accent, 0.8) : "rgba(31,91,52,0.8)";
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, TAU);
        ctx.fill();
      }
      ctx.fillStyle = "rgba(190,236,143,0.18)";
      ctx.fillRect(0, 0, size, Math.max(1, unit * 2));
    } else if (block === B.sand) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.06);
      ctx.fillRect(0, 0, size, size);
      for (let index = 0; index < 12; index += 1) {
        ctx.fillStyle = index % 2 ? "rgba(237,218,165,0.55)" : "rgba(137,113,69,0.35)";
        const dot = Math.max(1, unit * (0.7 + hash(wx, index, 5) * 1.4));
        ctx.fillRect(hash(wx, index, 8) * size, hash(index, wy, 3) * size, dot, dot);
      }
      ctx.fillStyle = "rgba(255,249,214,0.18)";
      ctx.fillRect(0, 0, size, Math.max(1, unit));
    } else if (block === B.planks) {
      ctx.fillStyle = shade(palette.base, (jitter - 0.5) * 0.08);
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = "rgba(89,50,27,0.65)";
      ctx.lineWidth = Math.max(1, unit);
      for (let row = 1; row <= 3; row += 1) {
        ctx.beginPath();
        ctx.moveTo(0, row * (size / 4));
        ctx.lineTo(size, row * (size / 4));
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(239,190,128,0.2)";
      ctx.fillRect(0, 0, size, Math.max(1, unit));
      for (let index = 0; index < 2; index += 1) {
        ctx.fillStyle = "rgba(80,45,22,0.55)";
        ctx.beginPath();
        ctx.arc(hash(wx, index, 9) * size, hash(index, wy, 7) * size, 1.4 * unit, 0, TAU);
        ctx.fill();
      }
    } else if (block === B.glass) {
      ctx.fillStyle = "rgba(173,228,239,0.2)";
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = "rgba(218,250,255,0.62)";
      ctx.lineWidth = Math.max(1, unit * 1.2);
      ctx.strokeRect(unit, unit, size - unit * 2, size - unit * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.38)";
      ctx.beginPath();
      ctx.moveTo(size * 0.22, size * 0.78);
      ctx.lineTo(size * 0.78, size * 0.22);
      ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.55)";
      ctx.fillRect(size * 0.6, size * 0.25, unit * 1.6, unit * 1.6);
    } else if (block === B.lantern) {
      ctx.fillStyle = "#23252d";
      ctx.fillRect(0, 0, size, size);
      ctx.fillStyle = "#41434b";
      ctx.fillRect(size * 0.2, size * 0.12, size * 0.6, size * 0.76);
      const glow = ctx.createRadialGradient(size / 2, size / 2, 1, size / 2, size / 2, size * 0.42);
      glow.addColorStop(0, "#fff5c9");
      glow.addColorStop(0.45, "#ffc95e");
      glow.addColorStop(1, "rgba(255,155,54,0.06)");
      ctx.fillStyle = glow;
      ctx.fillRect(size * 0.2, size * 0.14, size * 0.6, size * 0.72);
      ctx.fillStyle = "#2a2b31";
      ctx.fillRect(size * 0.18, size * 0.08, size * 0.64, size * 0.08);
      ctx.fillRect(size * 0.18, size * 0.84, size * 0.64, size * 0.08);
      ctx.strokeStyle = "#575862";
      ctx.beginPath();
      ctx.moveTo(size * 0.5, size * 0.06);
      ctx.lineTo(size * 0.5, 0);
      ctx.stroke();
    } else if (block === B.coal) {
      drawBlockTile(ctx, B.stone, 0, 0, size, wx, wy);
      ctx.fillStyle = "rgba(28,31,38,0.92)";
      const spots = [
        [0.18, 0.3, 0.15],
        [0.56, 0.2, 0.12],
        [0.72, 0.63, 0.18],
        [0.35, 0.72, 0.13],
        [0.46, 0.5, 0.09]
      ];
      spots.forEach(function (spot) {
        ctx.beginPath();
        ctx.ellipse(spot[0] * size, spot[1] * size, spot[2] * size, spot[2] * size * 0.7, 0.4, 0, TAU);
        ctx.fill();
      });
      ctx.fillStyle = "rgba(137,151,165,0.22)";
      ctx.fillRect(size * 0.12, size * 0.16, unit, unit);
    } else if (block === B.crystal) {
      drawBlockTile(ctx, B.stone, 0, 0, size, wx, wy);
      const crystalGlow = ctx.createRadialGradient(size / 2, size / 2, 1, size / 2, size / 2, size * 0.6);
      crystalGlow.addColorStop(0, "rgba(117,255,233,0.7)");
      crystalGlow.addColorStop(1, "rgba(83,80,255,0)");
      ctx.fillStyle = crystalGlow;
      ctx.fillRect(0, 0, size, size);
      ctx.fillStyle = "#7df0dc";
      ctx.beginPath();
      ctx.moveTo(size * 0.5, size * 0.1);
      ctx.lineTo(size * 0.67, size * 0.45);
      ctx.lineTo(size * 0.54, size * 0.84);
      ctx.lineTo(size * 0.38, size * 0.44);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "rgba(234,255,252,0.9)";
      ctx.beginPath();
      ctx.moveTo(size * 0.5, size * 0.14);
      ctx.lineTo(size * 0.59, size * 0.44);
      ctx.lineTo(size * 0.5, size * 0.68);
      ctx.closePath();
      ctx.fill();
    } else if (block === B.bedrock) {
      ctx.fillStyle = palette.base;
      ctx.fillRect(0, 0, size, size);
      ctx.fillStyle = palette.accent;
      for (let index = 0; index < 5; index += 1) {
        ctx.fillRect(hash(wx, index, 2) * size, hash(index, wy, 4) * size, size * 0.2, size * 0.12);
      }
    }
    ctx.restore();
  }

  function drawSurfaceDetails(ctx, state, tile, firstX, lastX, firstY, lastY) {
    const world = state.world;
    for (let x = firstX; x <= lastX; x += 1) {
      const surface = world.ground[x];
      if (surface < firstY - 1 || surface > lastY + 1) {
        continue;
      }
      const block = world.data[surface * world.width + x];
      if (block !== B.grass && block !== B.sand) {
        continue;
      }
      if (surface > 0 && world.data[(surface - 1) * world.width + x] !== B.air) {
        continue;
      }
      const sx = x * tile - state.camera.x - state.camera.shakeX;
      const sy = surface * tile - state.camera.y - state.camera.shakeY;
      const seed = hash(x, surface, 71);
      if (block === B.sand) {
        if (seed > 0.65) {
          ctx.fillStyle = "rgba(246,228,173,0.55)";
          ctx.beginPath();
          ctx.arc(sx + tile * 0.3, sy + tile * 0.55, tile * 0.08, 0, TAU);
          ctx.arc(sx + tile * 0.55, sy + tile * 0.6, tile * 0.06, 0, TAU);
          ctx.fill();
        }
        continue;
      }
      const sway = Math.sin(state.time * 1.6 + x * 0.8) * 1.3;
      ctx.strokeStyle = "rgba(87,150,75,0.9)";
      ctx.lineWidth = 1.3;
      for (let blade = 0; blade < 3; blade += 1) {
        const bx = sx + tile * (0.22 + blade * 0.22) + hash(x, blade, 41) * 4;
        const height = 5 + hash(x, blade, 12) * 7;
        ctx.beginPath();
        ctx.moveTo(bx, sy + 1);
        ctx.quadraticCurveTo(bx + sway, sy - height * 0.55, bx + sway * 1.6, sy - height);
        ctx.stroke();
      }
      if (seed > 0.84) {
        const flowerX = sx + tile * (0.3 + hash(x, 8, 5) * 0.4);
        const flowerY = sy - 5 - hash(x, 4, 9) * 4;
        ctx.strokeStyle = "rgba(79,131,66,0.9)";
        ctx.beginPath();
        ctx.moveTo(flowerX, sy);
        ctx.lineTo(flowerX + sway * 0.5, flowerY);
        ctx.stroke();
        ctx.fillStyle = seed > 0.93 ? "#f2c85e" : "#e98c8c";
        ctx.beginPath();
        ctx.arc(flowerX + sway * 0.5, flowerY, 2.8, 0, TAU);
        ctx.fill();
        ctx.fillStyle = "rgba(255,249,206,0.9)";
        ctx.beginPath();
        ctx.arc(flowerX + sway * 0.5, flowerY, 1.1, 0, TAU);
        ctx.fill();
      }
    }
  }

  function drawCaveFlora(ctx, state, tile, firstX, lastX, firstY, lastY) {
    const world = state.world;
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        if (world.data[y * world.width + x] !== B.air) {
          continue;
        }
        if (y <= world.ground[x] + 4 || y >= world.height - 1) {
          continue;
        }
        if (!worldApiSolid(world, x, y + 1)) {
          continue;
        }
        if (hash(x, y, 88) < 0.88) {
          continue;
        }
        const sx = x * tile - state.camera.x - state.camera.shakeX + tile * 0.5;
        const sy = (y + 1) * tile - state.camera.y - state.camera.shakeY;
        const warm = hash(x, y, 12) > 0.55;
        const cap = warm ? "#e9b26c" : "#77dfc6";
        const glow = ctx.createRadialGradient(sx, sy - 5, 1, sx, sy - 5, 18);
        glow.addColorStop(0, warm ? "rgba(244,183,103,0.22)" : "rgba(112,235,205,0.2)");
        glow.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = glow;
        ctx.fillRect(sx - 18, sy - 23, 36, 36);
        ctx.strokeStyle = "rgba(215,228,206,0.55)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + (warm ? 1 : -1), sy - 5);
        ctx.stroke();
        ctx.fillStyle = cap;
        ctx.beginPath();
        ctx.ellipse(sx, sy - 5, 3.1, 1.9, 0, 0, TAU);
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,236,0.55)";
        ctx.fillRect(sx - 1, sy - 5.5, 1.2, 1.2);
      }
    }
  }

  function worldApiSolid(world, x, y) {
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return false;
    }
    return world.data[y * world.width + x] !== B.air;
  }

  function drawWorld(ctx, state) {
    const tile = CONFIG.tileSize;
    const camera = state.camera;
    const world = state.world;
    const firstX = Math.max(0, Math.floor((camera.x + camera.shakeX) / tile) - 1);
    const lastX = Math.min(world.width - 1, Math.ceil((camera.x + camera.shakeX + CONFIG.viewWidth) / tile) + 1);
    const firstY = Math.max(0, Math.floor((camera.y + camera.shakeY) / tile) - 1);
    const lastY = Math.min(world.height - 1, Math.ceil((camera.y + camera.shakeY + CONFIG.viewHeight) / tile) + 1);

    drawCaveBackground(ctx, state, tile, firstX, lastX, firstY, lastY);

    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        const block = world.data[y * world.width + x];
        if (block === B.air) {
          continue;
        }
        const px = Math.floor(x * tile - camera.x - camera.shakeX);
        const py = Math.floor(y * tile - camera.y - camera.shakeY);
        drawBlockTile(ctx, block, px, py, tile, x, y);
        ctx.strokeStyle = "rgba(11,19,16,0.065)";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, tile - 1, tile - 1);
        const above = y > 0 ? world.data[(y - 1) * world.width + x] : B.air;
        if (above === B.air && block !== B.glass) {
          ctx.fillStyle = "rgba(239,253,220,0.13)";
          ctx.fillRect(px, py, tile, 2);
        }
        if (y < world.height - 1) {
          const below = world.data[(y + 1) * world.width + x];
          if (below === B.air) {
            ctx.fillStyle = "rgba(12,16,20,0.18)";
            ctx.fillRect(px, py + tile - 2, tile, 2);
          }
        }
      }
    }

    drawSurfaceDetails(ctx, state, tile, firstX, lastX, firstY, lastY);
    drawCaveFlora(ctx, state, tile, firstX, lastX, firstY, lastY);

    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let y = firstY; y <= lastY; y += 1) {
      for (let x = firstX; x <= lastX; x += 1) {
        const block = world.data[y * world.width + x];
        if (block !== B.lantern && block !== B.crystal) {
          continue;
        }
        const px = x * tile - camera.x - camera.shakeX + tile / 2;
        const py = y * tile - camera.y - camera.shakeY + tile / 2;
        const radius = block === B.lantern ? 105 : 64;
        const glow = ctx.createRadialGradient(px, py, 2, px, py, radius);
        glow.addColorStop(0, block === B.lantern ? "rgba(255,205,96,0.32)" : "rgba(106,245,224,0.28)");
        glow.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = glow;
        ctx.fillRect(px - radius, py - radius, radius * 2, radius * 2);
      }
    }
    ctx.restore();
  }

  function drawPlayer(ctx, state) {
    const player = state.player;
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    const px = player.x * tile - camera.x - camera.shakeX;
    const py = player.y * tile - camera.y - camera.shakeY;
    const moving = Math.abs(player.vx) > 0.5;
    const walk = moving && player.onGround ? Math.sin(player.animTime * 9.2) : 0;
    const bob = moving && player.onGround ? Math.abs(Math.sin(player.animTime * 9.2)) * 2 : 0;

    ctx.save();
    ctx.fillStyle = "rgba(7,12,12,0.24)";
    ctx.beginPath();
    ctx.ellipse(px, py + 1.5, 15, 4.5, 0, 0, TAU);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(px, py - bob);
    ctx.scale(player.facing, 1);

    if (state.daylight < 0.38) {
      const glow = ctx.createRadialGradient(0, -27, 2, 0, -27, 58);
      glow.addColorStop(0, "rgba(255,199,103,0.2)");
      glow.addColorStop(1, "rgba(255,180,70,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(-62, -88, 124, 124);
    }

    ctx.save();
    ctx.translate(-5, -18);
    ctx.rotate(player.onGround ? walk * 0.32 : -0.22);
    ctx.fillStyle = "#2b292d";
    ctx.fillRect(-4, 0, 8, 17);
    ctx.fillStyle = "#5a3e2b";
    ctx.fillRect(-4, 14, 9, 4);
    ctx.restore();

    ctx.save();
    ctx.translate(5, -18);
    ctx.rotate(player.onGround ? -walk * 0.32 : 0.24);
    ctx.fillStyle = "#3a373b";
    ctx.fillRect(-4, 0, 8, 17);
    ctx.fillStyle = "#6b4a31";
    ctx.fillRect(-4, 14, 9, 4);
    ctx.restore();

    ctx.fillStyle = "#203a37";
    roundedRect(ctx, -13, -43, 26, 28, 7);
    ctx.fill();
    ctx.fillStyle = "#2f5b52";
    roundedRect(ctx, -11, -42, 21, 25, 5);
    ctx.fill();

    ctx.fillStyle = "#8c4f3f";
    ctx.fillRect(-13, -27, 24, 3);
    ctx.fillStyle = "#e2a34f";
    ctx.fillRect(-12, -26, 25, 3);
    ctx.fillStyle = "#f0bd6d";
    ctx.fillRect(2, -25, 5, 8);

    ctx.fillStyle = "#d9a06d";
    ctx.fillRect(-9, -57, 20, 17);
    ctx.fillStyle = "#e8b37c";
    ctx.fillRect(-8, -55, 18, 13);
    ctx.fillStyle = "#2b3734";
    ctx.beginPath();
    ctx.arc(-2, -53, 10.5, Math.PI, TAU);
    ctx.fill();
    ctx.fillRect(-12, -54, 24, 4);
    ctx.fillStyle = "#3e5750";
    ctx.fillRect(-13, -55, 5, 8);

    ctx.fillStyle = "#233631";
    ctx.fillRect(3, -49, 2.5, 3);
    ctx.fillStyle = "#f5e6c8";
    ctx.fillRect(4, -48, 1.2, 1.2);
    ctx.fillStyle = "rgba(170,92,74,0.65)";
    ctx.fillRect(0, -45, 3, 1.2);

    ctx.fillStyle = "#e2a34f";
    roundedRect(ctx, -13, -41, 7, 7, 2);
    ctx.fill();

    ctx.save();
    ctx.translate(13, -30);
    ctx.rotate(-0.2);
    ctx.fillStyle = "#d9a06d";
    ctx.fillRect(-2, 0, 5, 12);
    ctx.restore();

    const held = state.selectedBlock;
    if (held != null) {
      ctx.save();
      ctx.translate(11, -36);
      ctx.globalAlpha = 0.96;
      drawBlockTile(ctx, held, 0, 0, 13, 7, 7);
      ctx.restore();
    }

    ctx.restore();
  }

  function drawTarget(ctx, state) {
    const hover = state.hover;
    if (!hover || hover.block === null) {
      return;
    }
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    if (hover.canMine) {
      const px = Math.floor(hover.x * tile - camera.x - camera.shakeX);
      const py = Math.floor(hover.y * tile - camera.y - camera.shakeY);
      ctx.fillStyle = "rgba(255,211,107,0.14)";
      ctx.fillRect(px, py, tile, tile);
      ctx.strokeStyle = "rgba(255,226,150,0.95)";
      ctx.lineWidth = 2;
      drawBracket(ctx, px + 2, py + 2, tile - 4, tile - 4);
    } else if (hover.empty) {
      const px = Math.floor(hover.x * tile - camera.x - camera.shakeX);
      const py = Math.floor(hover.y * tile - camera.y - camera.shakeY);
      ctx.strokeStyle = hover.inReach ? "rgba(219,245,236,0.28)" : "rgba(255,143,132,0.55)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 5]);
      ctx.strokeRect(px + 2, py + 2, tile - 4, tile - 4);
      ctx.setLineDash([]);
    }

    if (hover.canPlace && hover.placement) {
      const placement = hover.placement;
      const px = Math.floor(placement.x * tile - camera.x - camera.shakeX);
      const py = Math.floor(placement.y * tile - camera.y - camera.shakeY);
      ctx.save();
      ctx.globalAlpha = 0.48;
      drawBlockTile(ctx, state.selectedBlock, px, py, tile, placement.x, placement.y);
      ctx.restore();
      ctx.strokeStyle = "rgba(139,244,190,0.95)";
      ctx.lineWidth = 2;
      drawBracket(ctx, px + 1, py + 1, tile - 2, tile - 2);
    } else if (!hover.canMine && !hover.canPlace) {
      const px = Math.floor(hover.x * tile - camera.x - camera.shakeX);
      const py = Math.floor(hover.y * tile - camera.y - camera.shakeY);
      ctx.strokeStyle = "rgba(255,122,112,0.7)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px + 7, py + 7);
      ctx.lineTo(px + tile - 7, py + tile - 7);
      ctx.moveTo(px + tile - 7, py + 7);
      ctx.lineTo(px + 7, py + tile - 7);
      ctx.stroke();
    }
  }

  function drawBracket(ctx, x, y, width, height) {
    const length = Math.max(5, width * 0.24);
    ctx.beginPath();
    ctx.moveTo(x, y + length);
    ctx.lineTo(x, y);
    ctx.lineTo(x + length, y);
    ctx.moveTo(x + width - length, y);
    ctx.lineTo(x + width, y);
    ctx.lineTo(x + width, y + length);
    ctx.moveTo(x + width, y + height - length);
    ctx.lineTo(x + width, y + height);
    ctx.lineTo(x + width - length, y + height);
    ctx.moveTo(x + length, y + height);
    ctx.lineTo(x, y + height);
    ctx.lineTo(x, y + height - length);
    ctx.stroke();
  }

  function drawParticles(ctx, state) {
    const camera = state.camera;
    const tile = CONFIG.tileSize;
    state.particles.forEach(function (particle) {
      const alpha = clamp(particle.life / particle.maxLife, 0, 1);
      if (alpha <= 0) {
        return;
      }
      const x = particle.x * tile - camera.x - camera.shakeX;
      const y = particle.y * tile - camera.y - camera.shakeY;
      ctx.fillStyle = rgba(particle.color, alpha * 0.95);
      ctx.fillRect(x, y, particle.size, particle.size);
    });
  }

  function drawAtmosphere(ctx, state) {
    const light = state.daylight;
    const darkness = 1 - light;
    if (light > 0.3) {
      for (let index = 0; index < 18; index += 1) {
        const drift = state.time * (2.2 + hash(index, 1, 31) * 3.8);
        const x = (hash(index, 2, 54) * CONFIG.viewWidth + drift) % CONFIG.viewWidth;
        const y = 150 + hash(index, 4, 76) * 390 + Math.sin(state.time * 0.7 + index) * 14;
        const alpha = (0.035 + hash(index, 6, 12) * 0.07) * light;
        ctx.fillStyle = "rgba(255,244,197," + alpha.toFixed(3) + ")";
        ctx.beginPath();
        ctx.arc(x, y, 0.9 + hash(index, 8, 9) * 1.2, 0, TAU);
        ctx.fill();
      }
    }
    if (darkness > 0.08) {
      ctx.save();
      ctx.fillStyle = "rgba(6,11,25," + (darkness * 0.46).toFixed(3) + ")";
      ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);

      const tile = CONFIG.tileSize;
      const camera = state.camera;
      const firstX = Math.max(0, Math.floor((camera.x + camera.shakeX) / tile) - 1);
      const lastX = Math.min(state.world.width - 1, Math.ceil((camera.x + camera.shakeX + CONFIG.viewWidth) / tile) + 1);
      const firstY = Math.max(0, Math.floor((camera.y + camera.shakeY) / tile) - 1);
      const lastY = Math.min(state.world.height - 1, Math.ceil((camera.y + camera.shakeY + CONFIG.viewHeight) / tile) + 1);
      ctx.globalCompositeOperation = "lighter";
      for (let y = firstY; y <= lastY; y += 1) {
        for (let x = firstX; x <= lastX; x += 1) {
          const block = state.world.data[y * state.world.width + x];
          if (block !== B.lantern && block !== B.crystal) {
            continue;
          }
          const px = x * tile - camera.x - camera.shakeX + tile / 2;
          const py = y * tile - camera.y - camera.shakeY + tile / 2;
          const radius = block === B.lantern ? 92 : 54;
          const glow = ctx.createRadialGradient(px, py, 2, px, py, radius);
          glow.addColorStop(0, block === B.lantern ? "rgba(255,196,78,0.18)" : "rgba(99,240,217,0.14)");
          glow.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = glow;
          ctx.fillRect(px - radius, py - radius, radius * 2, radius * 2);
        }
      }

      const playerX = state.player.x * tile - camera.x - camera.shakeX;
      const playerY = state.player.y * tile - camera.y - camera.shakeY - 30;
      const aura = ctx.createRadialGradient(playerX, playerY, 10, playerX, playerY, 180);
      aura.addColorStop(0, "rgba(255,190,105,0.11)");
      aura.addColorStop(0.5, "rgba(255,176,83,0.05)");
      aura.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = aura;
      ctx.fillRect(playerX - 190, playerY - 190, 380, 380);

      for (let index = 0; index < 28; index += 1) {
        const phase = state.time * (0.35 + hash(index, 2, 52) * 0.45) + index * 1.71;
        const fireflyX = (hash(index, 7, 11) * CONFIG.viewWidth + Math.sin(phase * 1.4) * 48 + CONFIG.viewWidth) % CONFIG.viewWidth;
        const fireflyY = 170 + hash(index, 3, 21) * 390 + Math.cos(phase) * 26;
        const pulse = 0.4 + 0.6 * Math.abs(Math.sin(phase * 2.2));
        ctx.fillStyle = "rgba(255,225,132," + (darkness * pulse * 0.75).toFixed(3) + ")";
        ctx.beginPath();
        ctx.arc(fireflyX, fireflyY, 1.5, 0, TAU);
        ctx.fill();
      }
      ctx.restore();
    }

    const vignette = ctx.createRadialGradient(
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      CONFIG.viewHeight * 0.28,
      CONFIG.viewWidth / 2,
      CONFIG.viewHeight / 2,
      CONFIG.viewWidth * 0.66
    );
    vignette.addColorStop(0, "rgba(5,10,12,0)");
    vignette.addColorStop(1, "rgba(4,8,10,0.33)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
  }

  function renderFrame(ctx, state) {
    ctx.clearRect(0, 0, CONFIG.viewWidth, CONFIG.viewHeight);
    const daylight = daylightAt(state.dayTime);
    state.daylight = daylight;
    drawSky(ctx, state);
    drawWorld(ctx, state);
    drawTarget(ctx, state);
    drawPlayer(ctx, state);
    drawParticles(ctx, state);
    drawAtmosphere(ctx, state);
  }

  function spawnBlockBurst(particles, x, y, block, count) {
    const colours = PARTICLE_COLORS[block] || ["#dbe8dc"];
    const total = count || 10;
    for (let index = 0; index < total; index += 1) {
      const angle = Math.random() * TAU;
      const speed = 1.4 + Math.random() * 4.3;
      const life = 0.35 + Math.random() * 0.65;
      particles.push({
        x: x + 0.5 + (Math.random() - 0.5) * 0.6,
        y: y + 0.5 + (Math.random() - 0.5) * 0.6,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1.6,
        gravity: 9,
        life: life,
        maxLife: life,
        size: 1.5 + Math.random() * 3.2,
        color: colours[Math.floor(Math.random() * colours.length)]
      });
    }
  }

  function spawnSparkles(particles, x, y, count, colour) {
    const total = count || 10;
    for (let index = 0; index < total; index += 1) {
      const angle = Math.random() * TAU;
      const speed = 0.5 + Math.random() * 2.8;
      const life = 0.5 + Math.random() * 0.5;
      particles.push({
        x: x + 0.5,
        y: y + 0.5,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 0.8,
        gravity: 1.8,
        life: life,
        maxLife: life,
        size: 1 + Math.random() * 2.4,
        color: colour || "#ffe49a"
      });
    }
  }

  function updateParticles(particles, dt) {
    for (let index = particles.length - 1; index >= 0; index -= 1) {
      const particle = particles[index];
      particle.life -= dt;
      if (particle.life <= 0) {
        particles.splice(index, 1);
        continue;
      }
      particle.vy += particle.gravity * dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
    }
  }

  function blockIcon(ctx, block, size) {
    drawBlockTile(ctx, block, 0, 0, size || 32, 11, 9);
  }

  function renderMinimap(ctx, world, player, camera, width, height) {
    ctx.clearRect(0, 0, width, height);
    const sky = ctx.createLinearGradient(0, 0, 0, height);
    sky.addColorStop(0, "#182b30");
    sky.addColorStop(1, "#0c171b");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, width, height);
    const scaleX = width / world.width;
    const scaleY = height / world.height;
    for (let x = 0; x < world.width; x += 1) {
      const surface = world.ground[x];
      const block = world.data[surface * world.width + x];
      let colour = "#65864d";
      if (block === B.sand) {
        colour = "#b9a069";
      } else if (block === B.stone) {
        colour = "#6c7480";
      }
      ctx.fillStyle = colour;
      ctx.fillRect(Math.floor(x * scaleX), Math.floor(surface * scaleY), Math.ceil(scaleX), Math.ceil((world.height - surface) * scaleY));
      if (x % 9 === 0) {
        ctx.fillStyle = "rgba(255,255,255,0.06)";
        ctx.fillRect(Math.floor(x * scaleX), Math.floor(surface * scaleY), 1, Math.ceil((world.height - surface) * scaleY));
      }
    }
    const viewX = (camera.x / CONFIG.tileSize) * scaleX;
    const viewY = (camera.y / CONFIG.tileSize) * scaleY;
    ctx.strokeStyle = "rgba(255,245,204,0.7)";
    ctx.lineWidth = 1;
    ctx.strokeRect(
      Math.max(0.5, viewX),
      Math.max(0.5, viewY),
      Math.min(width - 1, (CONFIG.viewWidth / CONFIG.tileSize) * scaleX),
      Math.min(height - 1, (CONFIG.viewHeight / CONFIG.tileSize) * scaleY)
    );
    ctx.fillStyle = "#ffd46d";
    ctx.beginPath();
    ctx.arc(player.x * scaleX, (player.y - player.height / 2) * scaleY, 2.7, 0, TAU);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,221,133,0.4)";
    ctx.beginPath();
    ctx.arc(player.x * scaleX, (player.y - player.height / 2) * scaleY, 5.2, 0, TAU);
    ctx.stroke();
  }

  return {
    renderFrame: renderFrame,
    blockIcon: blockIcon,
    renderMinimap: renderMinimap,
    updateParticles: updateParticles,
    spawnBlockBurst: spawnBlockBurst,
    spawnSparkles: spawnSparkles,
    daylightAt: daylightAt,
    PALETTE: PALETTE
  };
});
