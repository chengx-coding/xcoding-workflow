(function (root) {
  "use strict";

  // Procedural sound: every effect is synthesized, so the page stays free of
  // audio files and network requests. Contexts are created lazily on a gesture
  // so autoplay policies never block the game.
  function createAudio() {
    let context = null;
    let muted = false;
    let played = 0;
    let lastError = null;

    function ensureContext() {
      if (context) {
        return context;
      }
      const Constructor = root.AudioContext || root.webkitAudioContext;
      if (!Constructor) {
        return null;
      }
      try {
        context = new Constructor();
      } catch (error) {
        lastError = error && error.message ? error.message : String(error);
        context = null;
      }
      return context;
    }

    function blip(frequency, duration, type, volume, delay) {
      const ctx = ensureContext();
      if (!ctx || muted) {
        return;
      }
      if (ctx.state === "suspended") {
        ctx.resume().catch(function () {});
      }
      const start = ctx.currentTime + (delay || 0);
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.type = type || "sine";
      oscillator.frequency.setValueAtTime(frequency, start);
      const peak = Math.max(0.0001, volume || 0.06);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(peak, start + 0.008);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      oscillator.connect(gain);
      gain.connect(ctx.destination);
      oscillator.start(start);
      oscillator.stop(start + duration + 0.02);
      played += 1;
    }

    function noiseBurst(duration, volume) {
      const ctx = ensureContext();
      if (!ctx || muted) {
        return;
      }
      const length = Math.max(1, Math.floor(ctx.sampleRate * duration));
      const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let index = 0; index < length; index += 1) {
        data[index] = (Math.random() * 2 - 1) * (1 - index / length);
      }
      const source = ctx.createBufferSource();
      const gain = ctx.createGain();
      gain.gain.value = volume || 0.05;
      source.buffer = buffer;
      source.connect(gain);
      gain.connect(ctx.destination);
      source.start();
      played += 1;
    }

    const sounds = {
      mine: function () { blip(180, 0.05, "square", 0.03); },
      break: function () { noiseBurst(0.12, 0.08); blip(96, 0.09, "triangle", 0.05); },
      place: function () { blip(320, 0.06, "square", 0.04); },
      craft: function () { blip(523, 0.1, "triangle", 0.05); blip(784, 0.14, "triangle", 0.05, 0.08); },
      quest: function () { blip(523, 0.12, "sine", 0.06); blip(659, 0.12, "sine", 0.06, 0.1); blip(784, 0.2, "sine", 0.06, 0.2); },
      jump: function () { blip(420, 0.09, "sine", 0.035); },
      hurt: function () { blip(140, 0.18, "sawtooth", 0.05); },
      save: function () { blip(660, 0.07, "sine", 0.04); blip(880, 0.09, "sine", 0.04, 0.06); },
      error: function () { blip(110, 0.16, "square", 0.04); }
    };

    function play(name) {
      const sound = sounds[name];
      if (!sound || muted) {
        return false;
      }
      try {
        sound();
        return true;
      } catch (error) {
        lastError = error && error.message ? error.message : String(error);
        return false;
      }
    }

    return {
      play: play,
      setMuted: function (value) {
        muted = Boolean(value);
        return muted;
      },
      toggle: function () {
        muted = !muted;
        return muted;
      },
      isMuted: function () {
        return muted;
      },
      state: function () {
        return {
          muted: muted,
          available: Boolean(context),
          played: played,
          error: lastError
        };
      }
    };
  }

  root.SandboxAudio = { createAudio: createAudio };
})(typeof globalThis !== "undefined" ? globalThis : this);
