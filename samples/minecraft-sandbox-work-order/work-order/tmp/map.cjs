"use strict";
const path = require("path");
const root = "C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project";
const cfg = require(path.join(root, "js/config.js"));
const worldApi = require(path.join(root, "js/world.js"));
const world = worldApi.createWorld(cfg.seed);
const surface = worldApi.surfaceMap(world);
const spawn = worldApi.findSpawn(world);
const camX = Math.max(0, Math.min(world.width * 24 - 960, spawn.x * 24 - 480));
const camY = Math.max(0, Math.min(world.height * 24 - 540, (spawn.y - 0.9) * 24 - 270));
const firstX = Math.floor(camX / 24), lastX = Math.ceil((camX + 960) / 24);
const firstY = Math.floor(camY / 24), lastY = Math.ceil((camY + 540) / 24);
console.log("spawn", spawn, "camera", camX, camY, "range", firstX, lastX, firstY, lastY);
const chars = { 0: ".", 1: "g", 2: "d", 3: "s", 4: "w", 5: "L", 6: "n", 7: "p", 8: "c", 9: "x" };
for (let y = firstY; y <= lastY; y += 1) {
  let line = String(y).padStart(2, " ") + " ";
  for (let x = firstX; x <= lastX; x += 1) {
    const b = world.data[y * world.width + x];
    line += y === surface[x] ? chars[b].toUpperCase() : chars[b];
  }
  console.log(line);
}
console.log("surfaces", Array.from(surface.slice(firstX, lastX + 1)).map((v, i) => (firstX + i) + ":" + v).join(" "));
