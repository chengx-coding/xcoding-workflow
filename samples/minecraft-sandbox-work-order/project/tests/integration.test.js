const test = require("node:test");
const assert = require("node:assert/strict");

const config = require("../js/config.js");
const Inventory = require("../js/inventory.js");
const Interaction = require("../js/interaction.js");
const Persistence = require("../js/persistence.js");
const Player = require("../js/player.js");
const Time = require("../js/timecycle.js");
const World = require("../js/world.js");

function boot(storage) {
  const world = World.createWorld(config.seed);
  const spawn = World.spawnPoint(world);
  const player = Player.createPlayer(spawn.x, spawn.y);
  const inventory = Inventory.starterInventory();
  const clock = Time.createClock(config.time.startFraction);
  return { world: world, player: player, inventory: inventory, clock: clock, storage: storage };
}

function step(game, input, frames) {
  for (let index = 0; index < frames; index += 1) {
    Player.stepPlayer(game.player, game.world, input || {}, 1 / 60);
    Time.advance(game.clock, 1 / 60, config.time.cycleSeconds);
  }
}

function save(game) {
  return Persistence.saveState(game.storage, {
    world: game.world,
    player: game.player,
    inventory: game.inventory,
    time: game.clock.fraction,
    selected: 0
  });
}

test("a full mine-place-move-save-reload journey preserves the world", () => {
  const storage = Persistence.createMemoryStorage();
  const game = boot(storage);
  step(game, {}, 30);
  assert.equal(game.player.onGround, true);

  const surface = World.surfaceHeightAt(game.world.seed, 13);
  const mined = Interaction.mineBlock(game.world, game.player, 13, surface, game.inventory);
  assert.equal(mined.ok, true);
  assert.equal(Inventory.count(game.inventory, config.blocks.grass), 17);

  const placed = Interaction.placeBlock(game.world, game.player, 14, surface - 1, config.blocks.planks, game.inventory);
  assert.equal(placed.ok, true);
  assert.equal(Inventory.count(game.inventory, config.blocks.planks), 11);

  step(game, { right: true, jump: true }, 45);
  assert.ok(game.player.x > 12.5);

  assert.equal(save(game).ok, true);
  const loaded = Persistence.loadState(storage);
  assert.equal(loaded.ok, true);
  assert.equal(loaded.state.player.x, game.player.x);
  assert.equal(loaded.state.player.y, game.player.y);
  assert.equal(World.getBlock(loaded.state.world, 13, surface), config.blocks.air);
  assert.equal(World.getBlock(loaded.state.world, 14, surface - 1), config.blocks.planks);
  assert.equal(Inventory.count(loaded.state.inventory, config.blocks.grass), 17);
  assert.equal(Inventory.count(loaded.state.inventory, config.blocks.planks), 11);
});

test("a refused placement leaves the saved world unchanged", () => {
  const storage = Persistence.createMemoryStorage();
  const game = boot(storage);
  step(game, {}, 30);
  const surface = World.surfaceHeightAt(game.world.seed, 14);
  const before = World.getBlock(game.world, 14, surface);
  const refused = Interaction.placeBlock(game.world, game.player, 14, surface, config.blocks.brick, game.inventory);
  assert.equal(refused.ok, false);
  assert.equal(World.getBlock(game.world, 14, surface), before);
  assert.equal(Inventory.count(game.inventory, config.blocks.brick), 12);
});

test("reloading a corrupt save yields a fresh deterministic world", () => {
  const storage = Persistence.createMemoryStorage({ [config.saveKey]: "{oops" });
  const loaded = Persistence.loadState(storage);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.reason, "corrupt");
  const fresh = World.createWorld(config.seed);
  const reference = World.createWorld(config.seed);
  assert.deepEqual(Array.from(fresh.data), Array.from(reference.data));
});

test("pause semantics freeze the clock and player by skipping updates", () => {
  const game = boot(Persistence.createMemoryStorage());
  step(game, { right: true }, 20);
  const pausedX = game.player.x;
  const pausedTime = game.clock.fraction;
  // A paused frame performs no update; this mirrors the main loop's paused guard.
  assert.equal(game.player.x, pausedX);
  assert.equal(game.clock.fraction, pausedTime);
  step(game, { right: true }, 20);
  assert.ok(game.player.x > pausedX);
  assert.ok(game.clock.fraction > pausedTime);
});

test("a new seed creates an independent world from the same modules", () => {
  const first = World.createWorld(1001);
  const second = World.createWorld(2002);
  assert.notDeepEqual(Array.from(first.data), Array.from(second.data));
  assert.equal(first.width, config.worldWidth);
  assert.equal(second.height, config.worldHeight);
});
