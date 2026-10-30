"use strict";
const path = require("path");
const root = "C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project";
const cfg = require(path.join(root, "js/config.js"));
const rng = require(path.join(root, "js/rng.js"));
const worldApi = require(path.join(root, "js/world.js"));
const playerApi = require(path.join(root, "js/player.js"));
const cameraApi = require(path.join(root, "js/camera.js"));
const ia = require(path.join(root, "js/interaction.js"));
const dn = require(path.join(root, "js/daynight.js"));
const storage = require(path.join(root, "js/storage.js"));
const audio = require(path.join(root, "js/audio.js"));
const ui = require(path.join(root, "js/ui.js"));
const render = require(path.join(root, "js/render.js"));

const world = worldApi.createWorld(cfg.seed);
const counts = {};
for (let i = 0; i < world.data.length; i += 1) counts[world.data[i]] = (counts[world.data[i]] || 0) + 1;
console.log("counts", JSON.stringify(counts));
let below = 0;
const surface = worldApi.surfaceMap(world);
let maxDepthAir = 0;
for (let x = 0; x < world.width; x += 1) {
  for (let y = surface[x] + 6; y < world.height; y += 1) {
    if (world.data[y * world.width + x] === 0) { below += 1; maxDepthAir = Math.max(maxDepthAir, y - surface[x]); }
  }
}
console.log("caveAir", below, "maxDepth", maxDepthAir);
console.log("surface sample", Array.from(surface.slice(0, 30)).join(","));
const spawn = worldApi.findSpawn(world);
console.log("spawn", spawn, "blockAbove", worldApi.getBlock(world, Math.floor(spawn.x), Math.floor(spawn.y) - 1), "ground", worldApi.getBlock(world, Math.floor(spawn.x), Math.floor(spawn.y)));
const p = playerApi.createPlayer(spawn.x, spawn.y);
for (let i = 0; i < 180; i += 1) playerApi.stepPlayer(p, world, { left: false, right: false, jump: false }, 1 / 60);
console.log("settled", p.x.toFixed(3), p.y.toFixed(3), "onGround", p.onGround);
const cam = cameraApi.createCamera();
cameraApi.followCamera(cam, p, world, { width: 960, height: 540 }, 24, 1 / 60, 9);
console.log("camera", cam.x.toFixed(1), cam.y.toFixed(1));
console.log("sky", dn.skyColors(0.25), dn.skyColors(0.75));
const inv = ia.createInventory();
console.log("inventory", JSON.stringify(inv));
console.log("hotbar8", ia.hotbarModel(inv)[7]);
console.log("render helpers", render.tileVariant(3, 4, cfg.seed), render.depthShade(5), render.crackStages(0.6), render.surfaceFor(world).length);
console.log("ui", ui.formatCoords(p), ui.formatDepth(p, surface[Math.floor(p.x)]), ui.parseSeedInput(" 42 "));
console.log("audio", audio.createAudioBoard({ factory: null }).play("mine"));
const fake = [];
const fakeStorage = { getItem: (k) => null, setItem: (k, v) => fake.push([k, v]), removeItem: () => {} };
const st = storage.createStore({ storage: fakeStorage });
console.log("save", st.saveGame({ seed: world.seed, worldText: worldApi.serializeWorld(world), player: { x: p.x, y: p.y }, inventory: { counts: inv.counts, selected: 0 }, timeOfDay: 0.3 }), fake[0][0]);
console.log("load", st.loadGame().ok);
