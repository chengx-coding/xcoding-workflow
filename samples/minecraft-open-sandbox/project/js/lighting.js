(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"));
  } else {
    root.SandboxLighting = factory(root.SandboxConfig, root.SandboxWorld);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD) {
  "use strict";

  if (!CONFIG || !WORLD) {
    throw new Error("SandboxConfig and SandboxWorld are required before SandboxLighting");
  }

  function smoothstep(t) {
    const value = Math.max(0, Math.min(1, t));
    return value * value * (3 - 2 * value);
  }

  // Time is a 0..1 day fraction: 0 sunrise, 0.25 noon, 0.5 sunset, 0.75 midnight.
  function skyLevelForTime(time) {
    const t = ((time % 1) + 1) % 1;
    if (t < 0.04) {
      return Math.round(4 + smoothstep(t / 0.04) * 11);
    }
    if (t < 0.46) {
      return CONFIG.skyDay;
    }
    if (t < 0.54) {
      return Math.round(CONFIG.skyDay - smoothstep((t - 0.46) / 0.08) * (CONFIG.skyDay - CONFIG.skyNight));
    }
    if (t < 0.96) {
      return CONFIG.skyNight;
    }
    return Math.round(CONFIG.skyNight + smoothstep((t - 0.96) / 0.04) * (CONFIG.skyDay - CONFIG.skyNight));
  }

  function phaseForTime(time) {
    const t = ((time % 1) + 1) % 1;
    if (t < 0.08 || t >= 0.92) {
      return "dawn";
    }
    if (t < 0.44) {
      return "day";
    }
    if (t < 0.56) {
      return "dusk";
    }
    return "night";
  }

  function computeLight(world, skyLevel) {
    const width = world.width;
    const height = world.height;
    const size = width * height;
    const light = new Uint8Array(size);
    const queueIndex = [];
    const queueLevel = [];

    function push(index, level) {
      if (level <= 0 || light[index] >= level) {
        return;
      }
      light[index] = level;
      queueIndex.push(index);
      queueLevel.push(level);
    }

    for (let x = 0; x < width; x += 1) {
      for (let y = 0; y < height; y += 1) {
        const index = y * width + x;
        const block = world.data[index];
        if (WORLD.blockDef(block).solid) {
          break;
        }
        push(index, skyLevel);
      }
    }

    for (let index = 0; index < size; index += 1) {
      const emission = WORLD.blockDef(world.data[index]).light;
      if (emission > 0) {
        push(index, emission);
      }
    }

    let head = 0;
    while (head < queueIndex.length) {
      const index = queueIndex[head];
      const level = queueLevel[head];
      head += 1;
      if (light[index] !== level) {
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
      for (let i = 0; i < neighbours.length; i += 1) {
        const neighbour = neighbours[i];
        if (neighbour < 0) {
          continue;
        }
        const block = world.data[neighbour];
        const solid = WORLD.blockDef(block).solid;
        const attenuation = solid ? 3 : block === CONFIG.blocks.water ? 2 : 1;
        push(neighbour, level - attenuation);
      }
    }

    return light;
  }

  function lightAt(light, world, x, y) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) {
      return 0;
    }
    if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
      return 0;
    }
    return light[y * world.width + x];
  }

  function darknessForLevel(level) {
    const normalized = Math.max(0, Math.min(CONFIG.lightMax, level)) / CONFIG.lightMax;
    return Math.max(0, Math.min(0.94, 1 - normalized));
  }

  return {
    skyLevelForTime: skyLevelForTime,
    phaseForTime: phaseForTime,
    computeLight: computeLight,
    lightAt: lightAt,
    darknessForLevel: darknessForLevel
  };
});
