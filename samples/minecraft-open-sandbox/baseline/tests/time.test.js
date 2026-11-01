const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const time = require("../js/time.js");

test("a new day starts just after dawn and advances through the clock", () => {
  const dawn = time.getDayInfo(0, config.daySeconds);
  assert.equal(dawn.clock, "06:00");
  assert.equal(dawn.day, 1);
  assert.equal(dawn.isNight, true, "the sun is at the horizon");
  const noon = time.getDayInfo(config.daySeconds * 0.25, config.daySeconds);
  assert.equal(noon.clock, "12:00");
  assert.equal(noon.day, 1);
  assert.equal(noon.isNight, false);
  assert.ok(noon.daylight > 0.9);
  const night = time.getDayInfo(config.daySeconds * 0.75, config.daySeconds);
  assert.equal(night.clock, "00:00");
  assert.equal(night.day, 1);
  assert.equal(night.isNight, true);
  assert.ok(night.daylight < 0.1);
});

test("the day counter rolls over after a full cycle", () => {
  const info = time.getDayInfo(config.daySeconds * 1.3, config.daySeconds);
  assert.equal(info.day, 2);
  assert.equal(info.clock, "13:12");
  assert.equal(info.phase, "Midday");
});

test("twilight is warm around the horizon", () => {
  const dawn = time.getDayInfo(config.daySeconds * 0.01, config.daySeconds);
  const noon = time.getDayInfo(config.daySeconds * 0.25, config.daySeconds);
  assert.ok(dawn.twilight > noon.twilight);
  assert.ok(dawn.daylight < noon.daylight);
});
