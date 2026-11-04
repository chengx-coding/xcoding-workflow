(function () {
  "use strict";

  let context = null;
  let master = null;
  let noiseBuffer = null;
  let muted = false;

  function ensureContext() {
    if (context) {
      if (context.state === "suspended") {
        context.resume();
      }
      return context;
    }
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return null;
    }
    try {
      context = new AudioContextClass();
      master = context.createGain();
      master.gain.value = muted ? 0 : 0.55;
      master.connect(context.destination);
      const length = Math.floor(context.sampleRate * 0.6);
      noiseBuffer = context.createBuffer(1, length, context.sampleRate);
      const data = noiseBuffer.getChannelData(0);
      let last = 0;
      for (let index = 0; index < length; index += 1) {
        const white = Math.random() * 2 - 1;
        last = last * 0.78 + white * 0.22;
        data[index] = last;
      }
      return context;
    } catch (error) {
      context = null;
      return null;
    }
  }

  function setMuted(value) {
    muted = !!value;
    if (master && context) {
      master.gain.setTargetAtTime(muted ? 0 : 0.55, context.currentTime, 0.02);
    }
  }

  function isMuted() {
    return muted;
  }

  function tone(frequency, duration, options) {
    const audio = ensureContext();
    if (!audio || muted) {
      return;
    }
    const settings = options || {};
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = settings.type || "sine";
    oscillator.frequency.setValueAtTime(frequency, audio.currentTime + (settings.delay || 0));
    if (settings.endFrequency) {
      oscillator.frequency.exponentialRampToValueAtTime(
        Math.max(20, settings.endFrequency),
        audio.currentTime + (settings.delay || 0) + duration
      );
    }
    const start = audio.currentTime + (settings.delay || 0);
    const volume = settings.volume === undefined ? 0.16 : settings.volume;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume), start + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain);
    gain.connect(master);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
  }

  function noise(duration, options) {
    const audio = ensureContext();
    if (!audio || muted || !noiseBuffer) {
      return;
    }
    const settings = options || {};
    const source = audio.createBufferSource();
    source.buffer = noiseBuffer;
    const filter = audio.createBiquadFilter();
    filter.type = settings.filter || "bandpass";
    filter.frequency.setValueAtTime(settings.frequency || 900, audio.currentTime + (settings.delay || 0));
    filter.Q.value = settings.q || 0.8;
    const gain = audio.createGain();
    const start = audio.currentTime + (settings.delay || 0);
    const volume = settings.volume === undefined ? 0.12 : settings.volume;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume), start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(master);
    source.start(start);
    source.stop(start + duration + 0.02);
  }

  function play(name, options) {
    if (muted) {
      return;
    }
    const settings = options || {};
    switch (name) {
      case "ui":
        tone(620, 0.06, { type: "square", volume: 0.035 });
        break;
      case "start":
        tone(392, 0.18, { type: "triangle", volume: 0.09 });
        tone(523.25, 0.26, { type: "triangle", volume: 0.08, delay: 0.12 });
        tone(659.25, 0.36, { type: "sine", volume: 0.06, delay: 0.24 });
        break;
      case "jump":
        tone(260, 0.12, { type: "sine", endFrequency: 420, volume: 0.055 });
        break;
      case "step":
        noise(0.055, { filter: "lowpass", frequency: 480, volume: 0.025 });
        break;
      case "mine":
        noise(0.07, { filter: "bandpass", frequency: 1200, q: 1.1, volume: settings.volume || 0.06 });
        tone(settings.pitch || 170, 0.04, { type: "square", volume: 0.02 });
        break;
      case "break":
        noise(0.25, { filter: "lowpass", frequency: 1100, volume: 0.13 });
        tone(settings.pitch || 120, 0.18, { type: "triangle", endFrequency: 55, volume: 0.08 });
        break;
      case "place":
        noise(0.08, { filter: "lowpass", frequency: 650, volume: 0.09 });
        tone(settings.pitch || 150, 0.09, { type: "triangle", endFrequency: 90, volume: 0.06 });
        break;
      case "pickup":
        tone(660, 0.08, { type: "square", volume: 0.035 });
        tone(880, 0.1, { type: "square", volume: 0.03, delay: 0.05 });
        break;
      case "craft":
        tone(523.25, 0.12, { type: "triangle", volume: 0.06 });
        tone(659.25, 0.12, { type: "triangle", volume: 0.055, delay: 0.09 });
        tone(783.99, 0.24, { type: "sine", volume: 0.05, delay: 0.18 });
        break;
      case "hurt":
        tone(190, 0.24, { type: "sawtooth", endFrequency: 70, volume: 0.09 });
        noise(0.15, { filter: "lowpass", frequency: 500, volume: 0.07 });
        break;
      case "death":
        tone(220, 0.4, { type: "triangle", endFrequency: 55, volume: 0.11 });
        tone(164, 0.55, { type: "sine", endFrequency: 40, volume: 0.08, delay: 0.1 });
        break;
      case "torch":
        noise(0.09, { filter: "highpass", frequency: 1500, volume: 0.035 });
        break;
      case "error":
        tone(160, 0.1, { type: "square", volume: 0.045 });
        tone(120, 0.16, { type: "square", volume: 0.035, delay: 0.07 });
        break;
      case "save":
        tone(740, 0.08, { type: "sine", volume: 0.025 });
        tone(988, 0.12, { type: "sine", volume: 0.02, delay: 0.06 });
        break;
      default:
        tone(440, 0.08, { type: "sine", volume: 0.03 });
        break;
    }
  }

  window.SandboxAudio = {
    ensureContext: ensureContext,
    play: play,
    setMuted: setMuted,
    isMuted: isMuted
  };
})();
