(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./content.js"));
  } else {
    root.MosswildInventory = factory(root.MosswildConfig, root.MosswildContent);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, CONTENT) {
  "use strict";

  const SLOT_COUNT = CONFIG.hotbarSlots;
  const TOOL_KEYS = Object.freeze(["pickaxe", "axe", "sword"]);

  function createFreshProgress() {
    return {
      flags: {
        workbenchCrafted: false,
        workbenchPlaced: false,
        stonePickaxeCrafted: false,
        lanternCrafted: false,
        lanternPlaced: false,
        introDismissed: false,
        celebrationSeen: false
      },
      stats: {
        logsGathered: 0,
        stoneMined: 0,
        coalFound: 0,
        ironFound: 0,
        blocksMined: 0,
        blocksPlaced: 0,
        hollowsDefeated: 0,
        deaths: 0,
        playSeconds: 0,
        distanceWalked: 0
      }
    };
  }

  function createFreshInventory() {
    const info = CONTENT.getToolInfo("pickaxe", 1);
    const startDurability = CONTENT.STARTING_TOOL_DURABILITY.pickaxe || info.durability;
    const hotbar = new Array(SLOT_COUNT).fill(null);
    hotbar[0] = "pickaxe";
    hotbar[1] = "torch";
    return {
      inventory: { torch: 3 },
      tools: {
        pickaxe: { tier: 1, durability: startDurability },
        axe: null,
        sword: null
      },
      hotbar,
      selectedSlot: 0
    };
  }

  function isToolKey(key) {
    return TOOL_KEYS.indexOf(key) !== -1;
  }

  function isItemKey(key) {
    return Object.prototype.hasOwnProperty.call(CONTENT.ITEMS, key);
  }

  function countItem(state, item) {
    if (!state || !isItemKey(item)) {
      return 0;
    }
    return Math.max(0, Math.floor(state.inventory[item] || 0));
  }

  function addItem(state, item, count) {
    if (!state || !isItemKey(item) || !Number.isFinite(count) || count <= 0) {
      return { ok: false, count: 0, autoSlotted: false };
    }
    const amount = Math.floor(count);
    state.inventory[item] = countItem(state, item) + amount;
    let autoSlotted = false;
    if (CONTENT.ITEMS[item].kind === "block" && state.hotbar.indexOf(item) === -1) {
      const empty = state.hotbar.indexOf(null);
      if (empty !== -1) {
        state.hotbar[empty] = item;
        autoSlotted = true;
      }
    }
    return { ok: true, count: amount, autoSlotted };
  }

  function removeItem(state, item, count) {
    const amount = Math.max(0, Math.floor(count || 0));
    if (!state || !isItemKey(item) || amount <= 0) {
      return false;
    }
    if (countItem(state, item) < amount) {
      return false;
    }
    state.inventory[item] -= amount;
    if (state.inventory[item] <= 0) {
      delete state.inventory[item];
      for (let i = 0; i < state.hotbar.length; i += 1) {
        if (state.hotbar[i] === item) {
          state.hotbar[i] = null;
        }
      }
    }
    return true;
  }

  function canAfford(state, costs) {
    const missing = [];
    Object.keys(costs || {}).forEach(function (item) {
      const need = costs[item];
      const have = countItem(state, item);
      if (have < need) {
        missing.push({ item, need, have });
      }
    });
    return { ok: missing.length === 0, missing };
  }

  function selectSlot(state, index) {
    const next = Math.max(0, Math.min(SLOT_COUNT - 1, Number(index) | 0));
    state.selectedSlot = next;
    return next;
  }

  function cycleSlot(state, direction) {
    let next = state.selectedSlot;
    for (let i = 0; i < SLOT_COUNT; i += 1) {
      next = (next + direction + SLOT_COUNT) % SLOT_COUNT;
      if (state.hotbar[next]) {
        state.selectedSlot = next;
        return next;
      }
    }
    state.selectedSlot = (state.selectedSlot + direction + SLOT_COUNT) % SLOT_COUNT;
    return state.selectedSlot;
  }

  function isBindable(state, key) {
    if (!state || !key) {
      return false;
    }
    if (isToolKey(key)) {
      return Boolean(state.tools[key]);
    }
    if (!isItemKey(key)) {
      return false;
    }
    const def = CONTENT.ITEMS[key];
    return def.kind === "block" && countItem(state, key) > 0;
  }

  function bindItemToSlot(state, key) {
    if (!isBindable(state, key)) {
      return { ok: false, reason: "unavailable" };
    }
    const existing = state.hotbar.indexOf(key);
    if (existing !== -1) {
      state.selectedSlot = existing;
      return { ok: true, slot: existing, existing: true };
    }
    const slot = state.selectedSlot;
    state.hotbar[slot] = key;
    return { ok: true, slot, existing: false };
  }

  function findToolHotbarSlot(state, toolKey) {
    return state.hotbar.indexOf(toolKey);
  }

  function ensureToolInHotbar(state, toolKey, replaceSelected) {
    if (!state.tools[toolKey]) {
      return -1;
    }
    const existing = findToolHotbarSlot(state, toolKey);
    if (existing !== -1) {
      return existing;
    }
    let empty = state.hotbar.indexOf(null);
    if (empty === -1 && replaceSelected) {
      empty = state.selectedSlot;
    }
    if (empty !== -1) {
      state.hotbar[empty] = toolKey;
      return empty;
    }
    return -1;
  }

  function getSelectedKey(state) {
    return state.hotbar[state.selectedSlot] || null;
  }

  function getSelectedToolKey(state) {
    const key = getSelectedKey(state);
    return key && isToolKey(key) && state.tools[key] ? key : null;
  }

  function getTool(state, toolKey) {
    return state.tools[toolKey] || null;
  }

  function getToolInfoForState(state, toolKey) {
    const tool = state.tools[toolKey];
    return tool ? CONTENT.getToolInfo(toolKey, tool.tier) : null;
  }

  function getToolDurability(state, toolKey) {
    const tool = state.tools[toolKey];
    if (!tool) {
      return null;
    }
    const info = CONTENT.getToolInfo(toolKey, tool.tier);
    return {
      current: tool.durability,
      max: info ? info.durability : tool.durability,
      ratio: info ? tool.durability / info.durability : 0,
      tier: tool.tier
    };
  }

  function clearToolFromHotbar(state, toolKey) {
    let removed = -1;
    for (let i = 0; i < state.hotbar.length; i += 1) {
      if (state.hotbar[i] === toolKey) {
        state.hotbar[i] = null;
        removed = i;
      }
    }
    if (removed === state.selectedSlot) {
      const fallback = state.hotbar.findIndex(function (entry) { return Boolean(entry); });
      state.selectedSlot = fallback === -1 ? state.selectedSlot : fallback;
    }
    return removed;
  }

  function useTool(state, toolKey, amount) {
    const tool = state.tools[toolKey];
    if (!tool) {
      return { ok: false, broken: false, remaining: 0 };
    }
    const use = Math.max(1, Math.floor(amount || 1));
    tool.durability = Math.max(0, tool.durability - use);
    if (tool.durability <= 0) {
      const info = CONTENT.getToolInfo(toolKey, tool.tier);
      state.tools[toolKey] = null;
      const slot = clearToolFromHotbar(state, toolKey);
      return {
        ok: true,
        broken: true,
        remaining: 0,
        slot,
        toolName: info ? info.name : "Tool"
      };
    }
    return { ok: true, broken: false, remaining: tool.durability };
  }

  function getBreakInfo(state, blockId, selectedKey) {
    const def = CONTENT.getBlockDef(blockId);
    if (!def || def.id === CONFIG.block.AIR) {
      return { ok: false, reason: "empty" };
    }
    if (def.unbreakable) {
      return { ok: false, reason: "unbreakable", def };
    }

    const key = selectedKey === undefined ? getSelectedKey(state) : selectedKey;
    const selectedTool = key && isToolKey(key) && state.tools[key] ? key : null;
    const tool = selectedTool ? state.tools[selectedTool] : null;
    const toolInfo = tool ? CONTENT.getToolInfo(selectedTool, tool.tier) : null;
    const preferred = def.preferredTool || null;
    const matchesPreferred = Boolean(preferred && selectedTool === preferred && toolInfo);
    const minTier = def.minTier || 0;

    if (def.requiresTool) {
      if (!matchesPreferred) {
        return {
          ok: false,
          reason: "tool",
          def,
          neededTool: preferred,
          neededTier: minTier,
          tool: selectedTool,
          duration: 0
        };
      }
      if (tool.tier < minTier) {
        return {
          ok: false,
          reason: "tier",
          def,
          neededTool: preferred,
          neededTier: minTier,
          tool: selectedTool,
          tier: tool.tier,
          duration: 0
        };
      }
    }

    const duration = matchesPreferred && toolInfo
      ? def.hardness / toolInfo.speed
      : def.hardness;

    return {
      ok: true,
      reason: "ready",
      def,
      duration: Math.max(0.05, duration),
      effective: matchesPreferred,
      tool: selectedTool,
      toolTier: tool ? tool.tier : 0,
      neededTool: preferred,
      neededTier: minTier
    };
  }

  function canCraft(state, recipeOrId, nearWorkbench) {
    const recipe = typeof recipeOrId === "string" ? CONTENT.getRecipe(recipeOrId) : recipeOrId;
    if (!recipe) {
      return { ok: false, reason: "unknown" };
    }
    if (recipe.station === "workbench" && !nearWorkbench) {
      return { ok: false, reason: "station", recipe };
    }

    if (recipe.output.kind === "tool") {
      const toolKey = recipe.output.tool;
      const targetTier = recipe.output.tier;
      const current = state.tools[toolKey];
      if (current && current.tier >= targetTier) {
        return {
          ok: false,
          reason: "owned",
          recipe,
          toolKey,
          currentTier: current.tier,
          toolName: CONTENT.getToolName(toolKey, current.tier)
        };
      }
    }

    const afford = canAfford(state, recipe.costs);
    if (!afford.ok) {
      return { ok: false, reason: "ingredients", recipe, missing: afford.missing };
    }
    return { ok: true, reason: "ready", recipe };
  }

  function craft(state, recipeOrId, nearWorkbench) {
    const recipe = typeof recipeOrId === "string" ? CONTENT.getRecipe(recipeOrId) : recipeOrId;
    const check = canCraft(state, recipe, nearWorkbench);
    if (!check.ok) {
      return check;
    }

    Object.keys(recipe.costs).forEach(function (item) {
      removeItem(state, item, recipe.costs[item]);
    });

    let autoSlotted = false;
    let upgraded = false;
    if (recipe.output.kind === "tool") {
      const toolKey = recipe.output.tool;
      const tier = recipe.output.tier;
      const info = CONTENT.getToolInfo(toolKey, tier);
      const previous = state.tools[toolKey];
      state.tools[toolKey] = { tier, durability: info.durability };
      upgraded = Boolean(previous);
      ensureToolInHotbar(state, toolKey, true);
    } else {
      const added = addItem(state, recipe.output.item, recipe.output.count);
      autoSlotted = added.autoSlotted;
    }

    return {
      ok: true,
      reason: "crafted",
      recipe,
      autoSlotted,
      upgraded
    };
  }

  function getAttackInfo(state) {
    const selected = getSelectedKey(state);
    if (selected && isToolKey(selected) && state.tools[selected]) {
      const tool = state.tools[selected];
      const info = CONTENT.getToolInfo(selected, tool.tier);
      return {
        damage: info.damage,
        tool: selected,
        tier: tool.tier,
        name: info.name,
        kind: selected === "sword" ? "sword" : "tool"
      };
    }
    return { damage: 1, tool: null, tier: 0, name: "Bare hands", kind: "hand" };
  }

  function getQuestInfo(state) {
    const steps = CONTENT.QUEST_STEPS;
    const stats = state.stats || {};
    const flags = state.flags || {};
    const tools = state.tools || {};
    const completed = steps.map(function (step) {
      if (step.type === "stat") {
        return (stats[step.stat] || 0) >= step.target;
      }
      if (step.type === "flag") {
        return Boolean(flags[step.flag]);
      }
      if (step.type === "tool") {
        return Boolean(tools[step.tool] && tools[step.tool].tier >= step.tier);
      }
      if (step.type === "ores") {
        return (stats.coalFound || 0) >= step.targets.coal
          && (stats.ironFound || 0) >= step.targets.iron;
      }
      return false;
    });
    const index = completed.findIndex(function (done) { return !done; });
    const allDone = index === -1;
    const currentStep = allDone ? null : steps[index];
    let progress = null;

    if (currentStep) {
      if (currentStep.type === "stat") {
        progress = {
          parts: [{
            label: currentStep.progressLabel,
            current: Math.min(currentStep.target, stats[currentStep.stat] || 0),
            target: currentStep.target
          }],
          current: Math.min(currentStep.target, stats[currentStep.stat] || 0),
          target: currentStep.target
        };
      } else if (currentStep.type === "ores") {
        const coal = Math.min(currentStep.targets.coal, stats.coalFound || 0);
        const iron = Math.min(currentStep.targets.iron, stats.ironFound || 0);
        progress = {
          parts: [
            { label: "coal", current: coal, target: currentStep.targets.coal },
            { label: "iron", current: iron, target: currentStep.targets.iron }
          ],
          current: coal + iron,
          target: currentStep.targets.coal + currentStep.targets.iron
        };
      } else {
        progress = { parts: [], current: 0, target: 1 };
      }
    }

    return {
      steps,
      completed,
      index,
      currentStep,
      progress,
      doneCount: completed.filter(Boolean).length,
      total: steps.length,
      allDone
    };
  }

  function getItemDisplayName(state, key) {
    if (!key) {
      return "Empty hand";
    }
    if (isToolKey(key)) {
      const tool = state.tools[key];
      return tool ? CONTENT.getToolName(key, tool.tier) : "Broken " + CONTENT.TOOL_TYPES[key].name;
    }
    const item = CONTENT.ITEMS[key];
    return item ? item.name : key;
  }

  function sanitizeInventoryState(raw) {
    const fresh = createFreshInventory();
    if (!raw || typeof raw !== "object") {
      return fresh;
    }

    const state = {
      inventory: {},
      tools: { pickaxe: null, axe: null, sword: null },
      hotbar: new Array(SLOT_COUNT).fill(null),
      selectedSlot: 0
    };

    if (raw.inventory && typeof raw.inventory === "object") {
      Object.keys(raw.inventory).forEach(function (key) {
        if (!isItemKey(key)) {
          return;
        }
        const amount = Math.floor(Number(raw.inventory[key]));
        if (Number.isFinite(amount) && amount > 0) {
          state.inventory[key] = Math.min(999999, amount);
        }
      });
    }

    TOOL_KEYS.forEach(function (toolKey) {
      const tool = raw.tools && raw.tools[toolKey];
      if (!tool || !Number.isInteger(tool.tier) || tool.tier < 1 || tool.tier > 3) {
        return;
      }
      const info = CONTENT.getToolInfo(toolKey, tool.tier);
      const durability = Math.floor(Number(tool.durability));
      if (!info || !Number.isFinite(durability) || durability <= 0) {
        return;
      }
      state.tools[toolKey] = { tier: tool.tier, durability: Math.min(info.durability, durability) };
    });

    const seen = new Set();
    if (Array.isArray(raw.hotbar)) {
      for (let i = 0; i < SLOT_COUNT; i += 1) {
        const key = raw.hotbar[i];
        if (typeof key !== "string" || seen.has(key)) {
          continue;
        }
        if (isToolKey(key) && state.tools[key]) {
          state.hotbar[i] = key;
          seen.add(key);
        } else if (isItemKey(key) && CONTENT.ITEMS[key].kind === "block" && countItem(state, key) > 0) {
          state.hotbar[i] = key;
          seen.add(key);
        }
      }
    }

    const rawSelected = Number(raw.selectedSlot);
    state.selectedSlot = Number.isInteger(rawSelected)
      ? Math.max(0, Math.min(SLOT_COUNT - 1, rawSelected))
      : 0;

    // Saved games should never make an owned tool impossible to reach.
    TOOL_KEYS.forEach(function (toolKey) {
      if (state.tools[toolKey] && state.hotbar.indexOf(toolKey) === -1) {
        const empty = state.hotbar.indexOf(null);
        if (empty !== -1) {
          state.hotbar[empty] = toolKey;
        }
      }
    });

    return state;
  }

  function getTotals(state) {
    return {
      itemKinds: Object.keys(state.inventory).filter(function (key) { return countItem(state, key) > 0; }).length,
      items: Object.keys(state.inventory).reduce(function (sum, key) {
        return sum + countItem(state, key);
      }, 0),
      tools: TOOL_KEYS.filter(function (key) { return Boolean(state.tools[key]); }).length
    };
  }

  return {
    SLOT_COUNT,
    TOOL_KEYS,
    createFreshInventory,
    createFreshProgress,
    sanitizeInventoryState,
    isToolKey,
    isItemKey,
    isBindable,
    countItem,
    addItem,
    removeItem,
    canAfford,
    selectSlot,
    cycleSlot,
    bindItemToSlot,
    ensureToolInHotbar,
    findToolHotbarSlot,
    getSelectedKey,
    getSelectedToolKey,
    getTool,
    getToolInfoForState,
    getToolDurability,
    useTool,
    getBreakInfo,
    canCraft,
    craft,
    getAttackInfo,
    getQuestInfo,
    getItemDisplayName,
    getTotals
  };
});
