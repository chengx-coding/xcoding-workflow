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
    serializeWorld: serializeWorld,
    deserializeWorld: deserializeWorld
  };
});
