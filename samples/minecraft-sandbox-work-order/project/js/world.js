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

  const BLOCK_MIN = 0;
  const BLOCK_MAX = CONFIG.blocks.bedrock;
  const SURFACE_BASE = Math.floor(CONFIG.worldHeight * 0.62);

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function normalizeSeed(seed) {
    const numeric = Number(seed);
    if (!Number.isFinite(numeric)) {
      return CONFIG.seed >>> 0;
    }
    return Math.trunc(numeric) >>> 0;
  }

  function mulberry32(seed) {
    let state = seed >>> 0;
    return function random() {
      state = (state + 0x6d2b79f5) >>> 0;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hash2(x, y, seed) {
    let value = (seed ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263)) >>> 0;
    value = Math.imul(value ^ (value >>> 13), 1274126177);
    return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
  }

  function smooth(value) {
    return value * value * (3 - 2 * value);
  }

  function noise2(x, y, seed) {
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const tx = smooth(x - x0);
    const ty = smooth(y - y0);
    const a = hash2(x0, y0, seed);
    const b = hash2(x0 + 1, y0, seed);
    const c = hash2(x0, y0 + 1, seed);
    const d = hash2(x0 + 1, y0 + 1, seed);
    const top = a + (b - a) * tx;
    const bottom = c + (d - c) * tx;
    return top + (bottom - top) * ty;
  }

  function fbm2(x, y, seed, octaves) {
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let weight = 0;
    const count = octaves || 3;
    for (let octave = 0; octave < count; octave += 1) {
      total += noise2(x * frequency, y * frequency, (seed + octave * 1013) >>> 0) * amplitude;
      weight += amplitude;
      amplitude *= 0.5;
      frequency *= 2.03;
    }
    return total / weight;
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
    if (!Number.isInteger(block) || block < BLOCK_MIN || block > BLOCK_MAX) {
      return false;
    }
    world.data[index] = block;
    return true;
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    return block !== null && block !== CONFIG.blocks.air;
  }

  function carveCaves(data, width, height, ground, seed) {
    for (let x = 2; x < width - 2; x += 1) {
      for (let y = ground[x] + 5; y < height - 3; y += 1) {
        const chamber = fbm2(x * 0.075, y * 0.105, (seed ^ 0x7f4a7c15) >>> 0, 3);
        const tunnel = 1 - Math.abs(noise2(x * 0.06, y * 0.082, (seed ^ 0x94d049bb) >>> 0) * 2 - 1);
        if (chamber > 0.665 || tunnel > 0.935) {
          data[y * width + x] = CONFIG.blocks.air;
        }
      }
    }
  }

  function scatterOres(data, width, height, ground, seed) {
    for (let x = 1; x < width - 1; x += 1) {
      for (let y = ground[x] + 4; y < height - 2; y += 1) {
        const index = y * width + x;
        if (data[index] !== CONFIG.blocks.stone) {
          continue;
        }
        const coalNoise = fbm2(x * 0.19, y * 0.2, (seed ^ 0x51a7c0de) >>> 0, 2);
        if (coalNoise > 0.72 && hash2(x, y, seed ^ 0x2f61d3) > 0.72) {
          data[index] = CONFIG.blocks.coal;
        }
        const crystalNoise = fbm2(x * 0.24, y * 0.22, (seed ^ 0xbadc0ffe) >>> 0, 2);
        if (y > height * 0.62 && crystalNoise > 0.775 && hash2(x, y, seed ^ 0x17c0) > 0.68) {
          data[index] = CONFIG.blocks.crystal;
        }
      }
    }
  }

  function plantTree(data, width, height, ground, x, trunk, random) {
    const surface = ground[x];
    if (surface - trunk - 2 < 3) {
      return false;
    }
    if (data[surface * width + x] !== CONFIG.blocks.grass) {
      return false;
    }
    for (let step = 1; step <= trunk; step += 1) {
      if (data[(surface - step) * width + x] !== CONFIG.blocks.air) {
        return false;
      }
    }
    for (let step = 1; step <= trunk; step += 1) {
      data[(surface - step) * width + x] = CONFIG.blocks.wood;
    }
    const crownY = surface - trunk;
    for (let dy = -2; dy <= 2; dy += 1) {
      for (let dx = -2; dx <= 2; dx += 1) {
        const distance = Math.abs(dx) + Math.abs(dy);
        if (distance > 3 || (distance === 3 && random() < 0.35)) {
          continue;
        }
        if (dx === 0 && dy >= 0) {
          continue;
        }
        const tx = x + dx;
        const ty = crownY + dy;
        if (tx > 0 && tx < width - 1 && ty > 0 && ty < height - 1) {
          if (data[ty * width + tx] === CONFIG.blocks.air) {
            data[ty * width + tx] = CONFIG.blocks.leaves;
          }
        }
      }
    }
    return true;
  }

  function plantTrees(data, width, height, ground, biomes, seed) {
    const random = mulberry32((seed ^ 0xa15f2c3d) >>> 0);
    let lastTree = -10;
    for (let x = 5; x < width - 5; x += 1) {
      if (x - lastTree < 5) {
        continue;
      }
      if (Math.abs(x - width / 2) < 5) {
        continue;
      }
      if (biomes[x] === 2) {
        continue;
      }
      const density = biomes[x] === 1 ? 0.42 : 0.2;
      if (hash2(x, 77, seed ^ 0x44b1) > density) {
        continue;
      }
      const trunk = 4 + Math.floor(random() * 3);
      if (plantTree(data, width, height, ground, x, trunk, random)) {
        lastTree = x;
      }
    }
  }

  function plantSpawnGrove(data, width, height, ground, seed) {
    const center = Math.floor(width / 2);
    const random = mulberry32((seed ^ 0x7e57a11) >>> 0);
    const offsets = [-7, 6, -13, 13];
    let planted = 0;
    for (let index = 0; index < offsets.length && planted < 2; index += 1) {
      const x = center + offsets[index];
      if (plantTree(data, width, height, ground, x, 5, random)) {
        planted += 1;
      }
    }
  }

  function addLandmarks(data, width, height, ground) {
    const center = Math.floor(width / 2);
    const candidates = [center + 14, center - 17, Math.floor(width * 0.23), Math.floor(width * 0.77)];
    candidates.forEach(function (x, index) {
      if (x < 3 || x >= width - 3) {
        return;
      }
      const surface = ground[x];
      if (surface < 5) {
        return;
      }
      for (let offset = 0; offset < 16; offset += 1) {
        const direction = offset === 0 ? 0 : index % 2 === 0 ? offset : -offset;
        const tx = x + direction;
        if (tx < 3 || tx >= width - 3) {
          continue;
        }
        const ty = ground[tx];
        const floor = data[ty * width + tx];
        if (floor !== CONFIG.blocks.grass && floor !== CONFIG.blocks.sand) {
          continue;
        }
        let clear = true;
        for (let lift = 1; lift <= 4; lift += 1) {
          if (data[(ty - lift) * width + tx] !== CONFIG.blocks.air) {
            clear = false;
            break;
          }
        }
        if (!clear) {
          continue;
        }
        data[(ty - 1) * width + tx] = CONFIG.blocks.wood;
        data[(ty - 2) * width + tx] = CONFIG.blocks.wood;
        data[(ty - 3) * width + tx] = CONFIG.blocks.lantern;
        return;
      }
    });
  }

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const normalizedSeed = normalizeSeed(seed);
    const data = new Uint8Array(width * height);
    const ground = new Int16Array(width);
    const biomes = new Uint8Array(width);

    for (let x = 0; x < width; x += 1) {
      const broad = fbm2(x * 0.0125, 8.4, (normalizedSeed ^ 0x9e3779b9) >>> 0, 3);
      const detail = fbm2(x * 0.058, 2.1, (normalizedSeed ^ 0x85ebca6b) >>> 0, 2);
      const ridge = Math.abs(noise2(x * 0.025, 9.7, (normalizedSeed ^ 0xc2b2ae35) >>> 0) - 0.5) * 2;
      const target = SURFACE_BASE - (broad - 0.5) * 22 - (detail - 0.5) * 7 + ridge * 4;
      ground[x] = clamp(Math.round(target), 22, height - 13);

      const biomeNoise = fbm2(x * 0.009, 31.7, (normalizedSeed ^ 0x27d4eb2f) >>> 0, 2);
      biomes[x] = biomeNoise > 0.635 ? 2 : biomeNoise > 0.46 ? 1 : 0;
      if (Math.abs(x - width / 2) < 18) {
        biomes[x] = 0;
      }
    }

    for (let x = 0; x < width; x += 1) {
      const surface = ground[x];
      const desert = biomes[x] === 2;
      for (let y = 0; y < height; y += 1) {
        let block = CONFIG.blocks.air;
        if (y >= height - 2) {
          block = CONFIG.blocks.bedrock;
        } else if (y === surface) {
          block = desert ? CONFIG.blocks.sand : CONFIG.blocks.grass;
        } else if (y > surface && y < surface + 4) {
          block = desert ? CONFIG.blocks.sand : CONFIG.blocks.dirt;
        } else if (y >= surface) {
          block = CONFIG.blocks.stone;
        }
        data[y * width + x] = block;
      }
    }

    carveCaves(data, width, height, ground, normalizedSeed);
    scatterOres(data, width, height, ground, normalizedSeed);
    plantTrees(data, width, height, ground, biomes, normalizedSeed);
    plantSpawnGrove(data, width, height, ground, normalizedSeed);
    addLandmarks(data, width, height, ground);

    return {
      width: width,
      height: height,
      seed: normalizedSeed,
      data: data,
      ground: ground,
      biomes: biomes
    };
  }

  function findSpawn(world, anchorX) {
    const center = Math.max(0, Math.min(world.width - 1, Math.round(anchorX == null ? world.width / 2 : anchorX)));
    for (let offset = 0; offset < 30; offset += 1) {
      for (const direction of offset === 0 ? [0] : [-1, 1]) {
        const x = center + offset * direction;
        if (x < 2 || x >= world.width - 2) {
          continue;
        }
        const surface = world.ground[x];
        if (getBlock(world, x, surface) === CONFIG.blocks.air) {
          continue;
        }
        if (isSolid(world, x, surface - 1) || isSolid(world, x, surface - 2)) {
          continue;
        }
        return { x: x + 0.5, y: surface };
      }
    }
    return { x: world.width / 2 + 0.5, y: Math.floor(world.height * 0.4) };
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
    const parsed = typeof text === "string" ? JSON.parse(text) : text;
    if (!parsed || !Number.isInteger(parsed.width) || !Number.isInteger(parsed.height)) {
      throw new Error("Invalid world payload");
    }
    if (parsed.width !== CONFIG.worldWidth || parsed.height !== CONFIG.worldHeight) {
      throw new Error("World dimensions do not match this build");
    }
    if (!Array.isArray(parsed.data) || parsed.data.length !== parsed.width * parsed.height) {
      throw new Error("Invalid world block data");
    }
    const fresh = createWorld(parsed.seed);
    for (let index = 0; index < parsed.data.length; index += 1) {
      const block = parsed.data[index];
      if (!Number.isInteger(block) || block < BLOCK_MIN || block > BLOCK_MAX) {
        throw new Error("Invalid block id in saved world");
      }
      fresh.data[index] = block;
    }
    return fresh;
  }

  return {
    createWorld: createWorld,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    normalizeSeed: normalizeSeed,
    findSpawn: findSpawn,
    hash2: hash2,
    noise2: noise2,
    fbm2: fbm2,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
