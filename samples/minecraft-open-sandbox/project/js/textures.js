(function () {
  "use strict";

  const TILE = 24;
  const VARIANTS = 3;
  const rng = window.SandboxRng;

  function hexToRgb(hex) {
    const value = parseInt(hex.replace("#", ""), 16);
    return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
  }

  function shade(hex, amount) {
    const color = hexToRgb(hex);
    const clamp = function (value) { return Math.max(0, Math.min(255, Math.round(value))); };
    return "rgb(" + clamp(color.r + amount) + "," + clamp(color.g + amount) + "," + clamp(color.b + amount) + ")";
  }

  function makeCanvas(size) {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    return canvas;
  }

  function fillPixelBase(ctx, color, variation, rand, size) {
    const step = 2;
    for (let y = 0; y < size; y += step) {
      for (let x = 0; x < size; x += step) {
        const offset = (rand() - 0.5) * variation;
        ctx.fillStyle = shade(color, offset);
        ctx.fillRect(x, y, step, step);
      }
    }
  }

  function speckle(ctx, colors, count, rand, size, min, max) {
    for (let index = 0; index < count; index += 1) {
      const x = Math.floor(rand() * size);
      const y = Math.floor(rand() * size);
      const w = min + Math.floor(rand() * (max - min + 1));
      ctx.fillStyle = colors[Math.floor(rand() * colors.length)];
      ctx.fillRect(x, y, w, w);
    }
  }

  function drawStoneBase(ctx, rand, size) {
    fillPixelBase(ctx, "#7c8384", 34, rand, size);
    speckle(ctx, ["#666f72", "#949b9a", "#5c6669"], 28, rand, size, 1, 2);
    ctx.strokeStyle = "rgba(55, 63, 65, 0.45)";
    ctx.lineWidth = 1;
    for (let crack = 0; crack < 2; crack += 1) {
      let x = Math.floor(rand() * size);
      let y = Math.floor(rand() * size);
      ctx.beginPath();
      ctx.moveTo(x, y);
      const steps = 2 + Math.floor(rand() * 3);
      for (let step = 0; step < steps; step += 1) {
        x += Math.floor((rand() - 0.5) * 7);
        y += 2 + Math.floor(rand() * 4);
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  function drawGrass(ctx, rand, size) {
    fillPixelBase(ctx, "#7a573c", 26, rand, size);
    speckle(ctx, ["#896245", "#664833", "#977155"], 18, rand, size, 1, 2);
    const lip = 5 + Math.floor(rand() * 3);
    for (let x = 0; x < size; x += 1) {
      const depth = lip + Math.floor(rand() * 2);
      ctx.fillStyle = "#4f8a3b";
      ctx.fillRect(x, 0, 1, depth);
      ctx.fillStyle = x % 3 === 0 ? "#6caf4e" : "#5c9b43";
      ctx.fillRect(x, 0, 1, Math.max(1, depth - 2));
    }
    ctx.fillStyle = "#7dc45a";
    ctx.fillRect(0, 0, size, 1);
    ctx.fillStyle = "rgba(53, 92, 42, 0.55)";
    for (let x = 0; x < size; x += 3) {
      ctx.fillRect(x, lip, 1, 2 + Math.floor(rand() * 3));
    }
    for (let blade = 0; blade < 4; blade += 1) {
      const x = Math.floor(rand() * size);
      ctx.fillStyle = "#73b953";
      ctx.fillRect(x, 0, 1, 2);
    }
  }

  function drawDirt(ctx, rand, size) {
    fillPixelBase(ctx, "#7d5a3d", 30, rand, size);
    speckle(ctx, ["#916b4a", "#62452f", "#a37a54", "#553b2a"], 30, rand, size, 1, 2);
  }

  function drawSand(ctx, rand, size) {
    fillPixelBase(ctx, "#d6bd7b", 26, rand, size);
    speckle(ctx, ["#b89d60", "#e8d292", "#c4a968"], 38, rand, size, 1, 2);
  }

  function drawCobble(ctx, rand, size) {
    ctx.fillStyle = "#4f5657";
    ctx.fillRect(0, 0, size, size);
    const stones = [
      [1, 1, 9, 8], [11, 2, 8, 6], [20, 1, 4, 9], [1, 10, 7, 6],
      [9, 9, 9, 7], [19, 11, 5, 5], [2, 17, 10, 6], [13, 17, 9, 6]
    ];
    stones.forEach(function (stone, index) {
      const base = index % 2 === 0 ? "#7f8888" : "#8f9796";
      ctx.fillStyle = shade(base, (rand() - 0.5) * 20);
      ctx.fillRect(stone[0], stone[1], stone[2], stone[3]);
      ctx.fillStyle = "rgba(255,255,255,0.16)";
      ctx.fillRect(stone[0], stone[1], stone[2], 1);
      ctx.fillStyle = "rgba(35,42,43,0.4)";
      ctx.fillRect(stone[0], stone[1] + stone[3] - 1, stone[2], 1);
    });
    speckle(ctx, ["#626b6b", "#a0a7a5"], 16, rand, size, 1, 1);
  }

  function drawWood(ctx, rand, size) {
    fillPixelBase(ctx, "#775233", 24, rand, size);
    ctx.fillStyle = "rgba(61, 38, 22, 0.55)";
    for (let x = 2; x < size; x += 5) {
      ctx.fillRect(x, 0, 1, size);
    }
    for (let line = 0; line < 6; line += 1) {
      const x = Math.floor(rand() * size);
      const y = Math.floor(rand() * size);
      ctx.fillStyle = "#9b7147";
      ctx.fillRect(x, y, 2, 1);
      ctx.fillStyle = "#593b25";
      ctx.fillRect(x + 2, y + 2, 1, 1);
    }
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.fillRect(5, 0, 1, size);
  }

  function drawLeaves(ctx, rand, size) {
    ctx.clearRect(0, 0, size, size);
    const greens = ["#356d35", "#468740", "#5b9b48", "#2a5a2c", "#6eae55"];
    for (let index = 0; index < 36; index += 1) {
      const x = Math.floor(rand() * (size - 4));
      const y = Math.floor(rand() * (size - 4));
      const w = 3 + Math.floor(rand() * 4);
      const h = 3 + Math.floor(rand() * 3);
      ctx.fillStyle = greens[Math.floor(rand() * greens.length)];
      ctx.fillRect(x, y, w, h);
    }
    for (let index = 0; index < 5; index += 1) {
      const x = Math.floor(rand() * (size - 2));
      const y = Math.floor(rand() * (size - 2));
      ctx.clearRect(x, y, 2, 2);
    }
    ctx.fillStyle = "rgba(20, 45, 22, 0.28)";
    for (let index = 0; index < 9; index += 1) {
      ctx.fillRect(Math.floor(rand() * size), Math.floor(rand() * size), 1, 1);
    }
  }

  function drawPlanks(ctx, rand, size) {
    fillPixelBase(ctx, "#b47b43", 22, rand, size);
    for (let y = 0; y < size; y += 6) {
      ctx.fillStyle = "rgba(83, 48, 24, 0.6)";
      ctx.fillRect(0, y, size, 1);
      ctx.fillStyle = "rgba(255, 221, 160, 0.18)";
      ctx.fillRect(0, y + 1, size, 1);
    }
    for (let index = 0; index < 10; index += 1) {
      ctx.fillStyle = "rgba(107, 63, 31, 0.42)";
      ctx.fillRect(Math.floor(rand() * size), Math.floor(rand() * size), 1, 4);
    }
    ctx.fillStyle = "rgba(63, 38, 20, 0.45)";
    [4, 15].forEach(function (x) {
      ctx.fillRect(x, 9, 1, 1);
      ctx.fillRect(x, 21, 1, 1);
    });
  }

  function drawOre(ctx, rand, size, colors) {
    drawStoneBase(ctx, rand, size);
    for (let cluster = 0; cluster < 5; cluster += 1) {
      const cx = 3 + Math.floor(rand() * (size - 7));
      const cy = 3 + Math.floor(rand() * (size - 7));
      for (let index = 0; index < 4; index += 1) {
        ctx.fillStyle = colors[Math.floor(rand() * colors.length)];
        ctx.fillRect(cx + Math.floor(rand() * 4), cy + Math.floor(rand() * 4), 2, 2);
      }
      ctx.fillStyle = "rgba(0,0,0,0.32)";
      ctx.fillRect(cx, cy + 4, 1, 1);
    }
  }

  function drawTorch(ctx, rand, size) {
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "rgba(255, 185, 72, 0.16)";
    ctx.fillRect(5, 0, 14, 14);
    ctx.fillStyle = "#6d4327";
    ctx.fillRect(10, 9, 4, 14);
    ctx.fillStyle = "#9b6a3c";
    ctx.fillRect(11, 10, 1, 12);
    ctx.fillStyle = "#2b1a12";
    ctx.fillRect(9, 21, 6, 2);
    ctx.fillStyle = "#ffb43b";
    ctx.fillRect(8, 4, 8, 7);
    ctx.fillStyle = "#ffd56a";
    ctx.fillRect(9, 2, 6, 7);
    ctx.fillStyle = "#fff2b0";
    ctx.fillRect(10, 1, 4, 4);
    ctx.fillStyle = "rgba(255, 95, 32, 0.75)";
    ctx.fillRect(11, 8, 2, 3);
  }

  function drawTable(ctx, rand, size) {
    drawPlanks(ctx, rand, size);
    ctx.fillStyle = "#6f4526";
    ctx.fillRect(0, 0, size, 3);
    ctx.fillRect(0, 0, 3, size);
    ctx.fillRect(size - 3, 0, 3, size);
    ctx.fillRect(0, size - 3, size, 3);
    ctx.fillStyle = "#c99355";
    ctx.fillRect(4, 4, 16, 16);
    ctx.fillStyle = "#5b3a22";
    for (let index = 0; index < 3; index += 1) {
      ctx.fillRect(7, 7 + index * 4, 10, 1);
      ctx.fillRect(7 + index * 4, 7, 1, 10);
    }
    ctx.fillStyle = "#e2b778";
    ctx.fillRect(4, 4, 16, 1);
    ctx.fillRect(4, 4, 1, 16);
  }

  function drawFurnace(ctx, rand, size) {
    drawCobble(ctx, rand, size);
    ctx.fillStyle = "#4b4f50";
    ctx.fillRect(4, 4, 16, 18);
    ctx.fillStyle = "#202527";
    ctx.fillRect(6, 11, 12, 9);
    ctx.fillStyle = "#333839";
    ctx.fillRect(5, 4, 14, 7);
    ctx.fillStyle = "#ff8f32";
    ctx.fillRect(8, 16, 2, 2);
    ctx.fillRect(13, 14, 2, 2);
    ctx.fillStyle = "#ffcf5e";
    ctx.fillRect(9, 18, 1, 1);
    ctx.fillRect(14, 16, 1, 1);
    ctx.fillStyle = "rgba(255,255,255,0.13)";
    ctx.fillRect(5, 5, 14, 1);
  }

  function drawGlass(ctx, rand, size) {
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "rgba(196, 236, 241, 0.2)";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "rgba(219, 251, 255, 0.78)";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, size - 1, size - 1);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fillRect(3, 4, 6, 1);
    ctx.fillRect(4, 3, 1, 6);
    ctx.fillRect(15, 16, 5, 1);
    ctx.fillStyle = "rgba(151, 211, 221, 0.3)";
    ctx.fillRect(1, 7, 1, 8);
  }

  function drawStoneBricks(ctx, rand, size) {
    fillPixelBase(ctx, "#7f8787", 20, rand, size);
    ctx.fillStyle = "#4b5254";
    for (let y = 0; y < size; y += 6) {
      ctx.fillRect(0, y, size, 1);
      const offset = (y / 6) % 2 === 0 ? 0 : 6;
      for (let x = offset; x < size; x += 12) {
        ctx.fillRect(x, y, 1, 6);
      }
    }
    speckle(ctx, ["#9aa39f", "#5f6868"], 18, rand, size, 1, 1);
    ctx.fillStyle = "rgba(255,255,255,0.14)";
    ctx.fillRect(1, 1, size - 2, 1);
  }

  function drawFlower(ctx, rand, size) {
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#3e7c3a";
    ctx.fillRect(11, 11, 2, 11);
    ctx.fillRect(8, 15, 3, 1);
    ctx.fillRect(13, 18, 3, 1);
    const petals = ["#e56345", "#f48b4c", "#f6b05b", "#d94f46"];
    for (let index = 0; index < 8; index += 1) {
      const angle = (index / 8) * Math.PI * 2;
      const x = 12 + Math.cos(angle) * 4;
      const y = 8 + Math.sin(angle) * 4;
      ctx.fillStyle = petals[index % petals.length];
      ctx.fillRect(Math.round(x), Math.round(y), 3, 3);
    }
    ctx.fillStyle = "#ffd768";
    ctx.fillRect(11, 7, 3, 3);
  }

  function drawTallGrass(ctx, rand, size) {
    ctx.clearRect(0, 0, size, size);
    const greens = ["#4f8d3f", "#65a44d", "#3d7135", "#7cbb5c"];
    for (let blade = 0; blade < 8; blade += 1) {
      const x = 2 + Math.floor(rand() * (size - 4));
      const h = 7 + Math.floor(rand() * 12);
      const lean = rand() < 0.5 ? -1 : 1;
      ctx.fillStyle = greens[Math.floor(rand() * greens.length)];
      ctx.fillRect(x, size - h, 1, h);
      ctx.fillRect(x + lean, size - h + 1, 1, Math.max(1, h - 5));
    }
  }

  function paintBlock(ctx, blockId, rand) {
    switch (blockId) {
      case 1: drawGrass(ctx, rand, TILE); break;
      case 2: drawDirt(ctx, rand, TILE); break;
      case 3: drawStoneBase(ctx, rand, TILE); break;
      case 4: drawWood(ctx, rand, TILE); break;
      case 5: drawLeaves(ctx, rand, TILE); break;
      case 6: drawCobble(ctx, rand, TILE); break;
      case 7: drawSand(ctx, rand, TILE); break;
      case 8: drawPlanks(ctx, rand, TILE); break;
      case 9: drawOre(ctx, rand, TILE, ["#252a2c", "#353b3e", "#171c1e"]); break;
      case 10: drawOre(ctx, rand, TILE, ["#c48b65", "#dfb18b", "#8f5e43"]); break;
      case 11: drawTorch(ctx, rand, TILE); break;
      case 12: drawTable(ctx, rand, TILE); break;
      case 13: drawFurnace(ctx, rand, TILE); break;
      case 14: drawGlass(ctx, rand, TILE); break;
      case 15: drawStoneBricks(ctx, rand, TILE); break;
      case 16: drawFlower(ctx, rand, TILE); break;
      case 17: drawTallGrass(ctx, rand, TILE); break;
      default:
        ctx.clearRect(0, 0, TILE, TILE);
        break;
    }
  }

  const blockCache = new Map();
  const iconCache = new Map();

  function getBlockCanvas(blockId, variant) {
    const key = blockId + ":" + variant;
    if (blockCache.has(key)) {
      return blockCache.get(key);
    }
    const canvas = makeCanvas(TILE);
    const ctx = canvas.getContext("2d");
    const rand = rng.sampleRng((blockId + 1) * 7919, (variant + 1) * 104729 + blockId);
    paintBlock(ctx, blockId, rand);
    blockCache.set(key, canvas);
    return canvas;
  }

  function drawBlock(ctx, blockId, x, y, size, variant) {
    if (blockId === 0) {
      return;
    }
    const image = getBlockCanvas(blockId, (variant || 0) % VARIANTS);
    ctx.drawImage(image, 0, 0, TILE, TILE, Math.round(x), Math.round(y), size, size);
  }

  function drawPickaxe(ctx, size, tier) {
    const head = tier >= 3 ? "#d8e0e3" : tier === 2 ? "#9ba3a5" : "#b9864f";
    const edge = tier >= 3 ? "#f4f7f8" : tier === 2 ? "#c4cbcc" : "#d6a566";
    ctx.strokeStyle = "#6d4327";
    ctx.lineWidth = Math.max(2, size * 0.09);
    ctx.lineCap = "square";
    ctx.beginPath();
    ctx.moveTo(size * 0.28, size * 0.82);
    ctx.lineTo(size * 0.66, size * 0.25);
    ctx.stroke();
    ctx.strokeStyle = head;
    ctx.lineWidth = Math.max(3, size * 0.12);
    ctx.beginPath();
    ctx.moveTo(size * 0.24, size * 0.26);
    ctx.quadraticCurveTo(size * 0.52, size * 0.05, size * 0.84, size * 0.25);
    ctx.stroke();
    ctx.strokeStyle = edge;
    ctx.lineWidth = Math.max(1, size * 0.035);
    ctx.beginPath();
    ctx.moveTo(size * 0.28, size * 0.22);
    ctx.quadraticCurveTo(size * 0.52, size * 0.04, size * 0.8, size * 0.21);
    ctx.stroke();
  }

  function drawIcon(ctx, itemId, size) {
    const item = window.SandboxConfig.items[itemId];
    if (!item) {
      ctx.fillStyle = "#b45b5b";
      ctx.fillRect(size * 0.2, size * 0.2, size * 0.6, size * 0.6);
      return;
    }
    if (item.blockId !== undefined) {
      const pad = size * 0.06;
      ctx.drawImage(getBlockCanvas(item.blockId, 0), 0, 0, TILE, TILE, pad, pad, size - pad * 2, size - pad * 2);
      return;
    }
    if (item.type === "tool") {
      drawPickaxe(ctx, size, item.tool.tier);
      return;
    }
    if (itemId === "stick") {
      ctx.strokeStyle = "#6d4327";
      ctx.lineWidth = Math.max(2, size * 0.1);
      ctx.beginPath();
      ctx.moveTo(size * 0.3, size * 0.8);
      ctx.lineTo(size * 0.7, size * 0.2);
      ctx.stroke();
      ctx.strokeStyle = "#a57441";
      ctx.lineWidth = Math.max(1, size * 0.04);
      ctx.beginPath();
      ctx.moveTo(size * 0.33, size * 0.77);
      ctx.lineTo(size * 0.68, size * 0.25);
      ctx.stroke();
      return;
    }
    if (itemId === "coal") {
      ctx.fillStyle = "#222729";
      ctx.beginPath();
      ctx.moveTo(size * 0.25, size * 0.55);
      ctx.lineTo(size * 0.38, size * 0.25);
      ctx.lineTo(size * 0.7, size * 0.22);
      ctx.lineTo(size * 0.8, size * 0.5);
      ctx.lineTo(size * 0.62, size * 0.78);
      ctx.lineTo(size * 0.3, size * 0.75);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#596367";
      ctx.fillRect(size * 0.34, size * 0.32, size * 0.12, size * 0.1);
      return;
    }
    if (itemId === "raw_iron") {
      ctx.fillStyle = "#8d7768";
      ctx.fillRect(size * 0.22, size * 0.42, size * 0.56, size * 0.4);
      ctx.fillStyle = "#c6926a";
      ctx.fillRect(size * 0.3, size * 0.3, size * 0.26, size * 0.2);
      ctx.fillRect(size * 0.56, size * 0.34, size * 0.16, size * 0.16);
      ctx.fillStyle = "#e0b58d";
      ctx.fillRect(size * 0.34, size * 0.34, size * 0.1, size * 0.06);
      return;
    }
    if (itemId === "iron_ingot") {
      ctx.fillStyle = "#c9d4d7";
      ctx.beginPath();
      ctx.moveTo(size * 0.22, size * 0.62);
      ctx.lineTo(size * 0.34, size * 0.36);
      ctx.lineTo(size * 0.76, size * 0.36);
      ctx.lineTo(size * 0.64, size * 0.62);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#eef5f6";
      ctx.fillRect(size * 0.34, size * 0.36, size * 0.42, size * 0.05);
      ctx.fillStyle = "#8b9b9f";
      ctx.fillRect(size * 0.27, size * 0.56, size * 0.4, size * 0.05);
      return;
    }
    ctx.fillStyle = "#c29456";
    ctx.fillRect(size * 0.28, size * 0.28, size * 0.44, size * 0.44);
  }

  function getIconCanvas(itemId, size) {
    const iconSize = size || 48;
    const key = itemId + ":" + iconSize;
    if (iconCache.has(key)) {
      return iconCache.get(key);
    }
    const canvas = makeCanvas(iconSize);
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    drawIcon(ctx, itemId, iconSize);
    iconCache.set(key, canvas);
    return canvas;
  }

  function drawItem(ctx, itemId, x, y, size) {
    const icon = getIconCanvas(itemId, 48);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(icon, Math.round(x), Math.round(y), size, size);
  }

  window.SandboxTextures = {
    TILE: TILE,
    VARIANTS: VARIANTS,
    getBlockCanvas: getBlockCanvas,
    drawBlock: drawBlock,
    getIconCanvas: getIconCanvas,
    drawItem: drawItem,
    shade: shade
  };
})();
