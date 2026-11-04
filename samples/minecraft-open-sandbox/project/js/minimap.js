/* Local top-down minimap and day/night orientation label. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./world.js"), require("./render.js"));
  } else {
    root.SandboxMinimap = factory(root.SandboxConfig, root.SandboxWorld, root.SandboxRender);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, WORLD, RENDER) {
  "use strict";

  const COLORS = {
    1: "#4e9b3e", 2: "#7a5230", 3: "#6f7378", 4: "#6d4a2a", 5: "#2e6b31",
    6: "#d8c27b", 7: "#2b6ca6", 8: "#4a4a4e", 9: "#8a6a55", 10: "#b07a43",
    11: "#c58f55", 12: "#777b80", 13: "#ffd166", 14: "#9fc4d6", 15: "#8a5a2f",
    16: "#777b80", 17: "#d94343", 18: "#3d8a3d"
  };

  function createMinimap(container, canvas, compass) {
    const ctx = canvas.getContext("2d");
    const scale = 2;
    let timer = 0;

    function draw(game) {
      if (!game.world || !game.player) {
        return;
      }
      const world = game.world;
      const player = game.player;
      const width = canvas.width;
      const height = canvas.height;
      const columns = Math.floor(width / scale);
      const rows = Math.floor(height / scale);
      const centerX = Math.floor(player.x);
      const centerY = Math.floor(player.y - player.height * 0.5);
      const night = RENDER.nightAmount(game.time);
      const sky = night > 0.5 ? "#101830" : "#8fc8e8";
      const startX = centerX - Math.floor(columns / 2);
      const startY = centerY - Math.floor(rows / 2);
      ctx.clearRect(0, 0, width, height);
      for (let row = 0; row < rows; row += 1) {
        const y = startY + row;
        for (let column = 0; column < columns; column += 1) {
          const x = startX + column;
          let color = sky;
          if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
            color = "#0a0d12";
          } else {
            const block = world.data[y * world.width + x];
            if (block === 0) {
              color = y > (world.surface[x] || 0) ? (night > 0.5 ? "#171310" : "#2a2019") : sky;
            } else {
              color = COLORS[block] || "#9e9e9e";
              if (block === 3 || block === 8 || block === 9) {
                color = "#5f6368";
              }
            }
          }
          ctx.fillStyle = color;
          ctx.fillRect(column * scale, row * scale, scale, scale);
        }
      }
      const playerColumn = Math.floor(width / 2 / scale) * scale;
      const playerRow = Math.floor(height / 2 / scale) * scale;
      ctx.fillStyle = "#7ee0a4";
      ctx.fillRect(playerColumn - 1, playerRow - 1, 4, 4);
      ctx.fillStyle = "#0b1016";
      ctx.fillRect(playerColumn, playerRow, 2, 2);
      if (game.entities && game.entities.list) {
        for (const entity of game.entities.list) {
          const column = Math.round((entity.x - startX) / 1) * scale;
          const row = Math.round((entity.y - entity.height * 0.5 - startY) / 1) * scale;
          if (column < 0 || row < 0 || column >= width || row >= height) {
            continue;
          }
          ctx.fillStyle = entity.hostile ? "#e05b5b" : "#f2c1c1";
          ctx.fillRect(column - 1, row - 1, 3, 3);
        }
      }
      if (compass) {
        compass.textContent = night > 0.5 ? "NIGHT" : "DAY";
      }
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
    }

    function update(game, dt) {
      timer -= dt;
      if (timer > 0) {
        return;
      }
      timer = 0.35;
      draw(game);
    }

    function setVisible(visible) {
      container.style.display = visible ? "block" : "none";
    }

    return { draw: draw, update: update, setVisible: setVisible };
  }

  return { createMinimap: createMinimap, colors: COLORS };
});
