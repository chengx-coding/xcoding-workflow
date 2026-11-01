(function (root) {
  "use strict";

  let audioContext = null;
  let masterGain = null;
  let noiseBuffer = null;
  let enabled = true;
  let nextAmbient = 0;
  let unlocked = false;

  function makeContext() {
    if (audioContext) {
      return audioContext;
    }
    const Context = root.AudioContext || root.webkitAudioContext;
    if (!Context) {
      return null;
    }
    try {
      audioContext = new Context();
      masterGain = audioContext.createGain();
      masterGain.gain.value = 0.5;
      masterGain.connect(audioContext.destination);
      const length = Math.floor(audioContext.sampleRate * 0.4);
      noiseBuffer = audioContext.createBuffer(1, length, audioContext.sampleRate);
      const data = noiseBuffer.getChannelData(0);
      for (let i = 0; i < length; i += 1) {
        data[i] = Math.random() * 2 - 1;
      }
      nextAmbient = audioContext.currentTime + 7 + Math.random() * 8;
    } catch (error) {
      audioContext = null;
      masterGain = null;
    }
    return audioContext;
  }

  function unlock() {
    const context = makeContext();
    if (!context) {
      return false;
    }
    if (context.state === "suspended") {
      context.resume().catch(function () {});
    }
    unlocked = true;
    return true;
  }

  function canPlay() {
    return enabled && unlocked && audioContext && masterGain && audioContext.state === "running";
  }

  function setEnabled(value) {
    enabled = Boolean(value);
    if (masterGain && audioContext) {
      masterGain.gain.setTargetAtTime(enabled ? 0.5 : 0, audioContext.currentTime, 0.03);
    }
    if (enabled) {
      unlock();
    }
  }

  function tone(frequency, duration, type, volume, options) {
    if (!canPlay()) {
      return;
    }
    const context = audioContext;
    const opts = options || {};
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type || "sine";
    oscillator.frequency.setValueAtTime(frequency, context.currentTime + (opts.delay || 0));
    if (opts.slideTo) {
      oscillator.frequency.exponentialRampToValueAtTime(
        Math.max(30, opts.slideTo),
        context.currentTime + (opts.delay || 0) + duration
      );
    }
    const start = context.currentTime + (opts.delay || 0);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, volume), start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain);
    gain.connect(masterGain);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.03);
  }

  function noise(duration, volume, filterFrequency, options) {
    if (!canPlay() || !noiseBuffer) {
      return;
    }
    const context = audioContext;
    const source = context.createBufferSource();
    source.buffer = noiseBuffer;
    const filter = context.createBiquadFilter();
    filter.type = options && options.highpass ? "highpass" : "lowpass";
    filter.frequency.value = filterFrequency;
    filter.Q.value = options && options.q ? options.q : 0.8;
    const gain = context.createGain();
    const start = context.currentTime + ((options && options.delay) || 0);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(volume, start + 0.006);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(masterGain);
    source.start(start);
    source.stop(start + duration + 0.04);
  }

  function soundForMaterial(kind) {
    if (kind === "stone") {
      return { noiseFreq: 980, tone: 180 };
    }
    if (kind === "wood") {
      return { noiseFreq: 460, tone: 140 };
    }
    if (kind === "leaves") {
      return { noiseFreq: 2100, tone: 280 };
    }
    if (kind === "soft") {
      return { noiseFreq: 1300, tone: 240 };
    }
    return { noiseFreq: 650, tone: 120 };
  }

  function play(name, arg) {
    if (!enabled) {
      return;
    }
    if (!audioContext) {
      return;
    }
    if (audioContext.state !== "running") {
      return;
    }
    switch (name) {
      case "ui":
        tone(540, 0.05, "triangle", 0.028, { slideTo: 430 });
        break;
      case "step":
        noise(0.045, 0.022, 200, {});
        break;
      case "jump":
        tone(290, 0.09, "sine", 0.022, { slideTo: 430 });
        break;
      case "land":
        noise(0.08, 0.04, 180, {});
        break;
      case "mine":
        {
          const material = soundForMaterial(arg || "dirt");
          noise(0.035, 0.03, material.noiseFreq, { highpass: true });
          tone(material.tone, 0.03, "triangle", 0.016, { slideTo: material.tone * 0.7 });
        }
        break;
      case "break":
        {
          const material = soundForMaterial(arg || "dirt");
          noise(0.18, 0.07, material.noiseFreq, {});
          tone(material.tone, 0.14, "triangle", 0.035, { slideTo: material.tone * 0.55 });
        }
        break;
      case "place":
        noise(0.07, 0.055, 420, {});
        tone(180, 0.08, "triangle", 0.025, { slideTo: 120 });
        break;
      case "pickup":
        tone(660, 0.06, "triangle", 0.025);
        tone(920, 0.08, "sine", 0.022, { delay: 0.045 });
        break;
      case "craft":
        tone(392, 0.09, "triangle", 0.035);
        tone(523, 0.1, "triangle", 0.032, { delay: 0.08 });
        tone(659, 0.16, "sine", 0.028, { delay: 0.16 });
        break;
      case "hurt":
        tone(120, 0.22, "sawtooth", 0.045, { slideTo: 62 });
        noise(0.13, 0.035, 250, {});
        break;
      case "swing":
        noise(0.1, 0.02, 1900, { highpass: true });
        break;
      case "hit":
        noise(0.09, 0.055, 500, {});
        tone(130, 0.08, "square", 0.025, { slideTo: 85 });
        break;
      case "hollow":
        tone(220, 0.44, "sine", 0.018, { slideTo: 155 });
        tone(333, 0.34, "triangle", 0.01, { delay: 0.15, slideTo: 277 });
        break;
      case "quest":
        [392, 523, 659, 784].forEach(function (note, index) {
          tone(note, 0.22, "triangle", 0.035, { delay: index * 0.12 });
        });
        break;
      case "lantern":
        [196, 261.6, 329.6, 392].forEach(function (note, index) {
          tone(note, 1.25, "sine", 0.022, { delay: index * 0.05 });
        });
        break;
      case "death":
        [220, 174, 130, 98].forEach(function (note, index) {
          tone(note, 0.5, "triangle", 0.035, { delay: index * 0.18, slideTo: note * 0.8 });
        });
        break;
      case "save":
        tone(480, 0.06, "sine", 0.017);
        tone(720, 0.08, "sine", 0.014, { delay: 0.06 });
        break;
      default:
        break;
    }
  }

  function ambientBird() {
    if (!canPlay()) {
      return;
    }
    const base = 1500 + Math.random() * 900;
    const count = 2 + Math.floor(Math.random() * 3);
    for (let i = 0; i < count; i += 1) {
      tone(base + i * 180, 0.06 + Math.random() * 0.04, "sine", 0.009, {
        delay: i * 0.09,
        slideTo: base * (1.18 + Math.random() * 0.2)
      });
    }
  }

  function ambientCrickets() {
    if (!canPlay()) {
      return;
    }
    const base = 1900 + Math.random() * 900;
    for (let i = 0; i < 3; i += 1) {
      tone(base, 0.035, "triangle", 0.006, { delay: i * 0.09 });
    }
  }

  function update(dayInfo, mode) {
    if (!canPlay() || mode !== "playing") {
      return;
    }
    const now = audioContext.currentTime;
    if (now < nextAmbient) {
      return;
    }
    if (dayInfo.isNight) {
      ambientCrickets();
      nextAmbient = now + 7 + Math.random() * 11;
    } else {
      ambientBird();
      nextAmbient = now + 9 + Math.random() * 14;
    }
  }

  root.MosswildAudio = {
    unlock,
    setEnabled,
    play,
    update,
    get enabled() {
      return enabled;
    }
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
