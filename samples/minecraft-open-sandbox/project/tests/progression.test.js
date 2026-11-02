const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const progression = require("../js/progression.js");

const B = config.blocks;

test("a new progress starts at the first stage", () => {
  const progress = progression.createProgress();
  assert.equal(progress.stage, 0);
  const summary = progression.summary(progress);
  assert.equal(summary.index, 0);
  assert.equal(summary.total, 8);
  assert.equal(summary.current.id, "wood");
  assert.equal(summary.done, false);
});

test("stages complete only in order and keep their rewards", () => {
  const progress = progression.createProgress();
  progression.record(progress, "workbenchPlaced");
  let events = progression.update(progress);
  assert.equal(events.newlyCompleted.length, 0, "workbench cannot complete before wood");

  progression.recordMine(progress, B.wood);
  progression.recordMine(progress, B.wood);
  progression.recordMine(progress, B.wood);
  progression.recordMine(progress, B.wood);
  events = progression.update(progress);
  assert.equal(events.newlyCompleted.length, 2);
  assert.equal(events.newlyCompleted[0].id, "wood");
  assert.equal(events.newlyCompleted[1].id, "workbench");
  assert.equal(progress.stage, 2);
});

test("the whole chain completes when every condition is met", () => {
  const progress = progression.createProgress();
  const stats = progress.stats;
  stats.woodCollected = 4;
  stats.workbenchPlaced = 1;
  stats.pickWoodCrafted = 1;
  stats.pickStoneCrafted = 1;
  stats.torchesPlaced = 1;
  stats.pickIronCrafted = 1;
  stats.emberMined = 3;
  stats.beaconPlaced = 1;
  const events = progression.update(progress);
  assert.equal(events.newlyCompleted.length, 8);
  assert.equal(events.complete, true);
  assert.equal(progress.stage, 8);
  const summary = progression.summary(progress);
  assert.equal(summary.done, true);
  assert.equal(summary.current, null);
  assert.equal(summary.title, "The beacon burns");
});

test("mining and placing feed the right counters", () => {
  const progress = progression.createProgress();
  progression.recordMine(progress, B.wood);
  progression.recordMine(progress, B.stone);
  progression.recordMine(progress, B.ember_ore);
  progression.recordPlace(progress, B.workbench);
  progression.recordPlace(progress, B.torch);
  progression.recordPlace(progress, B.beacon);
  assert.equal(progress.stats.woodCollected, 1);
  assert.equal(progress.stats.blocksMined, 3);
  assert.equal(progress.stats.emberMined, 1);
  assert.equal(progress.stats.workbenchPlaced, 1);
  assert.equal(progress.stats.torchesPlaced, 1);
  assert.equal(progress.stats.beaconPlaced, 1);
});

test("craft counters map recipe ids to tiers", () => {
  const progress = progression.createProgress();
  progression.recordCraft(progress, "wooden_pickaxe");
  progression.recordCraft(progress, "stone_pickaxe");
  progression.recordCraft(progress, "iron_pickaxe");
  progression.recordCraft(progress, "iron_ingot");
  assert.equal(progress.stats.pickWoodCrafted, 1);
  assert.equal(progress.stats.pickStoneCrafted, 1);
  assert.equal(progress.stats.pickIronCrafted, 1);
  assert.equal(progress.stats.ironSmelted, 1);
});

test("progress round-trips through save data", () => {
  const progress = progression.createProgress();
  progress.stage = 3;
  progress.stats.woodCollected = 9;
  progress.stats.blocksMined = 12;
  progress.stats.playtime = 120;
  const saved = progression.serialize(progress);
  const restored = progression.deserialize(saved);
  assert.equal(restored.stage, 3);
  assert.deepEqual(restored.completed, ["wood", "workbench", "pick_wood"]);
  assert.equal(restored.stats.woodCollected, 9);
  assert.equal(restored.stats.playtime, 120);
});

test("corrupt progress data falls back safely", () => {
  const restored = progression.deserialize({ stage: 99, stats: { woodCollected: "many" } });
  assert.ok(restored.stage <= 8);
  assert.equal(typeof restored.stats.woodCollected, "number");
});
