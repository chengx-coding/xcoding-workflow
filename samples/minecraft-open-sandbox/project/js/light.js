(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"));
  } else {
    root.SandboxLight = factory(root.SandboxConfig, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS) {
  "use strict";

  if (!CONFIG || !BLOCKS) {
    throw new Error("SandboxConfig and SandboxBlocks are required before SandboxLight");
  }

  const MAX_LIGHT = 15;
  const KEYS = [
    [0.0, 0.32],
    [0.045, 0.98],
    [0.5, 0.98],
    [0.62, 0.1],
    [0.9, 0.07],
    [0.965, 0.32],
    [1.0, 0.32]
  ];

  function dayFactor(time) {
    let value = Number(time) || 0;
    value = value - Math.floor(value);
    for (let i = 0; i < KEYS.length - 1; i += 1) {
      const a = KEYS[i];
      const b = KEYS[i + 1];
      if (value >= a[0] && value <= b[0]) {
        const span = b[0] - a[0];
        const t = span <= 0 ? 0 : (value - a[0]) / span;
        const smooth = t * t * (3 - 2 * t);
        return a[1] + (b[1] - a[1]) * smooth;
      }
    }
    return 0.32;
  }

  function isNight(time) {
    const value = ((Number(time) || 0) % 1 + 1) % 1;
    return value >= 0.62 && value < 0.94;
  }

  function isDuskOrDawn(time) {
    const value = ((Number(time) || 0) % 1 + 1) % 1;
    return (value >= 0.5 && value < 0.62) || (value >= 0.94 && value < 1);
  }

  function computeLight(world, bounds, time) {
    const x0 = Math.max(0, Math.floor(bounds.x0));
    const y0 = Math.max(0, Math.floor(bounds.y0));
    const x1 = Math.min(world.width - 1, Math.ceil(bounds.x1));
    const y1 = Math.min(world.height - 1, Math.ceil(bounds.y1));
    const width = Math.max(1, x1 - x0 + 1);
    const height = Math.max(1, y1 - y0 + 1);
    const data = new Uint8Array(width * height);
    const tops = new Int16Array(width);
    const sky = Math.max(4, Math.round(MAX_LIGHT * dayFactor(time)));
    const queue = [];

    for (let gx = 0; gx < width; gx += 1) {
      const x = x0 + gx;
      let firstSolid = -1;
      for (let y = 0; y <= y1; y += 1) {
        const block = world.data[y * world.width + x];
        // Tree wood and leaves are treated as translucent for the surface
        // level, so the open air under a canopy is not a hard shadow column.
        if (BLOCKS.isSolid(block) && block !== CONFIG.blocks.wood && block !== CONFIG.blocks.leaves) {
          firstSolid = y;
          break;
        }
      }
      if (firstSolid < 0) {
        firstSolid = y1 + 1;
      }
      tops[gx] = firstSolid;
      for (let gy = 0; gy < height; gy += 1) {
        const y = y0 + gy;
        if (y < firstSolid) {
          data[gy * width + gx] = sky;
          queue.push(gy * width + gx);
        }
      }
    }

    for (let gx = 0; gx < width; gx += 1) {
      for (let gy = 0; gy < height; gy += 1) {
        const block = world.data[(y0 + gy) * world.width + (x0 + gx)];
        const emission = BLOCKS.lightOf(block);
        if (emission > 0) {
          const index = gy * width + gx;
          if (data[index] < emission) {
            data[index] = emission;
            queue.push(index);
          }
        }
      }
    }

    const solidAt = function solidAt(gx, gy) {
      return BLOCKS.isSolid(world.data[(y0 + gy) * world.width + (x0 + gx)]);
    };

    for (let head = 0; head < queue.length; head += 1) {
      const index = queue[head];
      const value = data[index];
      if (value <= 1) {
        continue;
      }
      const gx = index % width;
      const gy = (index - gx) / width;
      const next = value - 1;
      if (gx > 0 && !solidAt(gx - 1, gy) && data[index - 1] < next) {
        data[index - 1] = next;
        queue.push(index - 1);
      }
      if (gx < width - 1 && !solidAt(gx + 1, gy) && data[index + 1] < next) {
        data[index + 1] = next;
        queue.push(index + 1);
      }
      if (gy > 0 && !solidAt(gx, gy - 1) && data[index - width] < next) {
        data[index - width] = next;
        queue.push(index - width);
      }
      if (gy < height - 1 && !solidAt(gx, gy + 1) && data[index + width] < next) {
        data[index + width] = next;
        queue.push(index + width);
      }
    }

    // Solid faces borrow light from their air neighbours so that exposed
    // terrain is readable instead of uniformly black.
    const airLight = data.slice();
    for (let gy = 0; gy < height; gy += 1) {
      for (let gx = 0; gx < width; gx += 1) {
        const index = gy * width + gx;
        const block = world.data[(y0 + gy) * world.width + (x0 + gx)];
        if (!BLOCKS.isSolid(block) || BLOCKS.lightOf(block) > 0) {
          continue;
        }
        let best = 0;
        if (gx > 0) {
          best = Math.max(best, airLight[index - 1]);
        }
        if (gx < width - 1) {
          best = Math.max(best, airLight[index + 1]);
        }
        if (gy > 0) {
          best = Math.max(best, airLight[index - width]);
        }
        if (gy < height - 1) {
          best = Math.max(best, airLight[index + width]);
        }
        data[index] = best > 0 ? best - 1 : 0;
      }
    }

    // A shallow ambient gradient keeps the first few rows of soil readable and
    // fades to a faint cave floor instead of a flat black rectangle.
    for (let gy = 0; gy < height; gy += 1) {
      const y = y0 + gy;
      for (let gx = 0; gx < width; gx += 1) {
        const depth = y - tops[gx];
        if (depth >= 0) {
          const index = gy * width + gx;
          const ambient = Math.max(2, 8 - depth * 2);
          if (data[index] < ambient) {
            data[index] = ambient;
          }
        }
      }
    }

    return {
      x0: x0,
      y0: y0,
      width: width,
      height: height,
      data: data,
      time: time,
      sky: sky
    };
  }

  function lightAt(light, x, y) {
    if (!light) {
      return 0;
    }
    const gx = x - light.x0;
    const gy = y - light.y0;
    if (gx < 0 || gy < 0 || gx >= light.width || gy >= light.height) {
      return 0;
    }
    return light.data[gy * light.width + gx];
  }

  function darknessAt(light, x, y) {
    const value = lightAt(light, x, y);
    return Math.max(0, Math.min(1, 1 - value / MAX_LIGHT));
  }

  return {
    MAX_LIGHT: MAX_LIGHT,
    dayFactor: dayFactor,
    isNight: isNight,
    isDuskOrDawn: isDuskOrDawn,
    computeLight: computeLight,
    lightAt: lightAt,
    darknessAt: darknessAt
  };
});
