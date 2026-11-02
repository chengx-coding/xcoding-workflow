const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const blocks = require("../js/blocks.js");

const B = config.blocks;
const I = config.items;

test("block registry describes the buildable world", () => {
  const ids = Object.keys(B).filter((key) => key !== "air");
  assert.ok(ids.length >= 14);
  for (const key of ids) {
    const def = blocks.get(B[key]);
    assert.ok(def, `missing definition for ${key}`);
    assert.equal(def.key, key);
    assert.equal(typeof def.hardness, "number");
    assert.equal(typeof def.solid, "boolean");
  }
  assert.equal(blocks.isSolid(B.air), false);
  assert.equal(blocks.isSolid(B.stone), true);
  assert.equal(blocks.isSolid(B.torch), false);
});

test("tool tiers gate the mineable blocks", () => {
  assert.equal(blocks.breakTime(B.stone, 0), null);
  assert.equal(blocks.breakTime(B.stone, 1) > 0, true);
  assert.equal(blocks.breakTime(B.iron_ore, 1), null);
  assert.equal(blocks.breakTime(B.iron_ore, 2) > 0, true);
  assert.equal(blocks.breakTime(B.ember_ore, 2), null);
  assert.equal(blocks.breakTime(B.ember_ore, 3) > 0, true);
  assert.equal(blocks.breakTime(B.dirt, 0) > 0, true);
  assert.equal(blocks.requiredTier(B.ember_ore), 3);
});

test("better tools mine the same block faster", () => {
  const wooden = blocks.breakTime(B.stone, 1);
  const stone = blocks.breakTime(B.stone, 2);
  const iron = blocks.breakTime(B.stone, 3);
  assert.ok(wooden > stone);
  assert.ok(stone > iron);
  assert.ok(blocks.breakTime(B.stone, 3) > 0.1);
});

test("drops follow the material chain", () => {
  assert.equal(blocks.dropOf(B.stone), B.cobble);
  assert.equal(blocks.dropOf(B.coal_ore), I.coal);
  assert.equal(blocks.dropOf(B.iron_ore), B.iron_ore);
  assert.equal(blocks.dropOf(B.ember_ore), B.ember_ore);
  assert.equal(blocks.dropOf(B.leaves), B.leaves);
  assert.equal(blocks.dropOf(B.air), null);
});

test("light and stations are declared on the right blocks", () => {
  assert.equal(blocks.lightOf(B.torch), 14);
  assert.equal(blocks.lightOf(B.beacon), 15);
  assert.equal(blocks.lightOf(B.stone), 0);
  assert.equal(blocks.stationOf(B.workbench), "workbench");
  assert.equal(blocks.stationOf(B.furnace), "furnace");
  assert.equal(blocks.stationOf(B.stone), "");
  assert.equal(blocks.needsSupport(B.torch), true);
});

test("tools expose their type and tier", () => {
  assert.deepEqual(blocks.toolOf(I.pick_wood), { type: "pickaxe", tier: 1 });
  assert.equal(blocks.toolTier(I.pick_iron), 3);
  assert.equal(blocks.swordDamage(I.sword_stone), 3);
  assert.equal(blocks.swordDamage(I.pick_stone), 0);
  assert.equal(blocks.isTool(I.stick), false);
});

test("inventory tool lookup finds the best pickaxe and sword", () => {
  const slots = [
    null,
    { id: I.pick_wood, count: 1 },
    { id: I.stick, count: 12 },
    { id: I.pick_iron, count: 1 },
    { id: I.sword_wood, count: 1 }
  ];
  assert.equal(blocks.bestPickTier(slots), 3);
  assert.equal(blocks.bestSwordDamage(slots), 2);
  assert.equal(blocks.bestPickTier([null]), 0);
});

test("item names resolve for blocks and items", () => {
  assert.equal(blocks.itemName(B.coal_ore), "Coal Ore");
  assert.equal(blocks.itemName(I.iron_ingot), "Iron Ingot");
  assert.equal(blocks.itemName(9999), "Unknown");
  assert.equal(blocks.itemDef(I.coal).kind, "item");
  assert.equal(blocks.itemDef(B.stone).kind, "block");
  assert.equal(blocks.itemDef(B.stone).blockId, B.stone);
});
