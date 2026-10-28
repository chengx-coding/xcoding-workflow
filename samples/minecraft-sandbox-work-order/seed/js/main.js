(function () {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const status = document.getElementById("status");
  const hud = document.getElementById("hud");
  const config = window.SandboxConfig;
  const worldApi = window.SandboxWorld;
  const playerApi = window.SandboxPlayer;
  const renderApi = window.SandboxRender;
  const camera = { x: 0, y: 0 };

  function setStatus(state, text) {
    status.dataset.state = state;
    status.title = text;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function updateCamera(world, player) {
    const worldPixelWidth = world.width * config.tileSize;
    const worldPixelHeight = world.height * config.tileSize;
    camera.x = clamp(player.x * config.tileSize - config.viewWidth / 2, 0, worldPixelWidth - config.viewWidth);
    camera.y = clamp(player.y * config.tileSize - config.viewHeight / 2, 0, worldPixelHeight - config.viewHeight);
  }

  window.addEventListener("error", function (event) {
    setStatus("error", event.message || "runtime error");
  });
  window.addEventListener("unhandledrejection", function (event) {
    setStatus("error", String(event.reason));
  });

  try {
    const world = worldApi.createWorld(config.seed);
    const spawnX = Math.floor(world.width / 2);
    const spawnY = Math.floor(world.height * 0.65) - 1;
    const player = playerApi.createPlayer(spawnX, spawnY);

    updateCamera(world, player);
    renderApi.renderFrame(ctx, { world: world, player: player, camera: camera });

    const firstSlot = document.querySelector("#hotbar .slot");
    if (firstSlot) {
      firstSlot.classList.add("is-selected");
    }

    hud.textContent = "Skeleton: movement, mining, building and saving are not implemented yet.";
    setStatus("ready", "ready");
    window.__sandbox = { world: world, player: player, camera: camera, ready: true };

    function frame() {
      renderApi.renderFrame(ctx, { world: world, player: player, camera: camera });
      window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  } catch (error) {
    setStatus("error", error && error.message ? error.message : String(error));
    throw error;
  }
})();
