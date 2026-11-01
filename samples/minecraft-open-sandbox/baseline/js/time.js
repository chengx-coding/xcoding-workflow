(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.MosswildTime = factory(root.MosswildConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const TAU = Math.PI * 2;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function smoothstep(edge0, edge1, value) {
    const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  }

  function getDayInfo(totalTime, daySeconds) {
    const cycle = Math.max(1, Number(daySeconds) || CONFIG.daySeconds);
    const safeTime = Number.isFinite(totalTime) ? Math.max(0, totalTime) : 0;
    const elapsedDays = safeTime / cycle;
    const fraction = elapsedDays - Math.floor(elapsedDays);
    const hoursFloat = (6 + fraction * 24) % 24;
    const hours = Math.floor(hoursFloat);
    const minutes = Math.floor((hoursFloat - hours) * 60);
    const sunHeight = Math.sin(fraction * TAU);
    const daylight = smoothstep(-0.055, 0.22, sunHeight);
    const twilight = clamp(1 - Math.abs(sunHeight) / 0.34, 0, 1) * (1 - daylight * 0.35);

    let phase = "Night";
    if (fraction < 0.035) {
      phase = "Dawn";
    } else if (fraction < 0.2) {
      phase = "Morning";
    } else if (fraction < 0.34) {
      phase = "Midday";
    } else if (fraction < 0.46) {
      phase = "Afternoon";
    } else if (fraction < 0.55) {
      phase = "Dusk";
    } else if (fraction < 0.8) {
      phase = "Night";
    } else {
      phase = "Deep night";
    }

    return {
      totalTime: safeTime,
      fraction,
      hoursFloat,
      hours,
      minutes,
      clock: String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0"),
      day: Math.floor(elapsedDays) + 1,
      sunHeight,
      daylight,
      twilight,
      isNight: daylight < 0.26,
      sunProgress: fraction < 0.5 ? fraction / 0.5 : null,
      moonProgress: fraction >= 0.5 ? (fraction - 0.5) / 0.5 : null,
      phase
    };
  }

  function formatClock(hours, minutes) {
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  return {
    getDayInfo,
    formatClock
  };
});
