/* Procedural pixel-art textures and item icons. No external assets. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"));
  } else {
    root.SandboxTextures = factory(root.SandboxConfig, root.SandboxRng);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG) {
  "use strict";

  const SIZE = 16;
  const B = CONFIG.blocks;
  const cache = { blocks: null, items: null };

  function makeCanvas() {
    const canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    return canvas;
  }

  function px(ctx, x, y, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, 1, 1);
  }

  function fill(ctx, color) {
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, SIZE, SIZE);
  }

  function speckle(ctx, color, count, random) {
    ctx.fillStyle = color;
    for (let i = 0; i < count; i += 1) {
      const x = Math.floor(random() * SIZE);
      const y = Math.floor(random() * SIZE);
      const w = random() < 0.2 ? 2 : 1;
      ctx.fillRect(x, y, w, 1);
    }
  }

  function line(ctx, x0, y0, x1, y1, color) {
    ctx.fillStyle = color;
    let dx = Math.abs(x1 - x0);
    let dy = Math.abs(y1 - y0);
    let sx = x0 < x1 ? 1 : -1;
    let sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    let x = x0;
    let y = y0;
    for (let guard = 0; guard < 64; guard += 1) {
      ctx.fillRect(x, y, 1, 1);
      if (x === x1 && y === y1) {
        break;
      }
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
    }
  }

  function paintGrass(ctx, random) {
    fill(ctx, "#7a5230");
    speckle(ctx, "#6a4527", 30, random);
    speckle(ctx, "#8b6038", 18, random);
    ctx.fillStyle = "#4e9b3e";
    ctx.fillRect(0, 0, SIZE, 4);
    for (let x = 0; x < SIZE; x += 1) {
      px(ctx, x, 0, random() < 0.55 ? "#67bf52" : "#3f8334");
      if (random() < 0.4) {
        px(ctx, x, 1, "#58aa45");
      }
      if (random() < 0.25) {
        px(ctx, x, 4, "#3f8334");
      }
      if (random() < 0.14) {
        px(ctx, x, 5, "#3f8334");
      }
    }
    for (let i = 0; i < 5; i += 1) {
      const x = 1 + Math.floor(random() * 14);
      px(ctx, x, 3, "#7ad35f");
    }
  }

  function paintDirt(ctx, random) {
    fill(ctx, "#7a5230");
    speckle(ctx, "#6a4527", 38, random);
    speckle(ctx, "#8b6038", 24, random);
    speckle(ctx, "#5c3b21", 12, random);
    for (let i = 0; i < 3; i += 1) {
      const x = Math.floor(random() * 14);
      const y = Math.floor(random() * 14);
      ctx.fillStyle = "#5c3b21";
      ctx.fillRect(x, y, 2, 1);
    }
  }

  function paintStone(ctx, random) {
    fill(ctx, "#6f7378");
    speckle(ctx, "#5d6166", 34, random);
    speckle(ctx, "#82878d", 26, random);
    speckle(ctx, "#4c5055", 10, random);
    for (let i = 0; i < 3; i += 1) {
      const x = Math.floor(random() * 12) + 1;
      const y = Math.floor(random() * 12) + 1;
      line(ctx, x, y, x + 2 + Math.floor(random() * 3), y + 1, "#565a5f");
    }
  }

  function paintWood(ctx, random) {
    fill(ctx, "#6d4a2a");
    for (let x = 0; x < SIZE; x += 4) {
      ctx.fillStyle = "#54371e";
      ctx.fillRect(x, 0, 1, SIZE);
    }
    for (let x = 2; x < SIZE; x += 4) {
      ctx.fillStyle = "#895f37";
      ctx.fillRect(x, 0, 1, SIZE);
    }
    speckle(ctx, "#7d552f", 22, random);
    for (let i = 0; i < 4; i += 1) {
      ctx.fillStyle = "#4a2f19";
      ctx.fillRect(1 + Math.floor(random() * 14), Math.floor(random() * 16), 1, 3);
    }
  }

  function paintLeaves(ctx, random) {
    fill(ctx, "#2e6b31");
    for (let i = 0; i < 48; i += 1) {
      const x = Math.floor(random() * SIZE);
      const y = Math.floor(random() * SIZE);
      ctx.fillStyle = random() < 0.5 ? "#3d8a3d" : "#245827";
      ctx.fillRect(x, y, random() < 0.3 ? 2 : 1, 1);
    }
    for (let i = 0; i < 12; i += 1) {
      const x = Math.floor(random() * SIZE);
      const y = Math.floor(random() * SIZE);
      ctx.clearRect(x, y, 1, 1);
    }
  }

  function paintSand(ctx, random) {
    fill(ctx, "#d8c27b");
    speckle(ctx, "#c4ad67", 34, random);
    speckle(ctx, "#e7d492", 22, random);
    speckle(ctx, "#b39a55", 8, random);
  }

  function paintWater(ctx, random) {
    fill(ctx, "#2b6ca6");
    for (let y = 0; y < SIZE; y += 4) {
      for (let x = 0; x < SIZE; x += 1) {
        if ((x + y + Math.floor(random() * 3)) % 7 < 3) {
          px(ctx, x, y + 1, "#3f83bd");
        }
      }
    }
    speckle(ctx, "#58a0d4", 12, random);
    ctx.globalAlpha = 1;
  }

  function paintCoal(ctx, random) {
    paintStone(ctx, random);
    for (let i = 0; i < 5; i += 1) {
      const x = 1 + Math.floor(random() * 12);
      const y = 2 + Math.floor(random() * 12);
      ctx.fillStyle = "#1c1c1e";
      ctx.fillRect(x, y, 2 + Math.floor(random() * 2), 2);
      px(ctx, x + 1, y, "#3a3a3e");
    }
  }

  function paintIron(ctx, random) {
    paintStone(ctx, random);
    for (let i = 0; i < 5; i += 1) {
      const x = 1 + Math.floor(random() * 12);
      const y = 2 + Math.floor(random() * 12);
      ctx.fillStyle = "#b98255";
      ctx.fillRect(x, y, 2, 2);
      px(ctx, x, y, "#e2b183");
    }
  }

  function paintPlanks(ctx, random) {
    fill(ctx, "#b07a43");
    for (let y = 0; y < SIZE; y += 4) {
      ctx.fillStyle = "#8a5a2f";
      ctx.fillRect(0, y, SIZE, 1);
      ctx.fillStyle = "#c58f55";
      ctx.fillRect(0, y + 1, SIZE, 1);
    }
    for (let i = 0; i < 5; i += 1) {
      ctx.fillStyle = "#7a4b27";
      const x = Math.floor(random() * 16);
      ctx.fillRect(x, Math.floor(random() * 4) * 4 + 2, 1, 1);
      ctx.fillRect((x + 7) % 16, Math.floor(random() * 4) * 4 + 2, 1, 1);
    }
  }

  function paintTable(ctx, random) {
    paintPlanks(ctx, random);
    ctx.fillStyle = "#5d3a1e";
    ctx.fillRect(0, 0, SIZE, 2);
    ctx.fillRect(0, 0, 2, SIZE);
    ctx.fillRect(0, SIZE - 2, SIZE, 2);
    ctx.fillStyle = "#d1a35e";
    ctx.fillRect(3, 3, 4, 4);
    ctx.fillRect(9, 9, 4, 4);
    ctx.fillStyle = "#6b4527";
    ctx.fillRect(4, 4, 2, 2);
    ctx.fillRect(10, 10, 2, 2);
    ctx.fillStyle = "#3a3a3e";
    ctx.fillRect(9, 3, 1, 5);
    ctx.fillRect(8, 3, 3, 1);
  }

  function paintFurnace(ctx, random) {
    paintStone(ctx, random);
    ctx.fillStyle = "#4b4d51";
    ctx.fillRect(3, 4, 10, 9);
    ctx.fillStyle = "#232326";
    ctx.fillRect(4, 6, 8, 6);
    ctx.fillStyle = "#f2a33b";
    ctx.fillRect(5, 9, 2, 2);
    ctx.fillRect(9, 9, 2, 2);
    ctx.fillStyle = "#f7d05a";
    ctx.fillRect(6, 10, 1, 1);
    ctx.fillRect(10, 10, 1, 1);
    ctx.fillStyle = "#8d9298";
    ctx.fillRect(3, 3, 10, 1);
  }

  function paintTorch(ctx) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "#6b4626";
    ctx.fillRect(7, 7, 2, 8);
    ctx.fillStyle = "#8f6236";
    ctx.fillRect(7, 7, 1, 8);
    ctx.fillStyle = "#f08a24";
    ctx.fillRect(6, 3, 4, 4);
    ctx.fillStyle = "#ffd166";
    ctx.fillRect(7, 2, 2, 3);
    ctx.fillStyle = "#fff3b0";
    ctx.fillRect(7, 3, 1, 1);
    ctx.fillStyle = "rgba(255, 190, 80, 0.35)";
    ctx.fillRect(5, 2, 6, 6);
  }

  function paintGlass(ctx) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "rgba(196, 226, 240, 0.28)";
    ctx.fillRect(1, 1, 14, 14);
    ctx.fillStyle = "rgba(210, 236, 248, 0.75)";
    ctx.fillRect(0, 0, SIZE, 1);
    ctx.fillRect(0, 0, 1, SIZE);
    ctx.fillRect(15, 0, 1, SIZE);
    ctx.fillRect(0, 15, SIZE, 1);
    ctx.fillStyle = "rgba(255, 255, 255, 0.55)";
    line(ctx, 3, 12, 12, 3, "rgba(255, 255, 255, 0.45)");
    line(ctx, 4, 13, 13, 4, "rgba(255, 255, 255, 0.25)");
  }

  function paintLadder(ctx) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "#8a5a2f";
    ctx.fillRect(3, 0, 2, SIZE);
    ctx.fillRect(11, 0, 2, SIZE);
    for (let y = 3; y < SIZE; y += 5) {
      ctx.fillStyle = "#b07a43";
      ctx.fillRect(3, y, 10, 2);
    }
  }

  function paintStoneBrick(ctx, random) {
    fill(ctx, "#777b80");
    ctx.fillStyle = "#5b5f64";
    ctx.fillRect(0, 7, SIZE, 1);
    ctx.fillRect(0, 15, SIZE, 1);
    for (let y = 0; y < 16; y += 8) {
      const offset = y === 0 ? 0 : 4;
      for (let x = offset; x < 16; x += 8) {
        ctx.fillRect(x, y, 1, 7);
      }
    }
    speckle(ctx, "#878c92", 14, random);
  }

  function paintFlower(ctx) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "#3d8a3d";
    ctx.fillRect(7, 8, 2, 7);
    ctx.fillRect(4, 11, 4, 1);
    ctx.fillStyle = "#d94343";
    ctx.fillRect(5, 3, 6, 5);
    ctx.fillStyle = "#ff6b6b";
    ctx.fillRect(6, 4, 2, 2);
    ctx.fillRect(8, 4, 2, 2);
    ctx.fillStyle = "#f7d05a";
    ctx.fillRect(7, 5, 2, 2);
  }

  function paintTallGrass(ctx) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "#3d8a3d";
    ctx.fillRect(3, 8, 1, 7);
    ctx.fillRect(6, 5, 1, 10);
    ctx.fillRect(9, 7, 1, 8);
    ctx.fillRect(12, 9, 1, 6);
    ctx.fillStyle = "#58aa45";
    ctx.fillRect(6, 4, 1, 2);
    ctx.fillRect(9, 6, 1, 2);
    ctx.fillRect(3, 7, 1, 2);
  }

  function paintBlock(id, variant) {
    const canvas = makeCanvas();
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    const random = RNG.mulberry32((id * 2654435761 + variant * 40503) >>> 0);
    switch (id) {
      case B.grass: paintGrass(ctx, random); break;
      case B.dirt: paintDirt(ctx, random); break;
      case B.stone: paintStone(ctx, random); break;
      case B.wood: paintWood(ctx, random); break;
      case B.leaves: paintLeaves(ctx, random); break;
      case B.sand: paintSand(ctx, random); break;
      case B.water: paintWater(ctx, random); break;
      case B.coalOre: paintCoal(ctx, random); break;
      case B.ironOre: paintIron(ctx, random); break;
      case B.planks: paintPlanks(ctx, random); break;
      case B.table: paintTable(ctx, random); break;
      case B.furnace: paintFurnace(ctx, random); break;
      case B.torch: paintTorch(ctx); break;
      case B.glass: paintGlass(ctx); break;
      case B.ladder: paintLadder(ctx); break;
      case B.stoneBrick: paintStoneBrick(ctx, random); break;
      case B.flower: paintFlower(ctx); break;
      case B.tallGrass: paintTallGrass(ctx); break;
      default: fill(ctx, "#9e9e9e"); break;
    }
    return canvas;
  }

  function createBlockTextures() {
    const map = {};
    Object.keys(CONFIG.blockDefs).forEach(function (key) {
      const id = Number(key);
      if (id === B.air) {
        return;
      }
      map[id] = [paintBlock(id, 0), paintBlock(id, 1), paintBlock(id, 2)];
    });
    cache.blocks = map;
    return map;
  }

  function iconBase() {
    return makeCanvas();
  }

  function paintTool(ctx, kind, materialColor, darkColor) {
    ctx.clearRect(0, 0, SIZE, SIZE);
    // Handle from bottom-left to top-right.
    line(ctx, 4, 13, 11, 6, "#6b4626");
    line(ctx, 5, 13, 12, 6, "#8f6236");
    if (kind === "pickaxe") {
      ctx.fillStyle = materialColor;
      ctx.fillRect(5, 3, 7, 2);
      ctx.fillRect(4, 4, 2, 2);
      ctx.fillRect(11, 4, 2, 2);
      ctx.fillStyle = darkColor;
      ctx.fillRect(6, 5, 1, 2);
      ctx.fillRect(10, 5, 1, 2);
    } else if (kind === "axe") {
      ctx.fillStyle = materialColor;
      ctx.fillRect(8, 2, 5, 6);
      ctx.fillStyle = darkColor;
      ctx.fillRect(11, 3, 2, 4);
      ctx.fillStyle = materialColor;
      ctx.fillRect(9, 8, 2, 2);
    } else if (kind === "sword") {
      ctx.fillStyle = materialColor;
      line(ctx, 8, 2, 13, 7, materialColor);
      line(ctx, 9, 2, 14, 7, darkColor);
      ctx.fillStyle = darkColor;
      ctx.fillRect(5, 8, 6, 2);
      ctx.fillStyle = "#6b4626";
      ctx.fillRect(4, 10, 2, 4);
    }
  }

  function paintItem(id) {
    const canvas = iconBase();
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    const def = CONFIG.itemDefs[id];
    if (!def) {
      fill(ctx, "#ff00ff");
      return canvas;
    }
    if (def.kind === "block") {
      const blockId = def.place;
      const variants = cache.blocks && cache.blocks[blockId];
      if (variants && variants[0]) {
        ctx.drawImage(variants[0], 0, 0);
        return canvas;
      }
    }
    if (def.kind === "tool") {
      const colors = {
        1: ["#b07a43", "#7a4b27"],
        2: ["#9aa0a6", "#6f7378"],
        3: ["#d8dde3", "#9aa0a6"]
      };
      const pair = colors[def.tier] || colors[1];
      paintTool(ctx, def.tool, pair[0], pair[1]);
      return canvas;
    }
    if (id === CONFIG.itemIds.stick) {
      line(ctx, 4, 12, 11, 4, "#8a5a2f");
      line(ctx, 5, 12, 12, 4, "#b07a43");
      return canvas;
    }
    if (id === CONFIG.itemIds.coal) {
      ctx.fillStyle = "#1c1c1e";
      ctx.fillRect(4, 6, 8, 6);
      ctx.fillRect(5, 5, 6, 8);
      ctx.fillStyle = "#3a3a3e";
      ctx.fillRect(6, 7, 3, 2);
      ctx.fillRect(10, 10, 2, 1);
      return canvas;
    }
    if (id === CONFIG.itemIds.rawIron) {
      ctx.fillStyle = "#b98255";
      ctx.fillRect(3, 6, 10, 7);
      ctx.fillRect(7, 4, 5, 3);
      ctx.fillStyle = "#e2b183";
      ctx.fillRect(5, 7, 3, 2);
      ctx.fillRect(9, 9, 2, 2);
      return canvas;
    }
    if (id === CONFIG.itemIds.ironIngot) {
      ctx.fillStyle = "#c9ced4";
      ctx.fillRect(4, 7, 8, 5);
      ctx.fillRect(5, 5, 6, 2);
      ctx.fillStyle = "#eef2f5";
      ctx.fillRect(5, 6, 4, 1);
      ctx.fillStyle = "#8f969d";
      ctx.fillRect(6, 11, 5, 1);
      return canvas;
    }
    if (id === CONFIG.itemIds.apple) {
      ctx.fillStyle = "#d94343";
      ctx.fillRect(4, 5, 8, 8);
      ctx.fillRect(5, 4, 6, 10);
      ctx.fillStyle = "#ff6b6b";
      ctx.fillRect(6, 6, 2, 2);
      ctx.fillStyle = "#3d8a3d";
      ctx.fillRect(8, 2, 2, 3);
      return canvas;
    }
    if (id === CONFIG.itemIds.rawPork || id === CONFIG.itemIds.cookedPork) {
      const meat = id === CONFIG.itemIds.cookedPork ? "#a85a35" : "#e88a8a";
      const edge = id === CONFIG.itemIds.cookedPork ? "#7a3d22" : "#c96b6b";
      ctx.fillStyle = edge;
      ctx.fillRect(3, 6, 10, 7);
      ctx.fillStyle = meat;
      ctx.fillRect(4, 7, 8, 5);
      ctx.fillStyle = edge;
      ctx.fillRect(6, 9, 3, 2);
      return canvas;
    }
    if (id === CONFIG.itemIds.slimeball) {
      ctx.fillStyle = "#66c46b";
      ctx.fillRect(4, 5, 8, 8);
      ctx.fillRect(5, 4, 6, 10);
      ctx.fillStyle = "#a2e6a5";
      ctx.fillRect(6, 6, 3, 3);
      return canvas;
    }
    if (id === CONFIG.itemIds.rottenFlesh) {
      ctx.fillStyle = "#7d6b4e";
      ctx.fillRect(4, 6, 8, 7);
      ctx.fillStyle = "#5d4e36";
      ctx.fillRect(6, 8, 4, 3);
      ctx.fillStyle = "#9a8768";
      ctx.fillRect(5, 7, 2, 1);
      return canvas;
    }
    fill(ctx, "#9e9e9e");
    return canvas;
  }

  function createItemIcons() {
    const map = {};
    Object.keys(CONFIG.itemDefs).forEach(function (key) {
      const id = Number(key);
      map[id] = paintItem(id);
    });
    cache.items = map;
    return map;
  }

  function ensure() {
    if (!cache.blocks) {
      createBlockTextures();
    }
    if (!cache.items) {
      createItemIcons();
    }
    return cache;
  }

  function blockVariants(id) {
    ensure();
    return cache.blocks[id] || null;
  }

  function itemIcon(id) {
    ensure();
    return cache.items[id] || null;
  }

  return {
    size: SIZE,
    create: ensure,
    createBlockTextures: createBlockTextures,
    createItemIcons: createItemIcons,
    blockVariants: blockVariants,
    itemIcon: itemIcon,
    paintBlock: paintBlock,
    paintItem: paintItem
  };
});
