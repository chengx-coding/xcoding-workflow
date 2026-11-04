/* Tiny procedural WebAudio sound effects. No audio files or network. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxAudio = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  let context = null;
  let master = null;
  let enabled = true;
  let unlocked = false;

  function ensureContext() {
    if (context) {
      return context;
    }
    const Constructor = typeof window !== "undefined" ? (window.AudioContext || window.webkitAudioContext) : null;
    if (!Constructor) {
      return null;
    }
    try {
      context = new Constructor();
      master = context.createGain();
      master.gain.value = enabled ? 0.2 : 0;
      master.connect(context.destination);
    } catch (error) {
      context = null;
      master = null;
    }
    return context;
  }

  function unlock() {
    const ctx = ensureContext();
    if (!ctx) {
      return false;
    }
    if (ctx.state === "suspended") {
      ctx.resume().catch(function () {});
    }
    unlocked = true;
    return true;
  }

  function now() {
    return context ? context.currentTime : 0;
  }

  function tone(settings) {
    if (!context || !master || !enabled) {
      return;
    }
    const start = now();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = settings.type || "square";
    oscillator.frequency.setValueAtTime(settings.from, start);
    if (settings.to && settings.to !== settings.from) {
      oscillator.frequency.exponentialRampToValueAtTime(Math.max(20, settings.to), start + settings.duration);
    }
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.001, settings.gain || 0.12), start + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + settings.duration);
    oscillator.connect(gain);
    gain.connect(master);
    oscillator.start(start);
    oscillator.stop(start + settings.duration + 0.02);
  }

  function noise(duration, frequency, gainValue) {
    if (!context || !master || !enabled) {
      return;
    }
    const length = Math.max(1, Math.floor(context.sampleRate * duration));
    const buffer = context.createBuffer(1, length, context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / length);
    }
    const source = context.createBufferSource();
    source.buffer = buffer;
    const filter = context.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = frequency || 900;
    filter.Q.value = 1.2;
    const gain = context.createGain();
    gain.gain.value = gainValue || 0.12;
    source.connect(filter);
    filter.connect(gain);
    gain.connect(master);
    source.start();
  }

  function play(name) {
    if (!enabled) {
      return;
    }
    if (!context || !unlocked) {
      return;
    }
    switch (name) {
      case "mine":
        noise(0.07, 520, 0.09);
        tone({ from: 120, to: 70, duration: 0.06, type: "square", gain: 0.05 });
        break;
      case "break":
        noise(0.14, 700, 0.16);
        tone({ from: 160, to: 60, duration: 0.12, type: "triangle", gain: 0.08 });
        break;
      case "place":
        noise(0.05, 320, 0.11);
        tone({ from: 180, to: 120, duration: 0.07, type: "square", gain: 0.07 });
        break;
      case "jump":
        tone({ from: 300, to: 450, duration: 0.1, type: "square", gain: 0.05 });
        break;
      case "step":
        noise(0.03, 240, 0.035);
        break;
      case "hurt":
        tone({ from: 190, to: 70, duration: 0.22, type: "sawtooth", gain: 0.11 });
        break;
      case "death":
        tone({ from: 220, to: 45, duration: 0.8, type: "sawtooth", gain: 0.12 });
        break;
      case "eat":
        noise(0.08, 500, 0.1);
        noise(0.08, 420, 0.08);
        break;
      case "pickup":
        tone({ from: 760, to: 980, duration: 0.07, type: "triangle", gain: 0.06 });
        break;
      case "craft":
        tone({ from: 523, to: 523, duration: 0.09, type: "triangle", gain: 0.08 });
        window.setTimeout(function () { tone({ from: 659, to: 659, duration: 0.09, type: "triangle", gain: 0.08 }); }, 80);
        window.setTimeout(function () { tone({ from: 784, to: 784, duration: 0.14, type: "triangle", gain: 0.08 }); }, 160);
        break;
      case "attack":
        tone({ from: 260, to: 120, duration: 0.09, type: "square", gain: 0.08 });
        noise(0.05, 900, 0.06);
        break;
      default:
        break;
    }
  }

  function setEnabled(value) {
    enabled = Boolean(value);
    if (master) {
      master.gain.value = enabled ? 0.2 : 0;
    }
  }

  function isEnabled() {
    return enabled;
  }

  function isUnlocked() {
    return unlocked;
  }

  return {
    unlock: unlock,
    play: play,
    setEnabled: setEnabled,
    isEnabled: isEnabled,
    isUnlocked: isUnlocked,
    ensureContext: ensureContext
  };
});
