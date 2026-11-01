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

  const MAX_BLOCK_ID = 9;

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
    return indexOf(world, x, y) >= 0;
  }

  // Deterministic surface row for one column. Columns 0-24 are the exact flat spawn
  // plateau at the base row, which keeps the seed tests stable for every seed.
  function surfaceHeightAt(seed, x) {
    const normalizedSeed = Number(seed) >>> 0;
    const column = Math.max(0, Math.floor(x));
    if (column <= CONFIG.plateauEndColumn) {
      return CONFIG.baseSurfaceRow;
    }
    let row;
    const noise = RNG.fbm1D((normalizedSeed ^ 0x9e3779b9) >>> 0, column * 0.09, 3);
    if (column <= CONFIG.blendEndColumn) {
      const t = (column - CONFIG.plateauEndColumn) / (CONFIG.blendEndColumn - CONFIG.plateauEndColumn + 1);
      row = Math.round(RNG.lerp(CONFIG.baseSurfaceRow, CONFIG.baseSurfaceRow - noise * 6.5, t));
    } else {
      row = Math.round(CONFIG.baseSurfaceRow - noise * 6.5);
    }
    // A fixed dune patch guarantees visible sand in every generated world.
    if (column >= 70 && column <= 77) {
      row = 36 + (column % 3);
    }
    return RNG.clamp(row, CONFIG.minSurfaceRow, CONFIG.maxSurfaceRow);
  }

  function surfaceKindAt(seed, x) {
    return surfaceHeightAt(seed, x) <= CONFIG.sandMaxSurfaceRow
      ? CONFIG.blocks.sand
      : CONFIG.blocks.grass;
  }

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const normalizedSeed = Number(seed) >>> 0;
    const data = new Uint8Array(width * height);
    const surfaces = new Int16Array(width);

    for (let x = 0; x < width; x += 1) {
      const top = surfaceHeightAt(normalizedSeed, x);
      const sandy = top <= CONFIG.sandMaxSurfaceRow;
      surfaces[x] = top;
      const soilDepth = sandy ? 2 : 3;
      for (let y = top; y < height; y += 1) {
        let block;
        if (y === top) {
          block = sandy ? CONFIG.blocks.sand : CONFIG.blocks.grass;
        } else if (y <= top + soilDepth) {
          block = sandy ? CONFIG.blocks.sand : CONFIG.blocks.dirt;
        } else {
          block = CONFIG.blocks.stone;
        }
        data[y * width + x] = block;
      }
      // Carved caves: winding air pockets that never touch the bedrock rows.
      for (let y = top + 5; y <= height - CONFIG.bedrockRows - 1; y += 1) {
        const cave = RNG.fbm2D((normalizedSeed ^ 0x51ed270b) >>> 0, x * 0.12, y * 0.18, 2);
        if (Math.abs(cave) < 0.045) {
          data[y * width + x] = CONFIG.blocks.air;
        }
      }
    }

    const world = {
      width: width,
      height: height,
      seed: normalizedSeed,
      data: data,
      surfaces: surfaces
    };

    plantTrees(world);
    sealFloor(world);
    return world;
  }

  // The bottom rows are the sealed world floor. They are re-asserted on creation and
  // on every load so a legacy or hand-edited payload cannot open the world.
  function sealFloor(world) {
    const start = Math.max(0, world.height - CONFIG.bedrockRows);
    for (let y = start; y < world.height; y += 1) {
      for (let x = 0; x < world.width; x += 1) {
        world.data[y * world.width + x] = CONFIG.blocks.stone;
      }
    }
    return world;
  }

  function plantTrees(world) {
    const occupied = [];
    for (let index = 0; index < 10; index += 1) {
      const jitter = Math.floor(RNG.unitHash(index, 1, world.seed) * 6);
      const x = 18 + index * 11 + jitter;
      if (x >= world.width - 3) {
        continue;
      }
      if (occupied.some(function (other) {
        return Math.abs(other - x) < 5;
      })) {
        continue;
      }
      if (RNG.unitHash(index, 2, world.seed) < 0.25) {
        continue;
      }
      const top = world.surfaces[x];
      if (top === undefined || top <= CONFIG.sandMaxSurfaceRow) {
        continue;
      }
      if (getBlock(world, x, top) !== CONFIG.blocks.grass) {
        continue;
      }
      const trunkHeight = 3 + Math.floor(RNG.unitHash(index, 3, world.seed) * 3);
      for (let step = 1; step <= trunkHeight; step += 1) {
        setBlock(world, x, top - step, CONFIG.blocks.wood);
      }
      const canopyY = top - trunkHeight;
      for (let dy = -1; dy <= 2; dy += 1) {
        const radius = dy <= 0 ? 2 : 1;
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (dx === 0 && dy <= 0) {
            continue;
          }
          const leafX = x + dx;
          const leafY = canopyY + dy;
          if (inBounds(world, leafX, leafY) && getBlock(world, leafX, leafY) === CONFIG.blocks.air) {
            setBlock(world, leafX, leafY, CONFIG.blocks.leaves);
          }
        }
      }
      occupied.push(x);
    }
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
    if (!Number.isInteger(block) || block < 0 || block > MAX_BLOCK_ID) {
      return false;
    }
    world.data[index] = block;
    return true;
  }

  function isSolid(world, x, y) {
    const block = getBlock(world, x, y);
    return block !== null && block !== CONFIG.blocks.air;
  }

  function spawnPoint(world) {
    const column = CONFIG.spawnColumn;
    return {
      x: column + 0.5,
      y: surfaceHeightAt(world.seed, column)
    };
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
      if (!Number.isInteger(block) || block < 0 || block > MAX_BLOCK_ID) {
        throw new Error("Invalid block id in world data");
      }
    }
    const restored = {
      width: parsed.width,
      height: parsed.height,
      seed: Number(parsed.seed) >>> 0,
      data: Uint8Array.from(parsed.data)
    };
    return sealFloor(restored);
  }
  // Run-length encoding for persistence: [[block, count], ...].
  function encodeBlocks(data) {
    const runs = [];
    let index = 0;
    while (index < data.length) {
      const block = data[index];
      let run = 1;
      while (index + run < data.length && data[index + run] === block) {
        run += 1;
      }
      runs.push([block, run]);
      index += run;
    }
    return runs;
  }

  function decodeBlocks(runs, length) {
    if (!Array.isArray(runs)) {
      throw new Error("Invalid block runs");
    }
    const data = new Uint8Array(length);
    let offset = 0;
    for (let index = 0; index < runs.length; index += 1) {
      const run = runs[index];
      if (!Array.isArray(run) || run.length !== 2) {
        throw new Error("Invalid block run");
      }
      const block = run[0];
      const count = run[1];
      if (!Number.isInteger(block) || block < 0 || block > MAX_BLOCK_ID) {
        throw new Error("Invalid block id in run");
      }
      if (!Number.isInteger(count) || count < 0 || offset + count > length) {
        throw new Error("Invalid block run length");
      }
      data.fill(block, offset, offset + count);
      offset += count;
    }
    if (offset !== length) {
      throw new Error("Block runs do not cover the world");
    }
    return data;
  }

  function worldToRle(world) {
    return {
      width: world.width,
      height: world.height,
      seed: world.seed,
      blocks: encodeBlocks(world.data)
    };
  }

  function worldFromRle(payload) {
    if (!payload || !Number.isInteger(payload.width) || !Number.isInteger(payload.height)) {
      throw new Error("Invalid world payload");
    }
    if (payload.width <= 0 || payload.height <= 0) {
      throw new Error("Invalid world dimensions");
    }
    const data = decodeBlocks(payload.blocks, payload.width * payload.height);
    const restored = {
      width: payload.width,
      height: payload.height,
      seed: Number(payload.seed) >>> 0,
      data: data
    };
    return sealFloor(restored);
  }

  return {
    createWorld: createWorld,
    sealFloor: sealFloor,
    surfaceHeightAt: surfaceHeightAt,
    surfaceKindAt: surfaceKindAt,
    spawnPoint: spawnPoint,
    inBounds: inBounds,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld,
    encodeBlocks: encodeBlocks,
    decodeBlocks: decodeBlocks,
    worldToRle: worldToRle,
    worldFromRle: worldFromRle
  };
});
