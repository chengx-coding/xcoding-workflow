/* Lightweight tick-based particle system for break/place/damage feedback. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxParticles = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const PALETTE = {
    1: ["#5c8f3b", "#7a5230", "#8b6038"],
    2: ["#7a5230", "#5c3b21", "#8b6038"],
    3: ["#6f7378", "#4c5055", "#82878d"],
    4: ["#6d4a2a", "#54371e", "#895f37"],
    5: ["#2e6b31", "#3d8a3d", "#245827"],
    6: ["#d8c27b", "#b39a55", "#e7d492"],
    8: ["#6f7378", "#1c1c1e", "#3a3a3e"],
    9: ["#6f7378", "#b98255", "#e2b183"],
    10: ["#b07a43", "#7a4b27", "#c58f55"],
    11: ["#b07a43", "#5d3a1e", "#d1a35e"],
    12: ["#6f7378", "#f2a33b", "#ffd166"],
    14: ["#c4e2f0", "#9fc4d6", "#ffffff"]
  };

  function createParticleSystem(options) {
    const settings = options || {};
    let reducedMotion = Boolean(settings.reducedMotion);
    const list = [];

    function add(x, y, color, size, speed) {
      list.push({
        x: x,
        y: y,
        vx: (Math.random() - 0.5) * (speed || 5),
        vy: -1.5 - Math.random() * 3,
        life: 0.4 + Math.random() * 0.35,
        maxLife: 0.75,
        color: color,
        size: size || (2 + Math.floor(Math.random() * 2))
      });
    }

    function spawnBlock(x, y, block, count) {
      const colors = PALETTE[block] || ["#9e9e9e", "#666666"];
      const total = reducedMotion ? 3 : (count || 9);
      for (let i = 0; i < total; i += 1) {
        add(x + 0.15 + Math.random() * 0.7, y + 0.15 + Math.random() * 0.7, colors[i % colors.length]);
      }
    }

    function spawnDamage(x, y, color) {
      const total = reducedMotion ? 2 : 6;
      for (let i = 0; i < total; i += 1) {
        add(x + (Math.random() - 0.5) * 0.5, y + (Math.random() - 0.5) * 0.5, color || "#e05b5b", 2, 4);
      }
    }

    function spawnSoft(x, y, color, count) {
      const total = reducedMotion ? 2 : (count || 5);
      for (let i = 0; i < total; i += 1) {
        add(x + (Math.random() - 0.5) * 0.8, y + (Math.random() - 0.5) * 0.8, color || "#f7d05a", 2, 2.5);
      }
    }

    function update(dt) {
      for (let i = list.length - 1; i >= 0; i -= 1) {
        const particle = list[i];
        particle.life -= dt;
        if (particle.life <= 0) {
          list.splice(i, 1);
          continue;
        }
        particle.vy += 18 * dt;
        particle.x += particle.vx * dt;
        particle.y += particle.vy * dt;
      }
    }

    function clear() {
      list.length = 0;
    }

    function setReducedMotion(value) {
      reducedMotion = Boolean(value);
      if (reducedMotion && list.length > 16) {
        list.length = 16;
      }
    }

    return {
      list: list,
      spawnBlock: spawnBlock,
      spawnDamage: spawnDamage,
      spawnSoft: spawnSoft,
      update: update,
      clear: clear,
      setReducedMotion: setReducedMotion,
      isReducedMotion: function () { return reducedMotion; }
    };
  }

  return {
    palette: PALETTE,
    createParticleSystem: createParticleSystem
  };
});
