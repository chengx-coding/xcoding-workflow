(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"));
  } else {
    root.SandboxCrafting = factory(root.SandboxConfig, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS) {
  "use strict";

  if (!CONFIG || !BLOCKS) {
    throw new Error("SandboxConfig and SandboxBlocks are required before SandboxCrafting");
  }

  const B = CONFIG.blocks;
  const I = CONFIG.items;

  const RECIPES = Object.freeze([
    {
      id: "planks",
      name: "Oak Planks",
      output: { id: B.planks, count: 4 },
      inputs: [{ id: B.wood, count: 1 }],
      station: ""
    },
    {
      id: "sticks",
      name: "Sticks",
      output: { id: I.stick, count: 4 },
      inputs: [{ id: B.planks, count: 2 }],
      station: ""
    },
    {
      id: "workbench",
      name: "Workbench",
      output: { id: B.workbench, count: 1 },
      inputs: [{ id: B.planks, count: 4 }],
      station: ""
    },
    {
      id: "torches",
      name: "Torches",
      output: { id: B.torch, count: 4 },
      inputs: [
        { id: I.stick, count: 1 },
        { id: I.coal, count: 1 }
      ],
      station: ""
    },
    {
      id: "wooden_pickaxe",
      name: "Wooden Pickaxe",
      output: { id: I.pick_wood, count: 1 },
      inputs: [
        { id: B.planks, count: 3 },
        { id: I.stick, count: 2 }
      ],
      station: "workbench"
    },
    {
      id: "wooden_sword",
      name: "Wooden Sword",
      output: { id: I.sword_wood, count: 1 },
      inputs: [
        { id: B.planks, count: 2 },
        { id: I.stick, count: 1 }
      ],
      station: "workbench"
    },
    {
      id: "stone_pickaxe",
      name: "Stone Pickaxe",
      output: { id: I.pick_stone, count: 1 },
      inputs: [
        { id: B.cobble, count: 3 },
        { id: I.stick, count: 2 }
      ],
      station: "workbench"
    },
    {
      id: "stone_sword",
      name: "Stone Sword",
      output: { id: I.sword_stone, count: 1 },
      inputs: [
        { id: B.cobble, count: 2 },
        { id: I.stick, count: 1 }
      ],
      station: "workbench"
    },
    {
      id: "furnace",
      name: "Furnace",
      output: { id: B.furnace, count: 1 },
      inputs: [{ id: B.cobble, count: 8 }],
      station: "workbench"
    },
    {
      id: "stone_bricks",
      name: "Stone Bricks",
      output: { id: B.stone_bricks, count: 4 },
      inputs: [{ id: B.cobble, count: 4 }],
      station: "workbench"
    },
    {
      id: "iron_pickaxe",
      name: "Iron Pickaxe",
      output: { id: I.pick_iron, count: 1 },
      inputs: [
        { id: I.iron_ingot, count: 3 },
        { id: I.stick, count: 2 }
      ],
      station: "workbench"
    },
    {
      id: "iron_sword",
      name: "Iron Sword",
      output: { id: I.sword_iron, count: 1 },
      inputs: [
        { id: I.iron_ingot, count: 2 },
        { id: I.stick, count: 1 }
      ],
      station: "workbench"
    },
    {
      id: "iron_ingot",
      name: "Smelt Iron Ingot",
      output: { id: I.iron_ingot, count: 1 },
      inputs: [
        { id: B.iron_ore, count: 1 },
        { id: I.coal, count: 1 }
      ],
      station: "furnace"
    },
    {
      id: "ember_shard",
      name: "Refine Ember Shard",
      output: { id: I.ember_shard, count: 1 },
      inputs: [
        { id: B.ember_ore, count: 1 },
        { id: I.coal, count: 1 }
      ],
      station: "furnace"
    },
    {
      id: "ember_beacon",
      name: "Ember Beacon",
      output: { id: B.beacon, count: 1 },
      inputs: [
        { id: I.ember_shard, count: 3 },
        { id: I.iron_ingot, count: 2 },
        { id: B.stone_bricks, count: 4 }
      ],
      station: "workbench"
    }
  ]);

  const BY_ID = Object.freeze(
    RECIPES.reduce(function build(map, recipe) {
      map[recipe.id] = recipe;
      return map;
    }, {})
  );

  function stationsNear(world, player, radius) {
    const stations = new Set();
    const r = radius || 4;
    const left = Math.floor(player.x - r);
    const right = Math.floor(player.x + r);
    const top = Math.floor(player.y - player.height - r);
    const bottom = Math.floor(player.y + r);
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (x < 0 || y < 0 || x >= world.width || y >= world.height) {
          continue;
        }
        const station = BLOCKS.stationOf(world.data[y * world.width + x]);
        if (station) {
          stations.add(station);
        }
      }
    }
    return stations;
  }

  function availability(recipe, inventory, stations) {
    const station = recipe.station || "";
    const stationOk = !station || (stations && stations.has(station));
    const missing = [];
    for (let i = 0; i < recipe.inputs.length; i += 1) {
      const input = recipe.inputs[i];
      const available = inventoryApiCount(inventory, input.id);
      if (available < input.count) {
        missing.push({ id: input.id, need: input.count, have: available });
      }
    }
    let reason = "";
    if (!stationOk) {
      reason = "station";
    } else if (missing.length > 0) {
      reason = "materials";
    }
    return {
      ok: stationOk && missing.length === 0,
      reason: reason,
      station: station,
      missing: missing
    };
  }

  function inventoryApiCount(inventory, id) {
    let total = 0;
    for (let i = 0; i < inventory.slots.length; i += 1) {
      const stack = inventory.slots[i];
      if (stack && stack.id === id) {
        total += stack.count;
      }
    }
    return total;
  }

  function take(inventory, id, count) {
    let remaining = count;
    for (let i = inventory.slots.length - 1; i >= 0 && remaining > 0; i -= 1) {
      const stack = inventory.slots[i];
      if (!stack || stack.id !== id) {
        continue;
      }
      const taken = Math.min(stack.count, remaining);
      stack.count -= taken;
      remaining -= taken;
      if (stack.count <= 0) {
        inventory.slots[i] = null;
      }
    }
    return remaining === 0;
  }

  function store(inventory, id, count) {
    let remaining = Math.max(0, Math.floor(count));
    const limit = BLOCKS.isTool(id) ? 1 : CONFIG.stackLimit;
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      const stack = inventory.slots[i];
      if (stack && stack.id === id && stack.count < limit) {
        const moved = Math.min(limit - stack.count, remaining);
        stack.count += moved;
        remaining -= moved;
      }
    }
    for (let i = 0; i < inventory.slots.length && remaining > 0; i += 1) {
      if (!inventory.slots[i]) {
        const moved = Math.min(limit, remaining);
        inventory.slots[i] = { id: id, count: moved };
        remaining -= moved;
      }
    }
    return remaining;
  }

  function craft(recipe, inventory, stations) {
    const state = availability(recipe, inventory, stations);
    if (!state.ok) {
      return { ok: false, reason: state.reason, missing: state.missing, station: state.station };
    }
    for (let i = 0; i < recipe.inputs.length; i += 1) {
      const input = recipe.inputs[i];
      if (!take(inventory, input.id, input.count)) {
        return { ok: false, reason: "materials", missing: [], station: state.station };
      }
    }
    const leftover = store(inventory, recipe.output.id, recipe.output.count);
    return {
      ok: true,
      leftover: leftover,
      output: recipe.output,
      station: state.station
    };
  }

  function list() {
    return RECIPES;
  }

  function byId(id) {
    return BY_ID[id] || null;
  }

  return {
    RECIPES: RECIPES,
    stationsNear: stationsNear,
    availability: availability,
    craft: craft,
    list: list,
    byId: byId
  };
});
