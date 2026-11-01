(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Integer avalanche hash. Deterministic for a given 32-bit input on every platform.
  function hash32(value) {
    let h = value >>> 0;
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b) >>> 0;
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b) >>> 0;
    return (h ^ (h >>> 16)) >>> 0;
  }

  function hash2(x, y, seed) {
    const value = Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(seed | 0, 69069);
    return hash32(value);
  }

  function unitHash(x, y, seed) {
    return hash2(x, y, seed) / 4294967296;
  }

  // Small, fast PRNG with an explicit seed: mulberry32.
  function mulberry32(seed) {
    let state = seed >>> 0;
    return function next() {
      state = (state + 0x6d2b79f5) | 0;
      let t = Math.imul(state ^ (state >>> 15), 1 | state);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function smoothstep(t) {
    return t * t * (3 - 2 * t);
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  // Value noise in [-1, 1] with smooth interpolation.
  function valueNoise1D(seed, x) {
    const base = Math.floor(x);
    const t = smoothstep(x - base);
    const a = unitHash(base, 0, seed) * 2 - 1;
    const b = unitHash(base + 1, 0, seed) * 2 - 1;
    return lerp(a, b, t);
  }

  function fbm1D(seed, x, octaves) {
    const count = octaves || 3;
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let normalizer = 0;
    for (let index = 0; index < count; index += 1) {
      total += valueNoise1D(seed + index * 7919, x * frequency) * amplitude;
      normalizer += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return normalizer === 0 ? 0 : total / normalizer;
  }

  function valueNoise2D(seed, x, y) {
    const baseX = Math.floor(x);
    const baseY = Math.floor(y);
    const tx = smoothstep(x - baseX);
    const ty = smoothstep(y - baseY);
    const top = lerp(unitHash(baseX, baseY, seed), unitHash(baseX + 1, baseY, seed), tx);
    const bottom = lerp(unitHash(baseX, baseY + 1, seed), unitHash(baseX + 1, baseY + 1, seed), tx);
    return lerp(top, bottom, ty) * 2 - 1;
  }

  function fbm2D(seed, x, y, octaves) {
    const count = octaves || 3;
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let normalizer = 0;
    for (let index = 0; index < count; index += 1) {
      total += valueNoise2D(seed + index * 6151, x * frequency, y * frequency) * amplitude;
      normalizer += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return normalizer === 0 ? 0 : total / normalizer;
  }

  return Object.freeze({
    hash32: hash32,
    hash2: hash2,
    unitHash: unitHash,
    mulberry32: mulberry32,
    smoothstep: smoothstep,
    lerp: lerp,
    clamp: clamp,
    valueNoise1D: valueNoise1D,
    fbm1D: fbm1D,
    valueNoise2D: valueNoise2D,
    fbm2D: fbm2D
  });
});
