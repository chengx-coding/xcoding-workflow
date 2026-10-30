(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxAudio = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Small procedural sound set. Each entry is a short envelope around an
  // oscillator, so the page ships no audio assets and stays offline.
  const SOUNDS = {
    mine: { type: "sawtooth", frequency: 150, sweep: 90, duration: 0.08, gain: 0.05 },
    break: { type: "square", frequency: 220, sweep: 70, duration: 0.16, gain: 0.06 },
    place: { type: "triangle", frequency: 300, sweep: 380, duration: 0.09, gain: 0.07 },
    jump: { type: "sine", frequency: 320, sweep: 520, duration: 0.12, gain: 0.05 },
    select: { type: "triangle", frequency: 620, sweep: 660, duration: 0.05, gain: 0.04 },
    deny: { type: "sawtooth", frequency: 120, sweep: 90, duration: 0.1, gain: 0.05 },
    save: { type: "sine", frequency: 520, sweep: 700, duration: 0.1, gain: 0.035 }
  };

  function defaultFactory() {
    if (typeof AudioContext !== "undefined") {
      return function () {
        return new AudioContext();
      };
    }
    if (typeof window !== "undefined" && window.webkitAudioContext) {
      return function () {
        return new window.webkitAudioContext();
      };
    }
    return null;
  }

  function createAudioBoard(options) {
    const settings = options || {};
    const factory = settings.factory === undefined ? defaultFactory() : settings.factory;
    let context = null;
    let muted = Boolean(settings.muted);
    let failures = 0;

    function ensure() {
      if (context || !factory) {
        return context;
      }
      try {
        context = factory();
      } catch (error) {
        failures += 1;
        context = null;
      }
      if (context && context.state === "suspended" && typeof context.resume === "function") {
        try {
          context.resume();
        } catch (error) {
          failures += 1;
        }
      }
      return context;
    }

    function isMuted() {
      return muted;
    }

    function setMuted(value) {
      muted = Boolean(value);
      return muted;
    }

    function play(name) {
      const spec = SOUNDS[name];
      if (!spec || muted) {
        return false;
      }
      const audio = ensure();
      if (!audio) {
        return false;
      }
      try {
        const now = audio.currentTime || 0;
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.type = spec.type;
        oscillator.frequency.setValueAtTime(spec.frequency, now);
        oscillator.frequency.exponentialRampToValueAtTime(Math.max(20, spec.sweep), now + spec.duration);
        gain.gain.setValueAtTime(spec.gain, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + spec.duration);
        oscillator.connect(gain);
        gain.connect(audio.destination);
        oscillator.start(now);
        oscillator.stop(now + spec.duration + 0.02);
        return true;
      } catch (error) {
        failures += 1;
        return false;
      }
    }

    return {
      ensure: ensure,
      play: play,
      setMuted: setMuted,
      isMuted: isMuted,
      getContext: function () {
        return context;
      },
      getFailures: function () {
        return failures;
      },
      sounds: Object.keys(SOUNDS)
    };
  }

  return {
    createAudioBoard: createAudioBoard,
    SOUNDS: SOUNDS
  };
});
