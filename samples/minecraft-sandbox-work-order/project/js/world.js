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

  const AIR = CONFIG.blocks.air;
  const SPAWN_MIN_X = 20;
  const SPAWN_MAX_X = 108;

  function indexOf(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return -1;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return -1;
    }
    return y * world.width + x;
  }

  function smoothstep(edge0, edge1, value) {
    const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  function terrainHeight(seed, x) {
    const random = RNG.createRandom((seed ^ RNG.hashString("heights")) >>> 0);
    const phaseA = random.range(0, Math.PI * 2);
    const phaseB = random.range(0, Math.PI * 2);
    const phaseC = random.range(0, Math.PI * 2);
    const base = Math.floor(CONFIG.worldHeight * 0.65);
    // A flat spawn plateau keeps the first moments of play safe and keeps the
    // seed contract stable: columns below SPAWN_MIN_X never move vertically.
    const plateau = x < SPAWN_MIN_X ? 0 : smoothstep(SPAWN_MIN_X, SPAWN_MIN_X + 26, x);
    const hills =
      2.6 * Math.sin(x * 0.085 + phaseA) +
      1.5 * Math.sin(x * 0.21 + phaseB) +
      0.7 * Math.sin(x * 0.47 + phaseC);
    const height = Math.round(base - hills * plateau);
    return Math.min(CONFIG.worldHeight - 12, Math.max(18, height));
  }

  function caveMask(seed, x, y) {
    const phase = RNG.hash2(0, 0, seed) * Math.PI * 2;
    const primary = Math.sin(x * 0.31 + phase) * Math.sin(y * 0.43 - phase * 0.6);
    const secondary = Math.sin((x + y) * 0.19 + phase * 1.7);
    const pocket = RNG.hash2(x, y, seed);
    return primary + secondary * 0.55 + (pocket - 0.5) * 0.35;
  }

  function isTerrainBlock(block) {
    return (
      block === CONFIG.blocks.grass ||
      block === CONFIG.blocks.dirt ||
      block === CONFIG.blocks.stone ||
      block === CONFIG.blocks.sand
    );
  }

  function plantTree(world, x, groundY, seed) {
    if (groundY < 6) {
      return;
    }
    const random = RNG.createRandom((seed ^ RNG.hashString("tree:" + x)) >>> 0);
    const trunkHeight = random.int(3, 5);
    if (groundY - trunkHeight - 3 < 1) {
      return;
    }
    for (let step = 1; step <= trunkHeight; step += 1) {
      setBlock(world, x, groundY - step, CONFIG.blocks.wood);
    }
    const crownY = groundY - trunkHeight;
    for (let dy = -2; dy <= 1; dy += 1) {
      const radius = dy === 1 ? 1 : 2;
      for (let dx = -radius; dx <= radius; dx += 1) {
        if (dx === 0 && dy === 0) {
          continue;
        }
        if (Math.abs(dx) === radius && Math.abs(dy) === 2) {
          continue;
        }
        const targetX = x + dx;
        const targetY = crownY + dy;
        if (getBlock(world, targetX, targetY) === AIR) {
          setBlock(world, targetX, targetY, CONFIG.blocks.leaves);
        }
      }
    }
  }

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const data = new Uint8Array(width * height);
    const world = {
      width: width,
      height: height,
      seed: Number(seed) >>> 0,
      data: data
    };
    const baseGround = Math.floor(height * 0.65);
    const random = RNG.createRandom((world.seed ^ RNG.hashString("decoration")) >>> 0);
    const heights = new Array(width);

    for (let x = 0; x < width; x += 1) {
      heights[x] = terrainHeight(world.seed, x);
      const surface = heights[x];
      const beach = surface >= baseGround + 2;
      const topBlock = beach ? CONFIG.blocks.sand : CONFIG.blocks.grass;
      const dirtDepth = 3 + (RNG.hash2(x, 0, world.seed) < 0.5 ? 0 : 1);

      for (let y = surface; y < height; y += 1) {
        let block;
        if (y === surface) {
          block = topBlock;
        } else if (y <= surface + dirtDepth) {
          block = beach ? CONFIG.blocks.sand : CONFIG.blocks.dirt;
        } else {
          block = CONFIG.blocks.stone;
        }
        data[y * width + x] = block;
      }
    }

    // Carve cave pockets below the surface, never through the surface itself
    // and never through the bedrock floor.
    for (let x = 0; x < width; x += 1) {
      const surface = heights[x];
      for (let y = surface + 6; y < height - 2; y += 1) {
        if (caveMask(world.seed, x, y) > 0.62) {
          data[y * width + x] = AIR;
        }
      }
    }

    // Trees grow on grass away from the spawn plateau; each one is derived from
    // the seed so the same seed always rebuilds the same forest.
    let lastTreeX = -10;
    for (let x = SPAWN_MIN_X + 6; x < width - 4; x += 1) {
      if (x - lastTreeX < 3) {
        continue;
      }
      if (RNG.hash2(x, 11, world.seed) > 0.86) {
        const surface = heights[x];
        if (data[surface * width + x] === CONFIG.blocks.grass) {
          plantTree(world, x, surface, world.seed);
          lastTreeX = x;
        }
      }
    }

    // The spawn plateau is kept clear so the player always starts in open air.
    for (let x = 2; x < SPAWN_MIN_X + 2; x += 1) {
      for (let y = 0; y < heights[x]; y += 1) {
        data[y * width + x] = AIR;
      }
    }

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
    return block !== null && block !== AIR;
  }

  // Surface y per column: the top-most terrain block, ignoring trees and
  // leaves. Used for depth shading and spawn searches.
  function surfaceMap(world) {
    const map = new Uint8Array(world.width);
    for (let x = 0; x < world.width; x += 1) {
      let surface = world.height;
      for (let y = 0; y < world.height; y += 1) {
        if (isTerrainBlock(world.data[y * world.width + x])) {
          surface = y;
          break;
        }
      }
      map[x] = surface;
    }
    return map;
  }

  function columnTop(world, x) {
    for (let y = 0; y < world.height; y += 1) {
      if (world.data[y * world.width + x] !== AIR) {
        return y;
      }
    }
    return world.height;
  }

  function findSpawn(world) {
    const start = Math.floor(world.width / 2);
    for (let radius = 0; radius < Math.floor(world.width / 2); radius += 1) {
      const candidates = radius === 0 ? [start] : [start + radius, start - radius];
      for (let index = 0; index < candidates.length; index += 1) {
        const x = candidates[index];
        if (x < SPAWN_MIN_X || x > SPAWN_MAX_X) {
          continue;
        }
        const top = columnTop(world, x);
        if (top + 2 >= world.height) {
          continue;
        }
        const ground = getBlock(world, x, top);
        if (!isSolid(world, x, top) || !isTerrainBlock(ground)) {
          continue;
        }
        if (isSolid(world, x, top - 1) || isSolid(world, x, top - 2)) {
          continue;
        }
        return { x: x + 0.5, y: top };
      }
    }
    return { x: start + 0.5, y: Math.floor(world.height * 0.65) };
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

  return {
    createWorld: createWorld,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    isTerrainBlock: isTerrainBlock,
    terrainHeight: terrainHeight,
    surfaceMap: surfaceMap,
    columnTop: columnTop,
    findSpawn: findSpawn,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
