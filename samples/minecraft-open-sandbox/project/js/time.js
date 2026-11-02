(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxTime = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxTime");
  }

  // t = 0 is sunrise (06:00), 0.25 noon, 0.5 sunset, 0.75 midnight.
  const SKY_STOPS = [
    { t: 0.0, top: [246, 178, 107], bottom: [255, 230, 192], haze: "#ffd9a0" },
    { t: 0.1, top: [99, 184, 242], bottom: [205, 238, 255], haze: "#e8f7ff" },
    { t: 0.3, top: [74, 168, 238], bottom: [191, 231, 255], haze: "#f0fbff" },
    { t: 0.46, top: [111, 181, 232], bottom: [255, 224, 176], haze: "#ffe6bf" },
    { t: 0.53, top: [201, 106, 74], bottom: [255, 178, 122], haze: "#ffc79b" },
    { t: 0.62, top: [12, 22, 52], bottom: [29, 42, 77], haze: "#2a3b63" },
    { t: 0.85, top: [5, 10, 28], bottom: [18, 28, 51], haze: "#182644" },
    { t: 0.96, top: [109, 90, 140], bottom: [226, 160, 106], haze: "#c9a0a0" }
  ];

  function wrap(t) {
    if (t >= 0 && t < 1) {
      return t;
    }
    return ((t % 1) + 1) % 1;
  }

  function createClock(options) {
    const settings = options || {};
    return {
      t: typeof settings.start === "number" ? wrap(settings.start) : 0.3,
      day: Number.isInteger(settings.day) ? settings.day : 1,
      length: settings.length > 0 ? settings.length : CONFIG.dayLength
    };
  }

  function advance(clock, dt) {
    const beforeDay = clock.day;
    let next = clock.t + (dt / clock.length);
    while (next >= 1) {
      next -= 1;
      clock.day += 1;
    }
    while (next < 0) {
      next += 1;
      clock.day -= 1;
    }
    clock.t = next;
    return { dayAdvanced: clock.day !== beforeDay, phase: phase(clock.t) };
  }

  function phase(t) {
    const value = wrap(t);
    if (value < 0.08 || value >= 0.94) {
      return "dawn";
    }
    if (value < 0.46) {
      return "day";
    }
    if (value < 0.56) {
      return "dusk";
    }
    return "night";
  }

  function daylight(t) {
    const elevation = Math.sin(wrap(t) * Math.PI * 2);
    const normalised = Math.min(Math.max((elevation + 0.12) / 0.55, 0), 1);
    return 0.16 + 0.84 * normalised;
  }

  function formatClock(t) {
    const hours = (wrap(t) * 24 + 6) % 24;
    const wholeHours = Math.floor(hours);
    const minutes = Math.floor((hours - wholeHours) * 60);
    return String(wholeHours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function mixColor(from, to, amount) {
    return [
      Math.round(from[0] + (to[0] - from[0]) * amount),
      Math.round(from[1] + (to[1] - from[1]) * amount),
      Math.round(from[2] + (to[2] - from[2]) * amount)
    ];
  }

  function css(color) {
    return "rgb(" + color[0] + ", " + color[1] + ", " + color[2] + ")";
  }

  function sky(t) {
    const value = wrap(t);
    let from = SKY_STOPS[SKY_STOPS.length - 1];
    let to = SKY_STOPS[0];
    for (let index = 0; index < SKY_STOPS.length; index += 1) {
      const current = SKY_STOPS[index];
      const next = SKY_STOPS[(index + 1) % SKY_STOPS.length];
      const nextT = index === SKY_STOPS.length - 1 ? 1 : next.t;
      if (value >= current.t && value < nextT) {
        from = current;
        to = next;
        break;
      }
    }
    const span = (to.t > from.t ? to.t : to.t + 1) - from.t;
    const amount = span <= 0 ? 0 : (value - from.t) / span;
    return {
      top: css(mixColor(from.top, to.top, amount)),
      bottom: css(mixColor(from.bottom, to.bottom, amount)),
      topRgb: mixColor(from.top, to.top, amount),
      bottomRgb: mixColor(from.bottom, to.bottom, amount),
      haze: from.haze,
      daylight: daylight(value)
    };
  }

  function sunPosition(t) {
    const value = wrap(t);
    const hours = (value * 24 + 6) % 24;
    // Sun rides from x=0 at 06:00 to x=1 at 18:00.
    const sunX = (hours - 6) / 12;
    const sunY = 0.5 - Math.sin((hours - 6) / 12 * Math.PI) * 0.45;
    const moonX = sunX + 0.5 > 1 ? sunX - 0.5 : sunX + 0.5;
    return {
      sun: { x: sunX, y: sunY, visible: hours >= 5.5 && hours <= 18.5 },
      moon: { x: moonX, y: 1 - sunY, visible: hours < 5.5 || hours > 18.5 }
    };
  }

  return {
    SKY_STOPS: SKY_STOPS,
    createClock: createClock,
    advance: advance,
    phase: phase,
    daylight: daylight,
    formatClock: formatClock,
    sky: sky,
    sunPosition: sunPosition
  };
});
