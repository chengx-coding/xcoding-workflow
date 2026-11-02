const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const worldApi = require("../js/world.js");
const inventory = require("../js/inventory.js");
const physics = require("../js/physics.js");
const placement = require("../js/placement.js");

const B = config.blocks;
const GROUND = Math.floor(config.worldHeight * 0.65);

function setup() {
  const world = worldApi.createWorld(config.seed);
  const bag = inventory.createInventory();
  const player = physics.createPlayer(10.5, GROUND);
  player.onGround = true;
  return { world: world, bag: bag, player: player };
}

test("placing requires a selected block item", () => {
  const ctx = setup();
  const check = placement.evaluate(ctx.world, ctx.player, ctx.bag, 11, GROUND - 1);
  assert.equal(check.ok, false);
  assert.equal(check.reason, "empty-hand");
});

test("a selected block can be placed next to solid ground", () => {
  const ctx = setup();
  inventory.add(ctx.bag, B.dirt, 2);
  inventory.select(ctx.bag, 0);
  const result = placement.place(ctx.world, ctx.player, ctx.bag, 11, GROUND - 1);
  assert.equal(result.ok, true);
  assert.equal(worldApi.getBlock(ctx.world, 11, GROUND - 1), B.dirt);
  assert.equal(inventory.count(ctx.bag, B.dirt), 1);
});

test("placement rejects out-of-reach, occupied and player-overlapping tiles", () => {
  const ctx = setup();
  inventory.add(ctx.bag, B.dirt, 5);
  assert.equal(placement.evaluate(ctx.world, ctx.player, ctx.bag, 60, GROUND - 1).reason, "out-of-reach");
  assert.equal(placement.evaluate(ctx.world, ctx.player, ctx.bag, 10, GROUND).reason, "occupied");
  const inside = placement.evaluate(ctx.world, ctx.player, ctx.bag, 10, GROUND - 1);
  assert.equal(inside.reason, "blocked-by-player");
});

test("floating blocks are rejected without support", () => {
  const ctx = setup();
  inventory.add(ctx.bag, B.dirt, 2);
  const check = placement.evaluate(ctx.world, ctx.player, ctx.bag, 12, GROUND - 4);
  assert.equal(check.ok, false);
  assert.equal(check.reason, "no-support");
});

test("torches need a supporting neighbour", () => {
  const ctx = setup();
  inventory.add(ctx.bag, B.torch, 2);
  const floating = placement.evaluate(ctx.world, ctx.player, ctx.bag, 12, GROUND - 3);
  assert.equal(floating.reason, "no-support");
  const onGround = placement.evaluate(ctx.world, ctx.player, ctx.bag, 11, GROUND - 1);
  assert.equal(onGround.ok, true);
  assert.equal(onGround.block, B.torch);
});

test("placing consumes the block and cancels reach for far tiles", () => {
  const ctx = setup();
  inventory.add(ctx.bag, B.planks, 1);
  const placed = placement.place(ctx.world, ctx.player, ctx.bag, 11, GROUND - 1);
  assert.equal(placed.ok, true);
  assert.equal(inventory.count(ctx.bag, B.planks), 0);
  const empty = placement.evaluate(ctx.world, ctx.player, ctx.bag, 11, GROUND - 2);
  assert.equal(empty.reason, "empty-hand");
});
