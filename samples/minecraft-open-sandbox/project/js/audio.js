(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SandboxAudio = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const MUTE_KEY = "emberdeep.muted";
  let context = null;
  let master = null;
  let muted = false;
  let noiseBuffer = null;

  try {
    muted = typeof localStorage !== "undefined" && localStorage.getItem(MUTE_KEY) === "1";
  } catch (error) {
    muted = false;
  }

  function hasAudio() {
    return typeof window !== "undefined" && !!(window.AudioContext || window.webkitAudioContext);
  }

  function unlock() {
    if (!hasAudio()) {
      return false;
    }
    if (!context) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      context = new Ctor();
      master = context.createGain();
      master.gain.value = 0.32;
      master.connect(context.destination);
      const length = Math.floor(context.sampleRate * 0.5);
      noiseBuffer = context.createBuffer(1, length, context.sampleRate);
      const data = noiseBuffer.getChannelData(0);
      for (let i = 0; i < length; i += 1) {
        data[i] = Math.random() * 2 - 1;
      }
    }
    if (context.state === "suspended") {
      context.resume();
    }
    return true;
  }

  function tone(frequency, duration, options) {
    if (!context || muted) {
      return;
    }
    const settings = options || {};
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = settings.type || "square";
    oscillator.frequency.setValueAtTime(frequency, context.currentTime);
    if (settings.slideTo) {
      oscillator.frequency.exponentialRampToValueAtTime(
        Math.max(20, settings.slideTo),
        context.currentTime + duration
      );
    }
    const peak = settings.gain === undefined ? 0.35 : settings.gain;
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(peak, context.currentTime + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + duration);
    oscillator.connect(gain);
    gain.connect(master);
    oscillator.start();
    oscillator.stop(context.currentTime + duration + 0.02);
  }

  function noise(duration, gainValue, filterFrequency) {
    if (!context || muted || !noiseBuffer) {
      return;
    }
    const source = context.createBufferSource();
    source.buffer = noiseBuffer;
    const filter = context.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = filterFrequency || 1200;
    const gain = context.createGain();
    gain.gain.setValueAtTime(gainValue || 0.25, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + duration);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(master);
    source.start();
    source.stop(context.currentTime + duration + 0.02);
  }

  function play(name) {
    if (!unlock()) {
      return;
    }
    switch (name) {
      case "mine":
        tone(220, 0.05, { type: "square", gain: 0.08, slideTo: 150 });
        noise(0.05, 0.06, 900);
        break;
      case "break":
        noise(0.14, 0.22, 700);
        tone(90, 0.14, { type: "sine", gain: 0.16, slideTo: 60 });
        break;
      case "place":
        tone(150, 0.08, { type: "triangle", gain: 0.2, slideTo: 110 });
        noise(0.05, 0.08, 500);
        break;
      case "pickup":
        tone(660, 0.07, { type: "triangle", gain: 0.14 });
        tone(880, 0.08, { type: "triangle", gain: 0.11 });
        break;
      case "craft":
        tone(523, 0.09, { type: "triangle", gain: 0.16 });
        window.setTimeout(function second() {
          tone(659, 0.1, { type: "triangle", gain: 0.14 });
        }, 70);
        window.setTimeout(function third() {
          tone(784, 0.14, { type: "triangle", gain: 0.13 });
        }, 140);
        break;
      case "hurt":
        tone(160, 0.18, { type: "sawtooth", gain: 0.2, slideTo: 70 });
        noise(0.12, 0.14, 600);
        break;
      case "death":
        tone(220, 0.3, { type: "sawtooth", gain: 0.2, slideTo: 90 });
        window.setTimeout(function second() {
          tone(140, 0.4, { type: "sine", gain: 0.16, slideTo: 60 });
        }, 180);
        break;
      case "quest":
        [523, 659, 784, 1047].forEach(function note(frequency, index) {
          window.setTimeout(function playNote() {
            tone(frequency, 0.16, { type: "triangle", gain: 0.13 });
          }, index * 90);
        });
        break;
      case "night":
        tone(110, 0.6, { type: "sine", gain: 0.1, slideTo: 82 });
        tone(164, 0.5, { type: "sine", gain: 0.06, slideTo: 130 });
        break;
      case "beacon":
        [261, 329, 392, 523, 659].forEach(function chord(frequency, index) {
          window.setTimeout(function playChord() {
            tone(frequency, 0.7, { type: "triangle", gain: 0.1 });
          }, index * 120);
        });
        break;
      case "ui":
        tone(440, 0.04, { type: "square", gain: 0.06 });
        break;
      case "error":
        tone(180, 0.09, { type: "square", gain: 0.08, slideTo: 120 });
        break;
      default:
        tone(440, 0.04, { type: "square", gain: 0.05 });
    }
  }

  function setMuted(value) {
    muted = !!value;
    try {
      localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    } catch (error) {
      // Storage may be unavailable; mute still applies for this session.
    }
    if (master && context) {
      master.gain.value = muted ? 0 : 0.32;
    }
    return muted;
  }

  function isMuted() {
    return muted;
  }

  return {
    unlock: unlock,
    play: play,
    setMuted: setMuted,
    isMuted: isMuted,
    hasAudio: hasAudio
  };
});
