(function (root) {
  "use strict";

  function createAudio() {
    let context = null;
    let master = null;
    let muted = false;
    let unavailable = false;

    function ensureContext() {
      if (unavailable) {
        return null;
      }
      if (context) {
        if (context.state === "suspended") {
          context.resume().catch(function () {});
        }
        return context;
      }
      const Ctor = root.AudioContext || root.webkitAudioContext;
      if (!Ctor) {
        unavailable = true;
        return null;
      }
      try {
        context = new Ctor();
        master = context.createGain();
        master.gain.value = 0.22;
        master.connect(context.destination);
      } catch (error) {
        unavailable = true;
        return null;
      }
      return context;
    }

    function tone(frequency, duration, type, startFrequency, volume) {
      if (muted) {
        return;
      }
      const audio = ensureContext();
      if (!audio) {
        return;
      }
      const now = audio.currentTime;
      const oscillator = audio.createOscillator();
      const gain = audio.createGain();
      oscillator.type = type || "square";
      oscillator.frequency.setValueAtTime(frequency, now);
      if (typeof startFrequency === "number") {
        oscillator.frequency.exponentialRampToValueAtTime(Math.max(20, startFrequency), now + duration);
      }
      gain.gain.setValueAtTime(volume === undefined ? 0.18 : volume, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
      oscillator.connect(gain);
      gain.connect(master);
      oscillator.start(now);
      oscillator.stop(now + duration + 0.02);
    }

    function noise(duration, volume, lowpass) {
      if (muted) {
        return;
      }
      const audio = ensureContext();
      if (!audio) {
        return;
      }
      const sampleCount = Math.max(1, Math.floor(audio.sampleRate * duration));
      const buffer = audio.createBuffer(1, sampleCount, audio.sampleRate);
      const channel = buffer.getChannelData(0);
      for (let i = 0; i < sampleCount; i += 1) {
        channel[i] = (Math.random() * 2 - 1) * (1 - i / sampleCount);
      }
      const source = audio.createBufferSource();
      source.buffer = buffer;
      const filter = audio.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.value = lowpass || 1400;
      const gain = audio.createGain();
      gain.gain.value = volume === undefined ? 0.2 : volume;
      source.connect(filter);
      filter.connect(gain);
      gain.connect(master);
      source.start();
    }

    function play(name) {
      if (muted) {
        return;
      }
      switch (name) {
        case "dig":
          noise(0.045, 0.16, 700);
          break;
        case "break":
          noise(0.14, 0.3, 1200);
          tone(180, 0.09, "triangle", 90, 0.1);
          break;
        case "place":
          tone(240, 0.07, "square", 180, 0.14);
          noise(0.04, 0.1, 500);
          break;
        case "jump":
          tone(300, 0.09, "sine", 460, 0.12);
          break;
        case "land":
          noise(0.06, 0.12, 400);
          break;
        case "craft":
          tone(523, 0.08, "triangle", 523, 0.14);
          root.setTimeout(function () {
            tone(784, 0.12, "triangle", 784, 0.12);
          }, 80);
          break;
        case "click":
          tone(620, 0.03, "square", 620, 0.08);
          break;
        case "save":
          tone(660, 0.07, "sine", 660, 0.11);
          root.setTimeout(function () {
            tone(990, 0.1, "sine", 990, 0.09);
          }, 70);
          break;
        case "error":
          tone(140, 0.12, "sawtooth", 110, 0.12);
          break;
        default:
          break;
      }
    }

    function toggleMute() {
      muted = !muted;
      if (muted && context) {
        master.gain.value = 0;
      } else if (!muted && master) {
        master.gain.value = 0.22;
      }
      return muted;
    }

    function isMuted() {
      return muted;
    }

    function unlock() {
      ensureContext();
    }

    return {
      play: play,
      toggleMute: toggleMute,
      isMuted: isMuted,
      unlock: unlock
    };
  }

  if (typeof module === "object" && module.exports) {
    module.exports = { createAudio: createAudio };
  } else {
    root.SandboxAudio = { createAudio: createAudio };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
