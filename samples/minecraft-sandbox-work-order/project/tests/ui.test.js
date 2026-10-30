const test = require("node:test");
const assert = require("node:assert/strict");

const ui = require("../js/ui.js");

test("movement, jump, pause, mute and help keys map to actions", () => {
  assert.equal(ui.keyToAction("a"), "left");
  assert.equal(ui.keyToAction("ArrowLeft"), "left");
  assert.equal(ui.keyToAction("d"), "right");
  assert.equal(ui.keyToAction("ArrowRight"), "right");
  assert.equal(ui.keyToAction(" "), "jump");
  assert.equal(ui.keyToAction("ArrowUp"), "jump");
  assert.equal(ui.keyToAction("p"), "pause");
  assert.equal(ui.keyToAction("Escape"), "pause");
  assert.equal(ui.keyToAction("m"), "mute");
  assert.equal(ui.keyToAction("h"), "help");
  assert.equal(ui.keyToAction("?"), "help");
  assert.equal(ui.keyToAction("r"), "respawn");
});

test("number keys map to numbered slots and unknown keys do nothing", () => {
  assert.equal(ui.keyToAction("1"), "slot1");
  assert.equal(ui.keyToAction("9"), "slot9");
  assert.equal(ui.keyToAction("0"), "none");
  assert.equal(ui.keyToAction("z"), "none");
  assert.equal(ui.keyToAction(null), "none");
});

test("typing in a seed field is not treated as game input", () => {
  assert.equal(ui.isTextEntryTarget("INPUT"), true);
  assert.equal(ui.isTextEntryTarget("textarea"), true);
  assert.equal(ui.isTextEntryTarget("BUTTON"), false);
  assert.equal(ui.isTextEntryTarget(""), false);
});

test("coordinates render as block-space text", () => {
  assert.equal(ui.formatCoords({ x: 12.7, y: 30.2 }), "x 12 · y 30");
  assert.equal(ui.formatCoords(null), "x – · y –");
});

test("depth tells above and below the surface", () => {
  assert.equal(ui.formatDepth({ x: 0, y: 20 }, 20), "at the surface");
  assert.equal(ui.formatDepth({ x: 0, y: 16 }, 20), "4 above ground");
  assert.equal(ui.formatDepth({ x: 0, y: 26 }, 20), "6 below surface");
  assert.equal(ui.formatDepth(null, 20), "depth –");
});

test("hotbar counts cap their displayed width", () => {
  assert.equal(ui.formatCount(0), "0");
  assert.equal(ui.formatCount(7), "7");
  assert.equal(ui.formatCount(99), "99");
  assert.equal(ui.formatCount(320), "99+");
  assert.equal(ui.formatCount(-1), "0");
  assert.equal(ui.formatCount("x"), "0");
});

test("seed parsing reports actionable errors", () => {
  assert.deepEqual(ui.parseSeedInput("1234"), { ok: true, seed: 1234 });
  assert.equal(ui.parseSeedInput("abc").ok, false);
  assert.equal(ui.parseSeedInput("").ok, false);
});

test("reduced motion is detected through the media query", () => {
  assert.equal(ui.prefersReducedMotion(null), false);
  assert.equal(
    ui.prefersReducedMotion(() => ({ matches: true })),
    true
  );
  assert.equal(
    ui.prefersReducedMotion(() => ({ matches: false })),
    false
  );
  assert.equal(
    ui.prefersReducedMotion(() => {
      throw new Error("unsupported");
    }),
    false
  );
});

test("the help list documents every required control", () => {
  const text = ui.HELP_CONTROLS.map((entry) => entry.keys + " " + entry.action).join(" ").toLowerCase();
  ["a", "d", "space", "left click", "right click", "1 - 9", "wheel", "p", "m", "h"].forEach((needle) => {
    assert.ok(text.includes(needle), "missing control: " + needle);
  });
  assert.ok(ui.HELP_CONTROLS.length >= 9);
});

test("toast messages can carry a detail", () => {
  assert.equal(ui.toastMessage("saved"), "World saved");
  assert.equal(ui.toastMessage("seeded", "42"), "Seed loaded: 42");
  assert.equal(ui.toastMessage("unknown"), "");
});
