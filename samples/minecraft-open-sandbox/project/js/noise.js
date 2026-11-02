(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./rng.js"));
  } else {
    root.SandboxNoise = factory(root.SandboxRng);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (RNG) {
  "use strict";

  if (!RNG) {
    throw new Error("SandboxRng is required before SandboxNoise");
  }

  function smoothstep(value) {
    return value * value * (3 - 2 * value);
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  // Value noise on an integer lattice. Deterministic for a seed and position.
  function createNoise1D(seed) {
    const origin = Number(seed) >>> 0;
    function lattice(x) {
      return RNG.unitFromHash(RNG.hashInts(origin, x, 0x1b873593));
    }
    function noise(x) {
      const floor = Math.floor(x);
      const fraction = x - floor;
      const left = lattice(floor);
      const right = lattice(floor + 1);
      return lerp(left, right, smoothstep(fraction));
    }
    function fbm(x, octaves, lacunarity, gain) {
      const count = octaves || 4;
      const step = lacunarity || 2;
      const amplitudeGain = gain || 0.5;
      let amplitude = 1;
      let frequency = 1;
      let sum = 0;
      let total = 0;
      for (let index = 0; index < count; index += 1) {
        sum += noise(x * frequency) * amplitude;
        total += amplitude;
        amplitude *= amplitudeGain;
        frequency *= step;
      }
      return sum / total;
    }
    return { noise: noise, fbm: fbm };
  }

  function createNoise2D(seed) {
    const origin = Number(seed) >>> 0;
    function lattice(x, y) {
      return RNG.unitFromHash(RNG.hashInts(origin, x, y));
    }
    function noise(x, y) {
      const floorX = Math.floor(x);
      const floorY = Math.floor(y);
      const fx = smoothstep(x - floorX);
      const fy = smoothstep(y - floorY);
      const topLeft = lattice(floorX, floorY);
      const topRight = lattice(floorX + 1, floorY);
      const bottomLeft = lattice(floorX, floorY + 1);
      const bottomRight = lattice(floorX + 1, floorY + 1);
      return lerp(lerp(topLeft, topRight, fx), lerp(bottomLeft, bottomRight, fx), fy);
    }
    function fbm(x, y, octaves, lacunarity, gain) {
      const count = octaves || 3;
      const step = lacunarity || 2;
      const amplitudeGain = gain || 0.5;
      let amplitude = 1;
      let frequency = 1;
      let sum = 0;
      let total = 0;
      for (let index = 0; index < count; index += 1) {
        sum += noise(x * frequency, y * frequency) * amplitude;
        total += amplitude;
        amplitude *= amplitudeGain;
        frequency *= step;
      }
      return sum / total;
    }
    return { noise: noise, fbm: fbm };
  }

  return {
    createNoise1D: createNoise1D,
    createNoise2D: createNoise2D,
    smoothstep: smoothstep,
    lerp: lerp
  };
});
