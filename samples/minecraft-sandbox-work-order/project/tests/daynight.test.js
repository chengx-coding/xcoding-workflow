const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const daynight = require("../js/daynight.js");

test("normalizeTime wraps any clock value into one day", () => {
  assert.equal(daynight.normalizeTime(0.25), 0.25);
  assert.ok(Math.abs(daynight.normalizeTime(1.25) - 0.25) < 1e-9);
  assert.ok(Math.abs(daynight.normalizeTime(-0.25) - 0.75) < 1e-9);
  assert.equal(daynight.normalizeTime("x"), 0);
});

test("advanceTime advances and wraps using the configured cycle", () => {
  const halfway = daynight.advanceTime(0, config.dayCycleSeconds / 2, config.dayCycleSeconds);
  assert.ok(Math.abs(halfway - 0.5) < 1e-9);
  const wrapped = daynight.advanceTime(0.9, config.dayCycleSeconds * 0.2, config.dayCycleSeconds);
  assert.ok(Math.abs(wrapped - 0.1) < 1e-9);
});

test("advanceTime ignores zero or invalid deltas", () => {
  assert.equal(daynight.advanceTime(0.3, 0, 240), 0.3);
  assert.equal(daynight.advanceTime(0.3, NaN, 240), 0.3);
});

test("phases and labels follow the day clock", () => {
  assert.equal(daynight.phaseOf(0.02), "dawn");
  assert.equal(daynight.phaseOf(0.25), "day");
  assert.equal(daynight.phaseOf(0.5), "dusk");
  assert.equal(daynight.phaseOf(0.8), "night");
  assert.equal(daynight.labelOf(0.25), "Day");
  assert.equal(daynight.labelOf(0.8), "Night");
});

test("noon is brighter than midnight", () => {
  assert.ok(daynight.daylight(0.25) > daynight.daylight(0.75));
  assert.ok(daynight.daylight(0.25) >= 0.95);
  assert.ok(daynight.daylight(0.75) < 0.2);
});

test("sky colours are distinct across the cycle", () => {
  const day = daynight.skyColors(0.25);
  const night = daynight.skyColors(0.75);
  assert.notEqual(day.top, night.top);
  assert.notEqual(day.bottom, night.bottom);
  assert.ok(day.light > night.light);
  assert.match(day.top, /^rgb\(\d+, \d+, \d+\)$/);
});

test("isNight covers the dark half of the cycle", () => {
  assert.equal(daynight.isNight(0.75), true);
  assert.equal(daynight.isNight(0.25), false);
  assert.equal(daynight.isNight(0.58), true);
});

test("the sun and moon sit opposite each other", () => {
  const bodies = daynight.celestial(0.25);
  const sunX = bodies.sun.x;
  const moonX = bodies.moon.x;
  assert.ok(Math.abs(sunX - 0.5) < 0.5);
  assert.ok(Math.abs(moonX - 0.5) < 0.5);
  assert.notDeepEqual(bodies.sun, daynight.celestial(0.75).sun);
});

test("the night tint grows as light fades", () => {
  assert.ok(daynight.nightTint(0.75) > daynight.nightTint(0.25));
  assert.ok(daynight.nightTint(0.25) >= 0);
  assert.ok(daynight.nightTint(0.75) <= 0.62);
});
