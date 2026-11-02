(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxBlocks = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxBlocks");
  }

  const B = CONFIG.blocks;
  const I = CONFIG.items;

  // hardness is seconds with a matching tier-0 tool; tier is the minimum
  // pickaxe tier required to break the block at all.
  const DEFS = Object.freeze({
    [B.grass]: {
      key: "grass",
      name: "Grass",
      solid: true,
      hardness: 0.24,
      tier: 0,
      drop: B.grass,
      palette: { base: "#57a05a", light: "#7fc47a", dark: "#3d7a41", accent: "#8d6e63" }
    },
    [B.dirt]: {
      key: "dirt",
      name: "Dirt",
      solid: true,
      hardness: 0.24,
      tier: 0,
      drop: B.dirt,
      palette: { base: "#8d6e63", light: "#a98474", dark: "#6a5148", accent: "#5b4339" }
    },
    [B.stone]: {
      key: "stone",
      name: "Stone",
      solid: true,
      hardness: 1.05,
      tier: 1,
      drop: B.cobble,
      palette: { base: "#7c8894", light: "#9aa6b1", dark: "#5c6771", accent: "#4c565f" }
    },
    [B.wood]: {
      key: "wood",
      name: "Oak Log",
      solid: true,
      hardness: 0.55,
      tier: 0,
      drop: B.wood,
      palette: { base: "#8a6239", light: "#a87c4b", dark: "#6a4a2a", accent: "#5a3d22" }
    },
    [B.leaves]: {
      key: "leaves",
      name: "Leaves",
      solid: true,
      hardness: 0.18,
      tier: 0,
      drop: B.leaves,
      palette: { base: "#3f8a46", light: "#61ad5f", dark: "#2e6a35", accent: "#7ec46b" }
    },
    [B.sand]: {
      key: "sand",
      name: "Sand",
      solid: true,
      hardness: 0.2,
      tier: 0,
      drop: B.sand,
      palette: { base: "#d8c68f", light: "#e8d9a9", dark: "#b9a470", accent: "#c9b47a" }
    },
    [B.planks]: {
      key: "planks",
      name: "Oak Planks",
      solid: true,
      hardness: 0.4,
      tier: 0,
      drop: B.planks,
      palette: { base: "#b98a52", light: "#d0a166", dark: "#94693b", accent: "#7d5730" }
    },
    [B.cobble]: {
      key: "cobble",
      name: "Cobblestone",
      solid: true,
      hardness: 1.0,
      tier: 1,
      drop: B.cobble,
      palette: { base: "#79838d", light: "#97a1aa", dark: "#5b646d", accent: "#4a535b" }
    },
    [B.coal_ore]: {
      key: "coal_ore",
      name: "Coal Ore",
      solid: true,
      hardness: 1.3,
      tier: 1,
      drop: I.coal,
      palette: { base: "#7c8894", light: "#2c3138", dark: "#5c6771", accent: "#1d2125" }
    },
    [B.iron_ore]: {
      key: "iron_ore",
      name: "Iron Ore",
      solid: true,
      hardness: 1.7,
      tier: 2,
      drop: B.iron_ore,
      palette: { base: "#7c8894", light: "#d6a887", dark: "#5c6771", accent: "#b07a55" }
    },
    [B.ember_ore]: {
      key: "ember_ore",
      name: "Ember Ore",
      solid: true,
      hardness: 2.4,
      tier: 3,
      drop: B.ember_ore,
      palette: { base: "#5b6170", light: "#ff8a4c", dark: "#3f4450", accent: "#ffcf6b" }
    },
    [B.torch]: {
      key: "torch",
      name: "Torch",
      solid: false,
      hardness: 0.1,
      tier: 0,
      drop: B.torch,
      light: 14,
      needsSupport: true,
      palette: { base: "#7a4a22", light: "#ffd27a", dark: "#4d3016", accent: "#ffe9a8" }
    },
    [B.workbench]: {
      key: "workbench",
      name: "Workbench",
      solid: true,
      hardness: 0.7,
      tier: 0,
      station: "workbench",
      drop: B.workbench,
      palette: { base: "#a97a45", light: "#c99a5f", dark: "#815c33", accent: "#5e4224" }
    },
    [B.furnace]: {
      key: "furnace",
      name: "Furnace",
      solid: true,
      hardness: 1.4,
      tier: 1,
      station: "furnace",
      drop: B.furnace,
      palette: { base: "#6e767f", light: "#8f99a3", dark: "#4d545b", accent: "#ff9c4a" }
    },
    [B.stone_bricks]: {
      key: "stone_bricks",
      name: "Stone Bricks",
      solid: true,
      hardness: 1.2,
      tier: 1,
      drop: B.stone_bricks,
      palette: { base: "#8a949e", light: "#a9b3bc", dark: "#6a747d", accent: "#59626b" }
    },
    [B.beacon]: {
      key: "beacon",
      name: "Ember Beacon",
      solid: true,
      hardness: 1.0,
      tier: 0,
      light: 15,
      drop: B.beacon,
      palette: { base: "#4a3f5c", light: "#ff9b45", dark: "#2f283c", accent: "#ffe08a" }
    }
  });

  const ITEM_DEFS = Object.freeze({
    [I.stick]: { key: "stick", name: "Stick", kind: "item" },
    [I.coal]: { key: "coal", name: "Coal", kind: "item", fuel: true },
    [I.iron_ingot]: { key: "iron_ingot", name: "Iron Ingot", kind: "item" },
    [I.ember_shard]: { key: "ember_shard", name: "Ember Shard", kind: "item", glow: true },
    [I.pick_wood]: { key: "pick_wood", name: "Wooden Pickaxe", kind: "tool", tool: { type: "pickaxe", tier: 1 } },
    [I.pick_stone]: { key: "pick_stone", name: "Stone Pickaxe", kind: "tool", tool: { type: "pickaxe", tier: 2 } },
    [I.pick_iron]: { key: "pick_iron", name: "Iron Pickaxe", kind: "tool", tool: { type: "pickaxe", tier: 3 } },
    [I.sword_wood]: { key: "sword_wood", name: "Wooden Sword", kind: "tool", tool: { type: "sword", tier: 1, damage: 2 } },
    [I.sword_stone]: { key: "sword_stone", name: "Stone Sword", kind: "tool", tool: { type: "sword", tier: 2, damage: 3 } },
    [I.sword_iron]: { key: "sword_iron", name: "Iron Sword", kind: "tool", tool: { type: "sword", tier: 3, damage: 4 } }
  });

  const TIER_NAMES = Object.freeze({ 0: "hand", 1: "wooden pickaxe", 2: "stone pickaxe", 3: "iron pickaxe" });
  const TIER_SPEED = Object.freeze({ 0: 1, 1: 2.4, 2: 3.6 });

  function isBlockId(id) {
    return Object.prototype.hasOwnProperty.call(DEFS, id);
  }

  function get(id) {
    return isBlockId(id) ? DEFS[id] : null;
  }

  function isAir(id) {
    return id === B.air;
  }

  function isSolid(id) {
    const def = get(id);
    return !!(def && def.solid);
  }

  function isPlaceable(id) {
    return isBlockId(id) && id !== B.air;
  }

  function requiredTier(id) {
    const def = get(id);
    return def ? def.tier : 0;
  }

  function hardnessOf(id) {
    const def = get(id);
    return def ? def.hardness : 0;
  }

  function dropOf(id) {
    const def = get(id);
    if (!def) {
      return null;
    }
    return Object.prototype.hasOwnProperty.call(def, "drop") ? def.drop : id;
  }

  function lightOf(id) {
    const def = get(id);
    return def && def.light ? def.light : 0;
  }

  function stationOf(id) {
    const def = get(id);
    return def && def.station ? def.station : "";
  }

  function needsSupport(id) {
    const def = get(id);
    return !!(def && def.needsSupport);
  }

  function breakTime(id, pickTier) {
    const def = get(id);
    if (!def) {
      return null;
    }
    const tier = Math.max(0, Math.min(3, Number(pickTier) || 0));
    if (tier < def.tier) {
      return null;
    }
    const factor = TIER_SPEED[Math.min(3, tier - def.tier)] || 1;
    return def.hardness / factor;
  }

  function itemName(id) {
    const block = get(id);
    if (block) {
      return block.name;
    }
    const item = ITEM_DEFS[id];
    return item ? item.name : "Unknown";
  }

  function itemDef(id) {
    const block = get(id);
    if (block) {
      return { key: block.key, name: block.name, kind: "block", blockId: id };
    }
    return ITEM_DEFS[id] || null;
  }

  function toolOf(id) {
    const item = ITEM_DEFS[id];
    return item && item.tool ? item.tool : null;
  }

  function isTool(id) {
    return !!toolOf(id);
  }

  function toolTier(id) {
    const tool = toolOf(id);
    return tool ? tool.tier : 0;
  }

  function swordDamage(id) {
    const tool = toolOf(id);
    return tool && tool.type === "sword" ? tool.damage || 1 : 0;
  }

  function bestPickTier(slots) {
    let best = 0;
    for (let index = 0; index < slots.length; index += 1) {
      const stack = slots[index];
      if (!stack || !stack.count) {
        continue;
      }
      const tool = toolOf(stack.id);
      if (tool && tool.type === "pickaxe") {
        best = Math.max(best, tool.tier);
      }
    }
    return best;
  }

  function bestSwordDamage(slots) {
    let best = 0;
    for (let index = 0; index < slots.length; index += 1) {
      const stack = slots[index];
      if (!stack || !stack.count) {
        continue;
      }
      best = Math.max(best, swordDamage(stack.id));
    }
    return best;
  }

  function tierName(tier) {
    return TIER_NAMES[Math.max(0, Math.min(3, Number(tier) || 0))];
  }

  return {
    DEFS: DEFS,
    ITEM_DEFS: ITEM_DEFS,
    TIER_NAMES: TIER_NAMES,
    get: get,
    isBlockId: isBlockId,
    isAir: isAir,
    isSolid: isSolid,
    isPlaceable: isPlaceable,
    requiredTier: requiredTier,
    hardnessOf: hardnessOf,
    dropOf: dropOf,
    lightOf: lightOf,
    stationOf: stationOf,
    needsSupport: needsSupport,
    breakTime: breakTime,
    itemName: itemName,
    itemDef: itemDef,
    toolOf: toolOf,
    isTool: isTool,
    toolTier: toolTier,
    swordDamage: swordDamage,
    bestPickTier: bestPickTier,
    bestSwordDamage: bestSwordDamage,
    tierName: tierName
  };
});
