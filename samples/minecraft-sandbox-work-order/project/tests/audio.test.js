const test = require("node:test");
const assert = require("node:assert/strict");

const audio = require("../js/audio.js");

function fakeContext(log) {
  return {
    currentTime: 0,
    state: "running",
    destination: {},
    resume() {
      log.push("resume");
    },
    createOscillator() {
      log.push("oscillator");
      return {
        type: "",
        frequency: {
          setValueAtTime() {},
          exponentialRampToValueAtTime() {}
        },
        connect() {},
        start() {
          log.push("start");
        },
        stop() {}
      };
    },
    createGain() {
      log.push("gain");
      return {
        gain: {
          setValueAtTime() {},
          exponentialRampToValueAtTime() {}
        },
        connect() {}
      };
    }
  };
}

test("the sound set covers the interaction vocabulary", () => {
  ["mine", "break", "place", "jump", "select", "deny"].forEach((name) => {
    assert.ok(Object.prototype.hasOwnProperty.call(audio.SOUNDS, name), "missing sound " + name);
  });
});

test("sound is a safe no-op without an audio context", () => {
  const board = audio.createAudioBoard({ factory: null });
  assert.equal(board.ensure(), null);
  assert.equal(board.play("mine"), false);
  assert.equal(board.isMuted(), false);
});

test("playing a sound builds one oscillator through the gain node", () => {
  const log = [];
  const board = audio.createAudioBoard({ factory: () => fakeContext(log) });
  assert.equal(board.play("mine"), true);
  assert.equal(log.filter((entry) => entry === "oscillator").length, 1);
  assert.equal(log.filter((entry) => entry === "gain").length, 1);
  assert.ok(log.includes("start"));
});

test("the audio context is created once and reused", () => {
  const log = [];
  let created = 0;
  const board = audio.createAudioBoard({
    factory: () => {
      created += 1;
      return fakeContext(log);
    }
  });
  board.play("mine");
  board.play("place");
  assert.equal(created, 1);
  assert.equal(log.filter((entry) => entry === "oscillator").length, 2);
});

test("muting suppresses new sound nodes", () => {
  const log = [];
  const board = audio.createAudioBoard({ factory: () => fakeContext(log) });
  board.setMuted(true);
  assert.equal(board.play("place"), false);
  assert.equal(log.filter((entry) => entry === "oscillator").length, 0);
  assert.equal(board.isMuted(), true);
  board.setMuted(false);
  assert.equal(board.play("place"), true);
});

test("unknown sound names are ignored", () => {
  const log = [];
  const board = audio.createAudioBoard({ factory: () => fakeContext(log) });
  assert.equal(board.play("explosion"), false);
  assert.equal(log.filter((entry) => entry === "oscillator").length, 0);
});

test("a suspended context is resumed on first use", () => {
  const log = [];
  const context = fakeContext(log);
  context.state = "suspended";
  const board = audio.createAudioBoard({ factory: () => context });
  board.ensure();
  assert.ok(log.includes("resume"));
});

test("an audio factory failure degrades to silence instead of throwing", () => {
  const board = audio.createAudioBoard({
    factory: () => {
      throw new Error("no audio");
    }
  });
  assert.equal(board.ensure(), null);
  assert.equal(board.play("mine"), false);
  assert.ok(board.getFailures() >= 1);
});
