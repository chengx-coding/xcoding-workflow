const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Render = require("../js/render.js");
const Time = require("../js/timecycle.js");
const World = require("../js/world.js");

function fakeContext() {
  const calls = [];
  const gradient = function (kind) {
    return {
      kind: kind,
      stops: [],
      addColorStop: function (offset, color) {
        this.stops.push([offset, color]);
      }
    };
  };
  const ctx = {
    calls: calls,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    globalAlpha: 1,
    globalCompositeOperation: "source-over",
    fillRect: function () {
      calls.push({ name: "fillRect", args: Array.prototype.slice.call(arguments), style: this.fillStyle });
    },
    strokeRect: function () {
      calls.push({ name: "strokeRect", args: Array.prototype.slice.call(arguments), style: this.strokeStyle });
    },
    beginPath: function () { calls.push({ name: "beginPath" }); },
    closePath: function () { calls.push({ name: "closePath" }); },
    arc: function () { calls.push({ name: "arc", args: Array.prototype.slice.call(arguments) }); },
    moveTo: function () { calls.push({ name: "moveTo" }); },
    lineTo: function () { calls.push({ name: "lineTo" }); },
    fill: function () { calls.push({ name: "fill", style: this.fillStyle }); },
    stroke: function () { calls.push({ name: "stroke", style: this.strokeStyle }); },
    save: function () { calls.push({ name: "save" }); },
    restore: function () { calls.push({ name: "restore" }); },
    clearRect: function () { calls.push({ name: "clearRect" }); },
    setTransform: function () {},
    createLinearGradient: function () { return gradient("linear"); },
    createRadialGradient: function () { return gradient("radial"); }
  };
  return ctx;
}

function makeWorld() {
  const width = 40;
  const height = 24;
  const data = new Uint8Array(width * height);
  for (let y = 10; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      data[y * width + x] = y === 10 ? config.blocks.grass : y < 14 ? config.blocks.dirt : config.blocks.stone;
    }
  }
  return { width: width, height: height, seed: 7, data: data };
}

function baseState(overrides) {
  const state = {
    world: makeWorld(),
    player: { x: 6.5, y: 10, vx: 0, vy: 0, onGround: true, facing: 1, width: 0.7, height: 1.8, walkTime: 0 },
    camera: { x: 32, y: 100 },
    time: 0.5,
    hover: null,
    particles: [],
    reducedMotion: false
  };
  Object.keys(overrides || {}).forEach(function (key) {
    state[key] = overrides[key];
  });
  return state;
}

test("a rendered frame paints the sky, terrain and player", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState());
  const sky = ctx.calls.find(function (call) {
    return call.name === "fillRect" && call.style && call.style.stops;
  });
  assert.ok(sky, "no sky gradient fill");
  assert.equal(sky.style.stops[0][1], Time.sky(0.5).topCss);
  assert.ok(ctx.calls.filter(function (call) { return call.name === "fillRect"; }).length > 60);
  assert.ok(ctx.calls.some(function (call) { return call.style === "#f2c49b"; }), "player was not drawn");
});

test("the sky palette changes materially between day and night", () => {
  const dayCtx = fakeContext();
  Render.renderFrame(dayCtx, baseState({ time: 0.5 }));
  const nightCtx = fakeContext();
  Render.renderFrame(nightCtx, baseState({ time: 0.0 }));
  const daySky = dayCtx.calls.find(function (call) { return call.name === "fillRect" && call.style && call.style.stops; });
  const nightSky = nightCtx.calls.find(function (call) { return call.name === "fillRect" && call.style && call.style.stops; });
  assert.notEqual(daySky.style.stops[0][1], nightSky.style.stops[0][1]);
  assert.equal(daySky.style.stops[0][1], Time.sky(0.5).topCss);
  assert.equal(nightSky.style.stops[0][1], Time.sky(0.0).topCss);
});

test("night draws a darkening overlay and a player light", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState({ time: 0.0 }));
  const overlay = ctx.calls.find(function (call) {
    return call.name === "fillRect" && typeof call.style === "string" && call.style.indexOf("rgba(8,14,34,") === 0;
  });
  assert.ok(overlay, "no night overlay");
  assert.ok(ctx.calls.some(function (call) { return call.name === "save"; }));
  assert.ok(ctx.calls.some(function (call) { return call.name === "fill" && call.style && call.style.stops; }));
});

test("daylight frames draw no night overlay", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState({ time: 0.5 }));
  assert.equal(
    ctx.calls.some(function (call) {
      return typeof call.style === "string" && call.style.indexOf("rgba(8,14,34,") === 0;
    }),
    false
  );
});

test("the hover highlight marks the targeted tile", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState({ hover: { x: 7, y: 9, reachable: true } }));
  assert.ok(ctx.calls.some(function (call) {
    return call.name === "strokeRect" && call.style === "rgba(255,196,107,0.95)";
  }));
  const refusedCtx = fakeContext();
  Render.renderFrame(refusedCtx, baseState({ hover: { x: 30, y: 9, reachable: false } }));
  assert.ok(refusedCtx.calls.some(function (call) {
    return call.name === "strokeRect" && call.style === "rgba(255,122,107,0.95)";
  }));
});

test("removing a block removes its tile drawing", () => {
  const world = makeWorld();
  const visibleBefore = fakeContext();
  Render.renderFrame(visibleBefore, baseState({ world: world }));
  const filledBefore = visibleBefore.calls.filter(function (call) { return call.name === "fillRect"; }).length;
  world.data[10 * world.width + 6] = config.blocks.air;
  const visibleAfter = fakeContext();
  Render.renderFrame(visibleAfter, baseState({ world: world }));
  const filledAfter = visibleAfter.calls.filter(function (call) { return call.name === "fillRect"; }).length;
  assert.ok(filledBefore > filledAfter, "removed block still affected the frame");
});

test("glass is translucent instead of opaque", () => {
  const world = makeWorld();
  world.data[9 * world.width + 6] = config.blocks.glass;
  const ctx = fakeContext();
  Render.drawWorld(ctx, baseState({ world: world }));
  assert.ok(ctx.calls.some(function (call) {
    return call.name === "fillRect" && call.style === "rgba(180,232,238,0.24)";
  }));
  assert.equal(ctx.calls.some(function (call) { return call.name === "clearRect"; }), false);
});

test("particles are drawn with their block colour and fade out", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState({
    particles: [
      { x: 7.2, y: 9.5, life: 0.4, maxLife: 0.8, size: 3, color: [90, 158, 74] },
      { x: 8.1, y: 9.1, life: 0.1, maxLife: 0.8, size: 2, color: [90, 158, 74] }
    ]
  }));
  const particleFills = ctx.calls.filter(function (call) {
    return call.name === "fillRect" && typeof call.style === "string" && call.style.indexOf("rgba(90,158,74,") === 0;
  });
  assert.equal(particleFills.length, 2);
});

test("visibleRange follows the camera and clamps to the world", () => {
  const world = makeWorld();
  const range = Render.visibleRange({ x: 0, y: 0 }, world);
  assert.equal(range.x0, 0);
  assert.equal(range.y0, 0);
  assert.ok(range.x1 >= 29 && range.x1 <= world.width - 1);
  const edge = Render.visibleRange({ x: world.width * config.tileSize - 100, y: world.height * config.tileSize - 100 }, world);
  assert.equal(edge.x1, world.width - 1);
  assert.equal(edge.y1, world.height - 1);
});

test("reduced motion removes time-driven star twinkle", () => {
  const moving = fakeContext();
  Render.drawSky(moving, { time: 0.1, camera: { x: 0, y: 0 }, reducedMotion: false });
  const still = fakeContext();
  Render.drawSky(still, { time: 0.1, camera: { x: 0, y: 0 }, reducedMotion: true });
  const movingStars = moving.calls.filter(function (call) { return typeof call.style === "string" && call.style.indexOf("rgba(232,242,255,") === 0; });
  const stillStars = still.calls.filter(function (call) { return typeof call.style === "string" && call.style.indexOf("rgba(232,242,255,") === 0; });
  assert.ok(movingStars.length > 0);
  assert.equal(movingStars.length, stillStars.length);
});

test("the bottom rows render as a distinct sealed bedrock face", () => {
  const world = makeWorld();
  world.data[(world.height - 1) * world.width + 6] = config.blocks.stone;
  const ctx = fakeContext();
  Render.drawWorld(ctx, baseState({ world: world, camera: { x: 0, y: 20 * config.tileSize } }));
  const bedrock = ctx.calls.filter(function (call) {
    return call.name === "fillRect" && call.style === "rgb(56,60,68)";
  });
  assert.ok(bedrock.length >= world.width, "bedrock faces were not drawn for the floor rows");
});

test("the minimap draws terrain columns, a viewport and the player dot", () => {
  const world = makeWorld();
  const ctx = fakeContext();
  Render.renderMinimap(ctx, world, { x: 6.5, y: 10 }, { x: 32, y: 100 }, { width: 180, height: 64 });
  const columns = ctx.calls.filter(function (call) {
    return call.name === "fillRect" && call.args[2] === 1 && call.args[3] >= 1;
  });
  assert.ok(columns.length >= 180, "terrain columns were not drawn");
  assert.ok(ctx.calls.some(function (call) { return call.name === "fillRect" && call.style === "#ffc46b"; }), "player dot missing");
  assert.ok(ctx.calls.some(function (call) { return call.name === "strokeRect" && call.style === "rgba(255,255,255,0.65)"; }), "viewport rectangle missing");
});

test("a break in progress draws growing cracks and a pickaxe swing", () => {
  const early = fakeContext();
  Render.renderFrame(early, baseState({ mining: { active: true, tile: { x: 7, y: 9 }, progress: 0.2 } }));
  const late = fakeContext();
  Render.renderFrame(late, baseState({ mining: { active: true, tile: { x: 7, y: 9 }, progress: 0.95 } }));
  const crackStyle = "rgba(14,10,8,0.88)";
  const earlyCracks = early.calls.filter(function (call) { return call.name === "stroke" && call.style === crackStyle; }).length;
  const lateCracks = late.calls.filter(function (call) { return call.name === "stroke" && call.style === crackStyle; }).length;
  assert.ok(lateCracks > earlyCracks, "cracks did not grow with progress");
  assert.ok(late.calls.some(function (call) { return call.name === "fillRect" && call.style === "#d7e0e8"; }), "pickaxe head not drawn");
});

test("no pickaxe or cracks are drawn when mining is inactive", () => {
  const ctx = fakeContext();
  Render.renderFrame(ctx, baseState());
  assert.equal(ctx.calls.some(function (call) { return call.style === "#d7e0e8"; }), false);
  assert.equal(ctx.calls.some(function (call) { return call.style === "rgba(14,10,8,0.88)"; }), false);
});
