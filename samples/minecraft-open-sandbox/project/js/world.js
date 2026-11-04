/* World generation, block access and world-level serialization. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"));
  } else {
    root.SandboxWorld = factory(root.SandboxConfig, root.SandboxRng);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxWorld");
  }
  if (!RNG) {
    throw new Error("SandboxRng is required before SandboxWorld");
  }

  const B = CONFIG.blocks;
  const D = CONFIG.blockDefs;

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
    return true;
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    const def = block === null ? null : D[block];
    return Boolean(def && def.solid);
  }

  function isOpaque(world, x, y) {
    const block = getBlock(world, x, y);
    const def = block === null ? null : D[block];
    return Boolean(def && def.opaque);
  }

  function isLiquid(world, x, y) {
    const block = getBlock(world, x, y);
    const def = block === null ? null : D[block];
    return Boolean(def && def.liquid);
  }

  function isReplaceable(world, x, y) {
    const block = getBlock(world, x, y);
    const def = block === null ? null : D[block];
    return Boolean(def && def.replaceable);
  }

  function put(world, x, y, block) {
    setBlock(world, x, y, block);
    if (block !== B.air) {
      world.edits += 1;
    }
  }

  function fillColumn(world, x, top, seed) {
    const height = world.height;
    const sandLine = x >= CONFIG.spawnPlateau && top >= CONFIG.seaLevel - 1;
    const dirtDepth = 3 + (RNG.hash2(x, 3, seed) % 3);
    for (let y = top; y < height; y += 1) {
      if (y === top) {
        put(world, x, y, sandLine ? B.sand : B.grass);
      } else if (y < top + dirtDepth) {
        put(world, x, y, sandLine ? B.sand : B.dirt);
      } else {
        put(world, x, y, B.stone);
      }
    }
    world.surface[x] = top;
  }

  function surfaceHeight(x, seed) {
    if (x < CONFIG.spawnPlateau) {
      return 62;
    }
    const broad = RNG.fbm1(x * 0.011, seed + 101, 3);
    const detail = RNG.fbm1(x * 0.052, seed + 202, 3);
    let height = 62 + broad * 11 + detail * 4;
    // A guaranteed pond basin keeps water and shoreline visible on every seed.
    if (x >= 30 && x <= 47) {
      const pond = Math.sin(((x - 30) / 17) * Math.PI);
      height += pond * 7;
    }
    return RNG.clamp(Math.round(height), 40, 80);
  }

  function carveCaves(world, seed) {
    const B0 = B.air;
    for (let x = CONFIG.spawnPlateau + 2; x < world.width - 2; x += 1) {
      const top = world.surface[x];
      for (let y = top + 4; y < world.height - 3; y += 1) {
        const chambers = RNG.fbm2(x * 0.083, y * 0.115, seed + 7, 3);
        const tunnels = Math.abs(RNG.fbm2(x * 0.045, y * 0.07, seed + 19, 2));
        if (chambers > 0.42 || tunnels < 0.045) {
          const current = getBlock(world, x, y);
          if (current === B.stone || current === B.dirt || current === B.grass) {
            setBlock(world, x, y, B0);
          }
        }
      }
    }
  }

  function carveOre(world, seed, block, veins, minY, maxY) {
    const random = RNG.mulberry32(seed);
    for (let vein = 0; vein < veins; vein += 1) {
      let x = 2 + Math.floor(random() * (world.width - 4));
      let y = minY + Math.floor(random() * Math.max(1, maxY - minY));
      const size = 3 + Math.floor(random() * 6);
      for (let step = 0; step < size; step += 1) {
        if (getBlock(world, x, y) === B.stone) {
          setBlock(world, x, y, block);
        }
        x += Math.floor(random() * 3) - 1;
        y += Math.floor(random() * 3) - 1;
        if (x < 1 || x >= world.width - 1 || y < 3 || y >= world.height - 1) {
          break;
        }
      }
    }
  }

  function addWater(world) {
    for (let x = 0; x < world.width; x += 1) {
      const top = world.surface[x];
      for (let y = CONFIG.seaLevel; y < top; y += 1) {
        if (getBlock(world, x, y) === B.air) {
          setBlock(world, x, y, B.water);
        }
      }
    }
  }

  function plantTree(world, x, groundY, seed) {
    const random = RNG.mulberry32(seed);
    const height = 4 + Math.floor(random() * 3);
    if (groundY - height - 2 < 2) {
      return false;
    }
    for (let y = 1; y <= height; y += 1) {
      if (getBlock(world, x, groundY - y) !== B.air) {
        return false;
      }
    }
    for (let y = 1; y <= height; y += 1) {
      setBlock(world, x, groundY - y, B.wood);
    }
    const crown = groundY - height;
    for (let dy = -2; dy <= 1; dy += 1) {
      const radius = dy === 1 ? 1 : 2;
      for (let dx = -radius; dx <= radius; dx += 1) {
        if (dx === 0 && dy <= 0) {
          continue;
        }
        if (Math.abs(dx) === radius && Math.abs(dy) === 2) {
          continue;
        }
        if (getBlock(world, x + dx, crown + dy) === B.air) {
          setBlock(world, x + dx, crown + dy, B.leaves);
        }
      }
    }
    return true;
  }

  function plantTrees(world, seed) {
    const random = RNG.mulberry32(seed ^ 0xa53c9e1);
    let x = CONFIG.spawnPlateau + 5;
    while (x < world.width - 4) {
      const top = world.surface[x];
      const ground = getBlock(world, x, top);
      if (ground === B.grass && x !== Math.floor(world.width / 2)) {
        if (random() < 0.72) {
          plantTree(world, x, top, (seed + x * 7919) >>> 0);
        }
        x += 5 + Math.floor(random() * 6);
      } else {
        x += 2;
      }
    }
  }

  function decorate(world, seed) {
    const random = RNG.mulberry32(seed ^ 0x51ed270b);
    for (let x = CONFIG.spawnPlateau; x < world.width; x += 1) {
      const top = world.surface[x];
      if (getBlock(world, x, top) !== B.grass || getBlock(world, x, top - 1) !== B.air) {
        continue;
      }
      const roll = random();
      if (roll < 0.07) {
        setBlock(world, x, top - 1, B.flower);
      } else if (roll < 0.22) {
        setBlock(world, x, top - 1, B.tallGrass);
      }
    }
  }

  function findSpawn(world) {
    const center = Math.floor(world.width / 2);
    for (let radius = 0; radius < Math.floor(world.width / 2) - 2; radius += 1) {
      for (const side of [0, -1, 1]) {
        const x = center + side * radius;
        if (x < 2 || x >= world.width - 2) {
          continue;
        }
        const top = world.surface[x];
        if (getBlock(world, x, top) === B.grass && top < CONFIG.seaLevel - 1) {
          return { x: x + 0.5, y: top };
        }
      }
    }
    for (let radius = 0; radius < Math.floor(world.width / 2) - 2; radius += 1) {
      for (const side of [0, -1, 1]) {
        const x = center + side * radius;
        if (x < 2 || x >= world.width - 2) {
          continue;
        }
        const top = world.surface[x];
        if (getBlock(world, x, top) === B.grass || getBlock(world, x, top) === B.sand) {
          return { x: x + 0.5, y: top };
        }
      }
    }
    return { x: center + 0.5, y: 62 };
  }

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const normalizedSeed = Number(seed) >>> 0;
    const world = {
      width: width,
      height: height,
      seed: normalizedSeed,
      data: new Uint8Array(width * height),
      surface: new Int16Array(width),
      edits: 0,
      version: 1
    };

    for (let x = 0; x < width; x += 1) {
      fillColumn(world, x, surfaceHeight(x, normalizedSeed), normalizedSeed);
    }

    carveCaves(world, normalizedSeed);
    carveOre(world, normalizedSeed ^ 0x1b873593, B.coalOre, 150, 24, height - 6);
    carveOre(world, normalizedSeed ^ 0x9e3779b9, B.ironOre, 80, 38, height - 4);
    addWater(world);
    plantTrees(world, normalizedSeed);
    decorate(world, normalizedSeed);

    // Keep the spawn column clear and the seed's first-column contract exact.
    const spawn = findSpawn(world);
    const spawnX = Math.floor(spawn.x);
    for (let dx = -2; dx <= 2; dx += 1) {
      const x = spawnX + dx;
      if (x < 0 || x >= width) {
        continue;
      }
      const top = world.surface[x];
      for (let y = top - 5; y < top; y += 1) {
        if (y >= 0 && (getBlock(world, x, y) === B.wood || getBlock(world, x, y) === B.leaves)) {
          setBlock(world, x, y, B.air);
        }
      }
      if (getBlock(world, x, top) === B.air) {
        setBlock(world, x, top, B.grass);
      }
      for (let y = top + 1; y < top + 4; y += 1) {
        if (getBlock(world, x, y) === B.air) {
          setBlock(world, x, y, B.dirt);
        }
      }
    }

    world.spawn = findSpawn(world);
    world.edits = 0;
    return world;
  }

  function rebuildWorld(seed, width, height, data, surface, spawn) {
    if (!Number.isInteger(width) || !Number.isInteger(height) || !data || data.length !== width * height) {
      throw new Error("Invalid world data");
    }
    const world = {
      width: width,
      height: height,
      seed: Number(seed) >>> 0,
      data: data instanceof Uint8Array ? data : Uint8Array.from(data),
      surface: new Int16Array(width),
      edits: 0,
      version: 1
    };
    if (Array.isArray(surface) || surface instanceof Int16Array) {
      for (let x = 0; x < width; x += 1) {
        world.surface[x] = Number(surface[x]) || 0;
      }
    } else {
      for (let x = 0; x < width; x += 1) {
        let top = height - 1;
        for (let y = 0; y < height; y += 1) {
          const block = getBlock(world, x, y);
          if (block !== B.air && block !== B.water) {
            top = y;
            break;
          }
        }
        world.surface[x] = top;
      }
    }
    world.spawn = spawn && Number.isFinite(spawn.x) && Number.isFinite(spawn.y)
      ? { x: Number(spawn.x), y: Number(spawn.y) }
      : findSpawn(world);
    return world;
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
    const world = {
      width: parsed.width,
      height: parsed.height,
      seed: Number(parsed.seed) >>> 0,
      data: Uint8Array.from(parsed.data),
      surface: new Int16Array(parsed.width),
      edits: 0,
      version: 1
    };
    for (let x = 0; x < world.width; x += 1) {
      let top = 0;
      for (let y = 0; y < world.height; y += 1) {
        const block = getBlock(world, x, y);
        if (block !== B.air && block !== B.water) {
          top = y;
          break;
        }
      }
      world.surface[x] = top;
    }
    world.spawn = findSpawn(world);
    return world;
  }

  function countBlock(world, block) {
    let total = 0;
    for (let i = 0; i < world.data.length; i += 1) {
      if (world.data[i] === block) {
        total += 1;
      }
    }
    return total;
  }

  return {
    createWorld: createWorld,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    isOpaque: isOpaque,
    isLiquid: isLiquid,
    isReplaceable: isReplaceable,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld,
    rebuildWorld: rebuildWorld,
    surfaceHeight: surfaceHeight,
    findSpawn: findSpawn,
    countBlock: countBlock
  };
});
