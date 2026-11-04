/* ============================================================
   BLOCKHAVEN — data, procedural textures, recipes and sound
   No dependencies. All art is drawn at runtime.
   ============================================================ */
(function () {
  "use strict";

  const BH = (window.BH = window.BH || {});

  // ---------- world constants ----------
  BH.W = 512;
  BH.H = 192;
  BH.DAY_LENGTH = 600;          // seconds for a full day + night
  BH.TILE = 16;                 // source texture resolution
  BH.REACH = 5.6;
  BH.SAVE_KEY = "blockhaven.save.v1";
  BH.SETTINGS_KEY = "blockhaven.settings.v1";
  BH.SAVE_VERSION = 1;

  // ---------- tile ids ----------
  const T = BH.T = {
    AIR: 0,
    GRASS: 1,
    DIRT: 2,
    STONE: 3,
    COBBLE: 4,
    SAND: 5,
    SANDSTONE: 6,
    LOG: 7,
    LEAVES: 8,
    PLANKS: 9,
    COAL_ORE: 10,
    IRON_ORE: 11,
    GOLD_ORE: 12,
    DIAMOND_ORE: 13,
    BEDROCK: 14,
    TORCH: 15,
    TABLE: 16,
    FURNACE: 17,
    GLASS: 18,
    ROSE: 19,
    DANDELION: 20,
    TALL_GRASS: 21,
    MUSHROOM: 22,
    GRAVEL: 23,
    BRICKS: 24,
    LAMP: 25,
    CACTUS: 26
  };

  // ---------- item ids ----------
  const I = BH.I = {
    STICK: 100,
    COAL: 101,
    IRON_INGOT: 102,
    GOLD_INGOT: 103,
    DIAMOND: 104,
    APPLE: 105,
    RAW_PORK: 106,
    COOKED_PORK: 107,
    CHARCOAL: 108,
    GOLDEN_APPLE: 109,
    WOOD_PICK: 110,
    STONE_PICK: 111,
    IRON_PICK: 112,
    DIAMOND_PICK: 113,
    WOOD_AXE: 114,
    STONE_AXE: 115,
    IRON_AXE: 116,
    WOOD_SWORD: 117,
    STONE_SWORD: 118,
    IRON_SWORD: 119,
    DIAMOND_SWORD: 120,
    DIAMOND_AXE: 121
  };

  // ---------- block definitions ----------
  // hard: seconds to break with the correct kind of tool
  // tool: preferred tool class, tier: minimum pickaxe tier for a drop
  BH.TILE_DEFS = [];
  function block(id, name, o) {
    BH.TILE_DEFS[id] = Object.assign({
      id, name, solid: true, hard: 1, tool: "pick", tier: 0, light: 0,
      opacity: 15, placeable: true, drop: id, dropCount: 1, flatIcon: false
    }, o || {});
  }

  block(T.AIR, "Air", { solid: false, hard: 0, opacity: 0, placeable: false, drop: -1 });
  block(T.GRASS, "Grass Block", { hard: 0.45, tool: "shovel", drop: T.DIRT });
  block(T.DIRT, "Dirt", { hard: 0.45, tool: "shovel" });
  block(T.STONE, "Stone", { hard: 1.35, tool: "pick", tier: 1, drop: T.COBBLE });
  block(T.COBBLE, "Cobblestone", { hard: 1.45, tool: "pick", tier: 1 });
  block(T.SAND, "Sand", { hard: 0.38, tool: "shovel" });
  block(T.SANDSTONE, "Sandstone", { hard: 1.05, tool: "pick", tier: 1 });
  block(T.LOG, "Oak Log", { hard: 1.1, tool: "axe" });
  block(T.LEAVES, "Oak Leaves", { hard: 0.22, opacity: 3, drop: T.LEAVES });
  block(T.PLANKS, "Oak Planks", { hard: 0.95, tool: "axe" });
  block(T.COAL_ORE, "Coal Ore", { hard: 1.8, tool: "pick", tier: 1, drop: I.COAL, dropCount: 1 });
  block(T.IRON_ORE, "Iron Ore", { hard: 2.15, tool: "pick", tier: 2, placeable: false });
  block(T.GOLD_ORE, "Gold Ore", { hard: 2.5, tool: "pick", tier: 3, placeable: false });
  block(T.DIAMOND_ORE, "Diamond Ore", { hard: 2.9, tool: "pick", tier: 3, drop: I.DIAMOND, placeable: false });
  block(T.BEDROCK, "Bedrock", { hard: Infinity, tool: "pick", tier: 99, placeable: false, drop: -1 });
  block(T.TORCH, "Torch", { solid: false, hard: 0.03, opacity: 0, light: 14, flatIcon: true });
  block(T.TABLE, "Crafting Table", { hard: 1.15, tool: "axe" });
  block(T.FURNACE, "Furnace", { hard: 1.9, tool: "pick", tier: 1, light: 2 });
  block(T.GLASS, "Glass", { hard: 0.3, opacity: 0, drop: T.GLASS, flatIcon: true });
  block(T.ROSE, "Rose", { solid: false, hard: 0.02, opacity: 0, flatIcon: true });
  block(T.DANDELION, "Dandelion", { solid: false, hard: 0.02, opacity: 0, flatIcon: true });
  block(T.TALL_GRASS, "Tall Grass", { solid: false, hard: 0.02, opacity: 0, flatIcon: true });
  block(T.MUSHROOM, "Mushroom", { solid: false, hard: 0.02, opacity: 0, flatIcon: true });
  block(T.GRAVEL, "Gravel", { hard: 0.55, tool: "shovel" });
  block(T.BRICKS, "Stone Bricks", { hard: 1.55, tool: "pick", tier: 1 });
  block(T.LAMP, "Glow Lamp", { hard: 0.35, opacity: 0, light: 15, flatIcon: true });
  block(T.CACTUS, "Cactus", { hard: 0.4, tool: "any", drop: T.CACTUS });

  // ---------- item definitions ----------
  BH.ITEM_DEFS = {};
  function item(id, name, o) {
    BH.ITEM_DEFS[id] = Object.assign({
      id, name, stack: 64, iconTile: null, tags: [], desc: ""
    }, o || {});
  }

  // Placeable blocks reuse their tile icon and name.
  for (let id = 1; id < BH.TILE_DEFS.length; id++) {
    const d = BH.TILE_DEFS[id];
    if (!d || !d.placeable) continue;
    item(id, d.name, { iconTile: id, stack: 64, block: id, flatIcon: d.flatIcon });
  }

  item(I.STICK, "Stick", { desc: "The beginning of every good tool." });
  item(I.COAL, "Coal", { desc: "Fuel. Also lights torches.", tags: ["coal", "fuel"] });
  item(I.CHARCOAL, "Charcoal", { desc: "A slow-burned log. Burns well.", tags: ["coal", "fuel"] });
  item(I.IRON_INGOT, "Iron Ingot", { desc: "Strong, dependable metal." });
  item(I.GOLD_INGOT, "Gold Ingot", { desc: "Soft and shiny. Maybe don't make a pickaxe." });
  item(I.DIAMOND, "Diamond", { desc: "Rare, blue, and very hard." });
  item(I.APPLE, "Apple", { stack: 16, food: 4, heal: 0, desc: "A crisp snack. Restores 2 hunger." });
  item(I.RAW_PORK, "Raw Porkchop", { stack: 16, food: 3, desc: "Better cooked in a furnace." });
  item(I.COOKED_PORK, "Cooked Porkchop", { stack: 16, food: 8, heal: 1, desc: "A proper meal. Restores 4 hunger." });
  item(I.GOLDEN_APPLE, "Golden Apple", { stack: 4, food: 10, heal: 8, desc: "A feast of legends. Restores health." });
  item(T.IRON_ORE, "Iron Ore", { iconTile: T.IRON_ORE, desc: "Smelt it in a furnace for iron." });
  item(T.GOLD_ORE, "Gold Ore", { iconTile: T.GOLD_ORE, desc: "Smelt it in a furnace for gold." });

  const toolData = {
    [I.WOOD_PICK]:    ["Wooden Pickaxe", "pick", 1, 1.7, 60],
    [I.STONE_PICK]:   ["Stone Pickaxe", "pick", 2, 2.9, 132],
    [I.IRON_PICK]:    ["Iron Pickaxe", "pick", 3, 4.6, 260],
    [I.DIAMOND_PICK]: ["Diamond Pickaxe", "pick", 4, 6.5, 520],
    [I.WOOD_AXE]:     ["Wooden Axe", "axe", 1, 1.8, 60],
    [I.STONE_AXE]:    ["Stone Axe", "axe", 2, 3.0, 132],
    [I.IRON_AXE]:     ["Iron Axe", "axe", 3, 4.6, 260],
    [I.DIAMOND_AXE]:  ["Diamond Axe", "axe", 4, 6.5, 520],
    [I.WOOD_SWORD]:   ["Wooden Sword", "sword", 1, 0, 60, 3],
    [I.STONE_SWORD]:  ["Stone Sword", "sword", 2, 0, 132, 4],
    [I.IRON_SWORD]:   ["Iron Sword", "sword", 3, 0, 260, 5],
    [I.DIAMOND_SWORD]:["Diamond Sword", "sword", 4, 0, 520, 7]
  };
  for (const id in toolData) {
    const d = toolData[id];
    item(Number(id), d[0], {
      stack: 1, tool: d[1], tier: d[2], speed: d[3], durability: d[4], damage: d[5] || 2,
      desc: d[1] === "sword" ? "A trusty blade." : "Speeds up " + (d[1] === "pick" ? "stone and ore." : "wood.")
    });
  }

  BH.getItem = function (id) {
    return BH.ITEM_DEFS[id] || null;
  };
  BH.maxStack = function (id) {
    const def = BH.ITEM_DEFS[id];
    return def ? def.stack : 64;
  };
  BH.itemName = function (id) {
    return BH.ITEM_DEFS[id] ? BH.ITEM_DEFS[id].name : "Unknown";
  };
  BH.isBlockItem = function (id) {
    const def = BH.ITEM_DEFS[id];
    return !!(def && def.block);
  };

  // ---------- crafting ----------
  BH.RECIPES = [
    { id: "planks", out: { id: T.PLANKS, n: 4 }, need: [{ id: T.LOG, n: 1 }], table: false },
    { id: "sticks", out: { id: I.STICK, n: 4 }, need: [{ id: T.PLANKS, n: 2 }], table: false },
    { id: "table", out: { id: T.TABLE, n: 1 }, need: [{ id: T.PLANKS, n: 4 }], table: false },
    { id: "torch", out: { id: T.TORCH, n: 4 }, need: [{ any: [I.COAL, I.CHARCOAL], n: 1 }, { id: I.STICK, n: 1 }], table: false },
    { id: "wood_pick", out: { id: I.WOOD_PICK, n: 1 }, need: [{ id: T.PLANKS, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "wood_sword", out: { id: I.WOOD_SWORD, n: 1 }, need: [{ id: T.PLANKS, n: 2 }, { id: I.STICK, n: 1 }], table: true },
    { id: "wood_axe", out: { id: I.WOOD_AXE, n: 1 }, need: [{ id: T.PLANKS, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "furnace", out: { id: T.FURNACE, n: 1 }, need: [{ id: T.COBBLE, n: 8 }], table: true },
    { id: "stone_pick", out: { id: I.STONE_PICK, n: 1 }, need: [{ id: T.COBBLE, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "stone_sword", out: { id: I.STONE_SWORD, n: 1 }, need: [{ id: T.COBBLE, n: 2 }, { id: I.STICK, n: 1 }], table: true },
    { id: "stone_axe", out: { id: I.STONE_AXE, n: 1 }, need: [{ id: T.COBBLE, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "bricks", out: { id: T.BRICKS, n: 4 }, need: [{ id: T.COBBLE, n: 4 }], table: true },
    { id: "lamp", out: { id: T.LAMP, n: 1 }, need: [{ id: T.GLASS, n: 4 }, { id: T.TORCH, n: 1 }], table: true },
    { id: "iron_pick", out: { id: I.IRON_PICK, n: 1 }, need: [{ id: I.IRON_INGOT, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "iron_sword", out: { id: I.IRON_SWORD, n: 1 }, need: [{ id: I.IRON_INGOT, n: 2 }, { id: I.STICK, n: 1 }], table: true },
    { id: "iron_axe", out: { id: I.IRON_AXE, n: 1 }, need: [{ id: I.IRON_INGOT, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "diamond_pick", out: { id: I.DIAMOND_PICK, n: 1 }, need: [{ id: I.DIAMOND, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "diamond_sword", out: { id: I.DIAMOND_SWORD, n: 1 }, need: [{ id: I.DIAMOND, n: 2 }, { id: I.STICK, n: 1 }], table: true },
    { id: "diamond_axe", out: { id: I.DIAMOND_AXE, n: 1 }, need: [{ id: I.DIAMOND, n: 3 }, { id: I.STICK, n: 2 }], table: true },
    { id: "golden_apple", out: { id: I.GOLDEN_APPLE, n: 1 }, need: [{ id: I.GOLD_INGOT, n: 3 }, { id: I.APPLE, n: 1 }], table: true }
  ];

  BH.SMELTS = [
    { id: "iron", in: { id: T.IRON_ORE, n: 1 }, out: { id: I.IRON_INGOT, n: 1 } },
    { id: "gold", in: { id: T.GOLD_ORE, n: 1 }, out: { id: I.GOLD_INGOT, n: 1 } },
    { id: "glass", in: { id: T.SAND, n: 1 }, out: { id: T.GLASS, n: 1 } },
    { id: "pork", in: { id: I.RAW_PORK, n: 1 }, out: { id: I.COOKED_PORK, n: 1 } },
    { id: "stone", in: { id: T.COBBLE, n: 1 }, out: { id: T.STONE, n: 1 } },
    { id: "charcoal", in: { id: T.LOG, n: 1 }, out: { id: I.CHARCOAL, n: 1 } }
  ];

  // ---------- utility ----------
  BH.clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  BH.lerp = (a, b, t) => a + (b - a) * t;
  BH.smooth = t => t * t * (3 - 2 * t);
  BH.smoothstep = (a, b, x) => {
    const t = BH.clamp((x - a) / (b - a), 0, 1);
    return t * t * (3 - 2 * t);
  };
  BH.mod = (n, m) => ((n % m) + m) % m;

  BH.hashString = function (str) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  };

  BH.mulberry32 = function (seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0;
      a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  };

  function hash2i(x, y, seed) {
    let h = (seed ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263)) | 0;
    h = Math.imul(h ^ h >>> 13, 1274126177);
    return (h ^ h >>> 16) >>> 0;
  }
  BH.hash2i = hash2i;
  BH.rand2 = (x, y, seed) => hash2i(x, y, seed) / 4294967296;

  BH.noise2 = function (x, y, seed) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = BH.smooth(xf), v = BH.smooth(yf);
    const a = hash2i(xi, yi, seed) / 4294967296;
    const b = hash2i(xi + 1, yi, seed) / 4294967296;
    const c = hash2i(xi, yi + 1, seed) / 4294967296;
    const d = hash2i(xi + 1, yi + 1, seed) / 4294967296;
    return BH.lerp(BH.lerp(a, b, u), BH.lerp(c, d, u), v);
  };

  BH.fbm2 = function (x, y, seed, oct, gain) {
    oct = oct || 3;
    gain = gain === undefined ? 0.5 : gain;
    let amp = 1, freq = 1, sum = 0, norm = 0;
    for (let i = 0; i < oct; i++) {
      sum += BH.noise2(x * freq, y * freq, seed + i * 1013) * amp;
      norm += amp;
      amp *= gain;
      freq *= 2.03;
    }
    return sum / norm;
  };

  BH.noise1 = function (x, seed) {
    const xi = Math.floor(x), xf = x - xi;
    const u = BH.smooth(xf);
    const a = hash2i(xi, 1337, seed) / 4294967296;
    const b = hash2i(xi + 1, 1337, seed) / 4294967296;
    return BH.lerp(a, b, u);
  };

  BH.mixColor = function (c1, c2, t) {
    return [
      Math.round(BH.lerp(c1[0], c2[0], t)),
      Math.round(BH.lerp(c1[1], c2[1], t)),
      Math.round(BH.lerp(c1[2], c2[2], t))
    ];
  };
  BH.rgb = (c, a) => a === undefined
    ? `rgb(${c[0]},${c[1]},${c[2]})`
    : `rgba(${c[0]},${c[1]},${c[2]},${a})`;

  // ---------- procedural tile textures ----------
  const texSeed = 8675309;
  BH.TILE_TEX = [];
  BH.TILE_VARIANTS = 4;

  function canvas2d(w, h) {
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const x = c.getContext("2d");
    x.imageSmoothingEnabled = false;
    return { c, g: x };
  }
  BH.canvas2d = canvas2d;

  function px(g, x, y, w, h, color) {
    g.fillStyle = color;
    g.fillRect(x | 0, y | 0, w | 0, h | 0);
  }

  function buildTileTex(id, variant) {
    const { c, g } = canvas2d(16, 16);
    const rnd = BH.mulberry32(texSeed + id * 7717 + variant * 9127);
    const R = () => rnd();
    const pick = arr => arr[(R() * arr.length) | 0];

    if (id === T.AIR) return c;

    if (id === T.GRASS) {
      drawDirt(g, R);
      const top = 3 + ((R() * 2) | 0);
      px(g, 0, 0, 16, top, pick(["#609f40", "#65a644", "#5b9a3c"]));
      for (let x = 0; x < 16; x++) {
        const d = 1 + ((R() * 3) | 0);
        px(g, x, top - 1, 1, d, pick(["#4e8734", "#568f38", "#477d30"]));
        if (R() < 0.5) px(g, x, top + d, 1, 1, pick(["#467a2e", "#3f6f2a"]));
      }
      for (let i = 0; i < 8; i++) px(g, (R() * 16) | 0, 1 + ((R() * 3) | 0), 1, 1, pick(["#7fbc57", "#76b44f", "#8dc462"]));
      for (let i = 0; i < 10; i++) px(g, (R() * 16) | 0, top + 1 + ((R() * 12) | 0), 1, 1, pick(["#65472f", "#8b6541", "#5c402a"]));
      return c;
    }

    if (id === T.DIRT) {
      drawDirt(g, R);
      return c;
    }

    if (id === T.STONE || id === T.COBBLE || id === T.BEDROCK) {
      drawStone(g, R);
      if (id === T.COBBLE) drawCobble(g, R);
      if (id === T.BEDROCK) {
        for (let i = 0; i < 22; i++) {
          px(g, (R() * 16) | 0, (R() * 16) | 0, 1 + ((R() * 3) | 0), 1 + ((R() * 2) | 0), pick(["#141a1d", "#262b2c", "#313638", "#0e1113"]));
        }
      }
      return c;
    }

    if (id === T.SAND) {
      px(g, 0, 0, 16, 16, "#d7c083");
      for (let i = 0; i < 80; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, pick(["#e4cf96", "#ccb479", "#c6ab6e", "#ead69e"]));
      for (let i = 0; i < 5; i++) px(g, (R() * 15) | 0, (R() * 16) | 0, 1, 1, "#a88d5a");
      return c;
    }

    if (id === T.SANDSTONE) {
      px(g, 0, 0, 16, 16, "#cbb47c");
      px(g, 0, 4, 16, 1, "#b9a069");
      px(g, 0, 10, 16, 1, "#d9c68f");
      for (let i = 0; i < 35; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, pick(["#d5c28a", "#bda46d", "#c6ad75"]));
      for (let i = 0; i < 3; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 2, 1, "#a88f5b");
      return c;
    }

    if (id === T.LOG) {
      px(g, 0, 0, 16, 16, "#6f4e2e");
      for (let x = 0; x < 16; x += 3) px(g, x + ((R() * 2) | 0), 0, 1 + ((R() * 2) | 0), 16, pick(["#583a22", "#604126", "#7d5934"]));
      for (let i = 0; i < 20; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1 + ((R() * 3) | 0), pick(["#8b653c", "#4b311d", "#76532f"]));
      px(g, 0, 0, 1, 16, "#4b311d");
      px(g, 15, 0, 1, 16, "#4b311d");
      return c;
    }

    if (id === T.LEAVES) {
      g.clearRect(0, 0, 16, 16);
      for (let i = 0; i < 34; i++) {
        const x = (R() * 14) | 0, y = (R() * 14) | 0;
        const s = 2 + ((R() * 3) | 0);
        px(g, x, y, s, s, pick(["#3b712e", "#467d34", "#54903c", "#326127", "#609e45"]));
      }
      for (let i = 0; i < 12; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, pick(["#76ad50", "#2b5523", "#86bb5b"]));
      for (let i = 0; i < 7; i++) g.clearRect((R() * 16) | 0, (R() * 16) | 0, 1 + ((R() * 2) | 0), 1);
      px(g, 0, 0, 16, 1, "rgba(37,78,29,.45)");
      return c;
    }

    if (id === T.PLANKS) {
      px(g, 0, 0, 16, 16, "#a47743");
      const rows = [0, 4, 8, 12];
      for (const y of rows) {
        px(g, 0, y, 16, 1, "#6e4b29");
        px(g, 0, y + 1, 16, 1, "#bc8e55");
      }
      for (let i = 0; i < 30; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1 + ((R() * 4) | 0), 1, pick(["#936834", "#b2854d", "#8b6031"]));
      const seams = [[5, 0], [11, 4], [4, 8], [12, 12]];
      for (const s of seams) px(g, s[0], s[1] + 1, 1, 3, "#73502c");
      return c;
    }

    if (id >= T.COAL_ORE && id <= T.DIAMOND_ORE) {
      drawStone(g, R);
      const palettes = {
        [T.COAL_ORE]: ["#222426", "#37393a", "#121415", "#4b4d4c"],
        [T.IRON_ORE]: ["#be8f67", "#d2a47a", "#8e6547", "#e0b78d"],
        [T.GOLD_ORE]: ["#e5b83e", "#f3d05c", "#a98122", "#fff09b"],
        [T.DIAMOND_ORE]: ["#5ad6cb", "#82efe2", "#2c9d9a", "#c3fff6"]
      }[id];
      for (let i = 0; i < 4; i++) {
        const x = 1 + ((R() * 11) | 0), y = 2 + ((R() * 10) | 0);
        px(g, x, y, 3, 3, palettes[0]);
        px(g, x, y, 1, 1, palettes[3]);
        px(g, x + 1, y + 2, 2, 1, palettes[2]);
        if (R() < 0.6) px(g, x + 3, y + 1, 1, 2, palettes[1]);
        if (R() < 0.5) px(g, x + 1, y - 1, 1, 1, palettes[1]);
      }
      return c;
    }

    if (id === T.TORCH) {
      g.clearRect(0, 0, 16, 16);
      px(g, 7, 6, 2, 10, "#6b4827");
      px(g, 7, 6, 1, 10, "#886035");
      px(g, 6, 14, 4, 1, "#4c321b");
      px(g, 6, 3, 4, 4, "#e98d2c");
      px(g, 7, 2, 2, 2, "#ffd569");
      px(g, 6, 5, 1, 1, "#c25c1e");
      px(g, 9, 4, 1, 2, "#f4b13d");
      px(g, 7, 1, 2, 1, "#fff4b1");
      return c;
    }

    if (id === T.TABLE) {
      px(g, 0, 0, 16, 16, "#8d6337");
      for (let y = 2; y < 16; y += 4) px(g, 0, y, 16, 1, "#5d4024");
      px(g, 0, 0, 16, 3, "#b98a50");
      px(g, 0, 3, 16, 1, "#543a22");
      px(g, 2, 4, 1, 12, "#694a2b");
      px(g, 13, 4, 1, 12, "#694a2b");
      px(g, 5, 6, 6, 1, "#4b3320");
      px(g, 5, 8, 1, 5, "#4b3320");
      px(g, 9, 6, 1, 3, "#c7a66e");
      px(g, 4, 10, 3, 1, "#b4b4a8");
      return c;
    }

    if (id === T.FURNACE) {
      drawStone(g, R);
      px(g, 0, 0, 16, 1, "#3a3e3e");
      px(g, 0, 15, 16, 1, "#303434");
      px(g, 4, 5, 8, 7, "#1a1b1a");
      px(g, 5, 6, 6, 4, "#0c0d0d");
      px(g, 6, 8, 4, 2, "#d8752b");
      px(g, 7, 9, 2, 1, "#ffd17a");
      px(g, 3, 4, 10, 1, "#5a5e5d");
      px(g, 3, 12, 10, 1, "#555958");
      return c;
    }

    if (id === T.GLASS) {
      g.clearRect(0, 0, 16, 16);
      g.fillStyle = "rgba(166,216,224,.18)";
      g.fillRect(0, 0, 16, 16);
      px(g, 0, 0, 16, 1, "rgba(197,241,242,.65)");
      px(g, 0, 15, 16, 1, "rgba(120,177,190,.55)");
      px(g, 0, 0, 1, 16, "rgba(197,241,242,.55)");
      px(g, 15, 0, 1, 16, "rgba(120,177,190,.5)");
      px(g, 3, 4, 1, 1, "#e7ffff");
      px(g, 4, 5, 1, 2, "rgba(235,255,255,.7)");
      px(g, 2, 8, 1, 1, "rgba(235,255,255,.45)");
      return c;
    }

    if (id === T.ROSE || id === T.DANDELION) {
      g.clearRect(0, 0, 16, 16);
      px(g, 7, 7, 1, 8, "#3f7b2c");
      px(g, 5, 10, 2, 1, "#4f8c35");
      px(g, 9, 8, 2, 1, "#4f8c35");
      px(g, 3, 14, 10, 1, "#365e27");
      if (id === T.ROSE) {
        px(g, 6, 2, 4, 5, "#b83e39");
        px(g, 5, 3, 1, 3, "#d75b4e");
        px(g, 10, 3, 1, 2, "#8d2c2e");
        px(g, 7, 1, 2, 1, "#dd6a59");
        px(g, 7, 3, 2, 2, "#7d222a");
      } else {
        px(g, 6, 2, 4, 4, "#e2c347");
        px(g, 5, 3, 1, 2, "#f2dd70");
        px(g, 10, 3, 1, 2, "#c6a531");
        px(g, 7, 1, 2, 1, "#f7e98e");
        px(g, 7, 3, 2, 2, "#b98a26");
      }
      return c;
    }

    if (id === T.TALL_GRASS) {
      g.clearRect(0, 0, 16, 16);
      for (let i = 0; i < 7; i++) {
        const x = 2 + ((R() * 12) | 0);
        const h = 4 + ((R() * 8) | 0);
        px(g, x, 15 - h, 1, h, pick(["#4a8835", "#5b9c40", "#3f762d", "#6aa84a"]));
        if (R() < .5) px(g, x + 1, 12, 1, 3, "#4f8c36");
      }
      px(g, 2, 15, 12, 1, "#3c632a");
      return c;
    }

    if (id === T.MUSHROOM) {
      g.clearRect(0, 0, 16, 16);
      px(g, 7, 9, 2, 5, "#e0d5b4");
      px(g, 6, 13, 4, 1, "#b9ad8f");
      px(g, 4, 4, 8, 5, "#c95042");
      px(g, 3, 6, 10, 2, "#a93d34");
      px(g, 5, 3, 6, 2, "#dc6250");
      px(g, 5, 5, 1, 1, "#f0c4a5");
      px(g, 9, 4, 1, 1, "#f0c4a5");
      px(g, 7, 6, 2, 1, "#e7b397");
      return c;
    }

    if (id === T.GRAVEL) {
      px(g, 0, 0, 16, 16, "#77726b");
      for (let i = 0; i < 55; i++) {
        const x = (R() * 15) | 0, y = (R() * 15) | 0;
        px(g, x, y, 1 + ((R() * 3) | 0), 1 + ((R() * 2) | 0), pick(["#918b82", "#625e58", "#a19a8f", "#534f4a", "#847c71"]));
      }
      return c;
    }

    if (id === T.BRICKS) {
      px(g, 0, 0, 16, 16, "#5b5d5c");
      for (let row = 0; row < 4; row++) {
        const off = row % 2 ? 4 : 0;
        for (let col = -1; col < 2; col++) {
          const x = off + col * 8;
          px(g, x + 1, row * 4 + 1, 6, 2, "#8d8f8b");
          px(g, x + 1, row * 4 + 1, 6, 1, "#a6a7a1");
          px(g, x + 1, row * 4 + 3, 6, 1, "#70726f");
        }
      }
      return c;
    }

    if (id === T.LAMP) {
      px(g, 0, 0, 16, 16, "#6d5636");
      px(g, 1, 1, 14, 14, "#d8a942");
      px(g, 2, 2, 12, 12, "#f4d477");
      px(g, 3, 3, 10, 10, "#fff3b3");
      px(g, 4, 4, 8, 8, "#f4c64f");
      px(g, 6, 6, 4, 4, "#fffbe0");
      px(g, 0, 0, 16, 1, "#4d3c25");
      px(g, 0, 15, 16, 1, "#4d3c25");
      return c;
    }

    if (id === T.CACTUS) {
      px(g, 0, 0, 16, 16, "#3f7c34");
      for (let x = 2; x < 16; x += 4) {
        px(g, x, 0, 1, 16, "#2b5b24");
        px(g, x + 1, 0, 1, 16, "#5a9c42");
      }
      for (let i = 0; i < 16; i++) {
        if (R() < 0.6) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, "#79b65a");
      }
      px(g, 0, 0, 16, 1, "#234a1e");
      px(g, 0, 15, 16, 1, "#234a1e");
      for (let y = 2; y < 15; y += 4) {
        px(g, 0, y, 2, 1, "#d7d890");
        px(g, 14, y + 1, 2, 1, "#d7d890");
      }
      return c;
    }

    // fallback
    px(g, 0, 0, 16, 16, "#ff00ff");
    return c;
  }

  function drawDirt(g, R) {
    px(g, 0, 0, 16, 16, "#79553a");
    for (let i = 0; i < 65; i++) {
      px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, ["#6c4a32", "#8a6341", "#5f422d", "#936b46", "#745035"][(R() * 5) | 0]);
    }
    for (let i = 0; i < 9; i++) {
      px(g, (R() * 14) | 0, (R() * 15) | 0, 2 + ((R() * 2) | 0), 1, ["#563b28", "#a07850"][(R() * 2) | 0]);
    }
  }

  function drawStone(g, R) {
    px(g, 0, 0, 16, 16, "#7b7e7d");
    for (let i = 0; i < 60; i++) {
      px(g, (R() * 16) | 0, (R() * 16) | 0, 1 + ((R() * 3) | 0), 1, ["#6c7070", "#858887", "#727575", "#8d908e", "#666a6b"][(R() * 5) | 0]);
    }
    for (let i = 0; i < 8; i++) {
      px(g, (R() * 13) | 0, (R() * 14) | 0, 2 + ((R() * 3) | 0), 2, ["#6a6e6d", "#898c8a"][(R() * 2) | 0]);
    }
  }

  function drawCobble(g, R) {
    for (let i = 0; i < 12; i++) {
      const x = (R() * 14) | 0, y = (R() * 14) | 0;
      const w = 2 + ((R() * 4) | 0), h = 2 + ((R() * 3) | 0);
      px(g, x, y, w, h, ["#8d908d", "#777b7a", "#9a9c98", "#696d6c"][(R() * 4) | 0]);
      px(g, x, y, w, 1, "#a8aaa5");
      px(g, x, y + h - 1, w, 1, "#555958");
    }
    for (let i = 0; i < 14; i++) px(g, (R() * 16) | 0, (R() * 16) | 0, 1, 1, "#4d5151");
  }

  function buildAllTextures() {
    for (let id = 0; id < BH.TILE_DEFS.length; id++) {
      if (!BH.TILE_DEFS[id]) continue;
      const arr = [];
      const variants = id === T.AIR ? 1 : BH.TILE_VARIANTS;
      for (let v = 0; v < variants; v++) arr.push(buildTileTex(id, v));
      BH.TILE_TEX[id] = arr;
    }
  }

  // ---------- icons ----------
  BH.ICONS = {};

  function makeBlockIcon(tileId) {
    const def = BH.TILE_DEFS[tileId];
    const tex = BH.TILE_TEX[tileId][0];
    const { c, g } = canvas2d(64, 64);

    if (!def || def.flatIcon || tileId === T.GLASS || tileId === T.LEAVES || tileId === T.TORCH || !def.solid) {
      g.drawImage(tex, 5, 5, 54, 54);
      // simple bevel for flat items that represent blocks
      g.globalCompositeOperation = "source-atop";
      g.fillStyle = "rgba(255,255,255,.10)";
      g.fillRect(5, 5, 54, 3);
      g.fillStyle = "rgba(0,0,0,.16)";
      g.fillRect(5, 56, 54, 3);
      g.globalCompositeOperation = "source-over";
      return c;
    }

    // A chunky isometric block icon, built from the tile texture.
    const top = (x, y) => { g.setTransform(1.75, .875, -1.75, .875, x, y); };
    // top face
    g.save();
    g.setTransform(1.75, .875, -1.75, .875, 32, 6);
    g.drawImage(tex, 0, 0, 16, 16);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "source-atop";
    g.fillStyle = "rgba(255,255,255,.20)";
    g.fillRect(0, 0, 64, 64);
    g.restore();

    // left face
    g.save();
    g.setTransform(1.75, .875, 0, 1.75, 4, 20);
    g.drawImage(tex, 0, 0, 16, 16);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "source-atop";
    g.fillStyle = "rgba(0,0,0,.07)";
    g.fillRect(0, 0, 64, 64);
    g.restore();

    // right face
    g.save();
    g.setTransform(1.75, -.875, 0, 1.75, 32, 34);
    g.drawImage(tex, 0, 0, 16, 16);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "source-atop";
    g.fillStyle = "rgba(0,0,0,.24)";
    g.fillRect(0, 0, 64, 64);
    g.restore();

    // subtle edge highlights
    g.strokeStyle = "rgba(255,246,218,.24)";
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(32, 6); g.lineTo(60, 20); g.lineTo(32, 34); g.lineTo(4, 20); g.closePath();
    g.stroke();
    return c;
  }

  function drawToolIcon(g, kind, tier) {
    const colors = {
      1: ["#a57a42", "#7b5730", "#c39658"],
      2: ["#8b8f8d", "#656968", "#b1b4af"],
      3: ["#d3d6d1", "#919994", "#f1f2ec"],
      4: ["#65d7cc", "#319f9b", "#b7fff7"]
    }[tier] || ["#a57a42", "#7b5730", "#c39658"];
    const mat = colors[0], dark = colors[1], light = colors[2];
    g.imageSmoothingEnabled = false;
    // dark outline under the whole sprite
    function pix(x, y, w, h, col) { px(g, x, y, w, h, col); }
    function handle() {
      for (let i = 0; i < 9; i++) {
        pix(8 + i, 22 - i, 2, 2, "#5b3b20");
        pix(9 + i, 22 - i, 1, 1, "#977044");
      }
    }
    if (kind === "pick") {
      handle();
      pix(10, 5, 3, 3, "#4d3827");
      pix(12, 6, 3, 2, "#4d3827");
      pix(15, 8, 3, 2, "#4d3827");
      pix(8, 7, 2, 2, "#4d3827");
      pix(9, 4, 3, 3, dark);
      pix(12, 5, 4, 2, mat);
      pix(16, 7, 3, 2, dark);
      pix(8, 6, 3, 2, dark);
      pix(9, 4, 2, 1, light);
      pix(13, 5, 2, 1, light);
      pix(18, 8, 1, 1, light);
      pix(8, 7, 1, 1, "#4d3827");
      pix(11, 8, 2, 1, "#4d3827");
    } else if (kind === "axe") {
      handle();
      pix(11, 6, 4, 3, "#4d3827");
      pix(14, 5, 4, 5, "#4d3827");
      pix(12, 5, 4, 4, dark);
      pix(15, 4, 3, 6, mat);
      pix(12, 5, 3, 2, mat);
      pix(15, 5, 2, 2, light);
      pix(18, 7, 1, 2, light);
      pix(12, 7, 2, 1, dark);
    } else if (kind === "sword") {
      for (let i = 0; i < 10; i++) {
        pix(7 + i, 24 - i, 2, 2, "#4d3827");
        pix(8 + i, 23 - i, 1, 1, light);
      }
      for (let i = 0; i < 4; i++) {
        pix(6 + i, 22 - i, 2, 2, mat);
        pix(7 + i, 21 - i, 1, 1, light);
      }
      pix(5, 17, 9, 2, dark);
      pix(6, 16, 8, 2, mat);
      pix(4, 21, 3, 3, "#5b3b20");
      pix(5, 20, 2, 2, "#977044");
      pix(3, 24, 3, 2, "#4d3827");
    }
  }

  function drawSimpleItem(g, id) {
    const P = (x, y, w, h, c) => px(g, x, y, w, h, c);
    if (id === I.STICK) {
      for (let i = 0; i < 26; i++) {
        const x = 17 + Math.round(i * 0.78);
        const y = 49 - Math.round(i * 1.08);
        P(x - 2, y - 2, 5, 5, "#4a2f1b");
        P(x, y, 3, 3, "#7a532e");
        P(x, y, 1, 1, "#b28855");
      }
    } else if (id === I.COAL || id === I.CHARCOAL) {
      const cols = id === I.COAL ? ["#25292b", "#3c4142", "#15181a", "#545858"] : ["#2b2621", "#443b32", "#171411", "#5b5044"];
      P(12, 11, 22, 22, cols[0]);
      P(9, 17, 8, 14, cols[0]);
      P(28, 15, 8, 12, cols[1]);
      P(14, 9, 12, 6, cols[1]);
      P(15, 13, 6, 6, cols[3]);
      P(25, 24, 4, 4, cols[2]);
    } else if (id === I.IRON_INGOT || id === I.GOLD_INGOT) {
      const c1 = id === I.IRON_INGOT ? "#d6d9d4" : "#f0cc57";
      const c2 = id === I.IRON_INGOT ? "#9da7a2" : "#b48d2d";
      const c3 = id === I.IRON_INGOT ? "#f4f6ef" : "#fff1a3";
      P(10, 20, 28, 6, c2);
      P(13, 16, 22, 12, c2);
      P(14, 16, 20, 8, c1);
      P(15, 16, 16, 3, c3);
      P(12, 30, 28, 6, "#5a5038");
      P(14, 30, 24, 2, c2);
    } else if (id === I.DIAMOND) {
      P(32, 10, 2, 2, "#d6fff8");
      for (let y = 0; y < 18; y++) {
        const w = y < 5 ? 4 + y * 3 : 20 - (y - 5) * 2;
        const a = y < 5 ? 8 - y * 1.4 : 2 + (y - 5) * 1.4;
        P(32 - w / 2, 13 + y, w, 1, y < 8 ? "#b8fff6" : "#4fd4ca");
      }
      P(16, 24, 32, 3, "#237c7c");
      P(24, 17, 4, 8, "#b6fff7");
    } else if (id === I.APPLE || id === I.GOLDEN_APPLE) {
      const gold = id === I.GOLDEN_APPLE;
      P(18, 17, 28, 26, gold ? "#ddb33e" : "#b83e39");
      P(14, 22, 7, 17, gold ? "#f0ca57" : "#d75449");
      P(43, 22, 7, 17, gold ? "#b28928" : "#8d292c");
      P(20, 14, 19, 7, gold ? "#f1d36a" : "#d75b4e");
      P(17, 37, 26, 7, gold ? "#a57c24" : "#7b2026");
      P(23, 21, 5, 5, gold ? "#fff4b0" : "#e17663");
      P(31, 15, 2, 5, "#5e3b20");
      P(32, 12, 6, 4, "#5d9b42");
      if (gold) {
        P(34, 28, 3, 3, "#fff3aa");
        P(23, 32, 2, 2, "#f8dd72");
      }
    } else if (id === I.RAW_PORK || id === I.COOKED_PORK) {
      const cooked = id === I.COOKED_PORK;
      P(13, 17, 34, 24, cooked ? "#8d5434" : "#df8f8d");
      P(10, 23, 8, 12, cooked ? "#a9683f" : "#eca6a0");
      P(42, 21, 7, 14, cooked ? "#6d3e27" : "#c97679");
      P(17, 21, 22, 8, cooked ? "#a6633c" : "#f1aaa4");
      P(23, 15, 8, 6, cooked ? "#c27a49" : "#f4b8b1");
      P(19, 31, 8, 4, cooked ? "#5f3622" : "#b8656d");
      P(34, 29, 5, 4, cooked ? "#c58a57" : "#f3c0b4");
      if (!cooked) P(30, 20, 4, 3, "#f8d0c8");
    } else {
      P(14, 14, 32, 32, "#ff00ff");
    }
  }

  function buildIcons() {
    for (let id = 0; id < BH.TILE_DEFS.length; id++) {
      if (!BH.TILE_DEFS[id] || id === T.AIR) continue;
      BH.ICONS[id] = makeBlockIcon(id).toDataURL("image/png");
    }
    for (const key in BH.ITEM_DEFS) {
      const id = Number(key);
      const def = BH.ITEM_DEFS[id];
      if (def.iconTile) {
        BH.ICONS[id] = makeBlockIcon(def.iconTile).toDataURL("image/png");
        continue;
      }
      const { c, g } = canvas2d(64, 64);
      if (def.tool) {
        g.save();
        g.translate(5, 3);
        g.scale(2, 2);
        drawToolIcon(g, def.tool, def.tier);
        g.restore();
      } else drawSimpleItem(g, id);
      BH.ICONS[id] = c.toDataURL("image/png");
    }
  }

  BH.iconOf = function (id) {
    return BH.ICONS[id] || "";
  };

  // Build once at boot.
  buildAllTextures();
  buildIcons();

  // ---------- sound ----------
  BH.Sound = {
    ctx: null,
    master: null,
    sfx: null,
    muted: false,
    noiseBuffer: null,
    lastZombie: 0,
    lastAmbient: 0,

    init() {
      if (this.ctx) return;
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = this.muted ? 0 : 0.55;
        this.master.connect(this.ctx.destination);
        this.sfx = this.ctx.createGain();
        this.sfx.gain.value = 0.7;
        this.sfx.connect(this.master);
        const len = this.ctx.sampleRate;
        const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
        const d = buf.getChannelData(0);
        for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
        this.noiseBuffer = buf;
      } catch (e) { /* audio is optional */ }
    },

    resume() {
      this.init();
      if (this.ctx && this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
    },

    setMuted(m) {
      this.muted = !!m;
      if (this.master) {
        const t = this.ctx.currentTime;
        this.master.gain.cancelScheduledValues(t);
        this.master.gain.linearRampToValueAtTime(m ? 0 : 0.55, t + 0.04);
      }
      try { localStorage.setItem(BH.SETTINGS_KEY, JSON.stringify({ muted: this.muted })); } catch (e) {}
    },

    tone(freq, dur, type, vol, slide, delay) {
      if (!this.ctx || this.muted) return;
      const t0 = this.ctx.currentTime + (delay || 0);
      const o = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      o.type = type || "square";
      o.frequency.setValueAtTime(freq, t0);
      if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(20, freq + slide), t0 + dur);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(vol || 0.04, t0 + 0.008);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      o.connect(g); g.connect(this.sfx);
      o.start(t0); o.stop(t0 + dur + 0.02);
    },

    noise(dur, vol, filterFreq, delay, rate) {
      if (!this.ctx || this.muted || !this.noiseBuffer) return;
      const t0 = this.ctx.currentTime + (delay || 0);
      const src = this.ctx.createBufferSource();
      src.buffer = this.noiseBuffer;
      src.playbackRate.value = rate || 1;
      const f = this.ctx.createBiquadFilter();
      f.type = "bandpass";
      f.frequency.value = filterFreq || 800;
      f.Q.value = 0.8;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(vol || 0.05, t0);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      src.connect(f); f.connect(g); g.connect(this.sfx);
      src.start(t0); src.stop(t0 + dur + 0.02);
    },

    click() { this.tone(420, 0.04, "square", 0.025, -80); },
    select() { this.tone(620, 0.035, "square", 0.018, 120); },
    breakBlock(tile) {
      const stone = [T.STONE, T.COBBLE, T.COAL_ORE, T.IRON_ORE, T.GOLD_ORE, T.DIAMOND_ORE, T.FURNACE, T.BRICKS, T.SANDSTONE].includes(tile);
      const wood = [T.LOG, T.PLANKS, T.TABLE, T.LEAVES].includes(tile);
      if (stone) {
        this.noise(0.16, 0.11, 700, 0, 0.7);
        this.tone(120, 0.1, "triangle", 0.04, -55);
      } else if (wood) {
        this.noise(0.14, 0.075, 520, 0, 1.2);
        this.tone(190, 0.12, "triangle", 0.035, -90);
      } else {
        this.noise(0.12, 0.06, 340, 0, 1.6);
      }
    },
    dig(tile) {
      const stone = [T.STONE, T.COBBLE, T.COAL_ORE, T.IRON_ORE, T.GOLD_ORE, T.DIAMOND_ORE].includes(tile);
      this.noise(0.035, 0.016, stone ? 950 : 420, 0, stone ? 0.8 : 1.7);
    },
    place() { this.tone(190, 0.08, "triangle", 0.05, -50); this.noise(0.05, 0.035, 600, 0, 1.4); },
    pickup() { this.tone(660, 0.06, "square", 0.032, 110); this.tone(990, 0.05, "square", 0.02, 80, 0.04); },
    hurt() { this.tone(180, 0.23, "sawtooth", 0.075, -110); this.noise(0.12, 0.055, 400, 0, 0.8); },
    eat() { this.noise(0.07, 0.055, 450, 0, 1.1); this.noise(0.06, 0.04, 360, 0.09, 0.9); },
    craft() { this.tone(520, 0.08, "square", 0.035, 100); this.tone(780, 0.1, "square", 0.03, 80, 0.07); },
    jump() { this.tone(320, 0.08, "square", 0.02, 80); },
    land() { this.noise(0.06, 0.04, 220, 0, 1); },
    step(tile) {
      const soft = [T.GRASS, T.DIRT, T.SAND, T.GRAVEL, T.LEAVES].includes(tile);
      this.noise(0.035, soft ? 0.018 : 0.012, soft ? 260 : 500, 0, soft ? 1.5 : 2);
    },
    zombie(volume) {
      if (!this.ctx || this.muted) return;
      const t0 = this.ctx.currentTime;
      const o = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      const f = this.ctx.createBiquadFilter();
      o.type = "sawtooth";
      o.frequency.setValueAtTime(82, t0);
      o.frequency.linearRampToValueAtTime(57, t0 + 0.5);
      f.type = "lowpass"; f.frequency.value = 390;
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.04 * (volume || 1), t0 + 0.06);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.55);
      o.connect(f); f.connect(g); g.connect(this.sfx);
      o.start(t0); o.stop(t0 + 0.6);
    },
    chirp(night) {
      if (!this.ctx || this.muted) return;
      if (night) {
        this.tone(2100 + Math.random() * 500, 0.035, "square", 0.007, -200);
        this.tone(2400 + Math.random() * 400, 0.03, "square", 0.006, -200, 0.07);
      } else {
        const f = 1200 + Math.random() * 900;
        this.tone(f, 0.08, "sine", 0.012, 600);
        this.tone(f + 250, 0.06, "sine", 0.009, 300, 0.1);
      }
    },
    save() { this.tone(440, 0.07, "sine", 0.018, 120); this.tone(660, 0.09, "sine", 0.012, 80, 0.06); }
  };

  try {
    const s = JSON.parse(localStorage.getItem(BH.SETTINGS_KEY) || "{}");
    BH.Sound.muted = !!s.muted;
  } catch (e) {}

})();
