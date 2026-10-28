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

  const GROUND = Math.floor(CONFIG.worldHeight * 0.65);
  const PLATEAU_END = 24;
  const PLATEAU_BLEND = 12;
  const MIN_SURFACE = 12;
  const MAX_SURFACE = GROUND + 2;

  function mix32(value) {
    let mixed = value >>> 0;
    mixed = Math.imul(mixed ^ (mixed >>> 16), 0x45d9f3b);
    mixed = Math.imul(mixed ^ (mixed >>> 16), 0x45d9f3b);
    return (mixed ^ (mixed >>> 16)) >>> 0;
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

  function smoothstep(edge0, edge1, value) {
    if (edge1 <= edge0) {
      return value < edge0 ? 0 : 1;
    }
    const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  function terrainProfile(seed) {
    const random = mulberry32(mix32(seed));
    return {
      amplitude: 3 + Math.floor(random() * 4),
      phaseA: random() * Math.PI * 2,
      phaseB: random() * Math.PI * 2,
      phaseC: random() * Math.PI * 2,
      treeSeed: mix32((seed >>> 0) ^ 0x85ebca6b)
    };
  }

  function heightFor(profile, column) {
    if (column <= PLATEAU_END) {
      return GROUND;
    }
    const blend = smoothstep(PLATEAU_END, PLATEAU_END + PLATEAU_BLEND, column);
    const wave =
      0.55 * Math.sin(column / 17 + profile.phaseA) +
      0.3 * Math.sin(column / 7.5 + profile.phaseB) +
      0.15 * Math.sin(column / 3.3 + profile.phaseC);
    return Math.max(MIN_SURFACE, Math.min(MAX_SURFACE, GROUND - Math.round(profile.amplitude * wave * blend)));
  }

  function surfaceHeightAt(seedOrWorld, column) {
    let seed = seedOrWorld;
    if (seedOrWorld && typeof seedOrWorld === "object") {
      seed = seedOrWorld.seed;
    }
    if (!Number.isFinite(column)) {
      return GROUND;
    }
    const index = Math.trunc(column);
    if (index < 0 || index >= CONFIG.worldWidth) {
      return GROUND;
    }
    return heightFor(terrainProfile(Number(seed) >>> 0), index);
  }

  function plantTree(data, width, height, column, surface, trunkHeight) {
    const top = surface - trunkHeight;
    if (top < 2 || column < 2 || column >= width - 2) {
      return;
    }
    for (let y = surface - 1; y >= top; y -= 1) {
      data[y * width + column] = CONFIG.blocks.wood;
    }
    for (let dy = -1; dy <= 1; dy += 1) {
      for (let dx = -2; dx <= 2; dx += 1) {
        if (Math.abs(dx) === 2 && dy !== 0) {
          continue;
        }
        if (dx === 0 && dy >= 0) {
          continue;
        }
        const x = column + dx;
        const y = top + dy;
        if (x < 0 || x >= width || y < 0 || y >= height) {
          continue;
        }
        if (data[y * width + x] === CONFIG.blocks.air) {
          data[y * width + x] = CONFIG.blocks.leaves;
        }
      }
    }
    const capY = top - 1;
    if (capY >= 0) {
      for (let dx = -1; dx <= 1; dx += 1) {
        const x = column + dx;
        if (x >= 0 && x < width && data[capY * width + x] === CONFIG.blocks.air) {
          data[capY * width + x] = CONFIG.blocks.leaves;
        }
      }
    }
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

  function createWorld(seed) {
    const width = CONFIG.worldWidth;
    const height = CONFIG.worldHeight;
    const seedValue = Number(seed) >>> 0;
    const data = new Uint8Array(width * height);
    const profile = terrainProfile(seedValue);

    for (let x = 0; x < width; x += 1) {
      const surface = heightFor(profile, x);
      data[surface * width + x] = CONFIG.blocks.grass;
      for (let y = surface + 1; y < height; y += 1) {
        data[y * width + x] = y <= surface + 3 ? CONFIG.blocks.dirt : CONFIG.blocks.stone;
      }
    }

    // A single tree near the spawn plateau guarantees wood is reachable early.
    plantTree(data, width, height, 18, heightFor(profile, 18), 4);

    const treeRandom = mulberry32(profile.treeSeed);
    let lastTreeColumn = -100;
    for (let x = 30; x < width - 2; x += 1) {
      if (treeRandom() > 0.07 || x - lastTreeColumn < 7) {
        continue;
      }
      const surface = heightFor(profile, x);
      plantTree(data, width, height, x, surface, 3 + Math.floor(treeRandom() * 2));
      lastTreeColumn = x;
    }

    return {
      width: width,
      height: height,
      seed: seedValue,
      data: data
    };
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
    return block !== null && block !== CONFIG.blocks.air;
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
    if (parsed.width <= 0 || parsed.height <= 0 || parsed.width * parsed.height > 1 << 20) {
      throw new Error("Invalid world dimensions");
    }
    if (!Array.isArray(parsed.data) || parsed.data.length !== parsed.width * parsed.height) {
      throw new Error("Invalid world block data");
    }
    for (const value of parsed.data) {
      if (!Number.isInteger(value) || value < 0 || value > 255) {
        throw new Error("Invalid world block value");
      }
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
    surfaceHeightAt: surfaceHeightAt,
    getBlock: getBlock,
    setBlock: setBlock,
    isSolid: isSolid,
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
