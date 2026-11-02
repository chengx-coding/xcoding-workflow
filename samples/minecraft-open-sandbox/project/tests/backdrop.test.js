const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const backdropApi = require("../js/backdrop.js");

const B = config.blocks;

test("recording an edit keeps before and after labels and a pulse", () => {
  const backdrop = backdropApi.createBackdrop();
  const edit = backdropApi.recordEdit(backdrop, { x: 4, y: 5, before: B.grass, after: B.air });
  assert.equal(edit.beforeName, "Grass");
  assert.equal(edit.afterName, "Air");
  assert.equal(backdrop.edits.length, 1);
  const pulse = backdropApi.currentPulse(backdrop);
  assert.equal(pulse.kind, "edit");
  assert.equal(pulse.before, "Grass");
  assert.equal(pulse.after, "Air");
});

test("a placed block over a flower records the covered content", () => {
  const backdrop = backdropApi.createBackdrop();
  backdropApi.recordEdit(backdrop, { x: 1, y: 1, before: B.flower, after: B.planks });
  assert.equal(backdropApi.currentPulse(backdrop).before, "Flower");
  assert.equal(backdrop.edits[0].before, B.flower);
});

test("undo and redo walk the edit history", () => {
  const backdrop = backdropApi.createBackdrop();
  backdropApi.recordEdit(backdrop, { x: 1, y: 1, before: B.grass, after: B.air });
  backdropApi.recordEdit(backdrop, { x: 2, y: 1, before: B.dirt, after: B.planks });
  assert.equal(backdropApi.canUndo(backdrop), true);
  const undone = backdropApi.undo(backdrop);
  assert.equal(undone.x, 2);
  assert.equal(undone.before, B.dirt);
  assert.equal(backdropApi.canRedo(backdrop), true);
  const redone = backdropApi.redo(backdrop);
  assert.equal(redone.x, 2);
  assert.equal(redone.after, B.planks);
  assert.equal(backdropApi.canRedo(backdrop), false);
});

test("a new edit after undo clears the redo stack", () => {
  const backdrop = backdropApi.createBackdrop();
  backdropApi.recordEdit(backdrop, { x: 1, y: 1, before: B.grass, after: B.air });
  backdropApi.undo(backdrop);
  assert.equal(backdropApi.canRedo(backdrop), true);
  backdropApi.recordEdit(backdrop, { x: 3, y: 1, before: B.stone, after: B.planks });
  assert.equal(backdropApi.canRedo(backdrop), false);
});

test("edit and pulse buffers are bounded", () => {
  const backdrop = backdropApi.createBackdrop({ cap: 3, pulseCap: 2 });
  for (let index = 0; index < 6; index += 1) {
    backdropApi.recordEdit(backdrop, { x: index, y: 0, before: B.stone, after: B.air });
  }
  assert.equal(backdrop.edits.length, 3);
  assert.equal(backdrop.edits[2].x, 5);
  assert.equal(backdrop.pulses.length, 2);
  assert.equal(backdropApi.currentPulse(backdrop).before, "Stone");
});

test("recent edits are returned newest first", () => {
  const backdrop = backdropApi.createBackdrop();
  backdropApi.recordEdit(backdrop, { x: 1, y: 0, before: B.stone, after: B.air });
  backdropApi.recordEdit(backdrop, { x: 2, y: 0, before: B.dirt, after: B.air });
  const recent = backdropApi.recentEdits(backdrop, 2);
  assert.equal(recent[0].x, 2);
  assert.equal(recent[1].x, 1);
});

test("mode, time and view pulses are recorded with their own kinds", () => {
  const backdrop = backdropApi.createBackdrop();
  backdropApi.pulse(backdrop, "mode", "Build", "Backdrop");
  assert.equal(backdropApi.currentPulse(backdrop).kind, "mode");
  backdropApi.pulse(backdrop, "time", "Day", "Dusk");
  assert.equal(backdropApi.currentPulse(backdrop).after, "Dusk");
  backdropApi.pulse(backdrop, "view", "1.0x", "1.5x");
  assert.equal(backdropApi.currentPulse(backdrop).kind, "view");
  assert.equal(backdropApi.isKind("view"), true);
  assert.equal(backdropApi.isKind("nope"), false);
});

test("describeEdit produces a readable before to after line", () => {
  const backdrop = backdropApi.createBackdrop();
  const edit = backdropApi.recordEdit(backdrop, { x: 7, y: 9, before: B.stone, after: B.torch });
  const description = backdropApi.describeEdit(edit);
  assert.equal(description.position, "(7, 9)");
  assert.equal(description.arrow, "Stone -> Torch");
});
