const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const clockApi = require("../js/time.js");

test("clock starts mid-morning with a one-based day count", () => {
  const clock = clockApi.createClock();
  assert.equal(clock.day, 1);
  assert.equal(clock.length, config.dayLength);
  assert.ok(clock.t > 0.2 && clock.t < 0.4);
});

test("advancing the clock wraps the day and increments the counter", () => {
  const clock = clockApi.createClock({ start: 0.3, day: 1 });
  const half = clockApi.advance(clock, config.dayLength * 0.5);
  assert.equal(clock.day, 1);
  assert.ok(Math.abs(clock.t - 0.8) < 1e-9);
  assert.equal(half.dayAdvanced, false);
  const wrapped = clockApi.advance(clock, config.dayLength * 0.3);
  assert.equal(clock.day, 2);
  assert.ok(Math.abs(clock.t - 0.1) < 1e-9);
  assert.equal(wrapped.dayAdvanced, true);
});

test("advancing backwards crosses midnight safely", () => {
  const clock = clockApi.createClock({ start: 0.02, day: 3 });
  clockApi.advance(clock, -config.dayLength * 0.05);
  assert.equal(clock.day, 2);
  assert.ok(Math.abs(clock.t - 0.97) < 1e-9);
});

test("phases follow the documented bands", () => {
  assert.equal(clockApi.phase(0.0), "dawn");
  assert.equal(clockApi.phase(0.97), "dawn");
  assert.equal(clockApi.phase(0.2), "day");
  assert.equal(clockApi.phase(0.5), "dusk");
  assert.equal(clockApi.phase(0.7), "night");
  assert.equal(clockApi.phase(1.2), "day");
});

test("clock formatting maps sunrise to 06:00 and noon to 12:00", () => {
  assert.equal(clockApi.formatClock(0), "06:00");
  assert.equal(clockApi.formatClock(0.25), "12:00");
  assert.equal(clockApi.formatClock(0.5), "18:00");
  assert.equal(clockApi.formatClock(0.75), "00:00");
});

test("daylight is bright by day and dark at night", () => {
  assert.ok(clockApi.daylight(0.25) > 0.9);
  assert.ok(clockApi.daylight(0.75) < 0.25);
  assert.ok(clockApi.daylight(0.25) > clockApi.daylight(0.45));
});

test("the sky palette changes between day and night and interpolates", () => {
  const noon = clockApi.sky(0.25);
  const night = clockApi.sky(0.75);
  const dusk = clockApi.sky(0.52);
  assert.notEqual(noon.top, night.top);
  assert.notEqual(noon.bottom, night.bottom);
  assert.notEqual(dusk.top, noon.top);
  assert.ok(noon.daylight > night.daylight);
  const between = clockApi.sky(0.3);
  assert.equal(typeof between.top, "string");
  assert.ok(between.top.startsWith("rgb("));
});

test("sun and moon positions are visible in their halves of the day", () => {
  const noon = clockApi.sunPosition(0.25);
  assert.equal(noon.sun.visible, true);
  assert.ok(noon.sun.x > 0.4 && noon.sun.x < 0.6);
  const midnight = clockApi.sunPosition(0.75);
  assert.equal(midnight.sun.visible, false);
  assert.equal(midnight.moon.visible, true);
});
