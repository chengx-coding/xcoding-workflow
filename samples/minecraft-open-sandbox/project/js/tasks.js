(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"), require("./blocks.js"));
  } else {
    root.SandboxTasks = factory(root.SandboxConfig, root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG, BLOCKS) {
  "use strict";

  if (!CONFIG || !BLOCKS) {
    throw new Error("SandboxConfig and SandboxBlocks are required before SandboxTasks");
  }

  const B = CONFIG.blocks;

  function createProgress() {
    return {
      mined: Object.create(null),
      collected: Object.create(null),
      crafted: Object.create(null),
      placed: { total: 0, byId: Object.create(null) },
      tasks: Object.create(null),
      deepest: 0,
      day: 1,
      playSeconds: 0
    };
  }

  function noteMined(progress, blockId) {
    progress.mined[blockId] = (progress.mined[blockId] || 0) + 1;
  }

  function noteCollected(progress, itemId, amount) {
    const quantity = Math.max(0, Math.floor(amount || 1));
    progress.collected[itemId] = (progress.collected[itemId] || 0) + quantity;
  }

  function notePlaced(progress, blockId) {
    progress.placed.total += 1;
    progress.placed.byId[blockId] = (progress.placed.byId[blockId] || 0) + 1;
  }

  function noteCrafted(progress, recipeId) {
    progress.crafted[recipeId] = (progress.crafted[recipeId] || 0) + 1;
  }

  function noteDepth(progress, y) {
    if (y > progress.deepest) {
      progress.deepest = y;
    }
  }

  const TASKS = [
    {
      id: "first_wood",
      title: "Punch a tree",
      hint: "Face a tree trunk and hold the mine button until three wood blocks drop.",
      reward: { id: B.torch, count: 2 },
      target: "3 wood",
      progress: function (p) { return Math.min(p.collected[B.wood] || 0, 3); },
      goal: 3,
      check: function (p) { return (p.collected[B.wood] || 0) >= 3; }
    },
    {
      id: "make_planks",
      title: "Craft planks",
      hint: "Open Crafting (C) and turn wood into planks.",
      reward: { id: 100, count: 4 },
      target: "4 planks",
      progress: function (p) { return Math.min(p.collected[B.planks] || 0, 4); },
      goal: 4,
      check: function (p) { return (p.collected[B.planks] || 0) >= 4; }
    },
    {
      id: "make_pickaxe",
      title: "Make a pickaxe",
      hint: "Craft sticks, then a wooden pickaxe so stone becomes collectable.",
      reward: { id: B.cobblestone, count: 4 },
      target: "1 pickaxe",
      progress: function (p) {
        return (p.crafted.wooden_pickaxe || 0) + (p.crafted.stone_pickaxe || 0) + (p.crafted.iron_pickaxe || 0);
      },
      goal: 1,
      check: function (p) {
        return (p.crafted.wooden_pickaxe || 0) + (p.crafted.stone_pickaxe || 0) + (p.crafted.iron_pickaxe || 0) >= 1;
      }
    },
    {
      id: "build_shelter",
      title: "Place 10 blocks",
      hint: "Select a block in the hotbar and right-click to build.",
      reward: { id: B.glass, count: 2 },
      target: "10 placed",
      progress: function (p) { return Math.min(p.placed.total, 10); },
      goal: 10,
      check: function (p) { return p.placed.total >= 10; }
    },
    {
      id: "light_dark",
      title: "Light the dark",
      hint: "Place a torch where the light is low; it pushes shadows back.",
      reward: { id: B.torch, count: 4 },
      target: "1 torch placed",
      progress: function (p) { return Math.min(p.placed.byId[B.torch] || 0, 1); },
      goal: 1,
      check: function (p) { return (p.placed.byId[B.torch] || 0) >= 1; }
    },
    {
      id: "dig_deep",
      title: "Dig deep",
      hint: "Carve down until you reach y=68. Coal and iron live below.",
      reward: { id: B.cobblestone, count: 8 },
      target: "reach y=68",
      progress: function (p) { return Math.min(p.deepest, 68); },
      goal: 68,
      check: function (p) { return p.deepest >= 68; }
    },
    {
      id: "find_iron",
      title: "Find iron",
      hint: "Iron ore needs a stone pickaxe. Look below y=60.",
      reward: { id: 102, count: 2 },
      target: "1 iron",
      progress: function (p) { return Math.min(p.collected[102] || 0, 1); },
      goal: 1,
      check: function (p) { return (p.collected[102] || 0) >= 1; }
    },
    {
      id: "survive_night",
      title: "Survive the night",
      hint: "Keep playing until day 2 begins.",
      reward: { id: B.glass, count: 4 },
      target: "day 2",
      progress: function (p) { return Math.min(p.day, 2); },
      goal: 2,
      check: function (p) { return p.day >= 2; }
    }
  ];

  function activeTask(progress) {
    for (let index = 0; index < TASKS.length; index += 1) {
      if (!progress.tasks[TASKS[index].id]) {
        return TASKS[index];
      }
    }
    return null;
  }

  function completedCount(progress) {
    return TASKS.filter(function (task) {
      return Boolean(progress.tasks[task.id]);
    }).length;
  }

  // Marks every satisfied task complete and returns the newly completed tasks
  // with their rewards. Rewards are applied by the caller so progress stays a
  // pure record.
  function sync(progress) {
    const completed = [];
    TASKS.forEach(function (task) {
      if (progress.tasks[task.id]) {
        return;
      }
      if (task.check(progress)) {
        progress.tasks[task.id] = true;
        completed.push(task);
      }
    });
    return completed;
  }

  function taskProgress(task, progress) {
    const value = task.progress(progress);
    return { value: value, goal: task.goal, text: value + "/" + task.goal };
  }

  function serialize(progress) {
    return {
      mined: Object.assign({}, progress.mined),
      collected: Object.assign({}, progress.collected),
      crafted: Object.assign({}, progress.crafted),
      placed: { total: progress.placed.total, byId: Object.assign({}, progress.placed.byId) },
      tasks: Object.assign({}, progress.tasks),
      deepest: progress.deepest,
      day: progress.day,
      playSeconds: progress.playSeconds
    };
  }

  function deserialize(payload) {
    const progress = createProgress();
    if (!payload) {
      return progress;
    }
    progress.mined = Object.assign(Object.create(null), payload.mined || {});
    progress.collected = Object.assign(Object.create(null), payload.collected || {});
    progress.crafted = Object.assign(Object.create(null), payload.crafted || {});
    progress.placed = {
      total: payload.placed && Number.isFinite(payload.placed.total) ? payload.placed.total : 0,
      byId: Object.assign(Object.create(null), (payload.placed && payload.placed.byId) || {})
    };
    progress.tasks = Object.assign(Object.create(null), payload.tasks || {});
    progress.deepest = Number.isFinite(payload.deepest) ? payload.deepest : 0;
    progress.day = Number.isFinite(payload.day) ? payload.day : 1;
    progress.playSeconds = Number.isFinite(payload.playSeconds) ? payload.playSeconds : 0;
    return progress;
  }

  return {
    TASKS: TASKS,
    createProgress: createProgress,
    noteMined: noteMined,
    noteCollected: noteCollected,
    notePlaced: notePlaced,
    noteCrafted: noteCrafted,
    noteDepth: noteDepth,
    activeTask: activeTask,
    completedCount: completedCount,
    sync: sync,
    taskProgress: taskProgress,
    serialize: serialize,
    deserialize: deserialize
  };
});
