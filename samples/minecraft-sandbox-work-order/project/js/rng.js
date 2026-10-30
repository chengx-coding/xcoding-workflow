(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxRng = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // FNV-1a over a string, used to turn an arbitrary label into a 32-bit seed.
  function hashString(text) {
    const source = String(text == null ? "" : text);
    let hash = 0x811c9dc5;
    for (let index = 0; index < source.length; index += 1) {
      hash ^= source.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193);
    }
    return hash >>> 0;
  }

  // Normalise anything seed-like to an unsigned 32-bit integer. A missing or
  // non-finite value becomes zero, matching the seed world contract.
  function normalizeSeed(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return 0;
    }
    return Math.trunc(number) >>> 0;
  }

  // Parse a user-typed seed. Whole numbers only, with surrounding space allowed.
  function parseSeedText(text) {
    const source = String(text == null ? "" : text).trim();
    if (source === "") {
      return { ok: false, reason: "empty", message: "Enter a whole number to load a seed." };
    }
    if (!/^[+-]?\d+$/.test(source)) {
      return { ok: false, reason: "format", message: "Seeds are whole numbers, for example 20261030." };
    }
    const value = Number(source);
    if (!Number.isSafeInteger(value)) {
      return { ok: false, reason: "range", message: "That number is too large; use a smaller whole number." };
    }
    return { ok: true, seed: normalizeSeed(value) };
  }

  function mulberry32(seed) {
    let state = seed >>> 0;
    return function random() {
      state = (state + 0x6d2b79f5) >>> 0;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function createRandom(seed) {
    const next = mulberry32(seed);
    return {
      next: next,
      range: function (min, max) {
        return min + next() * (max - min);
      },
      int: function (min, max) {
        return Math.floor(min + next() * (max - min + 1));
      },
      pick: function (items) {
        if (!items || items.length === 0) {
          return null;
        }
        return items[Math.floor(next() * items.length)];
      }
    };
  }

  // Stable per-cell hash so rendering and decoration never need global state.
  function hash2(x, y, seed) {
    let value = Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1) ^ (seed | 0);
    value = Math.imul(value ^ (value >>> 15), 0x2545f491);
    value ^= value >>> 13;
    return (value >>> 0) / 4294967296;
  }

  return {
    hashString: hashString,
    normalizeSeed: normalizeSeed,
    parseSeedText: parseSeedText,
    mulberry32: mulberry32,
    createRandom: createRandom,
    hash2: hash2
  };
});
