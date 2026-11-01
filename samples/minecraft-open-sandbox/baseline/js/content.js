(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.MosswildContent = factory(root.MosswildConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const B = CONFIG.block;

  const BLOCKS = Object.freeze({
    [B.AIR]: Object.freeze({
      id: B.AIR,
      key: "air",
      name: "Air",
      solid: false,
      unbreakable: true
    }),
    [B.GRASS]: Object.freeze({
      id: B.GRASS,
      key: "grass",
      name: "Grass Block",
      solid: true,
      hardness: 0.42,
      preferredTool: null,
      particle: ["#6f9f46", "#7b5536"],
      sound: "dirt",
      drops: [{ item: "dirt", min: 1, max: 1 }]
    }),
    [B.DIRT]: Object.freeze({
      id: B.DIRT,
      key: "dirt",
      name: "Dirt",
      solid: true,
      hardness: 0.38,
      preferredTool: null,
      particle: ["#8b6644", "#6f4f34"],
      sound: "dirt",
      drops: [{ item: "dirt", min: 1, max: 1 }]
    }),
    [B.STONE]: Object.freeze({
      id: B.STONE,
      key: "stone",
      name: "Stone",
      solid: true,
      hardness: 1.15,
      preferredTool: "pickaxe",
      requiresTool: true,
      minTier: 1,
      particle: ["#8a9095", "#676e74"],
      sound: "stone",
      drops: [{ item: "stone", min: 1, max: 1 }]
    }),
    [B.COAL_ORE]: Object.freeze({
      id: B.COAL_ORE,
      key: "coal_ore",
      name: "Coal Vein",
      solid: true,
      hardness: 1.35,
      preferredTool: "pickaxe",
      requiresTool: true,
      minTier: 1,
      particle: ["#2d3034", "#8a9095"],
      sound: "stone",
      drops: [{ item: "coal", min: 1, max: 2 }]
    }),
    [B.IRON_ORE]: Object.freeze({
      id: B.IRON_ORE,
      key: "iron_ore",
      name: "Iron Vein",
      solid: true,
      hardness: 1.6,
      preferredTool: "pickaxe",
      requiresTool: true,
      minTier: 2,
      particle: ["#c79265", "#8a9095"],
      sound: "stone",
      drops: [{ item: "iron", min: 1, max: 2 }]
    }),
    [B.GEM_ORE]: Object.freeze({
      id: B.GEM_ORE,
      key: "gem_ore",
      name: "Amberstone Vein",
      solid: true,
      hardness: 1.95,
      preferredTool: "pickaxe",
      requiresTool: true,
      minTier: 3,
      particle: ["#52d6b0", "#8a9095"],
      sound: "stone",
      drops: [{ item: "gem", min: 1, max: 1 }]
    }),
    [B.LOG]: Object.freeze({
      id: B.LOG,
      key: "log",
      name: "Oak Log",
      solid: true,
      hardness: 0.82,
      preferredTool: "axe",
      particle: ["#8b623d", "#5f432a"],
      sound: "wood",
      drops: [{ item: "log", min: 1, max: 1 }]
    }),
    [B.LEAVES]: Object.freeze({
      id: B.LEAVES,
      key: "leaves",
      name: "Oak Leaves",
      solid: true,
      hardness: 0.24,
      preferredTool: "axe",
      particle: ["#4e8146", "#355e37"],
      sound: "leaves",
      drops: [{ item: "leaves", min: 1, max: 1 }]
    }),
    [B.PLANKS]: Object.freeze({
      id: B.PLANKS,
      key: "planks",
      name: "Oak Planks",
      solid: true,
      hardness: 0.62,
      preferredTool: "axe",
      particle: ["#b08554", "#8b633b"],
      sound: "wood",
      drops: [{ item: "planks", min: 1, max: 1 }]
    }),
    [B.BRICK]: Object.freeze({
      id: B.BRICK,
      key: "brick",
      name: "Stone Bricks",
      solid: true,
      hardness: 1.25,
      preferredTool: "pickaxe",
      requiresTool: true,
      minTier: 1,
      particle: ["#8d918f", "#6f7472"],
      sound: "stone",
      drops: [{ item: "brick", min: 1, max: 1 }]
    }),
    [B.WORKBENCH]: Object.freeze({
      id: B.WORKBENCH,
      key: "workbench",
      name: "Workbench",
      solid: true,
      hardness: 0.68,
      preferredTool: "axe",
      particle: ["#ad8251", "#6d4d2f", "#c4c0a2"],
      sound: "wood",
      drops: [{ item: "workbench", min: 1, max: 1 }]
    }),
    [B.TORCH]: Object.freeze({
      id: B.TORCH,
      key: "torch",
      name: "Torch",
      solid: false,
      hardness: 0.08,
      preferredTool: null,
      requiresSupport: true,
      light: 5.5,
      particle: ["#f3bb57", "#7a5331"],
      sound: "soft",
      drops: [{ item: "torch", min: 1, max: 1 }]
    }),
    [B.LANTERN]: Object.freeze({
      id: B.LANTERN,
      key: "lantern",
      name: "Warden's Lantern",
      solid: false,
      hardness: 0.3,
      preferredTool: null,
      requiresSupport: true,
      light: 9,
      particle: ["#ffd47b", "#8a6434"],
      sound: "soft",
      drops: [{ item: "lantern", min: 1, max: 1 }]
    }),
    [B.CAMPFIRE]: Object.freeze({
      id: B.CAMPFIRE,
      key: "campfire",
      name: "Campfire",
      solid: false,
      hardness: 0.36,
      preferredTool: "axe",
      requiresSupport: true,
      light: 6.5,
      particle: ["#f08d3f", "#5d432c"],
      sound: "wood",
      drops: [{ item: "campfire", min: 1, max: 1 }]
    }),
    [B.BEDROCK]: Object.freeze({
      id: B.BEDROCK,
      key: "bedrock",
      name: "Bedrock",
      solid: true,
      unbreakable: true,
      particle: ["#303338", "#22252a"],
      sound: "stone",
      drops: []
    })
  });

  const ITEMS = Object.freeze({
    dirt: { name: "Dirt", kind: "block", block: B.DIRT, blurb: "Soft earth. Good for scaffolding and garden walls." },
    stone: { name: "Stone", kind: "block", block: B.STONE, blurb: "A dependable building block." },
    log: { name: "Oak Log", kind: "block", block: B.LOG, blurb: "Rough bark and pale heartwood." },
    leaves: { name: "Oak Leaves", kind: "block", block: B.LEAVES, blurb: "A rustling little block of canopy." },
    planks: { name: "Oak Planks", kind: "block", block: B.PLANKS, blurb: "Warm, tidy boards made from one log." },
    brick: { name: "Stone Bricks", kind: "block", block: B.BRICK, blurb: "Cut stone for walls that mean to stay." },
    workbench: { name: "Workbench", kind: "block", block: B.WORKBENCH, blurb: "Place it nearby to unlock tool recipes." },
    torch: { name: "Torch", kind: "block", block: B.TORCH, blurb: "A small flame. Place it on a wall or floor." },
    lantern: { name: "Warden's Lantern", kind: "block", block: B.LANTERN, blurb: "The old light of the valley. Place it to finish your field notes." },
    campfire: { name: "Campfire", kind: "block", block: B.CAMPFIRE, blurb: "A warm glow and a place to rest your eyes." },
    stick: { name: "Stick", kind: "material", blurb: "The bones of most good tools." },
    coal: { name: "Coal", kind: "material", blurb: "Black, bright, and useful for torches." },
    iron: { name: "Iron Shard", kind: "material", blurb: "Raw iron, bright at the edges. Needs a stone pickaxe." },
    gem: { name: "Amberstone", kind: "material", blurb: "A rare green gleam from the deep. A keepsake of brave digging." }
  });

  const TOOL_TYPES = Object.freeze({
    pickaxe: Object.freeze({
      name: "Pickaxe",
      verb: "break stone",
      description: "Fast on stone and ore. Required for rock."
    }),
    axe: Object.freeze({
      name: "Axe",
      verb: "chop wood",
      description: "Fast on logs, planks, and workbenches."
    }),
    sword: Object.freeze({
      name: "Sword",
      verb: "fight",
      description: "The quickest way to answer a hollow."
    })
  });

  const TOOL_TIERS = Object.freeze({
    pickaxe: Object.freeze({
      1: Object.freeze({ name: "Wooden Pickaxe", tier: 1, material: "Wood", durability: 70, speed: 2, damage: 1.4, color: "#ad7b4c" }),
      2: Object.freeze({ name: "Stone Pickaxe", tier: 2, material: "Stone", durability: 180, speed: 3.2, damage: 2, color: "#8d969a" }),
      3: Object.freeze({ name: "Iron Pickaxe", tier: 3, material: "Iron", durability: 400, speed: 4.5, damage: 2.8, color: "#d9dfdd" })
    }),
    axe: Object.freeze({
      1: Object.freeze({ name: "Wooden Axe", tier: 1, material: "Wood", durability: 65, speed: 1.9, damage: 1.8, color: "#ad7b4c" }),
      2: Object.freeze({ name: "Stone Axe", tier: 2, material: "Stone", durability: 180, speed: 3.1, damage: 2.6, color: "#8d969a" }),
      3: Object.freeze({ name: "Iron Axe", tier: 3, material: "Iron", durability: 400, speed: 4.3, damage: 3.6, color: "#d9dfdd" })
    }),
    sword: Object.freeze({
      1: Object.freeze({ name: "Wooden Sword", tier: 1, material: "Wood", durability: 75, speed: 1, damage: 2, color: "#ad7b4c" }),
      2: Object.freeze({ name: "Stone Sword", tier: 2, material: "Stone", durability: 200, speed: 1, damage: 3.2, color: "#8d969a" }),
      3: Object.freeze({ name: "Iron Sword", tier: 3, material: "Iron", durability: 450, speed: 1, damage: 4.8, color: "#d9dfdd" })
    })
  });

  const TIER_NAMES = Object.freeze({ 1: "Wooden", 2: "Stone", 3: "Iron" });

  const RECIPES = Object.freeze([
    Object.freeze({
      id: "planks",
      name: "Oak Planks",
      output: { kind: "item", item: "planks", count: 4 },
      costs: { log: 1 },
      station: null,
      blurb: "Split one log into four tidy boards."
    }),
    Object.freeze({
      id: "sticks",
      name: "Sticks",
      output: { kind: "item", item: "stick", count: 4 },
      costs: { planks: 2 },
      station: null,
      blurb: "Four handles, ready for work."
    }),
    Object.freeze({
      id: "workbench",
      name: "Workbench",
      output: { kind: "item", item: "workbench", count: 1 },
      costs: { planks: 4 },
      station: null,
      blurb: "Place this in the world to unlock the tool bench."
    }),
    Object.freeze({
      id: "torch",
      name: "Torches",
      output: { kind: "item", item: "torch", count: 4 },
      costs: { stick: 1, coal: 1 },
      station: null,
      blurb: "One coal and one stick make four small lights."
    }),
    Object.freeze({
      id: "wood_pickaxe",
      name: "Wooden Pickaxe",
      output: { kind: "tool", tool: "pickaxe", tier: 1 },
      costs: { planks: 3, stick: 2 },
      station: "workbench",
      blurb: "A humble start for cracking stone."
    }),
    Object.freeze({
      id: "wood_axe",
      name: "Wooden Axe",
      output: { kind: "tool", tool: "axe", tier: 1 },
      costs: { planks: 3, stick: 2 },
      station: "workbench",
      blurb: "Chop logs with far less huffing."
    }),
    Object.freeze({
      id: "wood_sword",
      name: "Wooden Sword",
      output: { kind: "tool", tool: "sword", tier: 1 },
      costs: { planks: 2, stick: 1 },
      station: "workbench",
      blurb: "A little courage, carved to a point."
    }),
    Object.freeze({
      id: "stone_pickaxe",
      name: "Stone Pickaxe",
      output: { kind: "tool", tool: "pickaxe", tier: 2 },
      costs: { stone: 3, stick: 2 },
      station: "workbench",
      blurb: "Strong enough to bite into iron veins."
    }),
    Object.freeze({
      id: "stone_axe",
      name: "Stone Axe",
      output: { kind: "tool", tool: "axe", tier: 2 },
      costs: { stone: 3, stick: 2 },
      station: "workbench",
      blurb: "A heavier head, a cleaner cut."
    }),
    Object.freeze({
      id: "stone_sword",
      name: "Stone Sword",
      output: { kind: "tool", tool: "sword", tier: 2 },
      costs: { stone: 2, stick: 1 },
      station: "workbench",
      blurb: "A dependable edge for the dark."
    }),
    Object.freeze({
      id: "iron_pickaxe",
      name: "Iron Pickaxe",
      output: { kind: "tool", tool: "pickaxe", tier: 3 },
      costs: { iron: 3, stick: 2 },
      station: "workbench",
      blurb: "Cuts deep stone and amberstone."
    }),
    Object.freeze({
      id: "iron_axe",
      name: "Iron Axe",
      output: { kind: "tool", tool: "axe", tier: 3 },
      costs: { iron: 3, stick: 2 },
      station: "workbench",
      blurb: "For the ambitious woodcutter."
    }),
    Object.freeze({
      id: "iron_sword",
      name: "Iron Sword",
      output: { kind: "tool", tool: "sword", tier: 3 },
      costs: { iron: 2, stick: 1 },
      station: "workbench",
      blurb: "A bright answer to the hollows."
    }),
    Object.freeze({
      id: "stone_bricks",
      name: "Stone Bricks",
      output: { kind: "item", item: "brick", count: 4 },
      costs: { stone: 4 },
      station: "workbench",
      blurb: "Four blocks become four fitted bricks."
    }),
    Object.freeze({
      id: "campfire",
      name: "Campfire",
      output: { kind: "item", item: "campfire", count: 1 },
      costs: { log: 3, stone: 4 },
      station: "workbench",
      blurb: "A generous circle of light and smoke."
    }),
    Object.freeze({
      id: "lantern",
      name: "Warden's Lantern",
      output: { kind: "item", item: "lantern", count: 1 },
      costs: { iron: 3, coal: 3, torch: 1 },
      station: "workbench",
      blurb: "The old ward. Craft it, then place it in the wild.",
      quest: true
    })
  ]);

  const QUEST_STEPS = Object.freeze([
    Object.freeze({
      id: "gather_logs",
      type: "stat",
      stat: "logsGathered",
      target: 4,
      title: "Gather oak logs",
      hint: "Hold left click on a tree trunk. An axe would speed this up, but hands will do.",
      progressLabel: "logs"
    }),
    Object.freeze({
      id: "craft_workbench",
      type: "flag",
      flag: "workbenchCrafted",
      title: "Craft a workbench",
      hint: "Press E. Turn logs into planks, then shape four planks into a workbench.",
      progressLabel: ""
    }),
    Object.freeze({
      id: "place_workbench",
      type: "flag",
      flag: "workbenchPlaced",
      title: "Place your workbench",
      hint: "Select the workbench on your hotbar, then right-click a patch of ground.",
      progressLabel: ""
    }),
    Object.freeze({
      id: "craft_stone_pickaxe",
      type: "flag",
      flag: "stonePickaxeCrafted",
      title: "Craft a stone pickaxe",
      hint: "Stand near your workbench and open your pack. Stone and sticks become a keener pick.",
      progressLabel: ""
    }),
    Object.freeze({
      id: "mine_stone",
      type: "stat",
      stat: "stoneMined",
      target: 8,
      title: "Mine eight stone",
      hint: "Stone hides beneath grass and dirt. Dig a stairway down and keep a torch handy.",
      progressLabel: "stone"
    }),
    Object.freeze({
      id: "find_ores",
      type: "ores",
      targets: { coal: 3, iron: 3 },
      title: "Find coal and iron",
      hint: "Coal glints in shallow caves. Iron waits deeper and needs a stone pickaxe.",
      progressLabel: "found"
    }),
    Object.freeze({
      id: "craft_lantern",
      type: "flag",
      flag: "lanternCrafted",
      title: "Craft the Warden's Lantern",
      hint: "At a workbench, gather three coal, three iron, and one torch into an old light.",
      progressLabel: ""
    }),
    Object.freeze({
      id: "place_lantern",
      type: "flag",
      flag: "lanternPlaced",
      title: "Kindle the lantern",
      hint: "Choose a spot beneath the sky or in the deep. Right-click to set the lantern down.",
      progressLabel: ""
    })
  ]);

  const STARTING_TOOL_DURABILITY = Object.freeze({ pickaxe: 70, axe: 65, sword: 75 });

  const HOLLOW = Object.freeze({
    health: 7,
    damage: 2,
    speed: 1.55,
    detectRange: 16,
    contactRange: 0.85,
    width: 0.68,
    height: 1.35,
    spawnCap: 5
  });

  const blockToItem = Object.create(null);
  const itemToBlock = Object.create(null);
  for (const idText of Object.keys(BLOCKS)) {
    const def = BLOCKS[idText];
    if (def && ITEMS[def.key] && ITEMS[def.key].kind === "block") {
      blockToItem[def.id] = def.key;
      itemToBlock[def.key] = def.id;
    }
  }

  function getBlockDef(id) {
    return BLOCKS[id] || BLOCKS[B.AIR];
  }

  function getItemDef(key) {
    return ITEMS[key] || null;
  }

  function getToolInfo(tool, tier) {
    const tiers = TOOL_TIERS[tool];
    return tiers ? tiers[tier] || null : null;
  }

  function getToolName(tool, tier) {
    const info = getToolInfo(tool, tier);
    return info ? info.name : TOOL_TYPES[tool] ? TOOL_TYPES[tool].name : "Tool";
  }

  function getRecipe(id) {
    return RECIPES.find(function (recipe) { return recipe.id === id; }) || null;
  }

  function rollDrops(blockId, random) {
    const def = getBlockDef(blockId);
    if (!def.unbreakable) {
      const rolls = [];
      (def.drops || []).forEach(function (drop) {
        if (drop.chance !== undefined && random() > drop.chance) {
          return;
        }
        const min = drop.min || 1;
        const max = drop.max || min;
        const count = min + Math.floor(random() * (max - min + 1));
        if (count > 0) {
          rolls.push({ item: drop.item, count: count });
        }
      });
      return rolls;
    }
    return [];
  }

  return Object.freeze({
    BLOCKS: BLOCKS,
    ITEMS: ITEMS,
    TOOL_TYPES: TOOL_TYPES,
    TOOL_TIERS: TOOL_TIERS,
    TIER_NAMES: TIER_NAMES,
    RECIPES: RECIPES,
    QUEST_STEPS: QUEST_STEPS,
    STARTING_TOOL_DURABILITY: STARTING_TOOL_DURABILITY,
    HOLLOW: HOLLOW,
    blockToItem: Object.freeze(blockToItem),
    itemToBlock: Object.freeze(itemToBlock),
    getBlockDef: getBlockDef,
    getItemDef: getItemDef,
    getToolInfo: getToolInfo,
    getToolName: getToolName,
    getRecipe: getRecipe,
    rollDrops: rollDrops
  });
});
