(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./content.js"));
  } else {
    root.MosswildWorld = factory(root.MosswildConfig, root.MosswildContent);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, CONTENT) {
  "use strict";

  if (!CONFIG || !CONTENT) {
    throw new Error("MosswildConfig and MosswildContent are required before MosswildWorld");
  }

  const B = CONFIG.block;

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

  function smoothstep(edge0, edge1, value) {
    const t = Math.max(0, Math.min(1, (value - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  function valueNoise1(seed, x) {
    const lower = Math.floor(x);
    const fraction = x - lower;
    const a = (hash2(seed, lower, 17) / 4294967295);
    const b = (hash2(seed, lower + 1, 17) / 4294967295);
    const eased = fraction * fraction * (3 - 2 * fraction);
    return a + (b - a) * eased;
  }

  function fbm1(seed, x) {
    return valueNoise1(seed, x) * 0.56
      + valueNoise1(seed ^ 0xa5a5a5, x * 2.03) * 0.29
      + valueNoise1(seed ^ 0x51ed27, x * 4.07) * 0.15;
  }

  function indexOf(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return -1;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return -1;
    }
    return y * world.width + x;
  }

  function getBlock(world, x, y) {
    const index = indexOf(world, x, y);
    return index < 0 ? null : world.data[index];
  }

  function setBlock(world, x, y, block) {
    const index = indexOf(world, x, y);
    if (index < 0) {
      return false;
    }
    world.data[index] = block;
    world.revision = (world.revision || 0) + 1;
    return true;
  }

  function isAir(world, x, y) {
    return getBlock(world, x, y) === B.AIR;
  }

  function isSolid(world, x, y) {
    if (x < 0 || x >= world.width || y >= world.height) {
      return true;
    }
    if (y < 0) {
      return false;
    }
    const def = CONTENT.getBlockDef(getBlock(world, x, y));
    return Boolean(def.solid);
  }

  function makeSurface(width) {
    return new Int16Array(width);
  }

  function generateHeights(seed) {
    const width = CONFIG.worldWidth;
    const heights = makeSurface(width);
    const center = Math.floor(width / 2);
    const hillPhase = (seed % 1000) / 170;

    for (let x = 0; x < width; x += 1) {
      const broad = (fbm1(seed ^ 0x3f19a7, x * 0.021 + 4.2) - 0.5) * 16;
      const rolling = (valueNoise1(seed ^ 0x7bf31, x * 0.061 + 1.8) - 0.5) * 5.6;
      const ripple = Math.sin(x * 0.14 + hillPhase) * 0.7;
      let height = 40 + broad + rolling + ripple;

      // A gentler shelf around spawn, without making the valley perfectly flat.
      const distance = Math.abs(x - center);
      const shelf = smoothstep(5, 24, distance);
      const spawnHeight = 40 + Math.sin(x * 0.09) * 0.25;
      height = spawnHeight * (1 - shelf) + height * shelf;

      heights[x] = Math.max(27, Math.min(54, Math.round(height)));
    }

    // A little clearing so the player always has room to breathe and build.
    for (let x = center - 6; x <= center + 6; x += 1) {
      if (x >= 0 && x < width) {
        heights[x] = 40;
      }
    }
    return heights;
  }

  function fillTerrain(world, heights, seed) {
    const width = world.width;
    const height = world.height;
    const dirtRandom = mulberry32(seed ^ 0x88c1a3);

    for (let x = 0; x < width; x += 1) {
      const surface = heights[x];
      const dirtDepth = 4 + Math.floor(dirtRandom() * 3);
      for (let y = surface; y < height; y += 1) {
        let block = B.STONE;
        if (y >= height - 2) {
          block = B.BEDROCK;
        } else if (y === surface) {
          block = B.GRASS;
        } else if (y < surface + dirtDepth) {
          block = B.DIRT;
        }
        world.data[y * width + x] = block;
      }
    }
  }

  function carveCave(world, startX, startY, steps, rng) {
    let x = startX;
    let y = startY;
    let direction = rng() < 0.5 ? -1 : 1;
    const width = world.width;
    const height = world.height;

    for (let step = 0; step < steps; step += 1) {
      const surface = world.surface[Math.max(0, Math.min(width - 1, x))] || 40;
      const minY = Math.max(4, surface + 4);
      if (y >= minY && y < height - 3) {
        const tall = rng() < 0.32 ? 1 : 0;
        for (let dy = -1; dy <= tall; dy += 1) {
          for (let dx = -1; dx <= 1; dx += 1) {
            if (dx === -1 && dy === tall && rng() < 0.6) {
              continue;
            }
            const px = x + dx;
            const py = y + dy;
            if (px <= 1 || px >= width - 2 || py <= 1 || py >= height - 2) {
              continue;
            }
            const block = getBlock(world, px, py);
            if (block === B.STONE || block === B.DIRT || block === B.GRASS) {
              setBlock(world, px, py, B.AIR);
            } else if (block === B.COAL_ORE || block === B.IRON_ORE || block === B.GEM_ORE) {
              // Caves keep their ore glints unless carving opens a fresh face.
              if (rng() < 0.2) {
                setBlock(world, px, py, B.AIR);
              }
            }
          }
        }
      }

      x += direction;
      if (x <= 3 || x >= width - 3) {
        direction *= -1;
      }
      if (rng() < 0.13) {
        direction *= -1;
      }
      if (rng() < 0.22) {
        y += rng() < 0.5 ? -1 : 1;
      }
      if (rng() < 0.055) {
        y += rng() < 0.5 ? -1 : 1;
      }
      y = Math.max(surface + 4, Math.min(height - 5, y));
    }
  }

  function carveRoundRoom(world, centerX, centerY, radiusX, radiusY) {
    for (let dy = -radiusY; dy <= radiusY; dy += 1) {
      for (let dx = -radiusX; dx <= radiusX; dx += 1) {
        if ((dx * dx) / (radiusX * radiusX) + (dy * dy) / (radiusY * radiusY) > 1) {
          continue;
        }
        const x = centerX + dx;
        const y = centerY + dy;
        if (x <= 1 || x >= world.width - 2 || y <= 1 || y >= world.height - 2) {
          continue;
        }
        const surface = world.surface[x] || 40;
        if (y < surface + 4) {
          continue;
        }
        const block = getBlock(world, x, y);
        if (block !== null && !CONTENT.getBlockDef(block).unbreakable) {
          setBlock(world, x, y, B.AIR);
        }
      }
    }
  }

  function carveSpawnStair(world, heights, seed) {
    const center = Math.floor(world.width / 2);
    const startX = center + 8;
    const startSurface = heights[Math.max(0, Math.min(world.width - 1, startX))] || 40;
    const rng = mulberry32(seed ^ 0x2b16af);
    const carved = [];

    for (let step = 0; step < 44; step += 1) {
      const x = startX + step;
      if (x >= world.width - 2) {
        break;
      }
      const floorY = startSurface + Math.floor(step / 2);
      for (let y = floorY - 1; y >= floorY - 3; y -= 1) {
        const block = getBlock(world, x, y);
        if (block !== null && !CONTENT.getBlockDef(block).unbreakable) {
          setBlock(world, x, y, B.AIR);
          carved.push({ x, y });
        }
      }
      // Widen the stair a little at the mouth so it reads as an invitation.
      if (step < 6) {
        const side = step % 2 === 0 ? -1 : 1;
        const px = startX + step + side;
        if (px > 0 && px < world.width) {
          setBlock(world, px, floorY - 1, B.AIR);
          setBlock(world, px, floorY - 2, B.AIR);
        }
      }
      if (rng() < 0.16) {
        // Store a few ledge blocks near the stair for visual interest.
        const ledgeX = x + 1;
        if (ledgeX < world.width - 1) {
          setBlock(world, ledgeX, floorY, B.STONE);
        }
      }
    }

    return { startX, carved };
  }

  function carveCaves(world, seed) {
    const rng = mulberry32(seed ^ 0x493a2d);
    const count = 16;
    for (let i = 0; i < count; i += 1) {
      const x = 10 + Math.floor(rng() * (world.width - 20));
      const surface = world.surface[x] || 40;
      const depth = 6 + Math.floor(rng() * 28);
      const y = Math.min(world.height - 7, surface + depth);
      const steps = 34 + Math.floor(rng() * 74);
      carveCave(world, x, y, steps, rng);
    }
    for (let i = 0; i < 4; i += 1) {
      const x = 20 + Math.floor(rng() * (world.width - 40));
      const surface = world.surface[x] || 40;
      const y = Math.min(world.height - 8, surface + 18 + Math.floor(rng() * 24));
      carveRoundRoom(world, x, y, 3 + Math.floor(rng() * 3), 2 + Math.floor(rng() * 2));
    }
  }

  function canPlaceOre(world, x, y) {
    if (x < 2 || x >= world.width - 2 || y < 2 || y >= world.height - 3) {
      return false;
    }
    const surface = world.surface[x] || 40;
    return y > surface + 2 && getBlock(world, x, y) === B.STONE;
  }

  function placeOreCluster(world, x, y, blockId, size, rng) {
    let placed = 0;
    for (let attempt = 0; attempt < size * 5 && placed < size; attempt += 1) {
      const radius = 1;
      const px = x + Math.floor(rng() * (radius * 2 + 1)) - radius;
      const py = y + Math.floor(rng() * (radius * 2 + 1)) - radius;
      if (canPlaceOre(world, px, py)) {
        setBlock(world, px, py, blockId);
        placed += 1;
      }
    }
    return placed;
  }

  function addOres(world, seed) {
    const rng = mulberry32(seed ^ 0x7faa19);
    const specs = [
      { block: B.COAL_ORE, clusters: 76, minDepth: 4, depthRange: 26, minSize: 2, maxSize: 5 },
      { block: B.IRON_ORE, clusters: 58, minDepth: 10, depthRange: 34, minSize: 2, maxSize: 4 },
      { block: B.GEM_ORE, clusters: 24, minDepth: 23, depthRange: 38, minSize: 1, maxSize: 3 }
    ];

    specs.forEach(function (spec) {
      for (let i = 0; i < spec.clusters; i += 1) {
        const x = 6 + Math.floor(rng() * (world.width - 12));
        const surface = world.surface[x] || 40;
        const depth = spec.minDepth + Math.floor(rng() * spec.depthRange);
        const y = surface + depth;
        if (y >= world.height - 4) {
          continue;
        }
        const size = spec.minSize + Math.floor(rng() * (spec.maxSize - spec.minSize + 1));
        placeOreCluster(world, x, y, spec.block, size, rng);
      }
    });

    // A visible coal glint near the bottom of the spawn stair so the first
    // descent has a clear reward and a hint of what waits below.
    const stairFloor = (world.surface[Math.floor(world.width / 2) + 10] || 40) + 6;
    const coalX = Math.floor(world.width / 2) + 23;
    if (canPlaceOre(world, coalX, stairFloor + 2)) {
      setBlock(world, coalX, stairFloor + 2, B.COAL_ORE);
      if (canPlaceOre(world, coalX + 1, stairFloor + 2)) {
        setBlock(world, coalX + 1, stairFloor + 2, B.COAL_ORE);
      }
      if (canPlaceOre(world, coalX + 1, stairFloor + 1)) {
        setBlock(world, coalX + 1, stairFloor + 1, B.COAL_ORE);
      }
    }
  }

  function addTree(world, x, seed, style, rng) {
    if (x < 3 || x >= world.width - 3) {
      return false;
    }
    const surface = world.surface[x];
    if (getBlock(world, x, surface) !== B.GRASS || getBlock(world, x, surface - 1) !== B.AIR) {
      return false;
    }
    // A tree needs two quiet rows under it and a little shoulder room.
    for (let dx = -1; dx <= 1; dx += 1) {
      const sx = x + dx;
      if (getBlock(world, sx, world.surface[sx] || 40) !== B.GRASS) {
        return false;
      }
    }

    const trunkHeight = style === "pine"
      ? 7 + Math.floor(rng() * 3)
      : 4 + Math.floor(rng() * 3);
    const topY = surface - trunkHeight;

    for (let y = surface - 1; y >= topY; y -= 1) {
      if (y < 2) {
        return false;
      }
    }

    for (let y = surface - 1; y >= topY; y -= 1) {
      setBlock(world, x, y, B.LOG);
    }

    if (style === "pine") {
      const layers = 4;
      for (let layer = 0; layer < layers; layer += 1) {
        const y = topY + layer - 1;
        const radius = Math.max(1, 3 - layer);
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (dx === 0 && layer < layers - 1 && rng() < 0.35) {
            continue;
          }
          for (let dy = 0; dy < 2; dy += 1) {
            const px = x + dx;
            const py = y + dy;
            if (getBlock(world, px, py) === B.AIR) {
              setBlock(world, px, py, B.LEAVES);
            }
          }
        }
      }
    } else {
      for (let dy = -2; dy <= 2; dy += 1) {
        const radius = dy === -2 || dy === 2 ? 2 : 3;
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (dx === 0 && dy >= 0) {
            continue;
          }
          if (dx * dx + dy * dy > radius * radius + 1) {
            continue;
          }
          const edge = Math.abs(dx) === radius || Math.abs(dy) === 2;
          if (edge && rng() < 0.22) {
            continue;
          }
          const px = x + dx;
          const py = topY + dy;
          if (px > 1 && px < world.width - 1 && getBlock(world, px, py) === B.AIR) {
            setBlock(world, px, py, B.LEAVES);
          }
        }
      }
    }
    return true;
  }

  function addTrees(world, seed, stairStartX) {
    const rng = mulberry32(seed ^ 0x1a83d5);
    const center = Math.floor(world.width / 2);
    const protectedStair = function (x) {
      return x >= stairStartX - 1 && x <= stairStartX + 46;
    };
    const trees = [];
    const forced = [
      { x: center - 9, style: "oak" },
      { x: center + 6, style: "oak" },
      { x: center + 19, style: "pine" },
      { x: center - 24, style: "pine" }
    ];
    forced.forEach(function (tree) {
      if (!protectedStair(tree.x) && addTree(world, tree.x, seed, tree.style, rng)) {
        trees.push(tree);
      }
    });

    let lastTreeX = -10;
    for (let x = 4; x < world.width - 4; x += 1) {
      if (Math.abs(x - center) < 5 || protectedStair(x) || x - lastTreeX < 4) {
        continue;
      }
      const surface = world.surface[x];
      if (getBlock(world, x, surface) !== B.GRASS || getBlock(world, x, surface - 1) !== B.AIR) {
        continue;
      }
      if (rng() > 0.11) {
        continue;
      }
      const style = rng() < 0.26 ? "pine" : "oak";
      if (addTree(world, x, seed, style, rng)) {
        lastTreeX = x;
        trees.push({ x, style });
      }
    }
    return trees;
  }

  function findSpawn(world) {
    const preferred = Math.floor(world.width / 2);
    for (let radius = 0; radius < 40; radius += 1) {
      const options = radius === 0 ? [preferred] : [preferred - radius, preferred + radius];
      for (let i = 0; i < options.length; i += 1) {
        const x = options[i];
        if (x < 1 || x >= world.width - 1) {
          continue;
        }
        const surface = world.surface[x];
        if (getBlock(world, x, surface) === B.GRASS
          && getBlock(world, x, surface - 1) === B.AIR
          && getBlock(world, x, surface - 2) === B.AIR) {
          return { x: x + 0.5, y: surface };
        }
      }
    }
    return { x: preferred + 0.5, y: 40 };
  }

  function createWorld(seedInput) {
    const seed = Number(seedInput) >>> 0;
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const data = new Uint8Array(width * height);
    const heights = generateHeights(seed);
    const world = {
      width,
      height,
      seed,
      data,
      surface: heights,
      revision: 0
    };

    fillTerrain(world, heights, seed);
    const stair = carveSpawnStair(world, heights, seed);
    carveCaves(world, seed);
    addOres(world, seed);
    addTrees(world, seed, stair.startX);

    // A small abandoned camp makes the clearing feel inhabited, and a single
    // torch marks the old stair into the dark below.
    const center = Math.floor(width / 2);
    const campX = center - 3;
    const campSurface = heights[campX];
    if (getBlock(world, campX, campSurface) === B.GRASS
      && getBlock(world, campX, campSurface - 1) === B.AIR) {
      setBlock(world, campX, campSurface - 1, B.CAMPFIRE);
    }
    const torchX = stair.startX - 1;
    const torchSurface = heights[torchX];
    if (getBlock(world, torchX, torchSurface) === B.GRASS
      && getBlock(world, torchX, torchSurface - 1) === B.AIR) {
      setBlock(world, torchX, torchSurface - 1, B.TORCH);
    }

    const spawn = findSpawn(world);
    world.spawn = spawn;
    world.meta = { stairStartX: stair.startX };
    return world;
  }

  function encodeRuns(data) {
    const runs = [];
    if (!data || data.length === 0) {
      return runs;
    }
    let value = data[0];
    let count = 1;
    for (let i = 1; i < data.length; i += 1) {
      if (data[i] === value && count < 65535) {
        count += 1;
      } else {
        runs.push(value, count);
        value = data[i];
        count = 1;
      }
    }
    runs.push(value, count);
    return runs;
  }

  function decodeRuns(runs, expectedLength) {
    if (!Array.isArray(runs) || runs.length % 2 !== 0) {
      throw new Error("Invalid block run data");
    }
    const data = new Uint8Array(expectedLength);
    let offset = 0;
    for (let i = 0; i < runs.length; i += 2) {
      const value = runs[i];
      const count = runs[i + 1];
      if (!Number.isInteger(value) || value < 0 || value > 15) {
        throw new Error("Invalid block id in save");
      }
      if (!Number.isInteger(count) || count < 0) {
        throw new Error("Invalid block run length");
      }
      if (offset + count > expectedLength) {
        throw new Error("Block run data is too long");
      }
      data.fill(value, offset, offset + count);
      offset += count;
    }
    if (offset !== expectedLength) {
      throw new Error("Block run data is too short");
    }
    return data;
  }

  function worldToSave(world) {
    return {
      width: world.width,
      height: world.height,
      seed: world.seed,
      surface: Array.from(world.surface),
      runs: encodeRuns(world.data),
      spawn: world.spawn
    };
  }

  function worldFromSave(payload) {
    if (!payload || typeof payload !== "object") {
      throw new Error("Missing world data");
    }
    const width = Number(payload.width);
    const height = Number(payload.height);
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
      throw new Error("Invalid world dimensions");
    }
    if (width > 512 || height > 256 || width * height > 131072) {
      throw new Error("World save is too large");
    }
    if (!Array.isArray(payload.surface) || payload.surface.length !== width) {
      throw new Error("Invalid surface data");
    }
    const surface = Int16Array.from(payload.surface.map(function (v) {
      if (!Number.isInteger(v) || v < 0 || v >= height) {
        throw new Error("Invalid surface height");
      }
      return v;
    }));
    const data = decodeRuns(payload.runs, width * height);
    const spawn = payload.spawn && Number.isFinite(payload.spawn.x) && Number.isFinite(payload.spawn.y)
      ? { x: Number(payload.spawn.x), y: Number(payload.spawn.y) }
      : { x: width / 2 + 0.5, y: surface[Math.floor(width / 2)] };
    return {
      width,
      height,
      seed: Number(payload.seed) >>> 0,
      data,
      surface,
      spawn,
      revision: 0,
      meta: {}
    };
  }

  function findGroundBelow(world, x, startY) {
    const top = Math.max(1, Math.min(world.height - 2, Math.floor(startY)));
    for (let y = top; y < world.height - 1; y += 1) {
      if (isSolid(world, x, y) && !isSolid(world, x, y - 1)) {
        return y;
      }
    }
    return world.height - 2;
  }

  function countBlocks(world, blockId) {
    let count = 0;
    for (let i = 0; i < world.data.length; i += 1) {
      if (world.data[i] === blockId) {
        count += 1;
      }
    }
    return count;
  }

  return {
    createWorld,
    getBlock,
    setBlock,
    isAir,
    isSolid,
    findGroundBelow,
    findSpawn,
    worldToSave,
    worldFromSave,
    encodeRuns,
    decodeRuns,
    countBlocks,
    indexOf,
    mulberry32,
    hash2
  };
});
