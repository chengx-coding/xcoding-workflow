const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Time = require("../js/timecycle.js");

test("normalize wraps fractions into the day", () => {
  assert.equal(Time.normalize(0.25), 0.25);
  assert.equal(Time.normalize(1.25), 0.25);
  assert.equal(Time.normalize(-0.25), 0.75);
  assert.equal(Time.normalize(Number.NaN), 0);
});

test("clock labels map day fractions to a 24-hour clock", () => {
  assert.equal(Time.clockLabel(0), "00:00");
  assert.equal(Time.clockLabel(0.25), "06:00");
  assert.equal(Time.clockLabel(0.5), "12:00");
  assert.equal(Time.clockLabel(0.75), "18:00");
  assert.equal(Time.clockLabel(0.32), "07:40");
});

test("phases cover night, dawn, day and dusk", () => {
  assert.equal(Time.phaseOf(0.05), "night");
  assert.equal(Time.phaseOf(0.27), "dawn");
  assert.equal(Time.phaseOf(0.5), "day");
  assert.equal(Time.phaseOf(0.78), "dusk");
  assert.equal(Time.phaseOf(0.95), "night");
});

test("daylight is brighter than night", () => {
  assert.ok(Time.lightLevel(0.5) > Time.lightLevel(0.0));
  assert.ok(Time.lightLevel(0.5) > 0.9);
  assert.ok(Time.lightLevel(0.0) < 0.4);
});

test("sky colours differ materially between day and night", () => {
  const day = Time.sky(0.5);
  const night = Time.sky(0.0);
  assert.notDeepEqual(day.top, night.top);
  assert.notEqual(day.topCss, night.topCss);
  assert.equal(day.phase, "day");
  assert.equal(night.phase, "night");
  assert.equal(Time.isNight(0.0), true);
  assert.equal(Time.isNight(0.5), false);
});

test("the clock advances and wraps at the cycle length", () => {
  const clock = Time.createClock(0.9);
  Time.advance(clock, config.time.cycleSeconds / 2, config.time.cycleSeconds);
  assert.ok(Math.abs(clock.fraction - 0.4) < 0.0001);
  Time.advance(clock, config.time.cycleSeconds * 3, config.time.cycleSeconds);
  assert.ok(Math.abs(clock.fraction - 0.4) < 0.0001);
});

test("advance ignores invalid deltas", () => {
  const clock = Time.createClock(0.3);
  Time.advance(clock, Number.NaN, config.time.cycleSeconds);
  Time.advance(clock, 10, 0);
  assert.equal(clock.fraction, 0.3);
});

test("sky sampling is continuous around the day boundary", () => {
  const justBefore = Time.sky(0.999);
  const justAfter = Time.sky(0.001);
  assert.ok(Math.abs(justBefore.light - justAfter.light) < 0.05);
  assert.equal(justBefore.phase, "night");
  assert.equal(justAfter.phase, "night");
});
