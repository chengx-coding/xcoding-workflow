(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Small deterministic generator. Every world feature draws from a stream
  // seeded from the world seed so the same seed always builds the same world.
  function mulberry32(seed) {
    let state = seed >>> 0;
    return function next() {
      state = (state + 0x6d2b79f5) >>> 0;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hash2(x, y, seed) {
    let h = (seed >>> 0) ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }

  function hash1(x, seed) {
    return hash2(x, 0x9e37, seed);
  }

  function smoothstep(t) {
    return t * t * (3 - 2 * t);
  }

  function valueNoise1D(x, seed) {
    const cell = Math.floor(x);
    const t = smoothstep(x - cell);
    const a = hash1(cell, seed);
    const b = hash1(cell + 1, seed);
    return a + (b - a) * t;
  }

  function valueNoise2D(x, y, seed) {
    const cx = Math.floor(x);
    const cy = Math.floor(y);
    const tx = smoothstep(x - cx);
    const ty = smoothstep(y - cy);
    const a = hash2(cx, cy, seed);
    const b = hash2(cx + 1, cy, seed);
    const c = hash2(cx, cy + 1, seed);
    const d = hash2(cx + 1, cy + 1, seed);
    const top = a + (b - a) * tx;
    const bottom = c + (d - c) * tx;
    return top + (bottom - top) * ty;
  }

  function fbm2D(x, y, seed, octaves) {
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let norm = 0;
    const count = octaves || 3;
    for (let i = 0; i < count; i += 1) {
      total += valueNoise2D(x * frequency, y * frequency, seed + i * 1013) * amplitude;
      norm += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return norm > 0 ? total / norm : 0;
  }

  function integerRange(random, min, max) {
    return min + Math.floor(random() * (max - min + 1));
  }

  return {
    mulberry32: mulberry32,
    hash1: hash1,
    hash2: hash2,
    valueNoise1D: valueNoise1D,
    valueNoise2D: valueNoise2D,
    fbm2D: fbm2D,
    integerRange: integerRange
  };
});
