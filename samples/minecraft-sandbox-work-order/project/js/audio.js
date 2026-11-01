(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxAudio = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SOUNDS = {
    mine: { from: 190, to: 110, duration: 0.09, type: "square", volume: 0.045 },
    place: { from: 240, to: 330, duration: 0.09, type: "triangle", volume: 0.05 },
    jump: { from: 340, to: 460, duration: 0.12, type: "sine", volume: 0.04 },
    select: { from: 660, to: 660, duration: 0.045, type: "sine", volume: 0.03 },
    refuse: { from: 150, to: 112, duration: 0.16, type: "sawtooth", volume: 0.045 },
    placeRefused: { from: 150, to: 112, duration: 0.16, type: "sawtooth", volume: 0.04 }
  };

  function createAudio(environment) {
    const env = environment || (typeof window !== "undefined" ? window : {});
    let context = null;
    let muted = false;
    let unavailable = false;

    function ensureContext() {
      if (context) {
        return context;
      }
      if (unavailable) {
        return null;
      }
      const Ctor = env.AudioContext || env.webkitAudioContext;
      if (typeof Ctor !== "function") {
        unavailable = true;
        return null;
      }
      try {
        context = new Ctor();
      } catch (error) {
        unavailable = true;
        return null;
      }
      return context;
    }

    function unlock() {
      const ctx = ensureContext();
      if (!ctx) {
        return false;
      }
      if (ctx.state === "suspended" && typeof ctx.resume === "function") {
        try {
          ctx.resume();
        } catch (error) {
          return false;
        }
      }
      return true;
    }

    function play(kind) {
      if (muted) {
        return false;
      }
      const sound = SOUNDS[kind];
      if (!sound) {
        return false;
      }
      const ctx = ensureContext();
      if (!ctx) {
        return false;
      }
      try {
        const now = ctx.currentTime;
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = sound.type;
        oscillator.frequency.setValueAtTime(sound.from, now);
        if (sound.to !== sound.from && typeof oscillator.frequency.exponentialRampToValueAtTime === "function") {
          oscillator.frequency.exponentialRampToValueAtTime(sound.to, now + sound.duration);
        }
        gain.gain.setValueAtTime(sound.volume, now);
        if (typeof gain.gain.exponentialRampToValueAtTime === "function") {
          gain.gain.exponentialRampToValueAtTime(0.0001, now + sound.duration);
        }
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(now);
        oscillator.stop(now + sound.duration);
        return true;
      } catch (error) {
        return false;
      }
    }

    function setMuted(value) {
      muted = value === true;
      return muted;
    }

    function isMuted() {
      return muted;
    }

    return {
      unlock: unlock,
      play: play,
      setMuted: setMuted,
      isMuted: isMuted
    };
  }

  return {
    createAudio: createAudio,
    SOUNDS: SOUNDS
  };
});
