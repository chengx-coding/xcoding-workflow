(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxDayNight = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const DAY_LENGTH = CONFIG && CONFIG.dayCycleSeconds ? CONFIG.dayCycleSeconds : 240;

  // Palette stops around the cycle. 0 is sunrise, 0.25 noon, 0.5 sunset,
  // 0.75 midnight. Each stop is [skyTop, skyMid, skyBottom, light].
  const STOPS = [
    { at: 0.0, top: [58, 74, 122], mid: [214, 138, 120], bottom: [246, 205, 156], light: 0.45 },
    { at: 0.12, top: [94, 158, 214], mid: [168, 210, 236], bottom: [226, 240, 246], light: 0.8 },
    { at: 0.25, top: [74, 156, 222], mid: [140, 205, 240], bottom: [214, 240, 252], light: 1.0 },
    { at: 0.4, top: [84, 148, 208], mid: [176, 206, 232], bottom: [240, 232, 210], light: 0.9 },
    { at: 0.5, top: [46, 58, 106], mid: [196, 116, 98], bottom: [244, 186, 130], light: 0.55 },
    { at: 0.6, top: [22, 28, 58], mid: [58, 58, 102], bottom: [104, 88, 122], light: 0.24 },
    { at: 0.75, top: [8, 12, 34], mid: [16, 22, 52], bottom: [30, 40, 74], light: 0.12 },
    { at: 0.9, top: [14, 20, 46], mid: [30, 38, 76], bottom: [58, 62, 104], light: 0.18 },
    { at: 1.0, top: [58, 74, 122], mid: [214, 138, 120], bottom: [246, 205, 156], light: 0.45 }
  ];

  function normalizeTime(time) {
    const value = Number(time);
    if (!Number.isFinite(value)) {
      return 0;
    }
    const wrapped = value % 1;
    return wrapped < 0 ? wrapped + 1 : wrapped;
  }

  function advanceTime(time, dt, cycleSeconds) {
    const cycle = Number(cycleSeconds) > 0 ? Number(cycleSeconds) : DAY_LENGTH;
    const step = Number(dt);
    if (!Number.isFinite(step) || step === 0) {
      return normalizeTime(time);
    }
    return normalizeTime(normalizeTime(time) + step / cycle);
  }

  function mix(a, b, t) {
    return a + (b - a) * t;
  }

  function sample(time) {
    const t = normalizeTime(time);
    let left = STOPS[0];
    let right = STOPS[STOPS.length - 1];
    for (let index = 0; index < STOPS.length - 1; index += 1) {
      if (t >= STOPS[index].at && t <= STOPS[index + 1].at) {
        left = STOPS[index];
        right = STOPS[index + 1];
        break;
      }
    }
    const span = right.at - left.at || 1;
    const raw = (t - left.at) / span;
    const ramp = raw * raw * (3 - 2 * raw);
    return {
      top: [0, 1, 2].map(function (channel) {
        return Math.round(mix(left.top[channel], right.top[channel], ramp));
      }),
      mid: [0, 1, 2].map(function (channel) {
        return Math.round(mix(left.mid[channel], right.mid[channel], ramp));
      }),
      bottom: [0, 1, 2].map(function (channel) {
        return Math.round(mix(left.bottom[channel], right.bottom[channel], ramp));
      }),
      light: mix(left.light, right.light, ramp)
    };
  }

  function skyColors(time) {
    const stop = sample(time);
    return {
      top: "rgb(" + stop.top.join(", ") + ")",
      mid: "rgb(" + stop.mid.join(", ") + ")",
      bottom: "rgb(" + stop.bottom.join(", ") + ")",
      light: stop.light
    };
  }

  function daylight(time) {
    return sample(time).light;
  }

  function isNight(time) {
    const t = normalizeTime(time);
    return t >= 0.55 || t < 0.06;
  }

  function phaseOf(time) {
    const t = normalizeTime(time);
    if (t < 0.08) {
      return "dawn";
    }
    if (t < 0.42) {
      return "day";
    }
    if (t < 0.55) {
      return "dusk";
    }
    return "night";
  }

  function labelOf(time) {
    const phase = phaseOf(time);
    if (phase === "dawn") {
      return "Dawn";
    }
    if (phase === "day") {
      return "Day";
    }
    if (phase === "dusk") {
      return "Dusk";
    }
    return "Night";
  }

  // Sun and moon travel across an arc. Returns screen-relative unit positions.
  function celestial(time) {
    const t = normalizeTime(time);
    const sunAngle = (t - 0.25) * Math.PI * 2;
    const moonAngle = sunAngle + Math.PI;
    return {
      sun: { x: 0.5 + Math.cos(sunAngle) * 0.42, y: 0.5 + Math.sin(sunAngle) * 0.42 },
      moon: { x: 0.5 + Math.cos(moonAngle) * 0.4, y: 0.5 + Math.sin(moonAngle) * 0.4 }
    };
  }

  function nightTint(time) {
    const light = daylight(time);
    return Math.min(0.62, Math.max(0, (1 - light) * 0.55));
  }

  return {
    dayLength: DAY_LENGTH,
    normalizeTime: normalizeTime,
    advanceTime: advanceTime,
    skyColors: skyColors,
    daylight: daylight,
    isNight: isNight,
    phaseOf: phaseOf,
    labelOf: labelOf,
    celestial: celestial,
    nightTint: nightTint
  };
});
