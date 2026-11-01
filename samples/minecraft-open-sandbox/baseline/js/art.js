(function (root) {
  "use strict";

  const CONFIG = root.MosswildConfig;
  const CONTENT = root.MosswildContent;
  const B = CONFIG.block;
  const TILE = CONFIG.tileSize;
  const ART_SEED = 0x1f2e3d4c;

  let blockSprites = null;
  let caveSprites = null;

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function mulberry32(seed) {
    let state = seed >>> 0;
    return function random() {
      state += 0x6d2b79f5;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hash2(seed, x, y) {
    let value = (seed ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263)) >>> 0;
    value = Math.imul(value ^ (value >>> 13), 1274126177);
    return (value ^ (value >>> 16)) >>> 0;
  }

  function pick(rng, values) {
    return values[Math.floor(rng() * values.length)];
  }

  function px(ctx, x, y, width, height, color) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(width), Math.round(height));
  }

  function edgeShade(ctx, strength) {
    ctx.fillStyle = "rgba(20, 22, 17, " + strength + ")";
    ctx.fillRect(0, TILE - 1, TILE, 1);
    ctx.fillRect(TILE - 1, 0, 1, TILE);
  }

  function stoneBase(ctx, rng, base, dark, light) {
    px(ctx, 0, 0, TILE, TILE, base);
    for (let i = 0; i < 14; i += 1) {
      const w = 2 + Math.floor(rng() * 7);
      const h = 2 + Math.floor(rng() * 5);
      const x = Math.floor(rng() * (TILE - w));
      const y = Math.floor(rng() * (TILE - h));
      ctx.fillStyle = i % 3 === 0 ? light : dark;
      ctx.globalAlpha = 0.45 + rng() * 0.35;
      ctx.fillRect(x, y, w, h);
      ctx.globalAlpha = 1;
    }
    for (let i = 0; i < 3; i += 1) {
      const x = 3 + Math.floor(rng() * (TILE - 8));
      const y = 4 + Math.floor(rng() * (TILE - 10));
      px(ctx, x, y, 1, 3 + Math.floor(rng() * 4), "rgba(44,49,52,0.55)");
      px(ctx, x + 1, y + 2, 2, 1, "rgba(44,49,52,0.4)");
    }
    edgeShade(ctx, 0.16);
  }

  function dirtBase(ctx, rng, withGrass) {
    px(ctx, 0, 0, TILE, TILE, "#775235");
    const dark = ["#67462e", "#5e3f28", "#835b3b"];
    const light = ["#906844", "#a1764f", "#805a39"];
    for (let i = 0; i < 22; i += 1) {
      const size = 1 + Math.floor(rng() * 3);
      px(ctx, Math.floor(rng() * TILE), Math.floor(rng() * TILE), size, size, rng() < 0.45 ? light[i % 3] : dark[i % 3]);
    }
    for (let i = 0; i < 4; i += 1) {
      const x = 2 + Math.floor(rng() * 27);
      const y = 10 + Math.floor(rng() * 20);
      px(ctx, x, y, 1, 2 + Math.floor(rng() * 3), "rgba(53, 35, 22, 0.55)");
    }
    if (withGrass) {
      const greens = ["#6d9c47", "#7cad50", "#5a8439", "#8cbb59"];
      const top = 5 + Math.floor(rng() * 2);
      px(ctx, 0, 0, TILE, top, "#6a9845");
      for (let x = 0; x < TILE; x += 1) {
        const fringe = Math.floor(rng() * 3);
        px(ctx, x, top, 1, fringe, pick(rng, greens));
        if (x % 4 === 0) {
          px(ctx, x, Math.max(0, top - 1), 1, 2, "rgba(158, 203, 92, 0.55)");
        }
      }
      for (let i = 0; i < 12; i += 1) {
        px(ctx, Math.floor(rng() * TILE), Math.floor(rng() * top), 1 + Math.floor(rng() * 2), 1, pick(rng, greens));
      }
      px(ctx, 0, Math.max(0, top - 1), TILE, 1, "rgba(183, 219, 122, 0.45)");
    }
    edgeShade(ctx, 0.14);
  }

  function drawGrass(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 71 + 3);
    dirtBase(ctx, rng, true);
  }

  function drawDirt(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 71 + 9);
    dirtBase(ctx, rng, false);
  }

  function drawStone(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 71 + 17);
    stoneBase(ctx, rng, "#7b8488", "#646d72", "#939b9e");
  }

  function drawOre(ctx, variant, colors) {
    const rng = mulberry32(ART_SEED + variant * 71 + colors.seed);
    stoneBase(ctx, rng, "#727b80", "#5b6469", "#8c9599");
    for (let cluster = 0; cluster < 4; cluster += 1) {
      const cx = 5 + Math.floor(rng() * 22);
      const cy = 5 + Math.floor(rng() * 21);
      const pieces = 2 + Math.floor(rng() * 3);
      for (let piece = 0; piece < pieces; piece += 1) {
        const x = cx + Math.floor(rng() * 5) - 2;
        const y = cy + Math.floor(rng() * 4) - 2;
        px(ctx, x, y, 2 + Math.floor(rng() * 2), 2, colors.dark);
        px(ctx, x, y, 1, 1, colors.light);
        if (rng() < 0.35) {
          px(ctx, x + 2, y + 1, 1, 1, colors.glow);
        }
      }
    }
    edgeShade(ctx, 0.18);
  }

  function drawLog(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 53 + 29);
    px(ctx, 0, 0, TILE, TILE, "#68482f");
    for (let x = 0; x < TILE; x += 2) {
      if (rng() < 0.5) {
        px(ctx, x, 0, 1, TILE, rng() < 0.4 ? "#7b5838" : "#543923");
      }
    }
    for (let i = 0; i < 5; i += 1) {
      const x = 3 + Math.floor(rng() * 26);
      px(ctx, x, 2 + Math.floor(rng() * 14), 2 + Math.floor(rng() * 2), 8 + Math.floor(rng() * 12), "rgba(69, 44, 25, 0.6)");
    }
    ctx.strokeStyle = "rgba(193, 145, 92, 0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(7, 4);
    ctx.bezierCurveTo(13, 9, 10, 19, 17, 28);
    ctx.moveTo(24, 5);
    ctx.bezierCurveTo(20, 12, 25, 19, 23, 27);
    ctx.stroke();
    // A pale cut on the side makes logs immediately legible.
    px(ctx, 4, 12, 7, 1, "rgba(220, 175, 113, 0.4)");
    px(ctx, 10, 12, 1, 4, "rgba(58, 37, 21, 0.6)");
    edgeShade(ctx, 0.24);
  }

  function drawLeaves(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 61 + 41);
    px(ctx, 0, 0, TILE, TILE, "#37633a");
    for (let i = 0; i < 26; i += 1) {
      const x = Math.floor(rng() * 29);
      const y = Math.floor(rng() * 28);
      const w = 2 + Math.floor(rng() * 4);
      const h = 1 + Math.floor(rng() * 3);
      const colors = ["#4a7b41", "#568949", "#2f5933", "#6f9f51", "#3f6f3c"];
      px(ctx, x, y, w, h, pick(rng, colors));
    }
    for (let i = 0; i < 7; i += 1) {
      px(ctx, 2 + Math.floor(rng() * 27), 2 + Math.floor(rng() * 27), 1, 1, "#93b95f");
    }
    // Sparse dark gaps make the canopy feel like clustered leaves.
    px(ctx, 12, 8, 2, 2, "rgba(24, 47, 28, 0.65)");
    px(ctx, 22, 18, 2, 1, "rgba(24, 47, 28, 0.6)");
    px(ctx, 6, 23, 1, 2, "rgba(24, 47, 28, 0.55)");
    edgeShade(ctx, 0.22);
  }

  function drawPlanks(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 83 + 67);
    px(ctx, 0, 0, TILE, TILE, "#a77d4f");
    const boards = [0, 11, 22];
    boards.forEach(function (y, index) {
      const shade = index % 2 === 0 ? "#ad8354" : "#9d7446";
      px(ctx, 0, y, TILE, 10, shade);
      px(ctx, 0, y, TILE, 1, "rgba(229, 190, 128, 0.38)");
      px(ctx, 0, y + 10, TILE, 1, "#664a2e");
      const nailX = index % 2 === 0 ? 4 : 25;
      px(ctx, nailX, y + 3, 1, 1, "#5c432b");
      px(ctx, nailX, y + 7, 1, 1, "#5c432b");
    });
    for (let i = 0; i < 9; i += 1) {
      px(ctx, 2 + Math.floor(rng() * 27), 2 + Math.floor(rng() * 27), 2 + Math.floor(rng() * 5), 1, "rgba(109, 76, 43, 0.38)");
    }
    px(ctx, 15, 11, 1, 10, "rgba(93, 63, 35, 0.5)");
    edgeShade(ctx, 0.18);
  }

  function drawBrick(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 59 + 89);
    px(ctx, 0, 0, TILE, TILE, "#5c605d");
    const mortar = "#676c67";
    const rows = [1, 9, 17, 25];
    rows.forEach(function (y, row) {
      const offset = row % 2 === 0 ? 0 : -8;
      for (let x = offset; x < TILE; x += 16) {
        px(ctx, x + 1, y, 14, 7, row % 2 === 0 ? "#8e9691" : "#848c87");
        px(ctx, x + 1, y, 14, 1, "#a6ada6");
        px(ctx, x + 1, y + 6, 14, 1, "#737a75");
        if (rng() < 0.45) {
          px(ctx, x + 4 + Math.floor(rng() * 7), y + 3, 1, 1, "#6a706b");
        }
      }
    });
    px(ctx, 0, 0, TILE, TILE, "rgba(0,0,0,0)");
    edgeShade(ctx, 0.22);
  }

  function drawWorkbench(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 67 + 101);
    px(ctx, 0, 0, TILE, TILE, "rgba(0,0,0,0)");
    px(ctx, 2, 4, 28, 9, "#5c4026");
    px(ctx, 3, 5, 26, 6, "#b68a58");
    px(ctx, 3, 5, 26, 1, "#d1a56e");
    px(ctx, 14, 6, 1, 5, "#7d5a36");
    px(ctx, 18, 6, 1, 5, "#7d5a36");
    px(ctx, 4, 12, 4, 17, "#785333");
    px(ctx, 24, 12, 4, 17, "#785333");
    px(ctx, 5, 12, 1, 17, "#a87b4c");
    px(ctx, 25, 12, 1, 17, "#a87b4c");
    px(ctx, 8, 19, 16, 3, "#8d633d");
    px(ctx, 8, 28, 16, 1, "#4e3521");
    px(ctx, 10, 23, 12, 5, "#3b2b1c");
    // A silver saw and a little hammer on the bench top.
    px(ctx, 20, 3, 7, 1, "#c5c9bf");
    px(ctx, 20, 4, 1, 3, "#826447");
    px(ctx, 7, 3, 1, 3, "#876444");
    px(ctx, 6, 2, 3, 1, "#9ea29a");
    px(ctx, 5, 15, 1, 8, "rgba(46, 30, 18, 0.5)");
    edgeShade(ctx, 0.24);
  }

  function drawBedrock(ctx, variant) {
    const rng = mulberry32(ART_SEED + variant * 73 + 113);
    px(ctx, 0, 0, TILE, TILE, "#34383b");
    for (let i = 0; i < 13; i += 1) {
      const x = Math.floor(rng() * 24);
      const y = Math.floor(rng() * 24);
      const w = 3 + Math.floor(rng() * 8);
      const h = 2 + Math.floor(rng() * 6);
      px(ctx, x, y, w, h, rng() < 0.5 ? "#292d30" : "#42474a");
      px(ctx, x, y, w, 1, "rgba(120, 126, 125, 0.2)");
    }
    edgeShade(ctx, 0.4);
  }

  function buildBlockSprites() {
    const sprites = {};
    const ids = [
      B.GRASS, B.DIRT, B.STONE, B.COAL_ORE, B.IRON_ORE, B.GEM_ORE,
      B.LOG, B.LEAVES, B.PLANKS, B.BRICK, B.WORKBENCH, B.BEDROCK
    ];
    ids.forEach(function (id) {
      sprites[id] = [];
      for (let variant = 0; variant < 3; variant += 1) {
        const canvas = makeCanvas(TILE, TILE);
        const ctx = canvas.getContext("2d");
        ctx.imageSmoothingEnabled = false;
        if (id === B.GRASS) drawGrass(ctx, variant);
        if (id === B.DIRT) drawDirt(ctx, variant);
        if (id === B.STONE) drawStone(ctx, variant);
        if (id === B.COAL_ORE) drawOre(ctx, variant, { seed: 127, dark: "#292b2c", light: "#5a5c5b", glow: "#a8a68c" });
        if (id === B.IRON_ORE) drawOre(ctx, variant, { seed: 131, dark: "#95633e", light: "#d39a64", glow: "#f4c994" });
        if (id === B.GEM_ORE) drawOre(ctx, variant, { seed: 137, dark: "#2e887b", light: "#52cdb3", glow: "#b1ffe5" });
        if (id === B.LOG) drawLog(ctx, variant);
        if (id === B.LEAVES) drawLeaves(ctx, variant);
        if (id === B.PLANKS) drawPlanks(ctx, variant);
        if (id === B.BRICK) drawBrick(ctx, variant);
        if (id === B.WORKBENCH) drawWorkbench(ctx, variant);
        if (id === B.BEDROCK) drawBedrock(ctx, variant);
        sprites[id].push(canvas);
      }
    });
    return sprites;
  }

  function buildCaveSprites() {
    const buckets = [
      { base: "#39342d", dark: "#2b2823", light: "#4a4035", root: "#293326" },
      { base: "#2a2a27", dark: "#1f211f", light: "#383632", root: "#242c24" },
      { base: "#1d1f1e", dark: "#171918", light: "#292b28", root: "#1b221d" }
    ];
    return buckets.map(function (bucket, bucketIndex) {
      const variants = [];
      for (let variant = 0; variant < 3; variant += 1) {
        const canvas = makeCanvas(TILE, TILE);
        const ctx = canvas.getContext("2d");
        const rng = mulberry32(ART_SEED + 1000 + bucketIndex * 91 + variant * 37);
        px(ctx, 0, 0, TILE, TILE, bucket.base);
        for (let i = 0; i < 16; i += 1) {
          const x = Math.floor(rng() * 28);
          const y = Math.floor(rng() * 28);
          const w = 3 + Math.floor(rng() * 9);
          const h = 2 + Math.floor(rng() * 5);
          px(ctx, x, y, w, h, i % 4 === 0 ? bucket.light : bucket.dark);
        }
        ctx.strokeStyle = "rgba(10, 11, 10, 0.3)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(4, 28);
        ctx.bezierCurveTo(11, 22, 13, 16, 18, 9);
        ctx.stroke();
        if (variant === 0 && rng() < 0.8) {
          px(ctx, 6, 0, 1, 4 + Math.floor(rng() * 6), bucket.root);
          px(ctx, 7, 6, 2, 1, bucket.root);
        }
        variants.push(canvas);
      }
      return variants;
    });
  }

  function ensureArt() {
    if (!blockSprites) {
      blockSprites = buildBlockSprites();
    }
    if (!caveSprites) {
      caveSprites = buildCaveSprites();
    }
  }

  function getBlockSprite(id, variant) {
    ensureArt();
    const group = blockSprites[id];
    if (!group) {
      return null;
    }
    return group[variant % group.length];
  }

  function getCaveSprite(depthBucket, variant) {
    ensureArt();
    const bucket = caveSprites[Math.max(0, Math.min(2, depthBucket))];
    return bucket[variant % bucket.length];
  }

  function drawToolGlyph(ctx, tool, tier) {
    const info = CONTENT.getToolInfo(tool, tier) || CONTENT.getToolInfo(tool, 1);
    const tierColor = info.color;
    const tierLight = tier === 3 ? "#ffffff" : tier === 2 ? "#bdc6c8" : "#d9a66b";
    const handle = "#8d643d";
    const handleLight = "#c08e58";
    const outline = "#241b13";
    ctx.save();
    if (tool === "pickaxe") {
      ctx.rotate(-0.58);
      px(ctx, -4, -2, 8, 26, outline);
      px(ctx, -3, 0, 6, 24, handle);
      px(ctx, -1, 1, 2, 21, handleLight);
      px(ctx, -18, -19, 36, 9, outline);
      px(ctx, -16, -17, 32, 5, tierColor);
      px(ctx, -15, -17, 30, 1, tierLight);
      px(ctx, -20, -15, 8, 9, outline);
      px(ctx, -18, -14, 6, 7, tierColor);
      px(ctx, 12, -15, 8, 9, outline);
      px(ctx, 12, -14, 6, 7, tierColor);
      px(ctx, -18, -14, 6, 1, "rgba(255,255,255,0.38)");
      px(ctx, 12, -14, 6, 1, "rgba(255,255,255,0.38)");
      px(ctx, -10, -15, 12, 1, "rgba(255,255,255,0.24)");
    } else if (tool === "axe") {
      ctx.rotate(-0.52);
      px(ctx, -3, -3, 7, 27, outline);
      px(ctx, -2, -1, 5, 25, handle);
      px(ctx, 0, 0, 2, 22, handleLight);
      ctx.beginPath();
      ctx.moveTo(1, -19);
      ctx.lineTo(20, -17);
      ctx.lineTo(23, -4);
      ctx.lineTo(12, 3);
      ctx.lineTo(1, -1);
      ctx.closePath();
      ctx.fillStyle = outline;
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(3, -17);
      ctx.lineTo(18, -15);
      ctx.lineTo(20, -6);
      ctx.lineTo(11, -1);
      ctx.lineTo(3, -3);
      ctx.closePath();
      ctx.fillStyle = tierColor;
      ctx.fill();
      px(ctx, 5, -15, 10, 2, tierLight);
      px(ctx, 4, -12, 7, 1, "rgba(255,255,255,0.22)");
    } else if (tool === "sword") {
      ctx.rotate(-0.66);
      px(ctx, -3, -1, 6, 18, outline);
      px(ctx, -2, 0, 4, 17, "#74502f");
      px(ctx, 0, 1, 1, 13, "#b0804e");
      px(ctx, -11, -7, 22, 6, outline);
      px(ctx, -9, -6, 18, 3, tierColor);
      px(ctx, -8, -6, 16, 1, tierLight);
      px(ctx, -3, -25, 7, 22, outline);
      px(ctx, -2, -24, 5, 20, tierColor);
      px(ctx, -2, -24, 1, 18, "rgba(255,255,255,0.55)");
      px(ctx, -1, -27, 3, 5, tierColor);
      px(ctx, -5, -13, 10, 3, outline);
      px(ctx, -3, -14, 6, 2, "#c7a76e");
    }
    ctx.restore();
  }

  function drawBlockIcon(ctx, key, size, state) {
    const item = CONTENT.ITEMS[key];
    if (!item || item.kind !== "block") {
      return;
    }
    const blockId = item.block;
    if (blockId === B.TORCH || blockId === B.LANTERN || blockId === B.CAMPFIRE) {
      drawSpecialBlockIcon(ctx, key, size);
      return;
    }
    const sprite = getBlockSprite(blockId, 0);
    if (!sprite) {
      return;
    }
    const inset = Math.round(size * 0.1);
    const drawSize = size - inset * 2;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
    ctx.fillRect(inset + 3, inset + 4, drawSize, drawSize);
    ctx.drawImage(sprite, inset, inset, drawSize, drawSize);
    ctx.strokeStyle = "rgba(239, 229, 201, 0.20)";
    ctx.lineWidth = 1;
    ctx.strokeRect(inset + 0.5, inset + 0.5, drawSize - 1, drawSize - 1);
    ctx.restore();
  }

  function drawSpecialBlockIcon(ctx, key, size) {
    ctx.save();
    ctx.translate(size / 2, size / 2);
    if (key === "torch") {
      const scale = size / 64;
      ctx.scale(scale, scale);
      px(ctx, -2, 2, 4, 25, "#5d4127");
      px(ctx, -1, 3, 2, 22, "#9f7448");
      drawFlame(ctx, 0, -4, 1.7, 0.7, 0);
      px(ctx, -10, 26, 20, 3, "rgba(42, 29, 18, 0.6)");
    } else if (key === "lantern") {
      const scale = size / 64;
      ctx.scale(scale, scale);
      ctx.strokeStyle = "#4e3d2b";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(0, -18, 9, Math.PI, 0);
      ctx.stroke();
      px(ctx, -11, -12, 22, 30, "#322a1f");
      px(ctx, -8, -9, 16, 24, "#5c4630");
      px(ctx, -6, -6, 12, 18, "#e6b967");
      px(ctx, -4, -4, 8, 14, "#ffe4a2");
      drawFlame(ctx, 0, 4, 0.9, 0.8, 2);
      px(ctx, -13, -13, 26, 3, "#8f764e");
      px(ctx, -13, 17, 26, 3, "#7d6443");
      px(ctx, -9, 20, 4, 5, "#4f3b27");
      px(ctx, 5, 20, 4, 5, "#4f3b27");
      px(ctx, 0, -2, 1, 8, "#815d31");
    } else if (key === "campfire") {
      const scale = size / 64;
      ctx.scale(scale, scale);
      px(ctx, -22, 15, 44, 6, "rgba(31, 24, 16, 0.65)");
      px(ctx, -20, 6, 40, 8, "#745132");
      px(ctx, -14, 10, 30, 6, "#5c3e28");
      px(ctx, -22, 3, 7, 9, "#575956");
      px(ctx, 16, 3, 7, 9, "#666764");
      drawFlame(ctx, 0, -1, 2.0, 0.6, 3);
      ctx.fillStyle = "rgba(100, 93, 78, 0.22)";
      ctx.beginPath();
      ctx.arc(4, -26, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(10, -37, 8, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawItemIcon(canvas, key, state) {
    ensureArt();
    const ctx = canvas.getContext("2d");
    const size = canvas.width;
    ctx.clearRect(0, 0, size, size);
    ctx.imageSmoothingEnabled = false;
    if (!key) {
      return;
    }
    if (key === "pickaxe" || key === "axe" || key === "sword") {
      const tool = state && state.tools ? state.tools[key] : null;
      const tier = tool ? tool.tier : 1;
      ctx.save();
      ctx.translate(size / 2, size / 2 + 3);
      const scale = size / 68;
      ctx.scale(scale, scale);
      drawToolGlyph(ctx, key, tier);
      ctx.restore();
      return;
    }
    const item = CONTENT.ITEMS[key];
    if (!item) {
      return;
    }
    if (item.kind === "block") {
      drawBlockIcon(ctx, key, size, state);
      return;
    }
    ctx.save();
    ctx.translate(size / 2, size / 2);
    const scale = size / 58;
    ctx.scale(scale, scale);
    if (key === "stick") {
      ctx.rotate(-0.7);
      px(ctx, -3, -17, 6, 36, "#4d3824");
      px(ctx, -1, -16, 2, 33, "#8f6742");
      px(ctx, 1, -16, 1, 30, "#b18759");
    } else if (key === "coal") {
      ctx.beginPath();
      ctx.moveTo(-15, -7);
      ctx.lineTo(-8, -16);
      ctx.lineTo(8, -14);
      ctx.lineTo(16, -3);
      ctx.lineTo(11, 13);
      ctx.lineTo(-8, 15);
      ctx.lineTo(-16, 5);
      ctx.closePath();
      ctx.fillStyle = "#232325";
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(-9, -10);
      ctx.lineTo(4, -12);
      ctx.lineTo(10, -5);
      ctx.lineTo(3, -3);
      ctx.lineTo(-6, -4);
      ctx.closePath();
      ctx.fillStyle = "#44464a";
      ctx.fill();
      px(ctx, -1, 4, 4, 3, "#5a5a58");
    } else if (key === "iron") {
      ctx.beginPath();
      ctx.moveTo(-15, 2);
      ctx.lineTo(-5, -15);
      ctx.lineTo(12, -10);
      ctx.lineTo(16, 5);
      ctx.lineTo(7, 16);
      ctx.lineTo(-10, 12);
      ctx.closePath();
      ctx.fillStyle = "#9b6a45";
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(-8, -3);
      ctx.lineTo(-2, -12);
      ctx.lineTo(8, -8);
      ctx.lineTo(10, 1);
      ctx.lineTo(3, 6);
      ctx.lineTo(-6, 4);
      ctx.closePath();
      ctx.fillStyle = "#c99563";
      ctx.fill();
      px(ctx, 0, -3, 4, 2, "#f2ce9b");
    } else if (key === "gem") {
      ctx.rotate(0.2);
      ctx.beginPath();
      ctx.moveTo(0, -18);
      ctx.lineTo(14, -4);
      ctx.lineTo(6, 16);
      ctx.lineTo(-9, 13);
      ctx.lineTo(-16, -3);
      ctx.closePath();
      ctx.fillStyle = "#2b6f62";
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(0, -14);
      ctx.lineTo(9, -3);
      ctx.lineTo(5, 11);
      ctx.lineTo(-5, 10);
      ctx.lineTo(-12, -2);
      ctx.closePath();
      ctx.fillStyle = "#4bd0ac";
      ctx.fill();
      px(ctx, 0, -10, 2, 9, "#a5ffe6");
      px(ctx, -7, -1, 5, 2, "#8af0d0");
    }
    ctx.restore();
  }

  function drawFlame(ctx, x, y, scale, alpha, seed) {
    const flicker = Math.sin(performance.now() / 90 + seed * 2.7) * 1.4;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);
    ctx.globalAlpha = alpha;
    px(ctx, -4, -1 + flicker, 8, 7, "#db7436");
    px(ctx, -3, -5 + flicker * 0.5, 6, 7, "#f2a23e");
    px(ctx, -2, -8 - flicker * 0.4, 4, 6, "#ffd369");
    px(ctx, -1, -10 - flicker * 0.7, 2, 4, "#fff1b3");
    ctx.restore();
  }

  function drawTorch(ctx, sx, sy, support, seed) {
    const flameX = sx + 16;
    const flameY = sy + 10;
    ctx.save();
    if (support === "left") {
      px(ctx, sx + 4, sy + 16, 11, 3, "#5c3e27");
      px(ctx, sx + 10, sy + 14, 3, 5, "#9b6b40");
      px(ctx, sx + 14, sy + 12, 4, 3, "#6c4b2d");
      drawFlame(ctx, sx + 14, sy + 11, 0.9, 0.95, seed);
    } else if (support === "right") {
      px(ctx, sx + 17, sy + 16, 11, 3, "#5c3e27");
      px(ctx, sx + 19, sy + 14, 3, 5, "#9b6b40");
      px(ctx, sx + 14, sy + 12, 4, 3, "#6c4b2d");
      drawFlame(ctx, sx + 18, sy + 11, 0.9, 0.95, seed);
    } else {
      const y = support === "above" ? sy + 22 : sy + 8;
      px(ctx, sx + 15, sy + 15, 2, support === "above" ? 15 : 15, "#5e432a");
      px(ctx, sx + 16, sy + 16, 1, 13, "#a57649");
      drawFlame(ctx, sx + 16, y, 1, 0.95, seed);
    }
    ctx.restore();
  }

  function drawLantern(ctx, sx, sy, support, seed) {
    ctx.save();
    if (support === "above") {
      ctx.strokeStyle = "#3c3023";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx + 16, sy + 1);
      ctx.lineTo(sx + 16, sy + 8);
      ctx.stroke();
    }
    const top = support === "above" ? sy + 8 : sy + 12;
    px(ctx, sx + 10, top - 2, 12, 4, "#735536");
    px(ctx, sx + 8, top + 2, 16, 17, "#3a2d20");
    px(ctx, sx + 10, top + 4, 12, 13, "#6c4e31");
    px(ctx, sx + 12, top + 6, 8, 9, "#d9a453");
    px(ctx, sx + 13, top + 6, 6, 8, "#ffd982");
    drawFlame(ctx, sx + 16, top + 14, 0.75, 0.85, seed);
    px(ctx, sx + 11, top + 17, 10, 3, "#29231c");
    px(ctx, sx + 13, top + 20, 2, 3, "#5b4630");
    px(ctx, sx + 17, top + 20, 2, 3, "#5b4630");
    px(ctx, sx + 15, top + 8, 2, 5, "#8b6739");
    if (support === "left") {
      px(ctx, sx + 2, top + 6, 8, 2, "#4a3926");
    } else if (support === "right") {
      px(ctx, sx + 22, top + 6, 8, 2, "#4a3926");
    }
    ctx.restore();
  }

  function drawCampfire(ctx, sx, sy, seed) {
    const t = performance.now() / 1000;
    ctx.save();
    px(ctx, sx + 1, sy + 25, 30, 4, "rgba(24, 20, 14, 0.45)");
    px(ctx, sx + 3, sy + 23, 26, 3, "#5e4630");
    px(ctx, sx + 1, sy + 17, 10, 6, "#6e6e64");
    px(ctx, sx + 21, sy + 18, 10, 5, "#79786d");
    px(ctx, sx + 5, sy + 15, 5, 11, "#63452d");
    px(ctx, sx + 20, sy + 14, 5, 12, "#725033");
    px(ctx, sx + 13, sy + 20, 7, 3, "#945e32");
    drawFlame(ctx, sx + 16, sy + 13, 1.9, 0.98, seed);
    drawFlame(ctx, sx + 10, sy + 17, 0.85, 0.72, seed + 3);
    ctx.globalAlpha = 0.18;
    ctx.fillStyle = "#b9ad95";
    for (let i = 0; i < 4; i += 1) {
      const drift = Math.sin(t * 0.7 + i * 1.9 + seed) * 4;
      ctx.beginPath();
      ctx.arc(sx + 16 + drift, sy - 1 - i * 8, 3 + i, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawSurfacePlant(ctx, sx, sy, seed, time) {
    const kind = seed % 100;
    const sway = Math.sin(time * 1.5 + seed * 0.37) * 1.3;
    ctx.save();
    if (kind < 47) {
      const strands = 4 + (seed % 3);
      for (let i = 0; i < strands; i += 1) {
        const offset = (i - (strands - 1) / 2) * 5;
        const height = 10 + ((seed + i * 11) % 11);
        ctx.strokeStyle = i % 3 === 0 ? "#a8ca65" : i % 3 === 1 ? "#7baa51" : "#5c873d";
        ctx.lineWidth = i % 3 === 0 ? 2.5 : 2;
        ctx.beginPath();
        ctx.moveTo(sx + 16 + offset, sy);
        ctx.quadraticCurveTo(
          sx + 16 + offset + sway + (i % 2 === 0 ? 4 : -4),
          sy - height * 0.55,
          sx + 16 + offset + sway * 1.8,
          sy - height
        );
        ctx.stroke();
        if (i % 2 === 0) {
          px(ctx, sx + 13 + offset + sway * 0.6, sy - height * 0.62, 4, 2, "#87b65a");
        }
      }
    } else if (kind < 68) {
      const flowerColors = ["#f0ce68", "#ef8f72", "#f3ecd2", "#a9d0e6", "#d89fdd"];
      const color = flowerColors[seed % flowerColors.length];
      ctx.strokeStyle = "#689642";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx + 16, sy);
      ctx.quadraticCurveTo(sx + 16 + sway, sy - 10, sx + 16 + sway, sy - 18);
      ctx.stroke();
      px(ctx, sx + 8, sy - 6, 6, 2, "#74a14a");
      px(ctx, sx + 19, sy - 4, 6, 2, "#74a14a");
      px(ctx, sx + 13, sy - 12, 4, 2, "#6c9745");
      const fx = sx + 16 + sway;
      const fy = sy - 20;
      px(ctx, fx - 3, fy - 4, 6, 5, color);
      px(ctx, fx - 5, fy - 1, 10, 4, color);
      px(ctx, fx - 2, fy + 2, 4, 3, color);
      px(ctx, fx - 1, fy, 3, 2, "#f8e29a");
    } else if (kind < 82) {
      const color = seed % 2 === 0 ? "#d8c894" : "#d17a5b";
      px(ctx, sx + 16, sy - 6, 2, 6, "#847052");
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.ellipse(sx + 18, sy - 8, 6, 3.5, -0.45, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255, 243, 202, 0.34)";
      ctx.beginPath();
      ctx.ellipse(sx + 19, sy - 9, 2.5, 1.4, -0.45, 0, Math.PI * 2);
      ctx.fill();
      px(ctx, sx + 16, sy - 12, 1, 5, "#6f5a3d");
    } else if (kind < 93) {
      px(ctx, sx + 13, sy - 3, 5, 3, "#7f7d6c");
      px(ctx, sx + 17, sy - 2, 3, 2, "#666556");
      px(ctx, sx + 12, sy - 5, 2, 2, "#6d7360");
    } else {
      const mushrooms = seed % 2 === 0;
      if (mushrooms) {
        px(ctx, sx + 14, sy - 5, 2, 5, "#d7c8a2");
        px(ctx, sx + 10, sy - 7, 9, 3, "#b56b55");
        px(ctx, sx + 12, sy - 8, 5, 1, "#d6896c");
      } else {
        px(ctx, sx + 10, sy - 2, 11, 2, "#777b65");
      }
    }
    ctx.restore();
  }

  function drawCaveDecor(ctx, sx, sy, seed, time) {
    ctx.save();
    if (seed % 5 === 0) {
      const glow = 0.55 + Math.sin(time * 2 + seed) * 0.2;
      ctx.globalAlpha = glow;
      px(ctx, sx + 10, sy + 27, 1, 3, "#7f9b90");
      px(ctx, sx + 7, sy + 25, 7, 3, "#3a6d68");
      px(ctx, sx + 8, sy + 24, 5, 2, "#58aaa0");
      px(ctx, sx + 21, sy + 27, 1, 3, "#7f9b90");
      px(ctx, sx + 18, sy + 26, 6, 2, "#38645f");
      px(ctx, sx + 19, sy + 25, 4, 2, "#55a89e");
      ctx.globalAlpha = 1;
    }
    if (seed % 11 === 0) {
      const len = 8 + (seed % 15);
      ctx.strokeStyle = "rgba(38, 58, 40, 0.8)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx + 8, sy);
      ctx.bezierCurveTo(sx + 12, sy + len * 0.5, sx + 4, sy + len, sx + 8 + Math.sin(time + seed) * 2, sy + len + 5);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawPlayer(ctx, player, state, camX, camY, time, mining) {
    const sx = Math.round(player.x * TILE - camX);
    const sy = Math.round(player.y * TILE - camY);
    const moving = Math.abs(player.vx) > 0.25 && player.onGround;
    const walk = moving ? Math.sin(player.walkPhase) : 0;
    const air = !player.onGround;
    const bob = moving ? Math.abs(Math.sin(player.walkPhase)) * 0.55 : Math.sin(time * 2.2) * 0.25;
    const facing = player.facing >= 0 ? 1 : -1;
    const blink = player.invulnerable > 0 && Math.floor(time * 22) % 2 === 0;

    ctx.save();
    ctx.globalAlpha = blink ? 0.48 : 1;
    ctx.fillStyle = "rgba(10, 16, 12, 0.28)";
    ctx.beginPath();
    ctx.ellipse(sx, sy, air ? 8 : 13, air ? 2.5 : 4, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.translate(sx, sy);
    ctx.scale(2 * facing, 2);

    // Scarf tail catches the wind behind the traveller.
    ctx.fillStyle = "#a35e37";
    ctx.fillRect(-7.8, -18.8 + bob, 4.2, 2.2);
    ctx.fillRect(-10.1 - (moving ? 0.6 : 0), -18.2 + bob + walk * 0.25, 3.2, 1.8);
    ctx.fillStyle = "#cc8050";
    ctx.fillRect(-7.5, -18.5 + bob, 4, 1.1);

    // Backpack.
    ctx.fillStyle = "#4b3725";
    ctx.fillRect(-7.8, -18.8 + bob, 4.7, 8.6);
    ctx.fillStyle = "#7b5939";
    ctx.fillRect(-7.3, -18.2 + bob, 3.7, 7.2);
    ctx.fillStyle = "#9e7447";
    ctx.fillRect(-6.4, -17.5 + bob, 2, 1.4);
    ctx.fillStyle = "#3e2d1f";
    ctx.fillRect(-6.4, -12.5 + bob, 2, 1.5);

    // Legs and boots.
    const legLift = air ? 2.4 : Math.max(0, walk) * 1.8;
    const legLift2 = air ? 1.4 : Math.max(0, -walk) * 1.8;
    ctx.fillStyle = "#27362d";
    ctx.fillRect(-4.2, -9.2, 3.7, 7.2 - legLift);
    ctx.fillRect(0.5, -9.2, 3.7, 7.2 - legLift2);
    ctx.fillStyle = "#374b3c";
    ctx.fillRect(-4.2, -9.2, 2.4, 6.2 - legLift);
    ctx.fillRect(0.5 + 1.2, -9.2, 2.2, 6.2 - legLift2);
    ctx.fillStyle = "#2b211a";
    ctx.fillRect(-4.6, -2.8 - legLift, 4.4, 2.8);
    ctx.fillRect(0.2, -2.8 - legLift2, 4.4, 2.8);
    ctx.fillStyle = "#56402b";
    ctx.fillRect(-4.6, -2.8 - legLift, 4.4, 0.8);
    ctx.fillRect(0.2, -2.8 - legLift2, 4.4, 0.8);

    // Coat and belt.
    ctx.fillStyle = "#1e2c25";
    ctx.fillRect(-5.2, -20.3 + bob, 10.4, 12);
    ctx.fillStyle = "#3c5e48";
    ctx.fillRect(-4.6, -19.8 + bob, 9.2, 10.4);
    ctx.fillStyle = "#4e7659";
    ctx.fillRect(-4.4, -19.6 + bob, 3.3, 8.4);
    ctx.fillStyle = "#2f4d3b";
    ctx.fillRect(1.4, -19.6 + bob, 3.2, 9.6);
    ctx.fillStyle = "#c99d5e";
    ctx.fillRect(-4.7, -11.3 + bob, 9.4, 1.6);
    ctx.fillStyle = "#5b4128";
    ctx.fillRect(0.1, -11.1 + bob, 2.1, 1.3);
    ctx.fillStyle = "#d6ad6c";
    ctx.fillRect(0.7, -10.8 + bob, 0.8, 0.8);

    // Back arm.
    ctx.fillStyle = "#2f4d3b";
    ctx.fillRect(-5.6, -18.2 + bob, 2.2, 6.3);
    ctx.fillStyle = "#d4a271";
    ctx.fillRect(-5.5, -12.4 + bob, 2.1, 1.7);

    // Head.
    ctx.fillStyle = "#18231d";
    ctx.fillRect(-4.9, -28.6 + bob, 9.8, 9.4);
    ctx.fillStyle = "#e2b282";
    ctx.fillRect(-4.2, -26.9 + bob, 8.4, 7.1);
    ctx.fillStyle = "#c99165";
    ctx.fillRect(1.9, -25.1 + bob, 2.2, 3.7);
    ctx.fillStyle = "#f0c999";
    ctx.fillRect(-3.6, -26 + bob, 3.4, 2.3);
    // Beanie.
    ctx.fillStyle = "#2a5c4c";
    ctx.fillRect(-5.1, -29.2 + bob, 10.2, 4.2);
    ctx.fillStyle = "#397763";
    ctx.fillRect(-4.6, -29 + bob, 9.2, 1.6);
    ctx.fillStyle = "#c69459";
    ctx.fillRect(-5.1, -25.6 + bob, 10.2, 1.5);
    ctx.fillStyle = "#e4b671";
    ctx.fillRect(2.9, -29 + bob, 1.7, 1);
    // Face.
    ctx.fillStyle = "#1c2922";
    ctx.fillRect(1.4, -24.2 + bob, 1.3, 1.6);
    ctx.fillRect(3.7, -24.1 + bob, 0.8, 0.8);
    ctx.fillStyle = "rgba(182, 101, 68, 0.55)";
    ctx.fillRect(-0.8, -22.7 + bob, 1.7, 0.7);
    // Scarf.
    ctx.fillStyle = "#b96d3f";
    ctx.fillRect(-4.7, -20.2 + bob, 9.4, 1.8);
    ctx.fillStyle = "#d68c53";
    ctx.fillRect(-4.2, -20 + bob, 7.7, 0.8);

    // Front arm and held item. The arm pivots at the shoulder.
    const shoulderX = 4.2;
    const shoulderY = -18.2 + bob;
    let swingAngle = -0.42;
    if (mining) {
      swingAngle += (Math.sin(time * 18) * 0.5 + 0.5) * 0.85;
    }
    if (player.swing > 0) {
      swingAngle += Math.sin(Math.min(1, player.swing / 0.24) * Math.PI) * 1.35;
    }
    ctx.save();
    ctx.translate(shoulderX, shoulderY);
    ctx.rotate(swingAngle);
    ctx.fillStyle = "#1e2c25";
    ctx.fillRect(-1.5, -1, 3.2, 7.4);
    ctx.fillStyle = "#426a50";
    ctx.fillRect(-1.1, 0, 2.5, 6.8);
    ctx.fillStyle = "#d4a271";
    ctx.fillRect(-1.1, 5.9, 2.6, 1.8);
    ctx.fillStyle = "#1b261f";
    ctx.fillRect(-1.2, 5.7, 2.8, 0.5);

    const selected = state.hotbar[state.selectedSlot] || null;
    if (selected === "pickaxe" || selected === "axe" || selected === "sword") {
      if (state.tools[selected]) {
        ctx.save();
        ctx.translate(0.5, 6.6);
        ctx.rotate(0.16);
        ctx.scale(0.28, 0.28);
        drawToolGlyph(ctx, selected, state.tools[selected].tier);
        ctx.restore();
      }
    } else if (selected && CONTENT.ITEMS[selected] && CONTENT.ITEMS[selected].kind === "block") {
      const sprite = getBlockSprite(CONTENT.ITEMS[selected].block, 0);
      if (sprite) {
        ctx.save();
        ctx.translate(0.8, 6.2);
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(sprite, 0, 0, 7, 7);
        ctx.restore();
      }
    }
    ctx.restore();

    // A small attack streak.
    if (player.swing > 0) {
      const progress = 1 - player.swing / 0.24;
      ctx.strokeStyle = "rgba(244, 231, 190, " + (0.55 * Math.sin(progress * Math.PI)).toFixed(3) + ")";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(5.5, -13.5, 10.5, -0.9 + progress * 0.9, 0.3 + progress * 1.2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawHollow(ctx, enemy, camX, camY, time, daylight) {
    const sx = Math.round(enemy.x * TILE - camX);
    const sy = Math.round(enemy.y * TILE - camY);
    const face = enemy.facing >= 0 ? 1 : -1;
    const bob = Math.sin(time * 4.2 + enemy.bobSeed * 7) * 2;
    const hurtFlash = enemy.hurtTimer > 0 && Math.floor(time * 30) % 2 === 0;
    const alpha = enemy.dying ? Math.max(0, enemy.dying) : 1;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "rgba(6, 9, 14, 0.34)";
    ctx.beginPath();
    ctx.ellipse(sx, sy, 12, 4, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.translate(sx, sy + bob);
    ctx.scale(face, 1);

    // Wispy tails.
    ctx.fillStyle = "#171a27";
    for (let i = 0; i < 3; i += 1) {
      const drift = Math.sin(time * 2.2 + i * 1.8 + enemy.bobSeed) * 1.6;
      ctx.beginPath();
      ctx.moveTo(-9 + i * 7, -11);
      ctx.lineTo(-12 + i * 8 + drift, -1);
      ctx.lineTo(-5 + i * 7, -5);
      ctx.closePath();
      ctx.fill();
    }
    // Body.
    ctx.fillStyle = hurtFlash ? "#e8dab6" : "#222437";
    ctx.beginPath();
    ctx.moveTo(-12, -26);
    ctx.quadraticCurveTo(-16, -38, -6, -43);
    ctx.quadraticCurveTo(0, -48, 8, -42);
    ctx.quadraticCurveTo(17, -35, 11, -22);
    ctx.lineTo(9, -8);
    ctx.lineTo(2, -12);
    ctx.lineTo(-4, -7);
    ctx.lineTo(-8, -13);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = hurtFlash ? "#fff2ce" : "#0c0d17";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Tiny horns.
    ctx.strokeStyle = hurtFlash ? "#fff2ce" : "#4b5366";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-8, -39);
    ctx.lineTo(-12, -45);
    ctx.moveTo(7, -40);
    ctx.lineTo(10, -46);
    ctx.stroke();

    // Eyes and glint.
    ctx.fillStyle = hurtFlash ? "#202127" : "#d9f0c8";
    ctx.fillRect(0.5, -35, 3.2, 2.3);
    ctx.fillRect(6.2, -35, 2.2, 2.3);
    ctx.fillStyle = "#7fa77c";
    ctx.fillRect(0.7, -34.5, 1.1, 1);
    ctx.fillRect(6.4, -34.5, 0.9, 1);
    ctx.fillStyle = "rgba(219, 240, 202, 0.15)";
    ctx.beginPath();
    ctx.ellipse(4, -26, 10, 8, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    if (enemy.health < enemy.maxHealth && !enemy.dying) {
      const width = 28;
      const left = sx - width / 2;
      const top = sy - 60 + bob;
      ctx.fillStyle = "rgba(9, 12, 15, 0.8)";
      ctx.fillRect(left - 1, top - 1, width + 2, 5);
      ctx.fillStyle = "#b86f59";
      ctx.fillRect(left, top, width * Math.max(0, enemy.health / enemy.maxHealth), 3);
      ctx.fillStyle = "rgba(244, 220, 174, 0.25)";
      ctx.fillRect(left, top, width * Math.max(0, enemy.health / enemy.maxHealth), 1);
    }
  }

  function initArt() {
    ensureArt();
  }

  root.MosswildArt = {
    TILE,
    init: initArt,
    getBlockSprite,
    getCaveSprite,
    drawItemIcon,
    drawToolGlyph,
    drawPlayer,
    drawHollow,
    drawTorch,
    drawLantern,
    drawCampfire,
    drawSurfacePlant,
    drawCaveDecor,
    drawSpecialBlockIcon,
    hash2
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
