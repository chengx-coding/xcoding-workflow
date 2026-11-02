(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"));
  } else {
    root.SandboxLighting = factory(root.SandboxConfig, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS) {
  "use strict";

  if (!CONFIG || !BLOCKS) {
    throw new Error("SandboxConfig and SandboxBlocks are required before SandboxLighting");
  }

  const MAX_LIGHT = 15;

  function createLight(world) {
    return {
      sky: new Uint8Array(world.width * world.height),
      block: new Uint8Array(world.width * world.height)
    };
  }

  function opaque(id) {
    const definition = BLOCKS.block(id);
    if (!definition || !definition.solid) {
      return false;
    }
    return !definition.transparent;
  }

  function spread(world, field, queue) {
    const width = world.width;
    const height = world.height;
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
      const neighbours = [
        x > 0 ? index - 1 : -1,
        x < width - 1 ? index + 1 : -1,
        y > 0 ? index - width : -1,
        y < height - 1 ? index + width : -1
      ];
      for (let step = 0; step < neighbours.length; step += 1) {
        const next = neighbours[step];
        if (next < 0 || opaque(world.data[next])) {
          continue;
        }
        if (field[next] < level - 1) {
          field[next] = level - 1;
          queue.push(next);
        }
      }
    }
  }

  function relight(world, light) {
    const width = world.width;
    const height = world.height;
    const sky = light.sky;
    const block = light.block;
    sky.fill(0);
    block.fill(0);

    const skyQueue = [];
    for (let x = 0; x < width; x += 1) {
      for (let y = 0; y < height; y += 1) {
        const index = y * width + x;
        if (opaque(world.data[index])) {
          break;
        }
        sky[index] = MAX_LIGHT;
        skyQueue.push(index);
      }
    }
    spread(world, sky, skyQueue);

    const blockQueue = [];
    for (let index = 0; index < world.data.length; index += 1) {
      const emission = BLOCKS.lightOf(world.data[index]);
      if (emission > 0) {
        block[index] = emission;
        blockQueue.push(index);
      }
    }
    spread(world, block, blockQueue);

    return light;
  }

  function daylightAt(t) {
    const wrapped = ((t % 1) + 1) % 1;
    const elevation = Math.sin(wrapped * Math.PI * 2);
    const normalised = Math.min(Math.max((elevation + 0.12) / 0.55, 0), 1);
    return 0.16 + 0.84 * normalised;
  }

  function brightnessAt(light, x, y, daylight, width) {
    const index = y * width + x;
    const sky = light.sky[index] * daylight;
    const block = light.block[index];
    const level = Math.max(sky, block);
    return level / MAX_LIGHT;
  }

  return {
    MAX_LIGHT: MAX_LIGHT,
    createLight: createLight,
    relight: relight,
    daylightAt: daylightAt,
    brightnessAt: brightnessAt,
    opaque: opaque
  };
});
