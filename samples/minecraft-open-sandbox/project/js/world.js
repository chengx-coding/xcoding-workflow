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
  const GROUND_ROW = Math.floor(CONFIG.worldHeight * 0.65);
  const PLATEAU_END = 48;
  const AIR = B.air;

  function indexOf(world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return -1;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return -1;
    }
    return y * world.width + x;
  }

  function inBounds(world, x, y) {
    return x >= 0 && y >= 0 && x < world.width && y < world.height;
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

  function isSolidId(block) {
    return block !== AIR && block !== B.torch;
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    return block !== null && isSolidId(block);
  }

  function isSolidAt(world, x, y) {
    if (!inBounds(world, x, y)) {
      return false;
    }
    return isSolid(world, x, y);
  }

  function isAirAt(world, x, y) {
    return getBlock(world, x, y) === AIR;
  }

  function isExposed(world, x, y) {
    return (
      isAirAt(world, x - 1, y) ||
      isAirAt(world, x + 1, y) ||
      isAirAt(world, x, y - 1) ||
      isAirAt(world, x, y + 1)
    );
  }

  function canPlaceAt(world, x, y, block) {
    if (!inBounds(world, x, y) || getBlock(world, x, y) !== AIR) {
      return false;
    }
    const supported =
      isSolidAt(world, x - 1, y) ||
      isSolidAt(world, x + 1, y) ||
      isSolidAt(world, x, y - 1) ||
      isSolidAt(world, x, y + 1);
    if (!supported) {
      return false;
    }
    if (block === B.torch) {
      return isSolidAt(world, x, y + 1) || isSolidAt(world, x - 1, y) || isSolidAt(world, x + 1, y);
    }
    return true;
  }

  function surfaceHeight(world, x) {
    if (x < 0 || x >= world.width) {
      return -1;
    }
    for (let y = 0; y < world.height; y += 1) {
      if (getBlock(world, x, y) !== AIR) {
        return y;
      }
    }
    return world.height;
  }

  function sampleColumns(world, x0, x1, count) {
    const columns = [];
    const start = Math.max(0, Math.min(world.width - 1, Math.floor(x0)));
    const end = Math.max(start + 1, Math.min(world.width, Math.ceil(x1)));
    const total = Math.max(1, Math.floor(count));
    for (let i = 0; i < total; i += 1) {
      const x = total === 1 ? start : Math.round(start + ((end - 1 - start) * i) / (total - 1));
      const surface = surfaceHeight(world, x);
      columns.push({ x: x, surface: surface, top: getBlock(world, x, surface) || AIR });
    }
    return columns;
  }

  function terrainHeightAt(x, seed) {
    if (x <= PLATEAU_END) {
      return GROUND_ROW;
    }
    const grow = Math.min(1, (x - PLATEAU_END) / 75);
    const ridge = (RNG.valueNoise1D(x / 30, seed + 7101) - 0.5) * 2;
    const detail = (RNG.valueNoise1D(x / 9, seed + 7102) - 0.5) * 2;
    const height = GROUND_ROW + Math.round(grow * (ridge * 8 + detail * 1.6));
    return Math.max(GROUND_ROW - 9, Math.min(GROUND_ROW + 9, height));
  }

  function carveCaves(world, seed) {
    const width = world.width;
    const height = world.height;
    const random = RNG.mulberry32(seed ^ 0x9e3779b9);
    let carved = 0;
    for (let x = 0; x < width; x += 1) {
      const top = terrainHeightAt(x, seed);
      for (let y = top + 6; y < height - 2; y += 1) {
        const depth = (y - top) / Math.max(1, height - top);
        const shape = RNG.fbm2D(x * 0.085, y * 0.11, seed + 4401, 3);
        const tunnel = RNG.valueNoise2D(x * 0.045, y * 0.07, seed + 4402);
        const threshold = 0.625 - depth * 0.035;
        const shaft =
          RNG.valueNoise2D(x * 0.19, y * 0.02, seed + 4403) > 0.855 && depth > 0.18;
        if ((shape > threshold && tunnel > 0.34) || shaft) {
          world.data[y * width + x] = AIR;
          carved += 1;
        }
      }
    }
    if (carved < 120) {
      const tunnelTop = Math.min(height - 6, GROUND_ROW + 12);
      for (let x = 60; x < Math.min(width - 2, 170); x += 1) {
        const wobble = Math.round(Math.sin(x * 0.4 + random()) * 1.2);
        for (let t = 0; t < 2; t += 1) {
          const y = tunnelTop + wobble + t;
          if (y > 0 && y < height - 2) {
            world.data[y * width + x] = AIR;
            carved += 1;
          }
        }
      }
    }
    return carved;
  }

  function placeVein(world, block, x, y, size) {
    const width = world.width;
    const height = world.height;
    let cx = x;
    let cy = y;
    const random = RNG.mulberry32((x * 73856093) ^ (y * 19349663) ^ block);
    for (let step = 0; step < size; step += 1) {
      if (cx > 1 && cx < width - 1 && cy > 2 && cy < height - 2) {
        const index = cy * width + cx;
        if (world.data[index] === B.stone) {
          world.data[index] = block;
        }
      }
      const roll = random();
      if (roll < 0.36) {
        cx += random() < 0.5 ? -1 : 1;
      } else if (roll < 0.72) {
        cy += random() < 0.5 ? -1 : 1;
      } else {
        cx += random() < 0.5 ? -1 : 1;
        cy += random() < 0.5 ? -1 : 1;
      }
    }
  }

  function populateOres(world, seed) {
    const width = world.width;
    const height = world.height;
    const random = RNG.mulberry32(seed + 991);
    const bands = [
      { block: B.coal_ore, minY: GROUND_ROW + 4, maxY: GROUND_ROW + 26, veins: 170, size: 5 },
      { block: B.iron_ore, minY: GROUND_ROW + 15, maxY: GROUND_ROW + 38, veins: 110, size: 4 },
      { block: B.ember_ore, minY: height - 26, maxY: height - 4, veins: 72, size: 3 }
    ];
    const counts = {};
    for (let b = 0; b < bands.length; b += 1) {
      const band = bands[b];
      let placed = 0;
      for (let i = 0; i < band.veins; i += 1) {
        const x = 2 + Math.floor(random() * (width - 4));
        const y = band.minY + Math.floor(random() * Math.max(1, band.maxY - band.minY));
        placeVein(world, band.block, x, y, band.size);
        placed += 1;
      }
      // Deterministically guarantee the band exists even on unlucky seeds.
      let found = 0;
      for (let y = band.minY; y < band.maxY; y += 1) {
        for (let x = 2; x < width - 2; x += 1) {
          if (getBlock(world, x, y) === band.block) {
            found += 1;
          }
        }
      }
      let attempt = 0;
      while (found < 24 && attempt < 40) {
        const x = 8 + ((attempt * 71 + seed) % (width - 20));
        const y = band.minY + ((attempt * 13) % Math.max(1, band.maxY - band.minY));
        placeVein(world, band.block, x, y, Math.max(3, band.size));
        found += 3;
        attempt += 1;
      }
      counts[band.block] = found;
    }
    return counts;
  }

  function plantTree(world, x, height) {
    const base = surfaceHeight(world, x);
    for (let y = 0; y < height; y += 1) {
      const ty = base - 1 - y;
      if (ty > 0) {
        setBlock(world, x, ty, B.wood);
      }
    }
    const top = base - height;
    for (let dy = -2; dy <= 1; dy += 1) {
      const radius = dy === 1 ? 1 : 2;
      for (let dx = -radius; dx <= radius; dx += 1) {
        if (dx === 0 && dy <= 0) {
          continue;
        }
        const tx = x + dx;
        const ty = top + dy;
        if (inBounds(world, tx, ty) && getBlock(world, tx, ty) === AIR) {
          setBlock(world, tx, ty, B.leaves);
        }
      }
    }
  }

  function populateTrees(world, seed) {
    const width = world.width;
    const random = RNG.mulberry32(seed + 3313);
    let trees = 0;
    let lastX = -10;
    const fixed = [34, 41, 66, 73];
    for (let i = 0; i < fixed.length; i += 1) {
      const x = fixed[i];
      if (x < width - 3 && surfaceHeight(world, x) === GROUND_ROW) {
        plantTree(world, x, 4 + (i % 3));
        lastX = x;
        trees += 1;
      }
    }
    for (let x = PLATEAU_END + 2; x < width - 4; x += 1) {
      if (x - lastX < 5) {
        continue;
      }
      if (random() > 0.085) {
        continue;
      }
      const top = surfaceHeight(world, x);
      if (getBlock(world, x, top) !== B.grass) {
        continue;
      }
      plantTree(world, x, 4 + Math.floor(random() * 3));
      lastX = x;
      trees += 1;
    }
    return trees;
  }

  function generate(world) {
    const width = world.width;
    const height = world.height;
    const seed = world.seed;
    const heights = new Int16Array(width);

    for (let x = 0; x < width; x += 1) {
      const h = terrainHeightAt(x, seed);
      heights[x] = h;
      const desert = x > 70 && RNG.valueNoise1D(x / 46, seed + 505) > 0.7;
      const soil = desert ? B.sand : B.dirt;
      const top = desert ? B.sand : B.grass;
      for (let y = h; y < height; y += 1) {
        let block = B.stone;
        if (y === h) {
          block = top;
        } else if (y <= h + 4) {
          block = soil;
        }
        world.data[y * width + x] = block;
      }
    }

    carveCaves(world, seed);
    const oreCounts = populateOres(world, seed);
    const trees = populateTrees(world, seed);

    // The world floor is unbreakable in practice: keep the bottom row stone.
    for (let x = 0; x < width; x += 1) {
      world.data[(height - 1) * width + x] = B.stone;
    }

    world.meta = {
      ground: GROUND_ROW,
      trees: trees,
      ores: oreCounts,
      spawn: { x: CONFIG.spawnX, y: GROUND_ROW }
    };
    return world;
  }

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const numericSeed = seed === undefined || seed === null ? CONFIG.seed : Number(seed) >>> 0;
    const world = {
      width: width,
      height: height,
      seed: numericSeed,
      data: new Uint8Array(width * height),
      meta: null
    };
    return generate(world);
  }

  function encodeRLE(data) {
    const pairs = [];
    let current = data[0];
    let count = 1;
    for (let i = 1; i < data.length; i += 1) {
      if (data[i] === current) {
        count += 1;
      } else {
        pairs.push([current, count]);
        current = data[i];
        count = 1;
      }
    }
    pairs.push([current, count]);
    return pairs;
  }

  function decodeRLE(pairs, length) {
    const data = new Uint8Array(length);
    let offset = 0;
    for (let i = 0; i < pairs.length; i += 1) {
      const pair = pairs[i];
      if (!Array.isArray(pair) || pair.length !== 2) {
        throw new Error("Invalid world run");
      }
      const block = pair[0];
      const count = pair[1];
      if (!Number.isInteger(block) || !Number.isInteger(count) || count <= 0) {
        throw new Error("Invalid world run");
      }
      if (offset + count > length) {
        throw new Error("World runs exceed block data");
      }
      data.fill(block, offset, offset + count);
      offset += count;
    }
    if (offset !== length) {
      throw new Error("World runs do not fill block data");
    }
    return data;
  }

  function serializeWorld(world) {
    return JSON.stringify({
      width: world.width,
      height: world.height,
      seed: world.seed,
      rle: encodeRLE(world.data)
    });
  }

  function deserializeWorld(text) {
    const parsed = typeof text === "string" ? JSON.parse(text) : text;
    if (!parsed || !Number.isInteger(parsed.width) || !Number.isInteger(parsed.height)) {
      throw new Error("Invalid world payload");
    }
    if (parsed.width <= 0 || parsed.height <= 0) {
      throw new Error("Invalid world size");
    }
    const length = parsed.width * parsed.height;
    let data;
    if (Array.isArray(parsed.rle)) {
      data = decodeRLE(parsed.rle, length);
    } else if (Array.isArray(parsed.data)) {
      if (parsed.data.length !== length) {
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
      data: data,
      meta: null
    };
  }

  return {
    GROUND_ROW: GROUND_ROW,
    PLATEAU_END: PLATEAU_END,
    indexOf: indexOf,
    inBounds: inBounds,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolidId: isSolidId,
    isSolid: isSolid,
    isSolidAt: isSolidAt,
    isAirAt: isAirAt,
    isExposed: isExposed,
    canPlaceAt: canPlaceAt,
    surfaceHeight: surfaceHeight,
    sampleColumns: sampleColumns,
    createWorld: createWorld,
    terrainHeightAt: terrainHeightAt,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld,
    encodeRLE: encodeRLE,
    decodeRLE: decodeRLE
  };
});
