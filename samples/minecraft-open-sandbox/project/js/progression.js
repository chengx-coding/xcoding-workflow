(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxProgression = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const B = CONFIG.blocks;

  const STAGES = Object.freeze([
    {
      id: "wood",
      title: "Gather wood",
      hint: "Hold left mouse on a tree trunk to chop wood.",
      done: function doneWood(stats) {
        return stats.woodCollected >= 4;
      }
    },
    {
      id: "workbench",
      title: "Build a workbench",
      hint: "Craft a workbench (4 planks), then place it with right mouse.",
      done: function doneBench(stats) {
        return stats.workbenchPlaced >= 1;
      }
    },
    {
      id: "pick_wood",
      title: "Craft a wooden pickaxe",
      hint: "At the workbench: 3 planks + 2 sticks.",
      done: function doneWoodPick(stats) {
        return stats.pickWoodCrafted >= 1;
      }
    },
    {
      id: "stone",
      title: "Reach the stone tier",
      hint: "Mine stone with the wooden pickaxe, then craft a stone pickaxe.",
      done: function doneStonePick(stats) {
        return stats.pickStoneCrafted >= 1;
      }
    },
    {
      id: "torch",
      title: "Light the dark",
      hint: "Mine coal, craft torches (stick + coal), and place one underground.",
      done: function doneTorch(stats) {
        return stats.torchesPlaced >= 1;
      }
    },
    {
      id: "iron",
      title: "Forge an iron pickaxe",
      hint: "Place a furnace, smelt iron ore with coal, then craft the iron pickaxe.",
      done: function doneIronPick(stats) {
        return stats.pickIronCrafted >= 1;
      }
    },
    {
      id: "ember",
      title: "Delve for ember",
      hint: "The ember band lies at the bottom of the world. Mine 3 ember ore.",
      done: function doneEmber(stats) {
        return stats.emberMined >= 3;
      }
    },
    {
      id: "beacon",
      title: "Raise the Ember Beacon",
      hint: "Refine ember shards at a furnace, then craft and place the beacon.",
      done: function doneBeacon(stats) {
        return stats.beaconPlaced >= 1;
      }
    }
  ]);

  const STAGE_BY_ID = Object.freeze(
    STAGES.reduce(function build(map, stage) {
      map[stage.id] = stage;
      return map;
    }, {})
  );

  function emptyStats() {
    return {
      woodCollected: 0,
      workbenchPlaced: 0,
      pickWoodCrafted: 0,
      pickStoneCrafted: 0,
      pickIronCrafted: 0,
      torchesPlaced: 0,
      emberMined: 0,
      beaconPlaced: 0,
      blocksMined: 0,
      ironSmelted: 0,
      daysSurvived: 0,
      playtime: 0
    };
  }

  function createProgress() {
    return {
      stage: 0,
      stats: emptyStats(),
      completed: []
    };
  }

  function record(progress, key, amount) {
    if (!progress || !Object.prototype.hasOwnProperty.call(progress.stats, key)) {
      return progress;
    }
    const delta = typeof amount === "number" ? amount : 1;
    progress.stats[key] += delta;
    return progress;
  }

  function recordMine(progress, blockId) {
    record(progress, "blocksMined");
    if (blockId === B.wood) {
      record(progress, "woodCollected");
    }
    if (blockId === B.ember_ore) {
      record(progress, "emberMined");
    }
    return progress;
  }

  function recordPlace(progress, blockId) {
    if (blockId === B.workbench) {
      record(progress, "workbenchPlaced");
    } else if (blockId === B.torch) {
      record(progress, "torchesPlaced");
    } else if (blockId === B.beacon) {
      record(progress, "beaconPlaced");
    }
    return progress;
  }

  function recordCraft(progress, recipeId) {
    if (recipeId === "wooden_pickaxe") {
      record(progress, "pickWoodCrafted");
    } else if (recipeId === "stone_pickaxe") {
      record(progress, "pickStoneCrafted");
    } else if (recipeId === "iron_pickaxe") {
      record(progress, "pickIronCrafted");
    } else if (recipeId === "iron_ingot") {
      record(progress, "ironSmelted");
    }
    return progress;
  }

  function update(progress) {
    const newlyCompleted = [];
    for (let i = progress.stage; i < STAGES.length; i += 1) {
      const stage = STAGES[i];
      if (!stage.done(progress.stats)) {
        break;
      }
      progress.completed.push(stage.id);
      progress.stage = i + 1;
      newlyCompleted.push(stage);
    }
    return { newlyCompleted: newlyCompleted, stage: progress.stage, complete: isComplete(progress) };
  }

  function isComplete(progress) {
    return progress.stage >= STAGES.length;
  }

  function current(progress) {
    const index = Math.min(progress.stage, STAGES.length - 1);
    return STAGES[index];
  }

  function summary(progress) {
    const done = isComplete(progress);
    return {
      index: progress.stage,
      total: STAGES.length,
      current: done ? null : current(progress),
      done: done,
      completed: progress.completed.slice(),
      title: done ? "The beacon burns" : current(progress).title,
      hint: done ? "The deep is lit. Keep building." : current(progress).hint
    };
  }

  function serialize(progress) {
    return {
      stage: progress.stage,
      completed: progress.completed.slice(),
      stats: Object.assign(emptyStats(), progress.stats)
    };
  }

  function deserialize(saved) {
    const progress = createProgress();
    if (!saved || typeof saved !== "object") {
      return progress;
    }
    const stats = saved.stats && typeof saved.stats === "object" ? saved.stats : {};
    for (const key of Object.keys(progress.stats)) {
      if (typeof stats[key] === "number" && Number.isFinite(stats[key])) {
        progress.stats[key] = Math.max(0, Math.floor(stats[key]));
      }
    }
    const stage = Number(saved.stage);
    progress.stage = Number.isInteger(stage) ? Math.max(0, Math.min(STAGES.length, stage)) : 0;
    progress.completed = STAGES.slice(0, progress.stage).map(function id(stageDef) {
      return stageDef.id;
    });
    return progress;
  }

  return {
    STAGES: STAGES,
    STAGE_BY_ID: STAGE_BY_ID,
    emptyStats: emptyStats,
    createProgress: createProgress,
    record: record,
    recordMine: recordMine,
    recordPlace: recordPlace,
    recordCraft: recordCraft,
    update: update,
    isComplete: isComplete,
    current: current,
    summary: summary,
    serialize: serialize,
    deserialize: deserialize
  };
});
