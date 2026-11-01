const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const content = require("../js/content.js");
const inv = require("../js/inventory.js");

function makeState() {
  const inventory = inv.createFreshInventory();
  const progress = inv.createFreshProgress();
  return {
    inventory: inventory.inventory,
    tools: inventory.tools,
    hotbar: inventory.hotbar,
    selectedSlot: inventory.selectedSlot,
    flags: progress.flags,
    stats: progress.stats
  };
}

test("a fresh pack starts with a wooden pickaxe, three torches, and a valid bar", () => {
  const state = makeState();
  assert.equal(state.tools.pickaxe.tier, 1);
  assert.equal(inv.countItem(state, "torch"), 3);
  assert.equal(state.hotbar.length, config.hotbarSlots);
  assert.equal(state.hotbar[state.selectedSlot], "pickaxe");
  assert.equal(inv.getSelectedToolKey(state), "pickaxe");
});

test("handcrafting turns logs into planks, sticks, and a workbench", () => {
  const state = makeState();
  inv.addItem(state, "log", 4);
  assert.equal(inv.craft(state, "planks", false).ok, true);
  assert.equal(inv.countItem(state, "planks"), 4);
  assert.equal(inv.craft(state, "workbench", false).ok, true);
  assert.equal(inv.countItem(state, "workbench"), 1);
  assert.equal(inv.craft(state, "sticks", false).ok, false, "no planks remain after the workbench");
  inv.addItem(state, "planks", 2);
  assert.equal(inv.craft(state, "sticks", false).ok, true);
  assert.equal(inv.countItem(state, "stick"), 4);
});

test("tools require a nearby walkable workbench", () => {
  const state = makeState();
  inv.addItem(state, "stone", 3);
  inv.addItem(state, "stick", 2);
  const blocked = inv.craft(state, "stone_pickaxe", false);
  assert.equal(blocked.ok, false);
  assert.equal(blocked.reason, "station");
  const result = inv.craft(state, "stone_pickaxe", true);
  assert.equal(result.ok, true);
  assert.equal(state.tools.pickaxe.tier, 2);
  assert.equal(state.tools.pickaxe.durability, content.getToolInfo("pickaxe", 2).durability);
  assert.equal(inv.countItem(state, "stone"), 0);
  assert.equal(inv.countItem(state, "stick"), 0);
});

test("owned tools cannot be downgraded or crafted twice", () => {
  const state = makeState();
  inv.addItem(state, "planks", 3);
  inv.addItem(state, "stick", 2);
  const existing = inv.craft(state, "wood_pickaxe", true);
  assert.equal(existing.ok, false);
  assert.equal(existing.reason, "owned");

  state.tools.pickaxe = { tier: 3, durability: 400 };
  const higher = inv.canCraft(state, "stone_pickaxe", true);
  assert.equal(higher.ok, false);
  assert.equal(higher.reason, "owned");
});

test("mining rules enforce tools, tiers, and speed bonuses", () => {
  const state = makeState();
  assert.equal(inv.getBreakInfo(state, config.block.STONE, "torch").reason, "tool");
  assert.equal(inv.getBreakInfo(state, config.block.IRON_ORE, "pickaxe").reason, "tier");
  assert.equal(inv.getBreakInfo(state, config.block.LOG, "pickaxe").ok, true);
  const stone = inv.getBreakInfo(state, config.block.STONE, "pickaxe");
  assert.equal(stone.ok, true);
  assert.equal(stone.effective, true);
  assert.ok(stone.duration < 1);

  const woodAxe = makeState();
  woodAxe.tools.axe = { tier: 1, durability: 65 };
  const log = inv.getBreakInfo(woodAxe, config.block.LOG, "axe");
  assert.equal(log.effective, true);
  assert.ok(log.duration < inv.getBreakInfo(woodAxe, config.block.LOG, "pickaxe").duration);

  state.tools.pickaxe = { tier: 3, durability: 400 };
  assert.equal(inv.getBreakInfo(state, config.block.GEM_ORE, "pickaxe").ok, true);
});

test("tools lose durability and vanish from the hotbar when broken", () => {
  const state = makeState();
  const first = inv.useTool(state, "pickaxe", 69);
  assert.equal(first.broken, false);
  assert.equal(state.tools.pickaxe.durability, 1);
  const second = inv.useTool(state, "pickaxe", 1);
  assert.equal(second.broken, true);
  assert.equal(state.tools.pickaxe, null);
  assert.equal(state.hotbar.indexOf("pickaxe"), -1);
});

test("depleting a block stack clears its empty hotbar slot", () => {
  const state = makeState();
  inv.addItem(state, "stone", 2);
  inv.selectSlot(state, state.hotbar.indexOf("stone"));
  assert.equal(inv.getSelectedKey(state), "stone");
  inv.removeItem(state, "stone", 1);
  assert.equal(inv.getSelectedKey(state), "stone");
  inv.removeItem(state, "stone", 1);
  assert.equal(inv.countItem(state, "stone"), 0);
  assert.equal(state.hotbar.indexOf("stone"), -1);
  assert.equal(inv.getSelectedToolKey(state), null);
});

test("hotbar binding only accepts owned tools and available blocks", () => {
  const state = makeState();
  inv.selectSlot(state, 4);
  const material = inv.bindItemToSlot(state, "coal");
  assert.equal(material.ok, false);
  const pickaxe = inv.bindItemToSlot(state, "pickaxe");
  assert.equal(pickaxe.ok, true);
  assert.equal(state.selectedSlot, 0);
  inv.addItem(state, "stone", 2);
  const stoneSlot = state.hotbar.indexOf("stone");
  assert.ok(stoneSlot > 0);
  inv.selectSlot(state, 6);
  const stone = inv.bindItemToSlot(state, "stone");
  assert.equal(stone.ok, true);
  assert.equal(stone.existing, true);
  assert.equal(state.selectedSlot, stoneSlot);
  assert.equal(state.hotbar[stoneSlot], "stone");
});

test("sanitizing a damaged save keeps only legal items, tools, and slots", () => {
  const state = inv.sanitizeInventoryState({
    inventory: { torch: 2, coal: -4, invalid: 99, stone: 2.7 },
    tools: {
      pickaxe: { tier: 2, durability: 9999 },
      axe: { tier: 9, durability: 10 },
      sword: { tier: 1, durability: 0 }
    },
    hotbar: ["axe", "torch", "stone", "torch", "nope", "pickaxe", null, null, null],
    selectedSlot: 30
  });
  assert.equal(state.inventory.torch, 2);
  assert.equal(state.inventory.coal, undefined);
  assert.equal(state.inventory.invalid, undefined);
  assert.equal(state.inventory.stone, 2);
  assert.equal(state.tools.pickaxe.tier, 2);
  assert.equal(state.tools.pickaxe.durability, content.getToolInfo("pickaxe", 2).durability);
  assert.equal(state.tools.axe, null);
  assert.equal(state.tools.sword, null);
  assert.equal(state.hotbar.filter(Boolean).length, 3);
  assert.equal(state.selectedSlot, 8);
});

test("every recipe and quest step references real content", () => {
  const recipeIds = new Set();
  content.RECIPES.forEach((recipe) => {
    assert.ok(!recipeIds.has(recipe.id), "duplicate recipe id " + recipe.id);
    recipeIds.add(recipe.id);
    Object.keys(recipe.costs).forEach((item) => assert.ok(content.ITEMS[item], "missing cost item " + item));
    if (recipe.output.kind === "item") {
      assert.ok(content.ITEMS[recipe.output.item], "missing output item " + recipe.output.item);
    } else {
      assert.ok(content.getToolInfo(recipe.output.tool, recipe.output.tier), "missing tool output");
    }
  });
  content.QUEST_STEPS.forEach((step) => {
    assert.ok(step.id && step.title && step.hint);
    if (step.type === "flag") {
      assert.ok(step.flag);
    }
    if (step.type === "stat") {
      assert.ok(step.stat && step.target > 0);
    }
  });
});

test("quest progress completes and the stone pickaxe step remains earned", () => {
  const state = makeState();
  const info = inv.getQuestInfo(state);
  assert.equal(info.index, 0);
  assert.equal(info.allDone, false);

  state.stats.logsGathered = 4;
  state.flags.workbenchCrafted = true;
  state.flags.workbenchPlaced = true;
  state.flags.stonePickaxeCrafted = true;
  state.stats.stoneMined = 8;
  state.stats.coalFound = 3;
  state.stats.ironFound = 3;
  state.flags.lanternCrafted = true;
  state.flags.lanternPlaced = true;
  const done = inv.getQuestInfo(state);
  assert.equal(done.allDone, true);
  assert.equal(done.doneCount, content.QUEST_STEPS.length);
  assert.equal(done.currentStep, null);

  // Breaking the tool does not erase the earned stone-pickaxe step.
  state.tools.pickaxe = null;
  assert.equal(inv.getQuestInfo(state).allDone, true);

  // The ore objective reports both resource counters.
  state.stats.coalFound = 2;
  state.flags.lanternPlaced = false;
  const partial = inv.getQuestInfo(state);
  assert.equal(partial.currentStep.id, "find_ores");
  assert.deepEqual(partial.progress.parts.map((part) => [part.label, part.current]), [["coal", 2], ["iron", 3]]);
});

test("attack and tool display information follows the selected item", () => {
  const state = makeState();
  assert.equal(inv.getAttackInfo(state).damage, content.getToolInfo("pickaxe", 1).damage);
  state.tools.sword = { tier: 3, durability: 450 };
  inv.addItem(state, "planks", 1);
  const slot = state.hotbar.indexOf(null);
  state.hotbar[slot] = "sword";
  state.selectedSlot = slot;
  const attack = inv.getAttackInfo(state);
  assert.equal(attack.damage, content.getToolInfo("sword", 3).damage);
  assert.equal(inv.getItemDisplayName(state, "sword"), "Iron Sword");
});
