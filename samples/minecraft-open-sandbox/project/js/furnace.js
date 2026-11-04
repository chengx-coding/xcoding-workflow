/* Furnace state, fuel and timed smelting. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./inventory.js"));
  } else {
    root.SandboxFurnace = factory(root.SandboxConfig, root.SandboxInventory);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, INV) {
  "use strict";

  const I = CONFIG.itemIds;
  const B = CONFIG.blocks;
  const COOK_SECONDS = 5;

  const SMELT = Object.freeze({
    [I.rawIron]: { id: I.ironIngot, count: 1 },
    [B.sand]: { id: B.glass, count: 1 },
    [I.rawPork]: { id: I.cookedPork, count: 1 }
  });

  const FUEL = Object.freeze({
    [I.coal]: 40,
    [B.planks]: 12,
    [B.wood]: 15,
    [I.stick]: 6,
    [B.ladder]: 8,
    [B.table]: 12
  });

  function key(x, y) {
    return x + "," + y;
  }

  function smeltFor(id) {
    return SMELT[id] || null;
  }

  function fuelFor(id) {
    return FUEL[id] || 0;
  }

  function createState() {
    return {
      input: null,
      fuel: null,
      output: null,
      burnTime: 0,
      burnMax: 0,
      cookTime: 0,
      cookMax: COOK_SECONDS,
      cookFor: null
    };
  }

  function createStore() {
    return {};
  }

  function get(store, x, y, create) {
    const id = key(x, y);
    if (!store[id] && create) {
      store[id] = createState();
    }
    return store[id] || null;
  }

  function remove(store, x, y) {
    delete store[key(x, y)];
  }

  function canAcceptOutput(state, output) {
    if (!state.output) {
      return true;
    }
    return state.output.id === output.id &&
      state.output.count + output.count <= INV.maxStack(output.id);
  }

  function tick(state, dt) {
    const recipe = state.input ? smeltFor(state.input.id) : null;
    if (recipe && state.cookFor !== state.input.id) {
      state.cookFor = state.input.id;
      state.cookTime = 0;
    }
    if (!recipe || !canAcceptOutput(state, recipe)) {
      state.cookTime = Math.max(0, state.cookTime - dt * 0.5);
      if (state.burnTime > 0) {
        state.burnTime = Math.max(0, state.burnTime - dt);
      }
      return { changed: false, active: state.burnTime > 0 };
    }

    if (state.burnTime <= 0 && state.fuel) {
      const value = fuelFor(state.fuel.id);
      if (value > 0) {
        state.fuel.count -= 1;
        if (state.fuel.count <= 0) {
          state.fuel = null;
        }
        state.burnMax = value;
        state.burnTime = value;
      }
    }

    if (state.burnTime <= 0) {
      state.cookTime = Math.max(0, state.cookTime - dt * 0.5);
      return { changed: false, active: false };
    }

    state.burnTime = Math.max(0, state.burnTime - dt);
    state.cookTime += dt;
    if (state.cookTime >= state.cookMax) {
      state.cookTime = 0;
      if (!state.output) {
        state.output = { id: recipe.id, count: recipe.count };
      } else {
        state.output.count += recipe.count;
      }
      state.input.count -= 1;
      if (state.input.count <= 0) {
        state.input = null;
      }
      return { changed: true, active: true, produced: recipe };
    }
    return { changed: false, active: true };
  }

  function tickAll(store, dt) {
    let changed = false;
    Object.keys(store).forEach(function (id) {
      const result = tick(store[id], dt);
      if (result.changed) {
        changed = true;
      }
    });
    return changed;
  }

  function serialize(store) {
    return Object.keys(store).map(function (id) {
      const state = store[id];
      const parts = id.split(",");
      return {
        x: Number(parts[0]),
        y: Number(parts[1]),
        input: state.input ? [state.input.id, state.input.count] : null,
        fuel: state.fuel ? [state.fuel.id, state.fuel.count] : null,
        output: state.output ? [state.output.id, state.output.count] : null,
        burnTime: state.burnTime,
        burnMax: state.burnMax,
        cookTime: state.cookTime
      };
    });
  }

  function deserialize(data) {
    const store = {};
    if (!Array.isArray(data)) {
      return store;
    }
    data.forEach(function (entry) {
      if (!entry || !Number.isInteger(entry.x) || !Number.isInteger(entry.y)) {
        return;
      }
      const state = createState();
      if (Array.isArray(entry.input)) {
        state.input = { id: entry.input[0], count: entry.input[1] };
      }
      if (Array.isArray(entry.fuel)) {
        state.fuel = { id: entry.fuel[0], count: entry.fuel[1] };
      }
      if (Array.isArray(entry.output)) {
        state.output = { id: entry.output[0], count: entry.output[1] };
      }
      state.burnTime = Number(entry.burnTime) || 0;
      state.burnMax = Number(entry.burnMax) || 0;
      state.cookTime = Number(entry.cookTime) || 0;
      state.cookFor = state.input ? state.input.id : null;
      store[key(entry.x, entry.y)] = state;
    });
    return store;
  }

  return {
    cookSeconds: COOK_SECONDS,
    smeltFor: smeltFor,
    fuelFor: fuelFor,
    createState: createState,
    createStore: createStore,
    get: get,
    remove: remove,
    key: key,
    tick: tick,
    tickAll: tickAll,
    serialize: serialize,
    deserialize: deserialize
  };
});
