(function () {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const scene = params.get("scene");
  if (!scene) {
    return;
  }

  const WORLD = window.SandboxWorld;
  const CONFIG = window.SandboxConfig;
  const B = CONFIG.blocks;

  function whenReady(callback) {
    if (window.__cubewood && window.__cubewood.ready) {
      callback(window.__cubewood);
      return;
    }
    window.setTimeout(function () { whenReady(callback); }, 40);
  }

  function clearToasts() {
    const toasts = document.getElementById("toasts");
    if (toasts) {
      toasts.innerHTML = "";
    }
  }

  function findFlat(world, span) {
    const heights = [];
    for (let x = 0; x < world.width; x += 1) {
      heights.push(WORLD.terrainHeightAt(world, x));
    }
    for (let x = 14; x < world.width - span - 4; x += 1) {
      let min = heights[x];
      let max = heights[x];
      for (let offset = 1; offset <= span; offset += 1) {
        min = Math.min(min, heights[x + offset]);
        max = Math.max(max, heights[x + offset]);
      }
      if (max - min <= 1 && min > 32 && min < 64) {
        return { x: x, ground: min };
      }
    }
    return { x: Math.floor(world.width / 2) - 3, ground: heights[Math.floor(world.width / 2)] };
  }

  function buildHut(api, originX, groundY) {
    const entries = [];
    const width = 7;
    for (let offset = 0; offset < width; offset += 1) {
      entries.push({ x: originX + offset, y: groundY - 1, id: B.planks });
    }
    for (let height = 2; height <= 4; height += 1) {
      entries.push({ x: originX, y: groundY - height, id: B.planks });
      entries.push({ x: originX + width - 1, y: groundY - height, id: B.planks });
    }
    for (let offset = 1; offset < width - 1; offset += 1) {
      entries.push({ x: originX + offset, y: groundY - 5, id: offset === 3 ? B.glass : B.planks });
    }
    entries.push({ x: originX + 2, y: groundY - 2, id: B.torch });
    entries.push({ x: originX + 4, y: groundY - 2, id: B.torch });
    entries.push({ x: originX + 3, y: groundY - 3, id: B.glass });
    api.commands.bulkSet(entries);
    return entries;
  }

  function findStand(world, centerX) {
    for (let radius = 2; radius < 14; radius += 1) {
      for (let direction = -1; direction <= 1; direction += 2) {
        const x = centerX + radius * direction;
        if (x < 2 || x >= world.width - 2) {
          continue;
        }
        const top = world.surface && world.surface[x] !== undefined ? world.surface[x] : WORLD.terrainHeightAt(world, x);
        if (top < 6 || top >= world.height - 4) {
          continue;
        }
        let clear = true;
        for (let dy = 1; dy <= 4; dy += 1) {
          if (WORLD.isSolid(world, x, top - dy)) {
            clear = false;
            break;
          }
          if (WORLD.getBlock(world, x, top - dy) !== B.air) {
            clear = false;
            break;
          }
        }
        if (clear) {
          return { x: x + 0.5, y: top };
        }
      }
    }
    return { x: centerX + 0.5, y: world.surface ? world.surface[centerX] : WORLD.terrainHeightAt(world, centerX) };
  }

  function findCave(world) {
    for (let y = 58; y < world.height - 6; y += 1) {
      for (let x = 40; x < world.width - 40; x += 1) {
        const here = WORLD.getBlock(world, x, y);
        const below = WORLD.getBlock(world, x, y + 1);
        const above = WORLD.getBlock(world, x, y - 1);
        if (here === B.air && above === B.air && below !== B.air && below !== B.air) {
          if (WORLD.isSolid(world, x, y + 1)) {
            return { x: x, y: y + 1 };
          }
        }
      }
    }
    return { x: Math.floor(world.width / 2), y: Math.floor(world.height * 0.7) };
  }

  whenReady(function (api) {
    const commands = api.commands;
    const game = api.game;
    commands.hideWelcome();
    api.audio.setMuted(true);
    game.settings.muted = true;
    api.ui.setMuteButton(true);
    const spawn = game.world.spawn || WORLD.findSpawn(game.world);
    const flat = findFlat(game.world, 8);

    switch (scene) {
      case "welcome": {
        commands.setTime(0.22);
        api.ui.setWelcome(true);
        break;
      }
      case "day": {
        commands.setTime(0.22);
        commands.setDay(4);
        buildHut(api, flat.x, flat.ground);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        break;
      }
      case "night": {
        commands.setTime(0.8);
        commands.setDay(4);
        buildHut(api, flat.x, flat.ground);
        commands.bulkSet([
          { x: flat.x + 1, y: flat.ground - 6, id: B.torch },
          { x: flat.x + 5, y: flat.ground - 6, id: B.torch }
        ]);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        break;
      }
      case "backdrop": {
        commands.setTime(0.24);
        buildHut(api, flat.x, flat.ground);
        commands.bulkSet([
          { x: flat.x + 2, y: flat.ground - 3, id: B.air },
          { x: flat.x + 4, y: flat.ground - 1, id: B.stone },
          { x: flat.x + 1, y: flat.ground - 1, id: B.cobblestone }
        ]);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        commands.toggleBackdrop();
        break;
      }
      case "zoom1": {
        commands.setTime(0.2);
        buildHut(api, flat.x, flat.ground);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        commands.setZoom(0.8, "scene");
        break;
      }
      case "zoom2": {
        commands.setTime(0.2);
        buildHut(api, flat.x, flat.ground);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        commands.setZoom(1.8, "scene");
        break;
      }
      case "cave": {
        const cave = findCave(game.world);
        commands.setTime(0.3);
        commands.teleport(cave.x + 0.5, cave.y);
        commands.bulkSet([
          { x: cave.x - 3, y: cave.y - 1, id: B.torch },
          { x: cave.x + 4, y: cave.y - 1, id: B.torch }
        ]);
        break;
      }
      case "inventory": {
        commands.setTime(0.24);
        commands.give(B.wood, 12);
        commands.give(B.planks, 8);
        commands.give(B.cobblestone, 6);
        commands.give(B.torch, 4);
        commands.give(110, 1);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        commands.openPanel("inventory");
        break;
      }
      case "crafting": {
        commands.setTime(0.24);
        commands.give(B.wood, 8);
        commands.give(B.planks, 6);
        commands.give(100, 4);
        commands.give(B.cobblestone, 8);
        commands.give(101, 2);
        const stand = findStand(game.world, flat.x + 3);
        commands.teleport(stand.x, stand.y);
        commands.openPanel("craft");
        break;
      }
      case "guide": {
        commands.setTime(0.24);
        commands.teleport(spawn.x, spawn.y);
        commands.openPanel("guide");
        break;
      }
      case "menu": {
        commands.setTime(0.24);
        commands.teleport(spawn.x, spawn.y);
        commands.openPanel("menu");
        break;
      }
      case "tower": {
        commands.setTime(0.52);
        const baseX = flat.x;
        const ground = flat.ground;
        commands.bulkSet([
          { x: baseX, y: ground - 1, id: B.cobblestone },
          { x: baseX + 1, y: ground - 1, id: B.cobblestone },
          { x: baseX + 2, y: ground - 1, id: B.cobblestone },
          { x: baseX, y: ground - 2, id: B.planks },
          { x: baseX + 2, y: ground - 2, id: B.planks },
          { x: baseX + 1, y: ground - 3, id: B.planks },
          { x: baseX + 1, y: ground - 4, id: B.torch }
        ]);
        commands.teleport(baseX + 1.5, ground);
        break;
      }
      default: {
        commands.setTime(0.25);
        break;
      }
    }

    commands.renderNow();
    clearToasts();
    window.setTimeout(clearToasts, 200);
    window.setTimeout(function () {
      document.documentElement.dataset.scene = scene;
    }, 400);
  });
})();
