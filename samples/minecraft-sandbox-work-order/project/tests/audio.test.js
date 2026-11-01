const test = require("node:test");
const assert = require("node:assert/strict");

const AudioKit = require("../js/audio.js");

function fakeEnvironment(options) {
  const settings = options || {};
  const created = [];
  function FakeParam() {
    this.value = 0;
    this.ramped = null;
  }
  FakeParam.prototype.setValueAtTime = function (value) {
    this.value = value;
  };
  FakeParam.prototype.exponentialRampToValueAtTime = function (value) {
    this.ramped = value;
  };
  function FakeContext() {
    this.currentTime = 0;
    this.state = settings.state || "running";
    this.destination = {};
    this.oscillators = [];
    this.gains = [];
  }
  FakeContext.prototype.createOscillator = function () {
    const oscillator = { type: "", frequency: new FakeParam(), connect: function () {}, start: function () { created.push("start"); }, stop: function () { created.push("stop"); } };
    this.oscillators.push(oscillator);
    return oscillator;
  };
  FakeContext.prototype.createGain = function () {
    const gain = { gain: new FakeParam(), connect: function () {} };
    this.gains.push(gain);
    return gain;
  };
  FakeContext.prototype.resume = function () {
    this.state = "running";
    created.push("resume");
  };
  const environment = { AudioContext: FakeContext };
  return { environment: environment, instances: [], created: created };
}

test("play creates a lazily initialised oscillator chain", () => {
  const fake = fakeEnvironment();
  const audio = AudioKit.createAudio(fake.environment);
  assert.equal(audio.play("mine"), true);
  assert.equal(audio.play("place"), true);
  assert.equal(fake.created.filter(function (entry) { return entry === "start"; }).length, 2);
});

test("muting blocks every sound until unmuted", () => {
  const fake = fakeEnvironment();
  const audio = AudioKit.createAudio(fake.environment);
  audio.setMuted(true);
  assert.equal(audio.isMuted(), true);
  assert.equal(audio.play("mine"), false);
  assert.equal(fake.created.length, 0);
  audio.setMuted(false);
  assert.equal(audio.play("mine"), true);
});

test("unknown sound kinds are ignored", () => {
  const fake = fakeEnvironment();
  const audio = AudioKit.createAudio(fake.environment);
  assert.equal(audio.play("explosion"), false);
  assert.equal(fake.created.length, 0);
});

test("a missing AudioContext fails silently", () => {
  const audio = AudioKit.createAudio({});
  assert.equal(audio.play("mine"), false);
  assert.equal(audio.unlock(), false);
});

test("unlock resumes a suspended context", () => {
  const fake = fakeEnvironment({ state: "suspended" });
  const audio = AudioKit.createAudio(fake.environment);
  assert.equal(audio.unlock(), true);
  assert.ok(fake.created.indexOf("resume") >= 0);
});

test("the sound table covers every interaction cue", () => {
  for (const kind of ["mine", "place", "jump", "select", "refuse"]) {
    assert.ok(AudioKit.SOUNDS[kind], "missing " + kind);
    assert.ok(AudioKit.SOUNDS[kind].duration > 0);
  }
});
