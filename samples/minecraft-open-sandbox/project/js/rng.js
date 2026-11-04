(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function hashString(text) {
    let hash = 2166136261 >>> 0;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return hash >>> 0;
  }

  function mulberry32(seed) {
    let state = (Number(seed) >>> 0) || 0x9e3779b9;
    return function random() {
      state = (state + 0x6d2b79f5) >>> 0;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function sampleRng(seed, salt) {
    return mulberry32((Number(seed) >>> 0) ^ (Number(salt) >>> 0));
  }

  function hash2(x, y, seed) {
    let hash = (Number(seed) >>> 0) ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263);
    hash = Math.imul(hash ^ (hash >>> 13), 1274126177);
    hash = (hash ^ (hash >>> 16)) >>> 0;
    return hash / 4294967296;
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function smoothstep(t) {
    return t * t * (3 - 2 * t);
  }

  function valueNoise1D(x, seed) {
    const floorX = Math.floor(x);
    const frac = x - floorX;
    const left = hash2(floorX, 0, seed);
    const right = hash2(floorX + 1, 0, seed);
    return lerp(left, right, smoothstep(frac));
  }

  function valueNoise2D(x, y, seed) {
    const floorX = Math.floor(x);
    const floorY = Math.floor(y);
    const fracX = x - floorX;
    const fracY = y - floorY;
    const topLeft = hash2(floorX, floorY, seed);
    const topRight = hash2(floorX + 1, floorY, seed);
    const bottomLeft = hash2(floorX, floorY + 1, seed);
    const bottomRight = hash2(floorX + 1, floorY + 1, seed);
    const sx = smoothstep(fracX);
    const sy = smoothstep(fracY);
    return lerp(lerp(topLeft, topRight, sx), lerp(bottomLeft, bottomRight, sx), sy);
  }

  function fbm1(x, seed, octaves, persistence) {
    const count = octaves || 4;
    const gain = persistence || 0.5;
    let amplitude = 1;
    let frequency = 1;
    let total = 0;
    let norm = 0;
    for (let octave = 0; octave < count; octave += 1) {
      total += valueNoise1D(x * frequency, (Number(seed) >>> 0) + octave * 1013) * amplitude;
      norm += amplitude;
      amplitude *= gain;
      frequency *= 2;
    }
    return total / norm;
  }

  function fbm2(x, y, seed, octaves, persistence) {
    const count = octaves || 3;
    const gain = persistence || 0.5;
    let amplitude = 1;
    let frequency = 1;
    let total = 0;
    let norm = 0;
    for (let octave = 0; octave < count; octave += 1) {
      total += valueNoise2D(x * frequency, y * frequency, (Number(seed) >>> 0) + octave * 2749) * amplitude;
      norm += amplitude;
      amplitude *= gain;
      frequency *= 2;
    }
    return total / norm;
  }

  return {
    hashString: hashString,
    mulberry32: mulberry32,
    sampleRng: sampleRng,
    hash2: hash2,
    lerp: lerp,
    smoothstep: smoothstep,
    valueNoise1D: valueNoise1D,
    valueNoise2D: valueNoise2D,
    fbm1: fbm1,
    fbm2: fbm2
  };
});
