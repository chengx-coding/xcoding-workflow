(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxConfig = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const BLOCKS = Object.freeze({
    air: 0,
    grass: 1,
    dirt: 2,
    stone: 3,
    wood: 4,
    leaves: 5
  });

  return Object.freeze({
    version: "0.1.0",
    tileSize: 24,
    viewWidth: 960,
    viewHeight: 540,
    worldWidth: 128,
    worldHeight: 64,
    gravity: 0.55,
    moveSpeed: 3.2,
    jumpSpeed: 8,
    reach: 5,
    saveKey: "xc-sandbox-sample-v1",
    blocks: BLOCKS,
    blockNames: Object.freeze({
      1: "grass",
      2: "dirt",
      3: "stone",
      4: "wood",
      5: "leaves"
    })
  });
});
