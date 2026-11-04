/* Deterministic, dependency-free randomness for world generation. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function hash32(value) {
    let h = value >>> 0;
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b) >>> 0;
    h = Math.imul(h ^ (h >>> 16), 0x45d9f3b) >>> 0;
    return (h ^ (h >>> 16)) >>> 0;
  }

  function hash2(x, y, seed) {
    return hash32((x | 0) * 374761393 + (y | 0) * 668265263 + (seed | 0) * 2246822519);
  }

  function mulberry32(seed) {
    let state = seed >>> 0;
    return function next() {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function noise1(x, seed) {
    const xi = Math.floor(x);
    const xf = x - xi;
    const a = (hash2(xi, 0, seed) / 4294967296) * 2 - 1;
    const b = (hash2(xi + 1, 0, seed) / 4294967296) * 2 - 1;
    const t = xf * xf * (3 - 2 * xf);
    return a + (b - a) * t;
  }

  function noise2(x, y, seed) {
    const xi = Math.floor(x);
    const yi = Math.floor(y);
    const xf = x - xi;
    const yf = y - yi;
    const smoothX = xf * xf * (3 - 2 * xf);
    const smoothY = yf * yf * (3 - 2 * yf);
    const a = (hash2(xi, yi, seed) / 4294967296) * 2 - 1;
    const b = (hash2(xi + 1, yi, seed) / 4294967296) * 2 - 1;
    const c = (hash2(xi, yi + 1, seed) / 4294967296) * 2 - 1;
    const d = (hash2(xi + 1, yi + 1, seed) / 4294967296) * 2 - 1;
    const top = a + (b - a) * smoothX;
    const bottom = c + (d - c) * smoothX;
    return top + (bottom - top) * smoothY;
  }

  function fbm1(x, seed, octaves) {
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let normal = 0;
    const count = octaves || 4;
    for (let i = 0; i < count; i += 1) {
      total += noise1(x * frequency, seed + i * 1013) * amplitude;
      normal += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return total / normal;
  }

  function fbm2(x, y, seed, octaves) {
    let total = 0;
    let amplitude = 1;
    let frequency = 1;
    let normal = 0;
    const count = octaves || 3;
    for (let i = 0; i < count; i += 1) {
      total += noise2(x * frequency, y * frequency, seed + i * 7919) * amplitude;
      normal += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return total / normal;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function range(seed, min, max) {
    return min + Math.floor(mulberry32(seed)() * (max - min + 1));
  }

  return {
    hash32: hash32,
    hash2: hash2,
    mulberry32: mulberry32,
    noise1: noise1,
    noise2: noise2,
    fbm1: fbm1,
    fbm2: fbm2,
    clamp: clamp,
    range: range
  };
});
