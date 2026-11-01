(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxWorld = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxWorld");
  }

  const W = CONFIG.worldWidth;
  const H = CONFIG.worldHeight;
  const BASE_GROUND = Math.floor(H * 0.65);
  const SEA_LEVEL = BASE_GROUND + 2;
  const BOTTOM_ROW = H - 1;

  function indexOf(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return -1;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return -1;
    }
    return y * world.width + x;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function mix32(value) {
    let n = value >>> 0;
    n = Math.imul(n ^ (n >>> 16), 0x7feb352d) >>> 0;
    n = Math.imul(n ^ (n >>> 15), 0x846ca68b) >>> 0;
    return (n ^ (n >>> 16)) >>> 0;
  }

  function hash2(x, y, seed) {
    return mix32((x | 0) * 374761393 + (y | 0) * 668265263 + seed * 2246822519);
  }

  function unitHash(x, y, seed) {
    return hash2(x, y, seed) / 4294967296;
  }

  function smoothstep(t) {
    return t * t * (3 - 2 * t);
  }

  function valueNoise1D(x, seed) {
    const x0 = Math.floor(x);
    const t = smoothstep(x - x0);
    const a = unitHash(x0, 0, seed);
    const b = unitHash(x0 + 1, 0, seed);
    return a + (b - a) * t;
  }

  function valueNoise2D(x, y, seed) {
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const tx = smoothstep(x - x0);
    const ty = smoothstep(y - y0);
    const a = unitHash(x0, y0, seed);
    const b = unitHash(x0 + 1, y0, seed);
    const c = unitHash(x0, y0 + 1, seed);
    const d = unitHash(x0 + 1, y0 + 1, seed);
    const top = a + (b - a) * tx;
    const bottom = c + (d - c) * tx;
    return top + (bottom - top) * ty;
  }

  function fbm1(x, seed, octaves) {
    let sum = 0;
    let amplitude = 1;
    let total = 0;
    let frequency = 1;
    for (let i = 0; i < octaves; i += 1) {
      sum += valueNoise1D(x * frequency, seed + i * 101) * amplitude;
      total += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return sum / total;
  }

  function createPrng(seed) {
    let state = seed >>> 0;
    return function random() {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function surfaceHeightAt(x, seed) {
    // The amplitude ramp is exactly zero for x <= 14, which keeps the seed
    // contract anchored at column 10 (see tests/world.test.js).
    const ramp = clamp((x - 14) / 26, 0, 1);
    const rolling = fbm1(x * 0.028, seed, 3);
    const detail = valueNoise1D(x * 0.11, seed + 977);
    const shaped = (rolling * 0.7 + detail * 0.3 - 0.5) * 2;
    const height = Math.round(shaped * 11 * ramp);
    return clamp(BASE_GROUND + height, 18, H - 18);
  }

  function makeWorld(seed) {
    const data = new Uint8Array(W * H);
    return {
      width: W,
      height: H,
      seed: seed >>> 0,
      data: data
    };
  }

  function fillTerrain(world, seed) {
    for (let x = 0; x < W; x += 1) {
      const ground = surfaceHeightAt(x, seed);
      const sandy = x > 24 && valueNoise1D(x * 0.06, seed + 555) > 0.74;
      for (let y = ground; y < H; y += 1) {
        let block = CONFIG.blocks.stone;
        if (y === ground) {
          block = sandy ? CONFIG.blocks.sand : CONFIG.blocks.grass;
        } else if (y <= ground + 3) {
          block = sandy ? CONFIG.blocks.sand : CONFIG.blocks.dirt;
        }
        world.data[y * W + x] = block;
      }
    }
  }

  function carveCaves(world, seed) {
    for (let x = 16; x < W - 4; x += 1) {
      const ground = surfaceHeightAt(x, seed);
      for (let y = ground + 5; y < BOTTOM_ROW; y += 1) {
        if (world.data[y * W + x] !== CONFIG.blocks.stone) {
          continue;
        }
        const cave = valueNoise2D(x * 0.07, y * 0.11, seed + 31);
        const tunnel = valueNoise2D(x * 0.16 + 40, y * 0.24, seed + 77);
        if (cave > 0.635 || tunnel > 0.72) {
          world.data[y * W + x] = CONFIG.blocks.air;
        }
      }
    }
    // Sparse surface shafts make caves discoverable by walking.
    for (let x = 34; x < W - 10; x += 1) {
      if (unitHash(x, 7, seed + 991) > 0.985) {
        const ground = surfaceHeightAt(x, seed);
        for (let y = ground + 1; y <= ground + 9 && y < BOTTOM_ROW; y += 1) {
          world.data[y * W + x] = CONFIG.blocks.air;
          if (x + 1 < W) {
            world.data[y * W + x + 1] = CONFIG.blocks.air;
          }
        }
      }
    }
  }

  function placeOres(world, seed) {
    for (let x = 6; x < W - 6; x += 1) {
      const ground = surfaceHeightAt(x, seed);
      for (let y = ground + 6; y < BOTTOM_ROW; y += 1) {
        if (world.data[y * W + x] !== CONFIG.blocks.stone) {
          continue;
        }
        const depthRatio = (y - ground) / Math.max(1, H - ground);
        if (y > H * 0.78 && unitHash(x, y, seed + 401) > 0.986) {
          world.data[y * W + x] = CONFIG.blocks.crystal;
        } else if (depthRatio > 0.16 && unitHash(x, y, seed + 23) > 0.955) {
          world.data[y * W + x] = CONFIG.blocks.coal;
        }
      }
    }
  }

  function placeLakes(world, seed) {
    for (let x = 0; x < W; x += 1) {
      const ground = surfaceHeightAt(x, seed);
      if (ground <= SEA_LEVEL) {
        continue;
      }
      for (let y = SEA_LEVEL; y < ground; y += 1) {
        if (world.data[y * W + x] === CONFIG.blocks.air) {
          world.data[y * W + x] = CONFIG.blocks.water;
        }
      }
      const bed = ground * W + x;
      if (world.data[bed] !== CONFIG.blocks.air) {
        world.data[bed] = CONFIG.blocks.sand;
      }
    }
  }

  function isColumnClear(world, x, fromY, count) {
    for (let y = fromY - count; y < fromY; y += 1) {
      if (y < 0 || world.data[y * W + x] !== CONFIG.blocks.air) {
        return false;
      }
    }
    return true;
  }

  function placeTrees(world, seed) {
    const random = createPrng(seed + 0x5f3759df);
    let lastX = -99;
    for (let x = 24; x < W - 12; x += 1) {
      if (x - lastX < 4) {
        continue;
      }
      if (random() > 0.3) {
        continue;
      }
      const ground = surfaceHeightAt(x, seed);
      if (ground > SEA_LEVEL) {
        continue;
      }
      const surfaceBlock = world.data[ground * W + x];
      if (surfaceBlock !== CONFIG.blocks.grass) {
        continue;
      }
      if (!isColumnClear(world, x, ground, 7)) {
        continue;
      }
      lastX = x;
      const trunk = 3 + Math.floor(random() * 3);
      for (let y = ground - trunk; y < ground; y += 1) {
        world.data[y * W + x] = CONFIG.blocks.wood;
      }
      const top = ground - trunk;
      for (let dx = -2; dx <= 2; dx += 1) {
        for (let dy = -2; dy <= 1; dy += 1) {
          if (Math.abs(dx) === 2 && (dy === 1 || dy === -2)) {
            continue;
          }
          const tx = x + dx;
          const ty = top + dy - 1;
          if (tx < 0 || tx >= W || ty < 0) {
            continue;
          }
          if (world.data[ty * W + tx] === CONFIG.blocks.air) {
            world.data[ty * W + tx] = CONFIG.blocks.leaves;
          }
        }
      }
      world.data[(top - 2) * W + x] = CONFIG.blocks.leaves;
    }
  }

  function isSafeSpawnColumn(world, x) {
    for (let y = 2; y < H - 8; y += 1) {
      const block = world.data[y * W + x];
      if (block === CONFIG.blocks.air || block === CONFIG.blocks.water) {
        continue;
      }
      if (block !== CONFIG.blocks.grass && block !== CONFIG.blocks.sand) {
        return -1;
      }
      if (world.data[(y - 1) * W + x] !== CONFIG.blocks.air) {
        return -1;
      }
      if (world.data[(y - 2) * W + x] !== CONFIG.blocks.air) {
        return -1;
      }
      return y;
    }
    return -1;
  }

  function findSpawn(world) {
    const centre = Math.floor(world.width / 2);
    for (let distance = 0; distance <= 20; distance += 1) {
      const candidates = distance === 0 ? [centre] : [centre + distance, centre - distance];
      for (let i = 0; i < candidates.length; i += 1) {
        const x = candidates[i];
        if (x < 4 || x >= world.width - 4) {
          continue;
        }
        const ground = isSafeSpawnColumn(world, x);
        if (ground > 24 && ground < world.height - 12) {
          return { x: x, y: ground };
        }
      }
    }
    return { x: centre, y: BASE_GROUND };
  }

  function forceGroundColumn(world, x, ground) {
    for (let y = ground; y < world.height; y += 1) {
      let block = CONFIG.blocks.stone;
      if (y === ground) {
        block = CONFIG.blocks.grass;
      } else if (y <= ground + 3) {
        block = CONFIG.blocks.dirt;
      }
      world.data[y * world.width + x] = block;
    }
    for (let y = Math.max(0, ground - 10); y < ground; y += 1) {
      world.data[y * world.width + x] = CONFIG.blocks.air;
    }
  }

  function prepareSpawnClearing(world, spawn) {
    const ground = spawn.y;
    for (let x = spawn.x - 2; x <= spawn.x + 5; x += 1) {
      if (x < 1 || x >= world.width - 1) {
        continue;
      }
      forceGroundColumn(world, x, ground);
    }
    const treeX = spawn.x + 4;
    const trunk = 3;
    for (let y = ground - trunk; y < ground; y += 1) {
      world.data[y * world.width + treeX] = CONFIG.blocks.wood;
    }
    const top = ground - trunk;
    for (let dx = -2; dx <= 2; dx += 1) {
      for (let dy = -2; dy <= 1; dy += 1) {
        if (Math.abs(dx) === 2 && (dy === 1 || dy === -2)) {
          continue;
        }
        const tx = treeX + dx;
        const ty = top + dy - 1;
        if (tx < 0 || tx >= world.width || ty < 0) {
          continue;
        }
        if (world.data[ty * world.width + tx] === CONFIG.blocks.air) {
          world.data[ty * world.width + tx] = CONFIG.blocks.leaves;
        }
      }
    }
    world.data[(top - 2) * world.width + treeX] = CONFIG.blocks.leaves;
    // Clear any water that the flattening exposed above the clearing.
    for (let x = spawn.x - 2; x <= spawn.x + 5; x += 1) {
      for (let y = ground - 10; y < ground; y += 1) {
        if (y < 0) {
          continue;
        }
        if (world.data[y * world.width + x] === CONFIG.blocks.water) {
          world.data[y * world.width + x] = CONFIG.blocks.air;
        }
      }
    }
  }

  function createWorld(seed) {
    const normalizedSeed = Number(seed) >>> 0;
    const world = makeWorld(normalizedSeed);
    fillTerrain(world, normalizedSeed);
    carveCaves(world, normalizedSeed);
    placeOres(world, normalizedSeed);
    placeLakes(world, normalizedSeed);
    placeTrees(world, normalizedSeed);
    const spawn = findSpawn(world);
    prepareSpawnClearing(world, spawn);
    for (let x = 0; x < W; x += 1) {
      world.data[BOTTOM_ROW * W + x] = CONFIG.blocks.stone;
    }
    world.spawn = spawn;
    return world;
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
    return true;
  }

  function blockDef(block) {
    return CONFIG.blockDefs[block] || CONFIG.blockDefs[0];
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    if (block === null) {
      return false;
    }
    const def = blockDef(block);
    return def.solid === true;
  }

  function isWater(world, x, y) {
    return getBlock(world, x, y) === CONFIG.blocks.water;
  }

  function isAir(world, x, y) {
    return getBlock(world, x, y) === CONFIG.blocks.air;
  }

  function isUnbreakable(world, x, y) {
    return y >= world.height - 1 || getBlock(world, x, y) === CONFIG.blocks.water;
  }

  function serializeWorld(world) {
    return JSON.stringify({
      width: world.width,
      height: world.height,
      seed: world.seed,
      data: Array.from(world.data)
    });
  }

  function deserializeWorld(text) {
    const parsed = JSON.parse(text);
    if (!parsed || !Number.isInteger(parsed.width) || !Number.isInteger(parsed.height)) {
      throw new Error("Invalid world payload");
    }
    if (!Array.isArray(parsed.data) || parsed.data.length !== parsed.width * parsed.height) {
      throw new Error("Invalid world block data");
    }
    return {
      width: parsed.width,
      height: parsed.height,
      seed: Number(parsed.seed) >>> 0,
      data: Uint8Array.from(parsed.data)
    };
  }

  function encodeRle(data) {
    const runs = [];
    let current = data[0];
    let count = 1;
    for (let i = 1; i < data.length; i += 1) {
      if (data[i] === current) {
        count += 1;
      } else {
        runs.push([current, count]);
        current = data[i];
        count = 1;
      }
    }
    runs.push([current, count]);
    return runs;
  }

  function decodeRle(runs, expectedLength) {
    if (!Array.isArray(runs)) {
      throw new Error("Invalid block runs");
    }
    const data = new Uint8Array(expectedLength);
    let offset = 0;
    for (let i = 0; i < runs.length; i += 1) {
      const run = runs[i];
      if (!Array.isArray(run) || run.length !== 2) {
        throw new Error("Invalid block run");
      }
      const block = run[0];
      const count = run[1];
      if (!Number.isInteger(block) || !Number.isInteger(count) || count <= 0) {
        throw new Error("Invalid block run values");
      }
      if (block < 0 || !CONFIG.blockDefs[block]) {
        throw new Error("Unknown block id in save");
      }
      if (offset + count > expectedLength) {
        throw new Error("Block runs exceed the world size");
      }
      data.fill(block, offset, offset + count);
      offset += count;
    }
    if (offset !== expectedLength) {
      throw new Error("Block runs do not cover the world");
    }
    return data;
  }

  function getSpawn(world) {
    if (world.spawn) {
      return { x: world.spawn.x, y: world.spawn.y };
    }
    const spawn = findSpawn(world);
    world.spawn = spawn;
    return { x: spawn.x, y: spawn.y };
  }

  return {
    BASE_GROUND: BASE_GROUND,
    SEA_LEVEL: SEA_LEVEL,
    createWorld: createWorld,
    surfaceHeightAt: surfaceHeightAt,
    getBlock: getBlock,
    setBlock: setBlock,
    blockDef: blockDef,
    isSolid: isSolid,
    isWater: isWater,
    isAir: isAir,
    isUnbreakable: isUnbreakable,
    getSpawn: getSpawn,
    findSpawn: findSpawn,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld,
    encodeRle: encodeRle,
    decodeRle: decodeRle
  };
});
