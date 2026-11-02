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

  // Block definitions. `tier` is the minimum pickaxe tier needed to harvest a
  // drop; a tier of 0 means the block can always be collected. `drop` is the
  // item id granted when harvested, or null for "breaks but drops nothing".
  const BLOCK_LIST = [
    {
      id: B.air, key: "air", name: "Air", solid: false, hardness: 0, tool: null,
      tier: 0, drop: null, light: 0, replaceable: true,
      colors: { base: "#000000", accent: "#000000", detail: "#000000" }
    },
    {
      id: B.grass, key: "grass", name: "Grass", solid: true, hardness: 0.55, tool: "shovel",
      tier: 0, drop: B.dirt, light: 0, replaceable: false,
      colors: { base: "#67ad45", accent: "#82c95b", detail: "#477f30", side: "#8a6a4a" }
    },
    {
      id: B.dirt, key: "dirt", name: "Dirt", solid: true, hardness: 0.45, tool: "shovel",
      tier: 0, drop: B.dirt, light: 0, replaceable: false,
      colors: { base: "#8a6a4a", accent: "#9c7a56", detail: "#6e533a" }
    },
    {
      id: B.stone, key: "stone", name: "Stone", solid: true, hardness: 1.6, tool: "pickaxe",
      tier: 1, drop: B.cobblestone, light: 0, replaceable: false,
      colors: { base: "#8b9097", accent: "#9ba0a6", detail: "#747a82" }
    },
    {
      id: B.wood, key: "wood", name: "Wood", solid: true, hardness: 1.05, tool: "axe",
      tier: 0, drop: B.wood, light: 0, replaceable: false,
      colors: { base: "#6b4a2b", accent: "#7d5835", detail: "#523720" }
    },
    {
      id: B.leaves, key: "leaves", name: "Leaves", solid: true, hardness: 0.18, tool: null,
      tier: 0, drop: null, light: 0, replaceable: false,
      colors: { base: "#59a244", accent: "#70bb58", detail: "#41792f" }
    },
    {
      id: B.planks, key: "planks", name: "Planks", solid: true, hardness: 0.65, tool: "axe",
      tier: 0, drop: B.planks, light: 0, replaceable: false,
      colors: { base: "#b78b52", accent: "#c79a5e", detail: "#9a7243" }
    },
    {
      id: B.cobblestone, key: "cobblestone", name: "Cobblestone", solid: true, hardness: 1.8, tool: "pickaxe",
      tier: 1, drop: B.cobblestone, light: 0, replaceable: false,
      colors: { base: "#7f848b", accent: "#94999f", detail: "#666b72" }
    },
    {
      id: B.coalOre, key: "coal_ore", name: "Coal ore", solid: true, hardness: 2.1, tool: "pickaxe",
      tier: 1, drop: 101, light: 0, replaceable: false,
      colors: { base: "#83888f", accent: "#2f2f2f", detail: "#5f656c" }
    },
    {
      id: B.ironOre, key: "iron_ore", name: "Iron ore", solid: true, hardness: 2.9, tool: "pickaxe",
      tier: 2, drop: 102, light: 0, replaceable: false,
      colors: { base: "#878c93", accent: "#c9a27a", detail: "#63696f" }
    },
    {
      id: B.sand, key: "sand", name: "Sand", solid: true, hardness: 0.4, tool: "shovel",
      tier: 0, drop: B.sand, light: 0, replaceable: false,
      colors: { base: "#d8c489", accent: "#e6d39a", detail: "#bca76c" }
    },
    {
      id: B.sandstone, key: "sandstone", name: "Sandstone", solid: true, hardness: 1.1, tool: "pickaxe",
      tier: 0, drop: B.sandstone, light: 0, replaceable: false,
      colors: { base: "#ccb77c", accent: "#dbc78b", detail: "#b09a63" }
    },
    {
      id: B.torch, key: "torch", name: "Torch", solid: false, hardness: 0.05, tool: null,
      tier: 0, drop: B.torch, light: 14, replaceable: false, support: true,
      colors: { base: "#6b4a2b", accent: "#ffb347", detail: "#ffe08a" }
    },
    {
      id: B.glass, key: "glass", name: "Glass", solid: true, hardness: 0.35, tool: null,
      tier: 0, drop: null, light: 0, replaceable: false, transparent: true,
      colors: { base: "#bfe8f2", accent: "#e2f7fb", detail: "#8fc9d8" }
    },
    {
      id: B.bedrock, key: "bedrock", name: "Bedrock", solid: true, hardness: Infinity, tool: null,
      tier: 0, drop: null, light: 0, replaceable: false,
      colors: { base: "#3c4148", accent: "#4b5158", detail: "#2d3238" }
    },
    {
      id: B.flower, key: "flower", name: "Flower", solid: false, hardness: 0.06, tool: null,
      tier: 0, drop: B.flower, light: 0, replaceable: true, support: true,
      colors: { base: "#3f7a2c", accent: "#e85d75", detail: "#f2c14e" }
    }
  ];

  const BLOCK_BY_ID = Object.create(null);
  BLOCK_LIST.forEach(function (definition) {
    BLOCK_BY_ID[definition.id] = definition;
  });

  const ITEM_LIST = [
    { id: 100, key: "stick", name: "Stick", kind: "material", color: "#a5763f" },
    { id: 101, key: "coal", name: "Coal", kind: "material", color: "#2f2f2f" },
    { id: 102, key: "iron", name: "Iron", kind: "material", color: "#d8dde3" },
    { id: 110, key: "wooden_pickaxe", name: "Wooden pickaxe", kind: "tool", tool: "pickaxe", tier: 1, speed: 2.2, color: "#a5763f" },
    { id: 111, key: "stone_pickaxe", name: "Stone pickaxe", kind: "tool", tool: "pickaxe", tier: 2, speed: 3.6, color: "#8b9097" },
    { id: 112, key: "iron_pickaxe", name: "Iron pickaxe", kind: "tool", tool: "pickaxe", tier: 3, speed: 5.4, color: "#d8dde3" },
    { id: 120, key: "wooden_axe", name: "Wooden axe", kind: "tool", tool: "axe", tier: 1, speed: 1.9, color: "#a5763f" },
    { id: 121, key: "stone_axe", name: "Stone axe", kind: "tool", tool: "axe", tier: 2, speed: 2.9, color: "#8b9097" },
    { id: 130, key: "wooden_shovel", name: "Wooden shovel", kind: "tool", tool: "shovel", tier: 1, speed: 1.9, color: "#a5763f" },
    { id: 131, key: "stone_shovel", name: "Stone shovel", kind: "tool", tool: "shovel", tier: 2, speed: 2.9, color: "#8b9097" },
    { id: 140, key: "compass", name: "Compass", kind: "material", color: "#d7b45a" }
  ];

  const ITEM_BY_ID = Object.create(null);
  ITEM_LIST.forEach(function (definition) {
    ITEM_BY_ID[definition.id] = definition;
  });

  function blockDefinition(id) {
    return BLOCK_BY_ID[id] || null;
  }

  function itemDefinition(id) {
    if (BLOCK_BY_ID[id]) {
      const block = BLOCK_BY_ID[id];
      return {
        id: block.id,
        key: block.key,
        name: block.name,
        kind: block.id === 0 ? "air" : "block",
        color: block.colors.base,
        block: block
      };
    }
    return ITEM_BY_ID[id] || null;
  }

  function nameOf(id) {
    const item = itemDefinition(id);
    return item ? item.name : "Unknown";
  }

  function isBlockItem(id) {
    return Boolean(BLOCK_BY_ID[id]) && id !== B.air;
  }

  function isSolidId(id) {
    const block = BLOCK_BY_ID[id];
    return Boolean(block) && block.solid;
  }

  function isReplaceable(id) {
    const block = BLOCK_BY_ID[id];
    return Boolean(block) && (block.replaceable || id === B.air);
  }

  function lightOf(id) {
    const block = BLOCK_BY_ID[id];
    return block ? block.light : 0;
  }

  function colorOf(id, tone) {
    const block = BLOCK_BY_ID[id];
    if (!block) {
      return "#ff00ff";
    }
    const colors = block.colors;
    if (tone && colors[tone]) {
      return colors[tone];
    }
    return colors.base;
  }

  function allBlocks() {
    return BLOCK_LIST.slice();
  }

  function allItems() {
    return ITEM_LIST.slice();
  }

  function toolItems() {
    return ITEM_LIST.filter(function (item) {
      return item.kind === "tool";
    });
  }

  return {
    BLOCK_LIST: BLOCK_LIST,
    ITEM_LIST: ITEM_LIST,
    block: blockDefinition,
    item: itemDefinition,
    nameOf: nameOf,
    isBlockItem: isBlockItem,
    isSolid: isSolidId,
    isReplaceable: isReplaceable,
    lightOf: lightOf,
    colorOf: colorOf,
    allBlocks: allBlocks,
    allItems: allItems,
    toolItems: toolItems
  };
});
