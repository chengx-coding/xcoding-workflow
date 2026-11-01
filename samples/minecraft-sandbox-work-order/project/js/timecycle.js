(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxTime = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  // A day starts at midnight (t=0) and noon is t=0.5. Colours and light are
  // interpolated between these cyclic keyframes.
  const KEYFRAMES = [
    { t: 0.0, top: [6, 10, 26], bottom: [18, 30, 58], light: 0.3 },
    { t: 0.2, top: [8, 14, 34], bottom: [24, 40, 70], light: 0.32 },
    { t: 0.26, top: [74, 96, 150], bottom: [248, 166, 120], light: 0.55 },
    { t: 0.33, top: [96, 180, 235], bottom: [214, 240, 252], light: 0.95 },
    { t: 0.66, top: [92, 176, 236], bottom: [212, 240, 250], light: 1.0 },
    { t: 0.74, top: [244, 146, 96], bottom: [255, 208, 150], light: 0.62 },
    { t: 0.82, top: [38, 48, 96], bottom: [120, 92, 110], light: 0.42 },
    { t: 0.9, top: [8, 12, 30], bottom: [20, 32, 60], light: 0.3 },
    { t: 1.0, top: [6, 10, 26], bottom: [18, 30, 58], light: 0.3 }
  ];

  function normalize(fraction) {
    const value = Number(fraction);
    if (!Number.isFinite(value)) {
      return 0;
    }
    const wrapped = value - Math.floor(value);
    return wrapped < 0 ? wrapped + 1 : wrapped;
  }

  function createClock(fraction) {
    return { fraction: normalize(fraction === undefined ? CONFIG.time.startFraction : fraction) };
  }

  function advance(clock, seconds, cycleSeconds) {
    const cycle = typeof cycleSeconds === "number" ? cycleSeconds : CONFIG.time.cycleSeconds;
    const delta = Number(seconds);
    if (!Number.isFinite(delta) || cycle <= 0) {
      return clock.fraction;
    }
    clock.fraction = normalize(clock.fraction + delta / cycle);
    return clock.fraction;
  }

  function phaseOf(fraction) {
    const t = normalize(fraction);
    if (t < 0.24) {
      return "night";
    }
    if (t < 0.32) {
      return "dawn";
    }
    if (t < 0.7) {
      return "day";
    }
    if (t < 0.84) {
      return "dusk";
    }
    return "night";
  }

  function sample(fraction) {
    const t = normalize(fraction);
    let index = 0;
    while (index < KEYFRAMES.length - 2 && t > KEYFRAMES[index + 1].t) {
      index += 1;
    }
    const from = KEYFRAMES[index];
    const to = KEYFRAMES[index + 1];
    const span = to.t - from.t;
    const local = span <= 0 ? 0 : (t - from.t) / span;
    function mix(a, b, ratio) {
      return [
        Math.round(a[0] + (b[0] - a[0]) * ratio),
        Math.round(a[1] + (b[1] - a[1]) * ratio),
        Math.round(a[2] + (b[2] - a[2]) * ratio)
      ];
    }
    return {
      top: mix(from.top, to.top, local),
      bottom: mix(from.bottom, to.bottom, local),
      light: from.light + (to.light - from.light) * local
    };
  }

  function css(rgb) {
    return "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
  }

  function sky(fraction) {
    const values = sample(fraction);
    return {
      top: values.top,
      bottom: values.bottom,
      topCss: css(values.top),
      bottomCss: css(values.bottom),
      light: values.light,
      phase: phaseOf(fraction)
    };
  }

  function lightLevel(fraction) {
    return sample(fraction).light;
  }

  function isNight(fraction) {
    return phaseOf(fraction) === "night";
  }

  function clockLabel(fraction) {
    const totalMinutes = Math.floor(normalize(fraction) * 24 * 60) % (24 * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  return {
    createClock: createClock,
    advance: advance,
    normalize: normalize,
    phaseOf: phaseOf,
    sky: sky,
    lightLevel: lightLevel,
    isNight: isNight,
    clockLabel: clockLabel
  };
});
