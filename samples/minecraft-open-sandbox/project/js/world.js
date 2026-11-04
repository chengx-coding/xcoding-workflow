(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./rng.js"));
  } else {
    root.SandboxWorld = factory(root.SandboxConfig, root.SandboxRng);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, RNG) {
  "use strict";

  if (!CONFIG || !RNG) {
    throw new Error("SandboxConfig and SandboxRng are required before SandboxWorld");
  }

  const B = CONFIG.blocks;
  const AIR = B.air;
  const TOP_LIGHT = 15;
  const TORCH_LIGHT = 14;

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

  function getBlockDef(blockId) {
    return CONFIG.blockDefs[blockId] || CONFIG.blockDefs[0];
  }

  function getBlockKey(blockId) {
    return getBlockDef(blockId).key;
  }

  function isOpaque(blockId) {
    const definition = getBlockDef(blockId);
    return definition.solid && !definition.transparent;
  }

  function isTransparent(blockId) {
    return !!getBlockDef(blockId).transparent;
  }

  function setBlock(world, x, y, block) {
    const index = indexOf(world, x, y);
    if (index < 0) {
      return false;
    }
    if (!Number.isInteger(block) || block < 0 || block >= CONFIG.blockDefs.length) {
      return false;
    }
    world.data[index] = block;
    return true;
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    return block !== null && !!getBlockDef(block).solid;
  }

  function isProtected(world, x, y) {
    return y >= world.height - 2;
  }

  function findSurfaceY(world, x) {
    if (x < 0 || x >= world.width) {
      return -1;
    }
    for (let y = 0; y < world.height; y += 1) {
      if (isSolid(world, x, y)) {
        return y;
      }
    }
    return world.height - 1;
  }

  function carveCaves(world, surface, baseY) {
    const seed = world.seed;
    for (let x = 20; x < world.width - 1; x += 1) {
      const startY = surface[x] + 4;
      for (let y = startY; y < world.height - 2; y += 1) {
        const current = world.data[y * world.width + x];
        if (current !== B.stone && current !== B.dirt) {
          continue;
        }
        const bandA = Math.abs(RNG.valueNoise2D(x * 0.057, y * 0.083, seed + 301) - 0.5);
        const bandB = Math.abs(RNG.valueNoise2D(x * 0.057 + 31, y * 0.083 - 17, seed + 302) - 0.5);
        const tunnel = bandA + bandB < 0.055;
        const depth = y - surface[x];
        const cavern = depth > 14 && y > baseY + 6 && RNG.fbm2(x * 0.027, y * 0.043, seed + 401, 3, 0.55) > 0.69;
        if (tunnel || cavern) {
          world.data[y * world.width + x] = AIR;
        }
      }
    }
  }

  function placeOres(world, surface) {
    const seed = world.seed;
    const cellSize = 2;
    for (let cx = 10; cx < Math.floor(world.width / cellSize) - 1; cx += 1) {
      for (let cy = 2; cy < Math.floor((world.height - 3) / cellSize); cy += 1) {
        const roll = RNG.hash2(cx, cy, seed + 501);
        const depth = cy * cellSize - surface[Math.min(world.width - 1, cx * cellSize)];
        if (depth < 5) {
          continue;
        }
        let ore = AIR;
        let spread = 0;
        if (roll < 0.013 && depth > 4) {
          ore = B.coalOre;
          spread = 1;
        } else if (roll > 0.995 && depth > 20) {
          ore = B.ironOre;
          spread = 1;
        }
        if (ore === AIR) {
          continue;
        }
        for (let dx = 0; dx <= spread; dx += 1) {
          for (let dy = 0; dy <= spread; dy += 1) {
            const x = cx * cellSize + dx;
            const y = cy * cellSize + dy;
            if (x <= 0 || y <= 2 || x >= world.width || y >= world.height - 2) {
              continue;
            }
            if (world.data[y * world.width + x] === B.stone) {
              world.data[y * world.width + x] = ore;
            }
          }
        }
      }
    }
  }

  function placeTree(world, x, groundY, height, rand) {
    if (groundY - height - 2 < 1) {
      return false;
    }
    const trunkTop = groundY - height;
    for (let step = 1; step <= height; step += 1) {
      const y = groundY - step;
      if (y >= 0) {
        world.data[y * world.width + x] = B.wood;
      }
    }
    const centerY = trunkTop - 1;
    for (let dy = -2; dy <= 2; dy += 1) {
      const radius = dy === -2 || dy === 2 ? 1 : 2;
      for (let dx = -radius; dx <= radius; dx += 1) {
        if (dx === 0 && dy === 0) {
          continue;
        }
        if (Math.abs(dx) === radius && Math.abs(dy) === 2 && rand() < 0.5) {
          continue;
        }
        const lx = x + dx;
        const ly = centerY + dy;
        if (lx < 0 || ly < 0 || lx >= world.width || ly >= world.height) {
          continue;
        }
        const index = ly * world.width + lx;
        if (world.data[index] === AIR) {
          world.data[index] = B.leaves;
        }
      }
    }
    return true;
  }

  function generateTerrain(world) {
    const width = world.width;
    const height = world.height;
    const seed = world.seed;
    const baseY = Math.floor(height * CONFIG.baseGroundRatio);
    const surface = new Int16Array(width);
    const treeRand = RNG.sampleRng(seed, 777);
    let lastTreeX = -100;

    for (let x = 0; x < width; x += 1) {
      let hill;
      if (x < 22) {
        hill = baseY;
      } else {
        const broad = RNG.fbm1(x * 0.018 + 7.3, seed + 101, 4, 0.55) - 0.5;
        const detail = RNG.fbm1(x * 0.071 + 2.1, seed + 211, 2, 0.5) - 0.5;
        hill = baseY + Math.round(broad * 18 + detail * 5);
        if (x < 42) {
          const blend = (x - 22) / 20;
          hill = Math.round(baseY * (1 - blend) + hill * blend);
        }
      }
      hill = Math.max(30, Math.min(height - 9, hill));
      surface[x] = hill;
      const lowValley = hill > baseY + 6 && x > 24;
      for (let y = hill; y < height; y += 1) {
        let block = B.stone;
        if (y === hill) {
          block = lowValley ? B.sand : B.grass;
        } else if (y < hill + 4) {
          block = lowValley ? B.sand : B.dirt;
        }
        world.data[y * width + x] = block;
      }
    }

    carveCaves(world, surface, baseY);
    placeOres(world, surface);

    for (let x = 24; x < width - 7; x += 1) {
      if (x - lastTreeX < 6) {
        continue;
      }
      const groundY = surface[x];
      if (world.data[groundY * width + x] !== B.grass) {
        continue;
      }
      if (treeRand() > 0.16) {
        continue;
      }
      const treeHeight = 4 + Math.floor(treeRand() * 4);
      if (placeTree(world, x, groundY - 1, treeHeight, treeRand)) {
        lastTreeX = x;
      }
    }

    const decorRand = RNG.sampleRng(seed, 909);
    for (let x = 22; x < width - 1; x += 1) {
      const groundY = surface[x];
      if (world.data[groundY * width + x] !== B.grass) {
        continue;
      }
      if (groundY - 1 < 0 || world.data[(groundY - 1) * width + x] !== AIR) {
        continue;
      }
      const roll = decorRand();
      if (roll < 0.09) {
        world.data[(groundY - 1) * width + x] = B.flower;
      } else if (roll < 0.34) {
        world.data[(groundY - 1) * width + x] = B.tallGrass;
      }
    }

    world.surface = surface;
    world.spawn = findSpawn(world, surface);
    clearSpawn(world, world.spawn);
    world.base = Uint8Array.from(world.data);
  }

  function findSpawn(world, surface) {
    const preferred = Math.floor(world.width * 0.43);
    let best = preferred;
    let bestScore = Infinity;
    for (let radius = 0; radius < Math.floor(world.width / 2); radius += 1) {
      const candidates = radius === 0 ? [preferred] : [preferred - radius, preferred + radius];
      for (let index = 0; index < candidates.length; index += 1) {
        const x = candidates[index];
        if (x < 4 || x >= world.width - 4) {
          continue;
        }
        const ground = surface[x];
        const groundBlock = world.data[ground * world.width + x];
        if (groundBlock !== B.grass && groundBlock !== B.sand) {
          continue;
        }
        let open = true;
        for (let y = ground - 3; y < ground; y += 1) {
          if (y < 0 || world.data[y * world.width + x] !== AIR) {
            open = false;
            break;
          }
        }
        if (!open) {
          continue;
        }
        let score = Math.abs(x - preferred);
        for (let dx = -1; dx <= 1; dx += 1) {
          const neighbor = surface[Math.max(0, Math.min(world.width - 1, x + dx))];
          score += Math.abs(neighbor - ground);
        }
        if (score < bestScore) {
          bestScore = score;
          best = x;
        }
      }
      if (bestScore < 3) {
        break;
      }
    }
    return { x: best + 0.5, y: surface[best] };
  }

  function clearSpawn(world, spawn) {
    const baseX = Math.floor(spawn.x);
    const baseY = Math.floor(spawn.y);
    for (let dx = -2; dx <= 2; dx += 1) {
      for (let dy = -4; dy <= 0; dy += 1) {
        const x = baseX + dx;
        const y = baseY + dy;
        if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
          continue;
        }
        const index = y * world.width + x;
        if (y < baseY) {
          world.data[index] = AIR;
        } else if (dx === 0) {
          world.data[index] = B.grass;
        }
      }
    }
  }

  function createWorld(seed) {
    const world = {
      width: CONFIG.worldWidth,
      height: CONFIG.worldHeight,
      seed: Number(seed === undefined ? CONFIG.seed : seed) >>> 0,
      data: new Uint8Array(CONFIG.worldWidth * CONFIG.worldHeight),
      surface: null,
      base: null,
      spawn: null,
      light: null
    };
    generateTerrain(world);
    updateLight(world);
    return world;
  }

  function recomputeLight(world) {
    const width = world.width;
    const height = world.height;
    const count = width * height;
    const sky = new Uint8Array(count);
    const blockLight = new Uint8Array(count);
    const skyQueue = [];
    const torchQueue = [];

    for (let x = 0; x < width; x += 1) {
      for (let y = 0; y < height; y += 1) {
        const index = y * width + x;
        if (isOpaque(world.data[index])) {
          break;
        }
        sky[index] = TOP_LIGHT;
        skyQueue.push(index);
      }
    }

    for (let index = 0; index < count; index += 1) {
      if (getBlockDef(world.data[index]).light > 0) {
        blockLight[index] = TORCH_LIGHT;
        torchQueue.push(index);
      }
    }

    function spread(queue, field) {
      let head = 0;
      while (head < queue.length) {
        const index = queue[head];
        head += 1;
        const level = field[index];
        if (level <= 1) {
          continue;
        }
        const x = index % width;
        const y = (index - x) / width;
        const neighbors = [
          x > 0 ? index - 1 : -1,
          x < width - 1 ? index + 1 : -1,
          y > 0 ? index - width : -1,
          y < height - 1 ? index + width : -1
        ];
        for (let n = 0; n < neighbors.length; n += 1) {
          const next = neighbors[n];
          if (next < 0 || isOpaque(world.data[next])) {
            continue;
          }
          const nextLevel = level - 1;
          if (field[next] < nextLevel) {
            field[next] = nextLevel;
            queue.push(next);
          }
        }
      }
    }

    spread(skyQueue, sky);
    spread(torchQueue, blockLight);
    world.light = { sky: sky, block: blockLight };
    return world.light;
  }

  function updateLight(world) {
    return recomputeLight(world);
  }

  function lightAt(world, x, y, dayFactor) {
    if (!world.light) {
      return 0;
    }
    const index = indexOf(world, x, y);
    if (index < 0) {
      return 0;
    }
    const daylight = Math.max(0, Math.min(1, dayFactor === undefined ? 1 : dayFactor));
    return Math.max(world.light.sky[index] * daylight, world.light.block[index]);
  }

  function dayFactor(timeOfDay) {
    const sun = Math.sin((timeOfDay - 0.25) * Math.PI * 2);
    return Math.max(0.12, Math.min(1, sun * 1.35 + 0.4));
  }

  function lightLevelAt(world, x, y, timeOfDay) {
    return lightAt(world, x, y, dayFactor(timeOfDay));
  }

  function getChanges(world) {
    if (!world.base) {
      return [];
    }
    const changes = [];
    for (let index = 0; index < world.data.length; index += 1) {
      if (world.data[index] !== world.base[index]) {
        const x = index % world.width;
        const y = (index - x) / world.width;
        changes.push([x, y, world.data[index]]);
      }
    }
    return changes;
  }

  function applyChanges(world, changes) {
    if (!Array.isArray(changes)) {
      return 0;
    }
    let applied = 0;
    for (let index = 0; index < changes.length; index += 1) {
      const change = changes[index];
      if (!Array.isArray(change) || change.length < 3) {
        continue;
      }
      const x = change[0];
      const y = change[1];
      const block = change[2];
      if (!Number.isInteger(x) || !Number.isInteger(y) || !Number.isInteger(block)) {
        continue;
      }
      if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
        continue;
      }
      if (block < 0 || block >= CONFIG.blockDefs.length) {
        continue;
      }
      if (setBlock(world, x, y, block)) {
        applied += 1;
      }
    }
    updateLight(world);
    return applied;
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
    for (let index = 0; index < parsed.data.length; index += 1) {
      const block = parsed.data[index];
      if (!Number.isInteger(block) || block < 0 || block >= CONFIG.blockDefs.length) {
        throw new Error("Invalid block id in world data");
      }
    }
    const world = {
      width: parsed.width,
      height: parsed.height,
      seed: Number(parsed.seed) >>> 0,
      data: Uint8Array.from(parsed.data),
      surface: null,
      base: null,
      spawn: null,
      light: null
    };
    world.base = Uint8Array.from(world.data);
    updateLight(world);
    return world;
  }

  function blockName(blockId) {
    return CONFIG.blockNames[blockId] || "unknown";
  }

  return {
    createWorld: createWorld,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    isProtected: isProtected,
    isOpaque: isOpaque,
    isTransparent: isTransparent,
    getBlockDef: getBlockDef,
    getBlockKey: getBlockKey,
    blockName: blockName,
    findSurfaceY: findSurfaceY,
    getChanges: getChanges,
    applyChanges: applyChanges,
    updateLight: updateLight,
    lightAt: lightAt,
    lightLevelAt: lightLevelAt,
    dayFactor: dayFactor,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
