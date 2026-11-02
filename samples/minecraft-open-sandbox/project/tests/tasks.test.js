const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const tasks = require("../js/tasks.js");

const B = config.blocks;

test("a fresh player starts on the first task and nothing is complete", () => {
  const progress = tasks.createProgress();
  assert.equal(tasks.completedCount(progress), 0);
  const active = tasks.activeTask(progress);
  assert.equal(active.id, "first_wood");
  assert.ok(active.hint.length > 10);
});

test("collecting wood completes the first task and grants its reward", () => {
  const progress = tasks.createProgress();
  tasks.noteCollected(progress, B.wood, 2);
  assert.equal(tasks.sync(progress).length, 0);
  tasks.noteCollected(progress, B.wood, 1);
  const completed = tasks.sync(progress);
  assert.equal(completed.length, 1);
  assert.equal(completed[0].id, "first_wood");
  assert.deepEqual(completed[0].reward, { id: B.torch, count: 2 });
  assert.equal(tasks.activeTask(progress).id, "make_planks");
});

test("a task completes only once", () => {
  const progress = tasks.createProgress();
  tasks.noteCollected(progress, B.wood, 5);
  assert.equal(tasks.sync(progress).length, 1);
  assert.equal(tasks.sync(progress).length, 0);
  assert.equal(progress.tasks.first_wood, true);
});

test("crafting, placing, depth, iron and day tasks all track progress", () => {
  const progress = tasks.createProgress();
  tasks.noteCollected(progress, B.wood, 3);
  tasks.noteCollected(progress, B.planks, 4);
  tasks.noteCrafted(progress, "wooden_pickaxe");
  tasks.notePlaced(progress, B.dirt);
  for (let index = 1; index < 10; index += 1) {
    tasks.notePlaced(progress, B.dirt);
  }
  tasks.notePlaced(progress, B.torch);
  tasks.noteDepth(progress, 68);
  tasks.noteCollected(progress, 102, 1);
  progress.day = 2;
  const completed = tasks.sync(progress);
  const ids = completed.map(function (task) { return task.id; }).sort();
  assert.deepEqual(ids, [
    "build_shelter", "dig_deep", "find_iron", "first_wood", "light_dark",
    "make_pickaxe", "make_planks", "survive_night"
  ]);
  assert.equal(tasks.activeTask(progress), null);
  assert.equal(tasks.completedCount(progress), tasks.TASKS.length);
});

test("task progress text reports value over goal", () => {
  const progress = tasks.createProgress();
  const task = tasks.TASKS[0];
  let info = tasks.taskProgress(task, progress);
  assert.equal(info.text, "0/3");
  tasks.noteCollected(progress, B.wood, 2);
  info = tasks.taskProgress(task, progress);
  assert.equal(info.text, "2/3");
});

test("progress serializes and restores without losing completions", () => {
  const progress = tasks.createProgress();
  tasks.noteCollected(progress, B.wood, 3);
  tasks.notePlaced(progress, B.torch);
  tasks.sync(progress);
  progress.day = 4;
  progress.deepest = 70;
  const restored = tasks.deserialize(tasks.serialize(progress));
  assert.equal(restored.tasks.first_wood, true);
  assert.equal(restored.tasks.light_dark, true);
  assert.equal(restored.collected[B.wood], 3);
  assert.equal(restored.placed.byId[B.torch], 1);
  assert.equal(restored.day, 4);
  assert.equal(restored.deepest, 70);
});
