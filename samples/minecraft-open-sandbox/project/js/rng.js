(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Mulberry32: small, fast, deterministic 32-bit PRNG.
  function createRng(seed) {
    let state = (Number(seed) >>> 0) || 0x9e3779b9;
    function next() {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = state;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    next.state = function () {
      return state >>> 0;
    };
    return next;
  }

  const FNV_OFFSET = 2166136261;
  const FNV_PRIME = 16777619;

  function hashString(value) {
    let hash = FNV_OFFSET;
    const text = String(value);
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, FNV_PRIME) >>> 0;
    }
    return hash >>> 0;
  }

  function hashInts(a, b, c) {
    let hash = FNV_OFFSET;
    const values = [a, b, c];
    for (let index = 0; index < values.length; index += 1) {
      const value = Number(values[index]) | 0;
      hash ^= value & 0xff;
      hash = Math.imul(hash, FNV_PRIME) >>> 0;
      hash ^= (value >>> 8) & 0xff;
      hash = Math.imul(hash, FNV_PRIME) >>> 0;
      hash ^= (value >>> 16) & 0xff;
      hash = Math.imul(hash, FNV_PRIME) >>> 0;
      hash ^= (value >>> 24) & 0xff;
      hash = Math.imul(hash, FNV_PRIME) >>> 0;
    }
    return hash >>> 0;
  }

  function unitFromHash(hash) {
    let t = hash >>> 0;
    t = Math.imul(t ^ (t >>> 16), 0x21f0aaad) >>> 0;
    t = Math.imul(t ^ (t >>> 15), 0x735a2d97) >>> 0;
    t = (t ^ (t >>> 15)) >>> 0;
    return t / 4294967296;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  return {
    createRng: createRng,
    hashString: hashString,
    hashInts: hashInts,
    unitFromHash: unitFromHash,
    clamp: clamp
  };
});
