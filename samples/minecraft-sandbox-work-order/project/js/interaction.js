(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./player.js"));
  } else {
    root.SandboxInteraction = factory(root.SandboxConfig, root.SandboxPlayer);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, PLAYER) {
  "use strict";

  const AIR = CONFIG.blocks.air;

  function createInventory(hotbar, stock) {
    const blocks = hotbar || CONFIG.hotbar;
    const counts = {};
    blocks.forEach(function (block) {
      counts[block] = 0;
    });
    const starter = stock || CONFIG.starterStock;
    Object.keys(starter).forEach(function (key) {
      counts[key] = starter[key];
    });
    return { counts: counts, selected: 0 };
  }

  function cloneInventory(inventory) {
    return {
      counts: Object.assign({}, inventory.counts),
      selected: inventory.selected
    };
  }

  function countOf(inventory, block) {
    return inventory.counts[block] || 0;
  }

  function addBlock(inventory, block, amount) {
    if (!block) {
      return 0;
    }
    const step = Number(amount) || 1;
    const current = countOf(inventory, block);
    const next = Math.min(CONFIG.maxStack, current + step);
    inventory.counts[block] = next;
    return next;
  }

  function spendBlock(inventory, block, amount) {
    const step = Number(amount) || 1;
    const current = countOf(inventory, block);
    if (current < step) {
      return false;
    }
    inventory.counts[block] = current - step;
    return true;
  }

  function normalizeSlot(index, length) {
    const size = Number(length) || CONFIG.hotbar.length;
    if (!Number.isFinite(Number(index))) {
      return 0;
    }
    const value = Math.trunc(Number(index)) % size;
    return value < 0 ? value + size : value;
  }

  function selectSlot(inventory, index, length) {
    inventory.selected = normalizeSlot(index, length);
    return inventory.selected;
  }

  function cycleSlot(inventory, delta, length) {
    const size = Number(length) || CONFIG.hotbar.length;
    return selectSlot(inventory, inventory.selected + (Number(delta) || 0), size);
  }

  function selectByNumber(inventory, digit, length) {
    const size = Number(length) || CONFIG.hotbar.length;
    const number = Number(digit);
    if (!Number.isInteger(number) || number < 1 || number > size) {
      return { ok: false, selected: inventory.selected };
    }
    return { ok: true, selected: selectSlot(inventory, number - 1, size) };
  }

  function selectedBlock(inventory, hotbar) {
    const blocks = hotbar || CONFIG.hotbar;
    return blocks[normalizeSlot(inventory.selected, blocks.length)];
  }

  function hotbarModel(inventory, hotbar, names) {
    const blocks = hotbar || CONFIG.hotbar;
    const labels = names || CONFIG.blockNames;
    return blocks.map(function (block, index) {
      return {
        index: index,
        digit: index + 1,
        block: block,
        name: labels[block] || "Block",
        count: countOf(inventory, block),
        selected: normalizeSlot(inventory.selected, blocks.length) === index
      };
    });
  }

  function targetCell(camera, screenX, screenY, tile) {
    const size = Number(tile) || CONFIG.tileSize;
    return {
      x: Math.floor((Number(screenX) + camera.x) / size),
      y: Math.floor((Number(screenY) + camera.y) / size)
    };
  }

  function playerCentre(player) {
    return { x: player.x, y: player.y - player.height / 2 };
  }

  function inReach(player, cellX, cellY, reach) {
    const centre = playerCentre(player);
    const limit = Number(reach) || CONFIG.reach;
    const distance = Math.hypot(cellX + 0.5 - centre.x, cellY + 0.5 - centre.y);
    return distance <= limit;
  }

  function insideBounds(world, x, y) {
    return x >= 0 && y >= 0 && x < world.width && y < world.height;
  }

  function isAdjacentToSolid(world, x, y) {
    const neighbours = [
      [x - 1, y],
      [x + 1, y],
      [x, y - 1],
      [x, y + 1]
    ];
    return neighbours.some(function (pair) {
      return insideBounds(world, pair[0], pair[1]) && world.data[pair[1] * world.width + pair[0]] !== AIR;
    });
  }

  function canMine(world, player, cellX, cellY, reach) {
    if (!insideBounds(world, cellX, cellY)) {
      return { ok: false, reason: "bounds" };
    }
    if (world.data[cellY * world.width + cellX] === AIR) {
      return { ok: false, reason: "empty" };
    }
    if (!inReach(player, cellX, cellY, reach)) {
      return { ok: false, reason: "reach" };
    }
    return { ok: true, reason: "" };
  }

  function mineBlock(world, player, inventory, cellX, cellY, reach) {
    const check = canMine(world, player, cellX, cellY, reach);
    if (!check.ok) {
      return { ok: false, reason: check.reason, block: AIR };
    }
    const block = world.data[cellY * world.width + cellX];
    world.data[cellY * world.width + cellX] = AIR;
    addBlock(inventory, block, 1);
    return { ok: true, reason: "", block: block };
  }

  // Placement target: an empty cell next to the hovered block, preferring the
  // neighbour closest to the player so building feels directional.
  function placementTarget(world, player, hoveredX, hoveredY) {
    if (!insideBounds(world, hoveredX, hoveredY)) {
      return null;
    }
    if (world.data[hoveredY * world.width + hoveredX] === AIR) {
      return { x: hoveredX, y: hoveredY };
    }
    const centre = playerCentre(player);
    const options = [
      [hoveredX - 1, hoveredY],
      [hoveredX + 1, hoveredY],
      [hoveredX, hoveredY - 1],
      [hoveredX, hoveredY + 1]
    ]
      .filter(function (pair) {
        return (
          insideBounds(world, pair[0], pair[1]) &&
          world.data[pair[1] * world.width + pair[0]] === AIR
        );
      })
      .map(function (pair) {
        return {
          x: pair[0],
          y: pair[1],
          distance: Math.hypot(pair[0] + 0.5 - centre.x, pair[1] + 0.5 - centre.y)
        };
      })
      .sort(function (left, right) {
        return left.distance - right.distance;
      });
    return options.length > 0 ? { x: options[0].x, y: options[0].y } : null;
  }

  function canPlace(world, player, inventory, cellX, cellY, reach) {
    if (!insideBounds(world, cellX, cellY)) {
      return { ok: false, reason: "bounds" };
    }
    if (world.data[cellY * world.width + cellX] !== AIR) {
      return { ok: false, reason: "occupied" };
    }
    if (!inReach(player, cellX, cellY, reach)) {
      return { ok: false, reason: "reach" };
    }
    if (!isAdjacentToSolid(world, cellX, cellY)) {
      return { ok: false, reason: "floating" };
    }
    if (PLAYER && PLAYER.overlapsCell && PLAYER.overlapsCell(player, cellX, cellY)) {
      return { ok: false, reason: "player" };
    }
    const block = selectedBlock(inventory);
    if (countOf(inventory, block) <= 0) {
      return { ok: false, reason: "stock" };
    }
    return { ok: true, reason: "" };
  }

  function placeBlock(world, player, inventory, cellX, cellY, reach) {
    const check = canPlace(world, player, inventory, cellX, cellY, reach);
    if (!check.ok) {
      return { ok: false, reason: check.reason, block: AIR };
    }
    const block = selectedBlock(inventory);
    spendBlock(inventory, block, 1);
    world.data[cellY * world.width + cellX] = block;
    return { ok: true, reason: "", block: block };
  }

  function blockHardness(block) {
    const value = CONFIG.hardness[block];
    return Number.isFinite(value) && value > 0 ? value : 0.5;
  }

  function createMiningState() {
    return { cell: null, progress: 0 };
  }

  // Advance a hold-to-mine action. Changing the target resets progress so every
  // block needs its own continuous hold.
  function advanceMining(state, cell, block, dt) {
    const sameCell =
      state.cell && cell && state.cell.x === cell.x && state.cell.y === cell.y;
    if (!sameCell) {
      state.cell = cell ? { x: cell.x, y: cell.y } : null;
      state.progress = 0;
    }
    if (!state.cell) {
      return { progress: 0, done: false };
    }
    const hardness = blockHardness(block);
    const step = Math.max(0, Number(dt) || 0);
    state.progress = Math.min(1, state.progress + step / hardness);
    return { progress: state.progress, done: state.progress >= 1 };
  }

  function miningProgress(state, cell) {
    if (!state.cell || !cell || state.cell.x !== cell.x || state.cell.y !== cell.y) {
      return 0;
    }
    return state.progress;
  }

  return {
    createInventory: createInventory,
    cloneInventory: cloneInventory,
    countOf: countOf,
    addBlock: addBlock,
    spendBlock: spendBlock,
    normalizeSlot: normalizeSlot,
    selectSlot: selectSlot,
    cycleSlot: cycleSlot,
    selectByNumber: selectByNumber,
    selectedBlock: selectedBlock,
    hotbarModel: hotbarModel,
    targetCell: targetCell,
    inReach: inReach,
    canMine: canMine,
    mineBlock: mineBlock,
    placementTarget: placementTarget,
    canPlace: canPlace,
    placeBlock: placeBlock,
    blockHardness: blockHardness,
    createMiningState: createMiningState,
    advanceMining: advanceMining,
    miningProgress: miningProgress
  };
});
