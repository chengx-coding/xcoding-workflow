(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"), require("./noise.js"), require("./blocks.js"));
  } else {
    root.SandboxWorld = factory(root.SandboxConfig, root.SandboxRng, root.SandboxNoise, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG, NOISE, BLOCKS) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxWorld");
  }
  if (!RNG || !NOISE || !BLOCKS) {
    throw new Error("SandboxRng, SandboxNoise and SandboxBlocks are required before SandboxWorld");
  }

  const B = CONFIG.blocks;

  function indexOf(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return -1;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return -1;
    }
    return y * world.width + x;
  }

  // Seed-compatible flat world. The legacy contract is kept intact so the
  // seed test suite remains a meaningful regression check; the game itself
  // uses generateWorld below.
  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const data = new Uint8Array(width * height);
    const ground = Math.floor(height * 0.65);

    for (let x = 0; x < width; x += 1) {
      for (let y = ground; y < height; y += 1) {
        if (y === ground) {
          data[y * width + x] = CONFIG.blocks.grass;
        } else if (y < ground + 3) {
          data[y * width + x] = CONFIG.blocks.dirt;
        } else {
          data[y * width + x] = CONFIG.blocks.stone;
        }
      }
    }

    return {
      width: width,
      height: height,
      seed: Number(seed) >>> 0,
      data: data
    };
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function generateWorld(seed) {
    const s = Number(seed) >>> 0;
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const data = new Uint8Array(width * height);
    const rng = RNG.createRng(s);
    const heightNoise = NOISE.createNoise1D(s ^ 0x51ed270b);
    const detailNoise = NOISE.createNoise1D(s ^ 0x2c1b3c6d);
    const biomeNoise = NOISE.createNoise1D(s ^ 0x7f4a7c15);
    const caveNoise = NOISE.createNoise2D(s ^ 0x9e3779b9);
    const oreNoise = NOISE.createNoise2D(s ^ 0x85ebca6b);
    const ironNoise = NOISE.createNoise2D(s ^ 0xc2b2ae35);

    const surface = new Int16Array(width);
    const biomes = new Array(width);
    const biomesByKey = { plains: "plains", forest: "forest", desert: "desert", rocky: "rocky" };

    function put(x, y, id) {
      if (x < 0 || y < 0 || x >= width || y >= height) {
        return;
      }
      data[y * width + x] = id;
    }

    function get(x, y) {
      if (x < 0 || y < 0 || x >= width || y >= height) {
        return B.bedrock;
      }
      return data[y * width + x];
    }

    // 1. Surface profile and biome bands.
    for (let x = 0; x < width; x += 1) {
      const rolling = (heightNoise.fbm(x * 0.021, 4) - 0.5) * 22;
      const detail = (detailNoise.fbm(x * 0.085, 2) - 0.5) * 5;
      const top = clamp(Math.round(48 + rolling + detail), 30, 70);
      surface[x] = top;
      const band = biomeNoise.fbm(x * 0.0045, 2);
      let biome = biomesByKey.plains;
      if (top < 37) {
        biome = biomesByKey.rocky;
      } else if (band < 0.4) {
        biome = biomesByKey.desert;
      } else if (band > 0.6) {
        biome = biomesByKey.forest;
      }
      biomes[x] = biome;
    }

    // 2. Terrain columns.
    for (let x = 0; x < width; x += 1) {
      const top = surface[x];
      const biome = biomes[x];
      const soilDepth = biome === biomesByKey.desert ? 4 : 3 + (x % 3);
      for (let y = top; y < height; y += 1) {
        let id;
        if (y === height - 1 || y === height - 2) {
          id = B.bedrock;
        } else if (y === top) {
          if (biome === biomesByKey.desert) {
            id = B.sand;
          } else if (biome === biomesByKey.rocky) {
            id = B.stone;
          } else {
            id = B.grass;
          }
        } else if (y < top + soilDepth) {
          id = biome === biomesByKey.desert ? (y < top + 2 ? B.sand : B.sandstone) : B.dirt;
        } else {
          id = B.stone;
        }
        put(x, y, id);
      }
    }

    // 3. Caves and tunnels, never opening the very surface skin.
    for (let x = 0; x < width; x += 1) {
      const top = surface[x];
      for (let y = top + 3; y < height - 2; y += 1) {
        const blob = caveNoise.fbm(x * 0.052, y * 0.078, 3);
        const tunnel = Math.abs(caveNoise.noise(x * 0.09, y * 0.13) - 0.5);
        if (blob > 0.655 || (tunnel < 0.024 && y > top + 6)) {
          put(x, y, B.air);
        }
      }
    }

    // 4. Ore veins inside remaining stone.
    const ironLine = Math.round(height * 0.63);
    for (let x = 0; x < width; x += 1) {
      for (let y = surface[x] + 4; y < height - 2; y += 1) {
        if (get(x, y) !== B.stone) {
          continue;
        }
        if (y > ironLine && ironNoise.noise(x * 0.42, y * 0.42) > 0.815) {
          put(x, y, B.ironOre);
        } else if (oreNoise.noise(x * 0.36, y * 0.36) > 0.79) {
          put(x, y, B.coalOre);
        }
      }
    }

    // 5. Trees and ground decoration.
    let lastTree = -10;
    for (let x = 4; x < width - 4; x += 1) {
      const biome = biomes[x];
      if (biome === biomesByKey.desert || biome === biomesByKey.rocky) {
        continue;
      }
      const chance = biome === biomesByKey.forest ? 0.17 : 0.055;
      if (rng() > chance || x - lastTree < 3) {
        continue;
      }
      const top = surface[x];
      if (get(x, top - 1) !== B.air) {
        continue;
      }
      const trunk = 3 + Math.floor(rng() * 3);
      let blocked = false;
      for (let step = 1; step <= trunk + 2; step += 1) {
        if (get(x, top - step) !== B.air) {
          blocked = true;
          break;
        }
      }
      if (blocked) {
        continue;
      }
      lastTree = x;
      for (let step = 1; step <= trunk; step += 1) {
        put(x, top - step, B.wood);
      }
      const crownY = top - trunk;
      for (let offsetY = -2; offsetY <= 1; offsetY += 1) {
        const radius = offsetY <= -1 ? 2 : 1;
        for (let offsetX = -radius; offsetX <= radius; offsetX += 1) {
          if (offsetX === 0 && offsetY === 1) {
            continue;
          }
          const targetY = crownY + offsetY;
          if (get(x + offsetX, targetY) === B.air) {
            put(x + offsetX, targetY, B.leaves);
          }
        }
      }
    }

    for (let x = 1; x < width - 1; x += 1) {
      if (biomes[x] === biomesByKey.rocky || biomes[x] === biomesByKey.desert) {
        continue;
      }
      if (get(x, surface[x]) === B.grass && get(x, surface[x] - 1) === B.air && rng() < 0.045) {
        put(x, surface[x] - 1, B.flower);
      }
    }

    const world = {
      width: width,
      height: height,
      seed: s,
      data: data,
      surface: surface,
      biomes: biomes
    };

    // 6. A clear spawn column near the centre.
    const spawnX = Math.floor(width / 2);
    for (let clearY = surface[spawnX] - 5; clearY < surface[spawnX]; clearY += 1) {
      if (get(spawnX, clearY) === B.wood || get(spawnX, clearY) === B.leaves) {
        put(spawnX, clearY, B.air);
      }
    }
    // Make sure the spawn column stands on terrain (not on a tree canopy).
    let spawnTop = surface[spawnX];
    while (spawnTop < height - 3 && !isGroundTile(world, spawnX, spawnTop)) {
      spawnTop += 1;
    }
    for (let clearY = spawnTop - 2; clearY < spawnTop; clearY += 1) {
      const id = get(spawnX, clearY);
      if (id === B.leaves || id === B.wood || id === B.flower || id === B.torch) {
        put(spawnX, clearY, B.air);
      }
    }
    world.spawn = { x: spawnX + 0.5, y: spawnTop };

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

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    return block !== null && BLOCKS.isSolid(block);
  }

  function surfaceHeightAt(world, x) {
    if (x < 0 || x >= world.width) {
      return -1;
    }
    for (let y = 0; y < world.height; y += 1) {
      if (BLOCKS.isSolid(world.data[y * world.width + x])) {
        return y;
      }
    }
    return world.height;
  }

  // Terrain is the walkable ground layer; canopies and decorations above it do
  // not count as standing ground.
  function isGroundTile(world, x, y) {
    const id = getBlock(world, x, y);
    if (id === null) {
      return false;
    }
    if (id === B.leaves || id === B.wood || id === B.flower || id === B.torch) {
      return false;
    }
    return BLOCKS.isSolid(id);
  }

  function terrainHeightAt(world, x) {
    if (x < 0 || x >= world.width) {
      return -1;
    }
    for (let y = 0; y < world.height; y += 1) {
      if (isGroundTile(world, x, y)) {
        return y;
      }
    }
    return world.height;
  }

  function findSpawn(world) {
    const x = Math.floor(world.width / 2);
    const top = terrainHeightAt(world, x);
    return { x: x + 0.5, y: top < 0 ? 1 : top };
  }

  function rleEncode(data) {
    const runs = [];
    let current = data[0];
    let count = 0;
    for (let index = 0; index < data.length; index += 1) {
      const value = data[index];
      if (value === current) {
        count += 1;
      } else {
        runs.push(current, count);
        current = value;
        count = 1;
      }
    }
    if (count > 0) {
      runs.push(current, count);
    }
    return runs;
  }

  function rleDecode(runs, expectedLength) {
    const data = new Uint8Array(expectedLength);
    let offset = 0;
    for (let index = 0; index < runs.length; index += 2) {
      const value = runs[index];
      const count = runs[index + 1];
      if (!Number.isInteger(count) || count < 0 || offset + count > expectedLength) {
        throw new Error("Invalid run-length data");
      }
      data.fill(value, offset, offset + count);
      offset += count;
    }
    if (offset !== expectedLength) {
      throw new Error("Run-length data does not fill the world");
    }
    return data;
  }

  function serializeWorld(world) {
    return JSON.stringify({
      width: world.width,
      height: world.height,
      seed: world.seed,
      rle: rleEncode(world.data)
    });
  }

  function deserializeWorld(text) {
    const parsed = JSON.parse(text);
    if (!parsed || !Number.isInteger(parsed.width) || !Number.isInteger(parsed.height)) {
      throw new Error("Invalid world payload");
    }
    let data;
    if (Array.isArray(parsed.rle)) {
      data = rleDecode(parsed.rle, parsed.width * parsed.height);
    } else if (Array.isArray(parsed.data)) {
      if (parsed.data.length !== parsed.width * parsed.height) {
        throw new Error("Invalid world block data");
      }
      data = Uint8Array.from(parsed.data);
    } else {
      throw new Error("Invalid world block data");
    }
    return {
      width: parsed.width,
      height: parsed.height,
      seed: Number(parsed.seed) >>> 0,
      data: data
    };
  }

  return {
    createWorld: createWorld,
    generateWorld: generateWorld,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    surfaceHeightAt: surfaceHeightAt,
    terrainHeightAt: terrainHeightAt,
    isGroundTile: isGroundTile,
    findSpawn: findSpawn,
    rleEncode: rleEncode,
    rleDecode: rleDecode,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
