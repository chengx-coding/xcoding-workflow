/* ============================================================
   BLOCKHAVEN — game loop, survival systems and presentation
   ============================================================ */
(function () {
  "use strict";

  const BH = window.BH;
  const T = BH.T;
  const I = BH.I;
  const W = BH.W, H = BH.H;
  const TAU = Math.PI * 2;

  const $ = sel => document.querySelector(sel);
  const el = {};
  const canvas = document.getElementById("world");
  const ctx = canvas.getContext("2d", { alpha: false });

  const view = { w: 0, h: 0, dpr: 1, tile: 36, hud: 1 };
  const cam = { x: W / 2, y: 78 };
  const mouse = { x: 0, y: 0, down: false, inside: true, tileX: 0, tileY: 0, valid: false };
  const keys = { left: false, right: false, jump: false, sprint: false };
  const hud = { hotbar: [], selectionFade: 0, saveFlash: 0, damageFlash: 0, shake: 0 };

  let state = "boot";
  let previousState = "title";
  let world = null;
  let player = null;
  let entities = [];
  let drops = [];
  let particles = [];
  let floaters = [];
  let messages = [];
  let worldTime = 0;
  let playTime = 0;
  let difficulty = "normal";
  let stats = { mined: 0, placed: 0, zombies: 0, deaths: 0, crafted: 0 };
  let hasSave = false;
  let started = false;
  let titlePreviewSeed = "";
  let lastFrame = 0;
  let elapsed = 0;
  let saveTimer = 0;
  let nearbyTimer = 0;
  let nearby = { table: false, furnace: false };
  let zombieTimer = 4;
  let pigTimer = 0;
  let ambientTimer = 8;
  let jumpBuffer = 0;
  let coyote = 0;
  let mineTarget = null;
  let mineProgress = 0;
  let mineParticleTimer = 0;
  let digSoundTimer = 0;
  let selectedFlash = 0;
  let showDebug = false;
  let saveErrorShown = false;
  let titleCamDrift = 0;
  let whisperCooldown = 0;

  let held = null;          // stack held by the cursor in an inventory screen
  let confirmCallback = null;
  let confirmReturn = "pause";
  let uiToastTimer = 0;
  let previousScreenForHelp = "title";
  let deathCause = "You ran out of health.";

  const hints = { log: false, tableCrafted: false, tablePlaced: false, night: false, zombie: false, dug: false };

  // ---------- DOM ----------
  function initDom() {
    const ids = [
      "boot", "titleScreen", "newWorldScreen", "inventoryScreen", "furnaceScreen",
      "pauseScreen", "helpScreen", "confirmScreen", "deathScreen", "itemCursor", "itemTooltip",
      "btnContinue", "btnPlay", "btnNewWorld", "btnHowTo", "btnTitleSound", "saveCard",
      "saveCardName", "saveCardMeta", "versionChip", "seedInput", "difficultyPicker",
      "difficultyHelp", "overwriteNotice", "createWorldBtn", "mainGrid", "invHotbar",
      "recipeList", "recipeCount", "nearTableBadge", "invEyebrow", "furnaceList",
      "furnaceFuel", "pauseSeed", "pauseDay", "pauseDepth", "pausePlaytime",
      "pauseMined", "pauseZombies", "pauseDeaths",
      "btnResume", "btnPauseHelp", "btnSaveNow", "btnPauseSound", "btnFullscreen",
      "btnQuit", "btnRespawn", "btnDeathQuit", "deathBody", "confirmTitle",
      "confirmBody", "confirmNo", "confirmYes", "uiToast"
    ];
    for (const id of ids) el[id] = document.getElementById(id);
  }

  // ---------- small utilities ----------
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function approach(v, target, step) {
    if (v < target) return Math.min(target, v + step);
    if (v > target) return Math.max(target, v - step);
    return target;
  }
  function dist2(ax, ay, bx, by) { const dx = ax - bx, dy = ay - by; return dx * dx + dy * dy; }
  function formatClock(t) {
    const mins = Math.floor(((6 * 60 + t * 24 * 60) % 1440 + 1440) % 1440);
    const hh = Math.floor(mins / 60), mm = mins % 60;
    return String(hh).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
  }
  function dayNumber() { return Math.floor(worldTime / BH.DAY_LENGTH) + 1; }
  function timeOfDay() { return BH.mod(worldTime / BH.DAY_LENGTH, 1); }
  function sunAltitude() { return Math.sin(timeOfDay() * TAU); }
  function daylightFactor() {
    return clamp(0.12 + 0.88 * BH.smoothstep(-0.12, 0.24, sunAltitude()), 0.12, 1);
  }
  function isNight() { return sunAltitude() < -0.055; }
  function formatPlaytime(sec) {
    const m = Math.floor(sec / 60);
    if (m < 60) return m + "m";
    return Math.floor(m / 60) + "h " + (m % 60) + "m";
  }
  function randomSeed() {
    const a = ["mossy", "quiet", "amber", "hollow", "wild", "soft", "old", "green", "lucky", "drifting", "copper", "misty"];
    const b = ["hills", "grove", "creek", "stone", "meadow", "pines", "ridge", "vale", "brook", "field", "cliff", "fern"];
    return a[(Math.random() * a.length) | 0] + "-" + b[(Math.random() * b.length) | 0] + "-" + ((Math.random() * 900 + 100) | 0);
  }
  function tileBelow(x, y) {
    const tx = Math.floor(x), ty = Math.floor(y + 0.01);
    return world.get(tx, ty);
  }
  function centerDistToPlayer(x, y) {
    return Math.hypot(x - player.x, y - (player.y - player.h * 0.5));
  }
  function itemDef(item) { return item ? BH.ITEM_DEFS[item.id] : null; }
  function itemStack(item) { return item ? item.count : 0; }
  function durabilityMax(item) {
    const d = itemDef(item);
    return d && d.durability ? d.durability : 0;
  }

  // ---------- game boot ----------
  function boot() {
    initDom();
    resize();
    try {
      const settings = JSON.parse(localStorage.getItem(BH.SETTINGS_KEY) || "{}");
      if (settings && settings.muted) BH.Sound.muted = true;
    } catch (e) {}
    updateSoundLabels();

    const loaded = readSave();
    if (loaded) {
      try {
        world = new BH.World(loaded.world.seed);
        world.applySerialized(loaded.world);
        player = playerFromSave(loaded.player);
        worldTime = Number(loaded.worldTime) || 0;
        playTime = Number(loaded.playTime) || 0;
        difficulty = ["peaceful", "normal", "hard"].includes(loaded.difficulty) ? loaded.difficulty : "normal";
        stats = Object.assign(stats, loaded.stats || {});
        entities = Array.isArray(loaded.entities) ? loaded.entities.map(entityFromSave).filter(Boolean) : [];
        if (!entities.some(e => e.type === "pig")) spawnInitialPigs(14);
        hasSave = true;
      } catch (err) {
        console.warn("Could not load save", err);
        world = null;
      }
    }

    if (!world) {
      titlePreviewSeed = randomSeed();
      world = new BH.World(titlePreviewSeed);
      player = createNewPlayer();
      worldTime = BH.DAY_LENGTH * 0.085;
      playTime = 0;
      entities = [];
      spawnInitialPigs(18);
      hasSave = false;
    }

    if (!player) player = createNewPlayer();
    if (!Number.isFinite(player.x) || !Number.isFinite(player.y)) {
      player.x = world.spawnX; player.y = world.spawnY;
    }
    sanitizePlayerPosition();
    snapCamera();
    buildMinimap();
    bindEvents();
    updateTitleUI();
    hideAllScreens();
    el.titleScreen.classList.remove("hidden");
    state = "title";
    canvas.style.cursor = "default";
    requestAnimationFrame(loop);
  }

  function readSave() {
    try {
      const raw = localStorage.getItem(BH.SAVE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || data.version !== BH.SAVE_VERSION || !data.world || !data.world.seed) return null;
      return data;
    } catch (e) { return null; }
  }

  function playerFromSave(p) {
    const base = createNewPlayer();
    if (!p) return base;
    base.x = Number(p.x);
    base.y = Number(p.y);
    base.health = clamp(Number(p.health) || 20, 0, 20);
    base.hunger = clamp(Number(p.hunger) || 20, 0, 20);
    base.selected = clamp(Number(p.selected) || 0, 0, 8);
    base.spawnX = Number(p.spawnX) || world.spawnX;
    base.spawnY = Number(p.spawnY) || world.spawnY;
    if (Array.isArray(p.inventory)) {
      base.inventory = new Array(36).fill(null);
      for (let i = 0; i < 36; i++) base.inventory[i] = sanitizeItem(p.inventory[i]);
    }
    return base;
  }

  function sanitizeItem(it) {
    if (!it || typeof it !== "object") return null;
    const id = Number(it.id);
    const def = BH.ITEM_DEFS[id];
    if (!def) return null;
    let count = Math.floor(Number(it.count));
    if (!Number.isFinite(count) || count <= 0) return null;
    count = Math.min(count, def.stack || 64);
    const out = { id, count };
    if (def.durability) {
      const dur = Number(it.dur);
      out.dur = Number.isFinite(dur) ? clamp(dur, 0, def.durability) : def.durability;
      if (out.dur <= 0) return null;
    }
    return out;
  }

  function createNewPlayer() {
    const p = {
      x: world.spawnX,
      y: world.spawnY - 0.02,
      w: 0.7,
      h: 1.8,
      vx: 0,
      vy: 0,
      onGround: false,
      face: 1,
      health: 20,
      maxHealth: 20,
      hunger: 20,
      invuln: 0,
      attackCd: 0,
      useCd: 0,
      regenTimer: 0,
      starveTimer: 0,
      airTime: 0,
      fallTop: world.spawnY,
      walkTime: 0,
      stepTimer: 0,
      swing: 0,
      selected: 0,
      inventory: new Array(36).fill(null),
      spawnX: world.spawnX,
      spawnY: world.spawnY
    };
    // A small starter kit: something to eat and a little light for the first cave.
    p.inventory[0] = { id: I.APPLE, count: 3 };
    p.inventory[1] = { id: T.TORCH, count: 6 };
    return p;
  }

  function entityFromSave(e) {
    if (!e || (e.type !== "pig" && e.type !== "zombie")) return null;
    const out = e.type === "pig" ? makePig(Number(e.x), Number(e.y)) : makeZombie(Number(e.x), Number(e.y));
    if (!Number.isFinite(out.x) || !Number.isFinite(out.y)) return null;
    out.hp = clamp(Number(e.hp) || out.hp, 0.1, out.maxHp);
    out.dir = e.dir === -1 ? -1 : 1;
    if (e.type === "pig") {
      out.timer = 1 + Math.random() * 3;
      out.flee = 0;
    }
    return out;
  }

  function sanitizePlayerPosition() {
    if (player.y > H - 2) player.y = world.spawnY;
    if (player.x < 2) player.x = 2;
    if (player.x > W - 2) player.x = W - 2;
    let tx = Math.floor(player.x);
    let ty = Math.floor(player.y - 0.2);
    for (let i = 0; i < 8 && world.isSolid(tx, ty); i++) {
      player.y = ty - 0.05;
      ty = Math.floor(player.y - 0.2);
    }
  }

  // ---------- save ----------
  function saveGame(manual) {
    if (!world || !player || (!started && !hasSave)) return;
    const invForSave = player.inventory.slice();
    if (held) {
      const free = invForSave.findIndex(slot => !slot);
      if (free >= 0) invForSave[free] = { id: held.id, count: held.count, dur: held.dur };
    }
    const data = {
      version: BH.SAVE_VERSION,
      savedAt: Date.now(),
      difficulty,
      worldTime,
      playTime,
      stats,
      world: world.serialize(),
      player: {
        x: player.x, y: player.y, health: player.health, hunger: player.hunger,
        selected: player.selected, spawnX: player.spawnX, spawnY: player.spawnY,
        inventory: invForSave
      },
      entities: entities.filter(e => e.type === "pig" || e.type === "zombie").slice(0, 40).map(e => ({
        type: e.type, x: +e.x.toFixed(2), y: +e.y.toFixed(2), hp: +e.hp.toFixed(1), dir: e.dir
      }))
    };
    try {
      localStorage.setItem(BH.SAVE_KEY, JSON.stringify(data));
      hasSave = true;
      hud.saveFlash = 2.2;
      if (manual) message("World saved.", "#b9d69a");
      updateTitleUI();
    } catch (err) {
      if (!saveErrorShown) {
        saveErrorShown = true;
        message("Saving is unavailable in this browser.", "#e1a080", 5);
        console.warn("Save failed", err);
      }
    }
  }

  function updateTitleUI() {
    if (!el.btnContinue) return;
    el.btnContinue.classList.toggle("hidden", !hasSave);
    el.btnPlay.classList.toggle("hidden", hasSave);
    el.saveCard.classList.toggle("hidden", !hasSave);
    if (hasSave) {
      el.saveCardName.textContent = world ? world.seedString : "Saved world";
      el.saveCardMeta.textContent = world
        ? "Day " + dayNumber() + " · " + formatClock(timeOfDay()) + " · " + capitalize(difficulty)
        : "Saved on this device";
    }
    el.versionChip.textContent = "OFFLINE · v1.0";
    el.btnTitleSound.textContent = "Sound: " + (BH.Sound.muted ? "Off" : "On");
  }
  function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  // ---------- world lifecycle ----------
  function startNewWorld(seed, diff) {
    BH.Sound.resume();
    world = new BH.World(seed || randomSeed());
    player = createNewPlayer();
    difficulty = diff || "normal";
    worldTime = BH.DAY_LENGTH * 0.08;
    playTime = 0;
    stats = { mined: 0, placed: 0, zombies: 0, deaths: 0, crafted: 0 };
    entities = [];
    drops = [];
    particles = [];
    floaters = [];
    messages = [];
    mineTarget = null;
    mineProgress = 0;
    held = null;
    spawnInitialPigs(22);
    sanitizePlayerPosition();
    snapCamera();
    buildMinimap();
    started = true;
    hasSave = true;
    saveGame(false);
    setState("playing");
    welcomeMessages();
  }

  function playPreviewWorld() {
    if (hasSave) { continueWorld(); return; }
    BH.Sound.resume();
    started = true;
    player.x = world.spawnX;
    player.y = world.spawnY - 0.02;
    player.health = player.maxHealth;
    player.hunger = 20;
    snapCamera();
    setState("playing");
    saveGame(false);
    welcomeMessages();
  }

  function welcomeMessages() {
    message("Welcome to Blockhaven.", "#e9d9b5", 3.6);
    setTimeout(() => { if (state === "playing") message("Hold LEFT-CLICK on a tree trunk to gather wood.", "#c7dba8", 5); }, 900);
    setTimeout(() => { if (state === "playing") message("Press E to open your inventory and craft.", "#c7dba8", 5); }, 5600);
  }

  function continueWorld() {
    if (!hasSave) { startNewWorld(randomSeed(), "normal"); return; }
    BH.Sound.resume();
    if (player.health <= 0) {
      player.health = player.maxHealth;
      player.hunger = Math.max(15, player.hunger);
      placePlayerAtSpawn();
      player.invuln = 1.5;
      message("You wake up at your spawn. Your pockets are safe.", "#c8dfa3", 4);
    } else {
      message("Welcome back to " + world.seedString + ".", "#e9d9b5", 3);
    }
    started = true;
    player.invuln = Math.max(player.invuln, 1.2);
    setState("playing");
    snapCamera();
  }

  function returnToTitle() {
    if (state !== "title") saveGame(false);
    if (held) returnHeldStack();
    if (el.itemCursor) el.itemCursor.classList.add("hidden");
    hideTooltip();
    setState("title");
    updateTitleUI();
    titleCamDrift = 0;
  }

  // ---------- screen state ----------
  const SCREEN_IDS = {
    title: "titleScreen", newworld: "newWorldScreen", inventory: "inventoryScreen",
    furnace: "furnaceScreen", pause: "pauseScreen", help: "helpScreen",
    confirm: "confirmScreen", dead: "deathScreen"
  };

  function hideAllScreens() {
    for (const key in SCREEN_IDS) {
      const node = el[SCREEN_IDS[key]];
      if (node) node.classList.add("hidden");
    }
    el.boot.classList.add("hidden");
  }

  function setState(next) {
    if (state === "inventory" && next !== "inventory" && held) returnHeldStack();
    if (el.uiToast) el.uiToast.classList.add("hidden");
    state = next;
    hideAllScreens();
    if (SCREEN_IDS[next]) el[SCREEN_IDS[next]].classList.remove("hidden");
    canvas.style.cursor = next === "playing" ? "none" : "default";
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    if (next === "inventory") {
      updateNearby();
      refreshInventoryUI();
      el.invEyebrow.textContent = nearby.table ? "SURVIVAL INVENTORY · TABLE NEARBY" : "SURVIVAL INVENTORY";
      el.nearTableBadge.textContent = nearby.table ? "Crafting table nearby" : "No table nearby";
      el.nearTableBadge.className = "status-badge " + (nearby.table ? "on" : "off");
      setTimeout(() => { if (el.seedInput) el.seedInput.blur(); }, 0);
    } else if (next === "furnace") {
      refreshFurnaceUI();
    } else if (next === "pause") {
      updatePauseUI();
    } else if (next === "dead") {
      el.deathBody.textContent = deathCause + " You wake up back at your spawn point. Your pockets are safe.";
    }
    mouse.down = false;
    mineTarget = null;
    if (next !== "playing") hideTooltip();
  }

  function pauseGame() {
    if (state !== "playing") return;
    saveGame(false);
    setState("pause");
  }

  function resumeGame() {
    BH.Sound.resume();
    setState("playing");
    lastFrame = performance.now();
  }

  function openInventory() {
    if (state !== "playing") return;
    BH.Sound.resume();
    updateNearby();
    setState("inventory");
    BH.Sound.click();
  }

  function closeInventory() {
    if (state !== "inventory") return;
    if (held) returnHeldStack();
    setState("playing");
    lastFrame = performance.now();
    BH.Sound.click();
  }

  function openFurnace() {
    if (state !== "playing") return;
    updateNearby();
    if (!nearby.furnace) {
      message("Stand beside a furnace to use it. Craft one with 8 cobblestone.", "#e0b18e", 3);
      return;
    }
    BH.Sound.resume();
    setState("furnace");
    BH.Sound.click();
  }

  function openHelp(from) {
    previousScreenForHelp = from || (state === "pause" ? "pause" : "title");
    setState("help");
  }

  function closeHelp() {
    if (state !== "help") return;
    setState(previousScreenForHelp || "title");
  }

  function askConfirm(title, body, yesLabel, cb) {
    confirmReturn = state === "confirm" ? "pause" : state;
    el.confirmTitle.textContent = title;
    el.confirmBody.textContent = body;
    el.confirmYes.textContent = yesLabel || "Confirm";
    confirmCallback = cb;
    setState("confirm");
  }

  function updatePauseUI() {
    el.pauseSeed.textContent = world.seedString;
    el.pauseDay.textContent = dayNumber();
    const depth = Math.max(0, Math.floor(player.y - world.groundAt(player.x)));
    el.pauseDepth.textContent = depth <= 0 ? "Surface" : depth + " blocks";
    el.pausePlaytime.textContent = formatPlaytime(playTime);
    el.pauseMined.textContent = stats.mined || 0;
    el.pauseZombies.textContent = stats.zombies || 0;
    el.pauseDeaths.textContent = stats.deaths || 0;
    el.btnPauseSound.textContent = "Sound: " + (BH.Sound.muted ? "Off" : "On");
  }

  function updateSoundLabels() {
    const label = "Sound: " + (BH.Sound.muted ? "Off" : "On");
    if (el.btnTitleSound) el.btnTitleSound.textContent = label;
    if (el.btnPauseSound) el.btnPauseSound.textContent = label;
  }

  function toggleSound() {
    BH.Sound.resume();
    BH.Sound.setMuted(!BH.Sound.muted);
    updateSoundLabels();
    if (!BH.Sound.muted) BH.Sound.click();
  }

  // ---------- inventory helpers ----------
  function makeItem(id, count, dur) {
    const def = BH.ITEM_DEFS[id];
    if (!def) return null;
    const it = { id, count: Math.max(1, Math.min(count || 1, def.stack || 64)) };
    if (def.durability) it.dur = dur === undefined ? def.durability : clamp(dur, 0, def.durability);
    return it;
  }

  function addItem(id, count, dur) {
    const def = BH.ITEM_DEFS[id];
    if (!def) return count;
    let left = Math.max(0, Math.floor(count));
    const max = def.stack || 64;
    if (max > 1) {
      for (let i = 0; i < player.inventory.length && left > 0; i++) {
        const it = player.inventory[i];
        if (it && it.id === id && it.count < max) {
          const take = Math.min(max - it.count, left);
          it.count += take;
          left -= take;
        }
      }
    }
    for (let i = 0; i < player.inventory.length && left > 0; i++) {
      if (!player.inventory[i]) {
        const take = Math.min(max, left);
        player.inventory[i] = { id, count: take };
        if (def.durability) player.inventory[i].dur = dur === undefined ? def.durability : clamp(dur, 0, def.durability);
        left -= take;
      }
    }
    if (left !== count) inventoryChanged();
    return left;
  }

  function canAddItem(id, count) {
    const def = BH.ITEM_DEFS[id];
    if (!def) return false;
    let cap = 0;
    const max = def.stack || 64;
    for (const it of player.inventory) {
      if (!it) cap += max;
      else if (it.id === id && max > 1) cap += Math.max(0, max - it.count);
      if (cap >= count) return true;
    }
    return cap >= count;
  }

  function countItem(id) {
    let n = 0;
    for (const it of player.inventory) if (it && it.id === id) n += it.count;
    return n;
  }

  function countAny(ids) {
    let n = 0;
    for (const it of player.inventory) if (it && ids.includes(it.id)) n += it.count;
    return n;
  }

  function takeItem(id, count) {
    let left = count;
    for (let i = 0; i < player.inventory.length && left > 0; i++) {
      const it = player.inventory[i];
      if (!it || it.id !== id) continue;
      const take = Math.min(it.count, left);
      it.count -= take;
      left -= take;
      if (it.count <= 0) player.inventory[i] = null;
    }
    if (left !== count) inventoryChanged();
    return count - left;
  }

  function takeAny(ids, count) {
    let left = count;
    for (const id of ids) {
      if (left <= 0) break;
      left -= takeItem(id, left);
    }
    return count - left;
  }

  function removeOneSelected() {
    const sel = player.inventory[player.selected];
    if (!sel) return null;
    sel.count--;
    const removed = { id: sel.id, count: 1, dur: sel.dur };
    if (sel.count <= 0) player.inventory[player.selected] = null;
    inventoryChanged();
    return removed;
  }

  function damageSelectedTool(amount) {
    const it = player.inventory[player.selected];
    if (!it) return;
    const def = BH.ITEM_DEFS[it.id];
    if (!def || !def.durability) return;
    it.dur = (it.dur === undefined ? def.durability : it.dur) - (amount || 1);
    if (it.dur <= 0) {
      message(def.name + " broke.", "#d79b7d", 3);
      player.inventory[player.selected] = null;
      BH.Sound.breakBlock(T.PLANKS);
    } else if (it.dur < def.durability * 0.15 && state === "playing") {
      // low-durability warning is shown on the hotbar itself
    }
    inventoryChanged();
  }

  function inventoryChanged() {
    if (state === "inventory") refreshInventoryUI();
    else if (state === "furnace") refreshFurnaceUI();
  }

  function hasIngredients(recipe) {
    for (const need of recipe.need) {
      const have = need.any ? countAny(need.any) : countItem(need.id);
      if (have < need.n) return false;
    }
    return true;
  }

  function missingText(recipe) {
    const parts = [];
    for (const need of recipe.need) {
      const have = need.any ? countAny(need.any) : countItem(need.id);
      const name = need.any ? need.any.map(id => BH.itemName(id)).join(" / ") : BH.itemName(need.id);
      if (have < need.n) parts.push((need.n - have) + " more " + name);
    }
    return parts.join(", ");
  }

  function canCraft(recipe) {
    return (!recipe.table || nearby.table) && hasIngredients(recipe) && canAddItem(recipe.out.id, recipe.out.n);
  }

  function craftRecipe(recipeId, many) {
    const recipe = BH.RECIPES.find(r => r.id === recipeId);
    if (!recipe) return;
    if (recipe.table && !nearby.table) {
      message("This recipe needs a crafting table nearby.", "#e1ad87", 3);
      return;
    }
    let made = 0;
    const count = many ? 32 : 1;
    for (let k = 0; k < count; k++) {
      if (!hasIngredients(recipe)) {
        if (made === 0) message("Missing: " + missingText(recipe), "#e1ad87", 3);
        break;
      }
      if (!canAddItem(recipe.out.id, recipe.out.n)) {
        if (made === 0) message("Your pockets are full.", "#e1ad87", 3);
        break;
      }
      for (const need of recipe.need) {
        if (need.any) takeAny(need.any, need.n);
        else takeItem(need.id, need.n);
      }
      addItem(recipe.out.id, recipe.out.n);
      made++;
      stats.crafted++;
    }
    if (made > 0) {
      BH.Sound.craft();
      message("Crafted " + BH.itemName(recipe.out.id) + (recipe.out.n > 1 ? " ×" + recipe.out.n : "") + (made > 1 ? " (" + made + ")" : ""), "#c8dfa3", 2.4);
      if (recipe.id === "table" && !hints.tableCrafted) {
        hints.tableCrafted = true;
        message("Place the crafting table with RIGHT-CLICK.", "#c8dfa3", 5);
      }
      if (recipe.out.id === I.WOOD_PICK) message("Wooden pickaxe ready. Stone and coal await.", "#c8dfa3", 4);
      // Newly crafted gear should be ready to use, not lost in the pockets.
      const outSlot = player.inventory.findIndex(it => it && it.id === recipe.out.id);
      if (outSlot >= 0 && outSlot < 9 && state === "inventory") {
        player.selected = outSlot;
        selectedFlash = 1.8;
      }
      refreshInventoryUI();
      refreshFurnaceUI();
    }
  }

  function smeltRecipe(recipeId) {
    const recipe = BH.SMELTS.find(r => r.id === recipeId);
    if (!recipe) return;
    if (countItem(recipe.in.id) < recipe.in.n) {
      message("Missing " + BH.itemName(recipe.in.id) + ".", "#e1ad87", 2.5);
      return;
    }
    const fuel = countAny([I.COAL, I.CHARCOAL]);
    if (fuel < 1) {
      message("The furnace needs coal or charcoal.", "#e1ad87", 2.5);
      return;
    }
    if (!canAddItem(recipe.out.id, recipe.out.n)) {
      message("Your pockets are full.", "#e1ad87", 2.5);
      return;
    }
    takeItem(recipe.in.id, recipe.in.n);
    if (countItem(I.COAL) > 0) takeItem(I.COAL, 1);
    else takeItem(I.CHARCOAL, 1);
    addItem(recipe.out.id, recipe.out.n);
    BH.Sound.craft();
    BH.Sound.noise(0.18, 0.04, 420, 0, 0.8);
    message("Smelted " + BH.itemName(recipe.out.id) + ".", "#e8c38b", 2.2);
    refreshFurnaceUI();
    refreshInventoryUI();
  }

  // ---------- inventory UI ----------
  function makeSlotDom(index) {
    const it = player.inventory[index];
    const b = document.createElement("button");
    b.className = "slot" + (index === player.selected && index < 9 ? " selected" : "");
    b.dataset.index = index;
    b.type = "button";
    if (!it) {
      b.setAttribute("aria-label", "Empty slot " + (index + 1));
      return b;
    }
    const def = BH.ITEM_DEFS[it.id];
    b.setAttribute("aria-label", (def ? def.name : "Item") + ", " + it.count);
    const icon = document.createElement("span");
    icon.className = "slot-icon";
    icon.style.backgroundImage = 'url("' + BH.iconOf(it.id) + '")';
    b.appendChild(icon);
    if (it.count > 1) {
      const c = document.createElement("span");
      c.className = "slot-count";
      c.textContent = it.count;
      b.appendChild(c);
    }
    if (def && def.durability && it.dur !== undefined && it.dur < def.durability) {
      const bar = document.createElement("span");
      bar.className = "slot-durability" + (it.dur < def.durability * 0.2 ? " critical" : it.dur < def.durability * 0.45 ? " low" : "");
      const fill = document.createElement("i");
      fill.style.width = Math.max(2, (it.dur / def.durability) * 100) + "%";
      bar.appendChild(fill);
      b.appendChild(bar);
    }
    return b;
  }

  function refreshInventoryUI() {
    if (!player) return;
    if (el.mainGrid) {
      el.mainGrid.innerHTML = "";
      for (let i = 9; i < 36; i++) el.mainGrid.appendChild(makeSlotDom(i));
    }
    if (el.invHotbar) {
      el.invHotbar.innerHTML = "";
      for (let i = 0; i < 9; i++) el.invHotbar.appendChild(makeSlotDom(i));
    }
    refreshRecipeList();
    updateHeldCursor();
  }

  function refreshRecipeList() {
    if (!el.recipeList) return;
    el.recipeList.innerHTML = "";
    let craftableCount = 0;
    for (const recipe of BH.RECIPES) {
      const tableOk = !recipe.table || nearby.table;
      const has = hasIngredients(recipe);
      const room = canAddItem(recipe.out.id, recipe.out.n);
      const ok = tableOk && has && room;
      if (ok) craftableCount++;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "recipe " + (ok ? "craftable" : (!tableOk ? "locked" : "missing"));
      b.dataset.recipe = recipe.id;
      const ic = document.createElement("span");
      ic.className = "recipe-icon";
      ic.style.backgroundImage = 'url("' + BH.iconOf(recipe.out.id) + '")';
      const copy = document.createElement("span");
      copy.className = "recipe-copy";
      const nm = document.createElement("span");
      nm.className = "recipe-name";
      nm.innerHTML = BH.itemName(recipe.out.id) + (recipe.out.n > 1 ? ' <span class="recipe-count">×' + recipe.out.n + "</span>" : "");
      const need = document.createElement("span");
      need.className = "recipe-need";
      const needParts = recipe.need.map(n => {
        const have = n.any ? countAny(n.any) : countItem(n.id);
        const label = n.n + " " + (n.any ? n.any.map(id => BH.itemName(id)).join("/") : BH.itemName(n.id));
        return '<span class="' + (have < n.n ? "no" : "") + '">' + label + "</span>";
      });
      need.innerHTML = needParts.join(" + ");
      copy.appendChild(nm);
      copy.appendChild(need);
      if (recipe.table) {
        const badge = document.createElement("span");
        badge.className = "recipe-badge table";
        badge.textContent = nearby.table ? "table nearby" : "needs table";
        copy.appendChild(badge);
      }
      const check = document.createElement("span");
      check.className = "recipe-check";
      check.textContent = ok ? "✓" : (recipe.table && !nearby.table ? "▣" : "·");
      b.appendChild(ic); b.appendChild(copy); b.appendChild(check);
      el.recipeList.appendChild(b);
    }
    if (el.recipeCount) el.recipeCount.textContent = craftableCount + "/" + BH.RECIPES.length;
  }

  function refreshFurnaceUI() {
    if (!el.furnaceList || !player) return;
    const fuel = countAny([I.COAL, I.CHARCOAL]);
    el.furnaceFuel.textContent = fuel + " Coal / Charcoal";
    el.furnaceList.innerHTML = "";
    for (const r of BH.SMELTS) {
      const have = countItem(r.in.id);
      const room = canAddItem(r.out.id, r.out.n);
      const ok = have >= r.in.n && fuel >= 1 && room;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "recipe " + (ok ? "craftable" : "missing");
      b.dataset.smelt = r.id;
      const ic = document.createElement("span");
      ic.className = "recipe-icon";
      ic.style.backgroundImage = 'url("' + BH.iconOf(r.out.id) + '")';
      const copy = document.createElement("span");
      copy.className = "recipe-copy";
      const nm = document.createElement("span");
      nm.className = "recipe-name";
      nm.textContent = BH.itemName(r.out.id);
      const need = document.createElement("span");
      need.className = "recipe-need";
      need.innerHTML = '<span class="' + (have < r.in.n ? "no" : "") + '">' + BH.itemName(r.in.id) + " ×" + r.in.n + '</span> + 1 Coal / Charcoal';
      copy.appendChild(nm); copy.appendChild(need);
      const check = document.createElement("span");
      check.className = "recipe-check";
      check.textContent = ok ? "✓" : "·";
      b.appendChild(ic); b.appendChild(copy); b.appendChild(check);
      el.furnaceList.appendChild(b);
    }
  }

  function showItemTooltip(index, x, y) {
    const it = player.inventory[index];
    if (!it) { hideTooltip(); return; }
    const def = BH.ITEM_DEFS[it.id];
    el.itemTooltip.innerHTML = "";
    const name = document.createElement("div");
    name.className = "tt-name";
    name.textContent = def ? def.name : "Item";
    const meta = document.createElement("div");
    meta.className = "tt-meta";
    let txt = "";
    if (def && def.durability) txt += "Durability " + it.dur + " / " + def.durability + " · ";
    if (def && def.tool) txt += capitalize(def.tool) + " · ";
    if (def && def.desc) txt += def.desc;
    if (!txt) txt = "A useful thing.";
    meta.textContent = txt;
    el.itemTooltip.appendChild(name);
    el.itemTooltip.appendChild(meta);
    el.itemTooltip.classList.remove("hidden");
    const tw = 220, th = 64;
    el.itemTooltip.style.left = Math.min(window.innerWidth - tw - 12, x + 18) + "px";
    el.itemTooltip.style.top = Math.min(window.innerHeight - th - 12, y + 18) + "px";
  }
  function hideTooltip() { if (el.itemTooltip) el.itemTooltip.classList.add("hidden"); }

  function updateHeldCursor() {
    if (!el.itemCursor) return;
    if (!held) { el.itemCursor.classList.add("hidden"); return; }
    el.itemCursor.classList.remove("hidden");
    el.itemCursor.style.backgroundImage = 'url("' + BH.iconOf(held.id) + '")';
    el.itemCursor.innerHTML = "";
    if (held.count > 1) {
      const c = document.createElement("span");
      c.className = "slot-count";
      c.textContent = held.count;
      el.itemCursor.appendChild(c);
    }
  }

  function returnHeldStack() {
    if (!held) return;
    const left = addItem(held.id, held.count, held.dur);
    if (left > 0) spawnDrop(held.id, left, player.x, player.y - 0.8, held.dur);
    held = null;
    updateHeldCursor();
    hideTooltip();
    refreshInventoryUI();
  }

  function handleSlotClick(index, button, shift) {
    const inv = player.inventory;
    if (shift) {
      const fromHotbar = index < 9;
      const item = inv[index];
      if (!item) return;
      const range = fromHotbar ? [9, 36] : [0, 9];
      let leftover = item.count;
      const max = BH.maxStack(item.id);
      for (let i = range[0]; i < range[1] && leftover > 0; i++) {
        const dst = inv[i];
        if (dst && dst.id === item.id && max > 1 && dst.count < max) {
          const n = Math.min(max - dst.count, leftover);
          dst.count += n; leftover -= n;
        }
      }
      for (let i = range[0]; i < range[1] && leftover > 0; i++) {
        if (!inv[i]) {
          inv[i] = { id: item.id, count: leftover, dur: item.dur };
          leftover = 0;
        }
      }
      if (leftover === 0) inv[index] = null;
      else item.count = leftover;
      BH.Sound.click();
      inventoryChanged();
      return;
    }

    if (!held) {
      if (!inv[index]) return;
      if (button === 2) {
        const take = Math.ceil(inv[index].count / 2);
        held = { id: inv[index].id, count: take, dur: inv[index].dur };
        inv[index].count -= take;
        if (inv[index].count <= 0) inv[index] = null;
      } else {
        held = inv[index];
        inv[index] = null;
      }
      BH.Sound.click();
      updateHeldCursor();
      refreshInventoryUI();
      return;
    }

    const dst = inv[index];
    if (!dst) {
      if (button === 2) {
        inv[index] = { id: held.id, count: 1, dur: held.dur };
        held.count--;
        if (held.count <= 0) held = null;
      } else {
        inv[index] = held;
        held = null;
      }
    } else if (dst.id === held.id && BH.maxStack(dst.id) > 1) {
      const max = BH.maxStack(dst.id);
      const n = button === 2 ? 1 : held.count;
      const take = Math.min(max - dst.count, n);
      dst.count += take; held.count -= take;
      if (held.count <= 0) held = null;
    } else {
      if (button === 2) {
        // Swap one with the stack under the cursor.
        const tmp = { id: dst.id, count: 1, dur: dst.dur };
        dst.count--;
        if (dst.count <= 0) inv[index] = held;
        else inv[index] = dst;
        if (inv[index] === dst) {
          const add = { id: tmp.id, count: 1, dur: tmp.dur };
          const left = addItem(add.id, add.count, add.dur);
          if (left) spawnDrop(add.id, left, player.x, player.y - 1);
        }
        held = null;
      } else {
        inv[index] = held;
        held = dst;
      }
    }
    BH.Sound.click();
    updateHeldCursor();
    refreshInventoryUI();
  }

  // ---------- nearby interactions ----------
  function updateNearby() {
    if (!world || !player) return;
    let table = false, furnace = false;
    const px = Math.floor(player.x), py = Math.floor(player.y);
    for (let y = py - 6; y <= py + 4; y++) {
      for (let x = px - 6; x <= px + 6; x++) {
        const t = world.get(x, y);
        if (t === T.TABLE) table = true;
        else if (t === T.FURNACE) furnace = true;
        if (table && furnace) break;
      }
      if (table && furnace) break;
    }
    nearby.table = table;
    nearby.furnace = furnace;
    if (table && !hints.tablePlaced) {
      hints.tablePlaced = true;
      message("Crafting table nearby. Better recipes unlocked.", "#c8dfa3", 3.5);
    }
  }

  // ---------- player actions ----------
  function tryJump() {
    jumpBuffer = 0.14;
  }

  function updatePlayer(dt) {
    if (!player) return;
    const moving = (keys.left ? -1 : 0) + (keys.right ? 1 : 0);
    const sprinting = keys.sprint && moving !== 0;
    const target = moving * (sprinting ? 7.3 : 4.8);
    const accel = player.onGround ? 55 : 20;
    player.vx = approach(player.vx, target, accel * dt * (moving ? 1 : 1.35));
    if (moving !== 0) player.face = moving;
    if (!keys.jump && player.vy < -4) player.vy += 28 * dt;

    jumpBuffer = Math.max(0, jumpBuffer - dt);
    coyote = player.onGround ? 0.11 : Math.max(0, coyote - dt);
    if (jumpBuffer > 0 && (player.onGround || coyote > 0)) {
      player.vy = -13.2;
      player.onGround = false;
      coyote = 0;
      jumpBuffer = 0;
      player.airTime = 0;
      player.fallTop = player.y;
      BH.Sound.jump();
    }

    const wasGround = player.onGround;
    moveBody(player, dt, 38);
    if (player.onGround) {
      if (!wasGround && player.airTime > 0.25) {
        const fall = player.y - player.fallTop;
        if (fall > 3.6) {
          const dmg = Math.floor(fall - 3);
          if (dmg > 0) hurtPlayer(dmg, fall > 9 ? "The fall was too far." : "You hit the ground hard.", 0);
          if (player.onGround) BH.Sound.land();
        }
      }
      player.airTime = 0;
      player.fallTop = player.y;
      if (Math.abs(player.vx) < 0.05) player.vx = 0;
    } else {
      player.airTime += dt;
      if (player.y < player.fallTop) player.fallTop = player.y;
    }

    if (player.onGround && Math.abs(player.vx) > 0.3) {
      player.walkTime += Math.abs(player.vx) * dt;
      player.stepTimer -= dt;
      if (player.stepTimer <= 0) {
        player.stepTimer = sprinting ? 0.25 : 0.36;
        BH.Sound.step(tileBelow(player.x, player.y));
        if (Math.random() < 0.5) {
          const ground = Math.floor(player.y + 0.05);
          for (let i = 0; i < 2; i++) {
            particles.push({
              x: player.x + (Math.random() - 0.5) * 0.5,
              y: player.y - 0.03,
              vx: (Math.random() - 0.5) * 0.5 - player.vx * 0.08,
              vy: -Math.random() * 0.5,
              life: 0.35, max: 0.35, size: 0.07,
              color: ["#79613c", "#4f673c", "#a58d62"][(Math.random() * 3) | 0],
              gravity: 3
            });
          }
        }
      }
    }

    player.swing = Math.max(0, player.swing - dt * 4.8);
    player.invuln = Math.max(0, player.invuln - dt);
    player.attackCd = Math.max(0, player.attackCd - dt);
    player.useCd = Math.max(0, player.useCd - dt);

    // Hunger: walking works up an appetite, idling barely does.
    let burn = 0.007;
    if (Math.abs(player.vx) > 0.2) burn += sprinting ? 0.037 : 0.016;
    if (!player.onGround) burn += 0.008;
    player.hunger = Math.max(0, player.hunger - burn * dt);

    if (player.hunger >= 16 && player.health < player.maxHealth &&
        player.onGround && Math.abs(player.vx) < 0.35) {
      player.regenTimer += dt;
      if (player.regenTimer > 8.5) {
        player.regenTimer = 0;
        player.health = Math.min(player.maxHealth, player.health + 1);
        player.hunger = Math.max(0, player.hunger - 1.25);
        hud.damageFlash = Math.max(0, hud.damageFlash * 0.4);
      }
    } else player.regenTimer = 0;

    if (player.hunger <= 0) {
      player.starveTimer += dt;
      if (player.starveTimer > 7) {
        player.starveTimer = 0;
        hurtPlayer(1, "Hunger wears you down.", 0);
      }
    } else player.starveTimer = 0;

    if (player.y > H + 3) hurtPlayer(999, "You fell out of the world.", 0);
    if (player.y < -6 || player.x < 1 || player.x > W - 1) {
      player.x = clamp(player.x, 2, W - 2);
    }

    updateMining(dt);
  }

  function moveBody(e, dt, gravity) {
    e.vy = Math.min(e.vy + gravity * dt, 44);
    const steps = clamp(Math.ceil(Math.max(Math.abs(e.vx), Math.abs(e.vy)) * dt / 0.35), 1, 6);
    const sdt = dt / steps;
    let hitWall = false;
    for (let s = 0; s < steps; s++) {
      // horizontal
      e.x += e.vx * sdt;
      let top = Math.floor(e.y - e.h + 0.001);
      let bottom = Math.floor(e.y - 0.001);
      if (e.vx > 0) {
        const tx = Math.floor(e.x + e.w / 2 - 0.0001);
        for (let ty = top; ty <= bottom; ty++) {
          if (world.isSolid(tx, ty)) {
            e.x = tx - e.w / 2 - 0.0001;
            e.vx = 0; hitWall = true; break;
          }
        }
      } else if (e.vx < 0) {
        const tx = Math.floor(e.x - e.w / 2 + 0.0001);
        for (let ty = top; ty <= bottom; ty++) {
          if (world.isSolid(tx, ty)) {
            e.x = tx + 1 + e.w / 2 + 0.0001;
            e.vx = 0; hitWall = true; break;
          }
        }
      }
      // vertical
      e.y += e.vy * sdt;
      e.onGround = false;
      if (e.vy >= 0) {
        const ty = Math.floor(e.y);
        const left = Math.floor(e.x - e.w / 2 + 0.001);
        const right = Math.floor(e.x + e.w / 2 - 0.001);
        for (let tx = left; tx <= right; tx++) {
          if (world.isSolid(tx, ty)) {
            e.y = ty;
            e.vy = 0;
            e.onGround = true;
            break;
          }
        }
      } else {
        const ty = Math.floor(e.y - e.h);
        const left = Math.floor(e.x - e.w / 2 + 0.001);
        const right = Math.floor(e.x + e.w / 2 - 0.001);
        for (let tx = left; tx <= right; tx++) {
          if (world.isSolid(tx, ty)) {
            e.y = ty + 1 + e.h + 0.0001;
            e.vy = 0;
            break;
          }
        }
      }
    }
    e.hitWall = hitWall;
    e.x = clamp(e.x, 2, W - 2);
  }

  // ---------- mining / building / using ----------
  function targetTile() {
    const wx = cam.x + (mouse.x - view.w / 2) / view.tile;
    const wy = cam.y + (mouse.y - view.h / 2) / view.tile;
    return { x: Math.floor(wx), y: Math.floor(wy), fx: wx - Math.floor(wx), fy: wy - Math.floor(wy) };
  }

  function canReach(tx, ty) {
    return centerDistToPlayer(tx + 0.5, ty + 0.5) <= BH.REACH;
  }

  function entityUnderMouse() {
    const wx = cam.x + (mouse.x - view.w / 2) / view.tile;
    const wy = cam.y + (mouse.y - view.h / 2) / view.tile;
    let best = null, bestD = Infinity;
    for (const e of entities) {
      if (e.dead) continue;
      if (wx >= e.x - e.w / 2 - 0.25 && wx <= e.x + e.w / 2 + 0.25 &&
          wy >= e.y - e.h - 0.2 && wy <= e.y + 0.15) {
        const d = dist2(wx, wy, e.x, e.y - e.h / 2);
        if (d < bestD) { bestD = d; best = e; }
      }
    }
    return best;
  }

  function updateMining(dt) {
    if (!mouse.down || !mouse.inside) { mineTarget = null; mineProgress = 0; return; }
    const mob = entityUnderMouse();
    if (mob && centerDistToPlayer(mob.x, mob.y - mob.h / 2) < BH.REACH + 0.8) {
      mineTarget = null; mineProgress = 0;
      if (player.attackCd <= 0) attackMob(mob);
      return;
    }
    const hit = targetTile();
    if (!hit || !canReach(hit.x, hit.y)) { mineTarget = null; mineProgress = 0; return; }
    const id = world.get(hit.x, hit.y);
    if (id === T.AIR || id === T.BEDROCK) { mineTarget = null; mineProgress = 0; return; }
    if (!mineTarget || mineTarget.x !== hit.x || mineTarget.y !== hit.y) {
      mineTarget = { x: hit.x, y: hit.y, id };
      mineProgress = 0;
    }
    const def = BH.TILE_DEFS[id];
    if (!def) return;
    const heldIt = player.inventory[player.selected];
    const heldDef = itemDef(heldIt);
    let speed = 1.45;
    if (def.tool === "pick" && heldDef && heldDef.tool === "pick") speed = Math.max(1, heldDef.speed);
    else if (def.tool === "axe" && heldDef && heldDef.tool === "axe") speed = Math.max(1, heldDef.speed);
    else if (def.tool === "shovel") speed = 1.45;
    if (def.tier > 0) {
      const tier = heldDef && heldDef.tool === "pick" ? heldDef.tier : 0;
      if (tier < def.tier) speed *= 0.25;
    }
    if (def.hard === Infinity) { mineTarget = null; return; }
    const duration = Math.max(0.035, def.hard / speed);
    mineProgress += dt / duration;
    digSoundTimer -= dt;
    mineParticleTimer -= dt;
    if (mineParticleTimer <= 0) {
      mineParticleTimer = 0.12;
      spawnBlockChip(hit.x, hit.y, id);
    }
    if (digSoundTimer <= 0) {
      digSoundTimer = 0.22;
      BH.Sound.dig(id);
    }
    if (mineProgress >= 1) {
      breakBlock(hit.x, hit.y, id, heldDef);
      mineProgress = 0;
      mineTarget = null;
    }
  }

  function breakBlock(tx, ty, id, heldDef) {
    const def = BH.TILE_DEFS[id];
    if (!def || id === T.BEDROCK) return;
    if (!world.set(tx, ty, T.AIR)) return;
    stats.mined++;
    spawnBlockBurst(tx, ty, id);
    BH.Sound.breakBlock(id);
    hud.shake = Math.max(hud.shake, 0.06);
    breakUnsupportedNeighbours(tx, ty);
    const pickTier = heldDef && heldDef.tool === "pick" ? heldDef.tier : 0;
    const wrongTier = def.tier > 0 && pickTier < def.tier;
    let dropId = def.drop;
    let dropCount = def.dropCount || 1;
    if (id === T.LEAVES) {
      dropId = T.LEAVES;
      dropCount = 1;
      if (Math.random() < 0.12) spawnDrop(I.APPLE, 1, tx + 0.5, ty + 0.3);
      if (Math.random() < 0.10) spawnDrop(I.STICK, 1, tx + 0.5, ty + 0.3);
    } else if (id === T.TALL_GRASS || id === T.ROSE || id === T.DANDELION || id === T.MUSHROOM) {
      dropId = id; dropCount = 1;
    } else if (id === T.GLASS) {
      dropId = T.GLASS; dropCount = 1;
    }
    if (!wrongTier && dropId > 0 && dropCount > 0) {
      const left = addItem(dropId, dropCount);
      if (left > 0) spawnDrop(dropId, left, tx + 0.5, ty + 0.3);
      else floaters.push({ text: "+" + dropCount + " " + BH.itemName(dropId), x: tx + 0.5, y: ty - 0.1, life: 1.1, max: 1.1, color: "#e9dfc3" });
      BH.Sound.pickup();
    } else if (wrongTier) {
      message("This needs a stronger pickaxe. Stone, iron, gold and diamond are tiered.", "#e1ad87", 3.4);
    }
    if (dropId === T.LOG && !hints.log) {
      hints.log = true;
      message("Press E to craft planks and sticks from your logs.", "#c8dfa3", 5);
    }
    if (def.tool === "pick" || def.tool === "axe") {
      if (heldDef && heldDef.tool === def.tool) damageSelectedTool(1);
    }
    updateNearby();
  }


  function attachedNeedsSupport(id) {
    return id === T.TORCH || id === T.ROSE || id === T.DANDELION ||
           id === T.TALL_GRASS || id === T.MUSHROOM;
  }

  function attachedSupported(x, y, id) {
    if (id === T.TORCH) {
      return world.isSolid(x - 1, y) || world.isSolid(x + 1, y) ||
             world.isSolid(x, y - 1) || world.isSolid(x, y + 1);
    }
    return world.isSolid(x, y + 1);
  }

  function breakUnsupportedNeighbours(tx, ty) {
    const around = [[tx, ty - 1], [tx - 1, ty], [tx + 1, ty], [tx, ty + 1]];
    for (const [x, y] of around) {
      const id = world.get(x, y);
      if (!attachedNeedsSupport(id) || attachedSupported(x, y, id)) continue;
      world.set(x, y, T.AIR);
      spawnBlockBurst(x, y, id);
      const left = addItem(id, 1);
      if (left > 0) spawnDrop(id, left, x + 0.5, y + 0.3);
      BH.Sound.breakBlock(id);
    }
  }

  function attackMob(mob) {
    if (!mob || mob.dead || player.attackCd > 0) return;
    const heldIt = player.inventory[player.selected];
    const heldDef = itemDef(heldIt);
    let dmg = 1;
    if (heldDef) {
      if (heldDef.tool === "sword") dmg = heldDef.damage;
      else if (heldDef.tool) dmg = 2;
      else if (heldDef.food) dmg = 1;
    }
    player.attackCd = 0.34;
    player.swing = 1;
    mob.hp -= dmg;
    mob.hurt = 0.22;
    mob.flash = 0.22;
    const dir = mob.x >= player.x ? 1 : -1;
    mob.vx += dir * 5.4;
    mob.vy = Math.min(mob.vy, -3.2);
    mob.flee = 5;
    hud.shake = Math.max(hud.shake, 0.12);
    BH.Sound.hurt();
    burstHit(mob.x, mob.y - mob.h / 2, "#bd5f4e");
    if (heldDef && heldDef.durability) damageSelectedTool(1);
    if (mob.hp <= 0) killMob(mob);
  }

  function killMob(mob) {
    mob.dead = true;
    if (mob.type === "pig") {
      BH.Sound.tone(430, 0.16, "sawtooth", 0.035, -190);
      BH.Sound.tone(300, 0.13, "square", 0.02, -80, 0.12);
      spawnDrop(I.RAW_PORK, 1 + (Math.random() < 0.35 ? 1 : 0), mob.x, mob.y - 0.4);
    } else {
      stats.zombies++;
      if (Math.random() < 0.24) spawnDrop(I.COAL, 1, mob.x, mob.y - 0.4);
      if (Math.random() < 0.09) spawnDrop(I.IRON_INGOT, 1, mob.x, mob.y - 0.4);
      message("Zombie defeated.", "#cbdda6", 1.8);
    }
    for (let i = 0; i < 8; i++) {
      particles.push({
        x: mob.x, y: mob.y - mob.h * 0.5,
        vx: (Math.random() - 0.5) * 6, vy: -Math.random() * 5,
        life: 0.7, max: 0.7, size: 0.11,
        color: mob.type === "pig" ? "#d98f8d" : "#517d50", gravity: 16
      });
    }
  }

  function hurtPlayer(amount, cause, knock) {
    if (state !== "playing" || player.invuln > 0 || player.health <= 0) return;
    player.health -= amount;
    player.invuln = 0.72;
    hud.damageFlash = 1;
    hud.shake = Math.max(hud.shake, 0.28);
    BH.Sound.hurt();
    burstHit(player.x, player.y - 0.9, "#b94b3e");
    if (knock) player.vx += knock;
    if (player.health <= 0) {
      player.health = 0;
      die(cause);
    }
  }

  function die(cause) {
    deathCause = cause || "You ran out of health.";
    stats.deaths++;
    player.vx = 0;
    player.vy = 0;
    mouse.down = false;
    mineTarget = null;
    saveGame(false);
    setState("dead");
    BH.Sound.hurt();
  }

  function placePlayerAtSpawn() {
    player.x = player.spawnX || world.spawnX;
    let y = (player.spawnY || world.spawnY) - 0.05;
    const tx = Math.floor(player.x);
    for (let i = 0; i < 20; i++) {
      const feetSolid = world.isSolid(tx, Math.floor(y - 0.05));
      const headSolid = world.isSolid(tx, Math.floor(y - player.h + 0.05));
      if (!feetSolid && !headSolid) break;
      y += 1;
    }
    player.y = y;
    player.vx = 0;
    player.vy = 0;
    player.airTime = 0;
    player.fallTop = y;
  }

  function respawn() {
    placePlayerAtSpawn();
    player.health = player.maxHealth;
    player.hunger = Math.max(15, player.hunger);
    player.invuln = 1.4;
    player.airTime = 0;
    player.fallTop = player.y;
    entities = entities.filter(e => e.type === "pig" || dist2(e.x, e.y, player.x, player.y) > 22 * 22);
    drops = [];
    particles = [];
    state = "playing";
    setState("playing");
    snapCamera();
    message("You wake up at your spawn. Your pockets are safe.", "#c8dfa3", 4);
    saveGame(false);
  }

  function placementTarget(hit, blockId) {
    const tx = hit.x, ty = hit.y;
    const targetId = world.get(tx, ty);
    let px = tx, py = ty;
    if (targetId !== T.AIR) {
      const sides = [
        { x: tx, y: ty - 1, d: hit.fy },
        { x: tx, y: ty + 1, d: 1 - hit.fy },
        { x: tx - 1, y: ty, d: hit.fx },
        { x: tx + 1, y: ty, d: 1 - hit.fx }
      ].sort((a, b) => a.d - b.d);
      px = sides[0].x; py = sides[0].y;
    }
    if (!canReach(px, py)) return null;
    if (world.get(px, py) !== T.AIR) return null;
    const support = world.isSolid(px - 1, py) || world.isSolid(px + 1, py) ||
                    world.isSolid(px, py - 1) || world.isSolid(px, py + 1);
    if (!support) return null;
    const bdef = BH.TILE_DEFS[blockId];
    if (bdef && bdef.solid) {
      const left = player.x - player.w / 2, right = player.x + player.w / 2;
      const top = player.y - player.h, bottom = player.y;
      if (px + 1 > left && px < right && py + 1 > top && py < bottom) return null;
    }
    return { x: px, y: py };
  }

  function useSelected() {
    if (player.useCd > 0) return;
    const hit = targetTile();
    const it = player.inventory[player.selected];
    const def = itemDef(it);
    const tx = hit.x, ty = hit.y;
    const targetId = world.get(tx, ty);
    // Interact with a table or furnace first (Shift places instead).
    if (!keys.sprint && canReach(tx, ty) && (targetId === T.TABLE || targetId === T.FURNACE)) {
      if (targetId === T.TABLE) openInventory();
      else openFurnace();
      return;
    }
    if (!it || !def) return;
    if (def.food) {
      if (player.hunger >= player.maxHealth - 0.1 && !def.heal) {
        message("You're not hungry.", "#d9cfb4", 2);
        return;
      }
      if (player.health >= player.maxHealth && player.hunger >= player.maxHealth && def.heal) {
        message("You already feel fine.", "#d9cfb4", 2);
        return;
      }
      player.hunger = Math.min(20, player.hunger + (def.food || 0));
      player.health = Math.min(player.maxHealth, player.health + (def.heal || 0));
      it.count--;
      if (it.count <= 0) player.inventory[player.selected] = null;
      player.useCd = 0.35;
      player.swing = 0.7;
      BH.Sound.eat();
      for (let i = 0; i < 5; i++) {
        particles.push({
          x: player.x + (Math.random() - 0.5) * 0.3, y: player.y - 1.2,
          vx: (Math.random() - 0.5) * 1.3, vy: -0.8 - Math.random(),
          life: 0.5, max: 0.5, size: 0.06, color: def.heal ? "#e6c15a" : "#b96150", gravity: 2
        });
      }
      message(def.name + " restored " + Math.round((def.food || 0) / 2) + " hunger.", "#d5e3b1", 2);
      inventoryChanged();
      return;
    }
    if (!def.block) return;
    const dest = placementTarget(hit, def.block);
    if (!dest) {
      const targetNow = world.get(tx, ty);
      if (targetNow === T.AIR) message("Place blocks against another block.", "#d9c7a7", 2.2);
      return;
    }
    const px = dest.x, py = dest.y;
    world.set(px, py, def.block);
    player.useCd = 0.14;
    player.swing = 0.8;
    it.count--;
    if (it.count <= 0) player.inventory[player.selected] = null;
    stats.placed++;
    BH.Sound.place();
    spawnPlaceBurst(px, py, def.block);
    if (def.block === T.TABLE && !hints.tablePlaced) hints.tablePlaced = true;
    updateNearby();
    inventoryChanged();
  }

  function dropSelected() {
    const it = player.inventory[player.selected];
    if (!it) return;
    it.count--;
    spawnDrop(it.id, 1, player.x + player.face * 0.35, player.y - 1.0, it.dur);
    if (it.count <= 0) player.inventory[player.selected] = null;
    inventoryChanged();
    BH.Sound.click();
  }

  // ---------- drops / particles ----------
  function spawnDrop(id, count, x, y, dur) {
    if (!BH.ITEM_DEFS[id] || count <= 0) return;
    const max = BH.maxStack(id);
    while (count > 0) {
      const n = Math.min(max, count);
      count -= n;
      drops.push({
        id, count: n, dur: dur === undefined ? (BH.ITEM_DEFS[id].durability || undefined) : dur,
        x, y, vx: (Math.random() - 0.5) * 3.8, vy: -3.2 - Math.random() * 2.4,
        w: 0.34, h: 0.34, age: 0, onGround: false, dead: false
      });
    }
    if (drops.length > 160) drops.splice(0, drops.length - 160);
  }

  function updateDrops(dt) {
    for (const d of drops) {
      if (d.dead) continue;
      d.age += dt;
      d.vx *= Math.pow(0.06, dt);
      const fall = d.vy;
      moveBody(d, dt, 24);
      if (d.onGround && fall > 7) { d.vy = -fall * 0.23; d.onGround = false; }
      if (d.age > 0.45) {
        const dx = player.x - d.x, dy = (player.y - 0.8) - d.y;
        const dist = Math.hypot(dx, dy);
        if (dist < 2.2) {
          d.vx += (dx / Math.max(0.2, dist)) * 20 * dt;
          d.vy += (dy / Math.max(0.2, dist)) * 16 * dt;
        }
        if (dist < 0.6 && canAddItem(d.id, d.count)) {
          const picked = d.count;
          const left = addItem(d.id, d.count, d.dur);
          if (left < picked) {
            d.count = left;
            BH.Sound.pickup();
            if (left <= 0) {
              d.dead = true;
              floaters.push({ text: "+" + picked + " " + BH.itemName(d.id), x: d.x, y: d.y, life: 1.0, max: 1.0, color: "#e9dfc3" });
            }
            inventoryChanged();
          }
        }
      }
      if (d.y > H + 2) d.dead = true;
    }
    drops = drops.filter(d => !d.dead);
  }

  function spawnBlockChip(tx, ty, id) {
    const palette = blockPalette(id);
    for (let i = 0; i < 2; i++) {
      particles.push({
        x: tx + 0.2 + Math.random() * 0.6,
        y: ty + 0.2 + Math.random() * 0.6,
        vx: (Math.random() - 0.5) * 2.6,
        vy: -Math.random() * 2.8,
        life: 0.3 + Math.random() * 0.25, max: 0.55, size: 0.05 + Math.random() * 0.06,
        color: palette[(Math.random() * palette.length) | 0], gravity: 10
      });
    }
  }

  function spawnBlockBurst(tx, ty, id) {
    const palette = blockPalette(id);
    for (let i = 0; i < 12; i++) {
      particles.push({
        x: tx + 0.5 + (Math.random() - 0.5) * 0.5,
        y: ty + 0.5 + (Math.random() - 0.5) * 0.5,
        vx: (Math.random() - 0.5) * 7,
        vy: -Math.random() * 5.5,
        life: 0.5 + Math.random() * 0.5, max: 1, size: 0.07 + Math.random() * 0.1,
        color: palette[(Math.random() * palette.length) | 0], gravity: 18
      });
    }
  }

  function spawnPlaceBurst(tx, ty, id) {
    const palette = blockPalette(id);
    for (let i = 0; i < 5; i++) {
      particles.push({
        x: tx + 0.2 + Math.random() * 0.6,
        y: ty + 0.7,
        vx: (Math.random() - 0.5) * 3, vy: -Math.random() * 1.5,
        life: 0.3, max: 0.3, size: 0.05, color: palette[0], gravity: 8
      });
    }
  }

  function burstHit(x, y, color) {
    for (let i = 0; i < 7; i++) {
      particles.push({
        x, y, vx: (Math.random() - 0.5) * 7, vy: -Math.random() * 5,
        life: 0.4 + Math.random() * 0.3, max: 0.7, size: 0.08,
        color, gravity: 16
      });
    }
  }

  function blockPalette(id) {
    const table = {
      [T.GRASS]: ["#5e9e3d", "#79553a", "#436f2b"],
      [T.DIRT]: ["#79553a", "#8e6845", "#5e402b"],
      [T.STONE]: ["#7b7e7d", "#8d908e", "#666a6b"],
      [T.COBBLE]: ["#888b88", "#a3a49f", "#666a69"],
      [T.SAND]: ["#d7c083", "#e5d29b", "#bda56e"],
      [T.SANDSTONE]: ["#cbb47c", "#ddc790", "#b39a63"],
      [T.LOG]: ["#6f4e2e", "#835f39", "#503720"],
      [T.LEAVES]: ["#467d34", "#5a9640", "#2f5f28"],
      [T.PLANKS]: ["#a47743", "#b98c52", "#79562f"],
      [T.COAL_ORE]: ["#2b2d2d", "#4b4d4c", "#7b7e7d"],
      [T.IRON_ORE]: ["#be8f67", "#7b7e7d", "#d2a47a"],
      [T.GOLD_ORE]: ["#e5b83e", "#7b7e7d", "#f3d05c"],
      [T.DIAMOND_ORE]: ["#5ad6cb", "#7b7e7d", "#82efe2"],
      [T.TORCH]: ["#e98d2c", "#6b4827", "#ffd569"],
      [T.TABLE]: ["#8d6337", "#b98a50", "#5d4024"],
      [T.FURNACE]: ["#777b7a", "#d8752b", "#5a5e5d"],
      [T.GLASS]: ["#c5f1f2", "#9fd2d8", "#e7ffff"],
      [T.GRAVEL]: ["#77726b", "#918b82", "#625e58"],
      [T.BRICKS]: ["#8d8f8b", "#a6a7a1", "#5b5d5c"],
      [T.LAMP]: ["#f4d477", "#fff3b3", "#d8a942"],
      [T.CACTUS]: ["#3f7c34", "#5a9c42", "#2b5b24"]
    };
    return table[id] || ["#8c826d", "#a4977e", "#6e6556"];
  }

  function updateParticles(dt) {
    for (const p of particles) {
      p.life -= dt;
      p.vy += (p.gravity || 0) * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    particles = particles.filter(p => p.life > 0);
    for (const f of floaters) {
      f.life -= dt;
      f.y -= dt * 0.8;
    }
    floaters = floaters.filter(f => f.life > 0);
  }

  // ---------- mobs ----------
  function makePig(x, y) {
    return {
      type: "pig", x, y, w: 0.9, h: 0.72, vx: 0, vy: 0, onGround: false,
      hp: 6, maxHp: 6, dir: Math.random() < 0.5 ? -1 : 1, timer: 1 + Math.random() * 3,
      flee: 0, hurt: 0, age: 0, dead: false, jumpCd: 0
    };
  }

  function makeZombie(x, y) {
    return {
      type: "zombie", x, y, w: 0.65, h: 1.78, vx: 0, vy: 0, onGround: false,
      hp: 12, maxHp: 12, dir: Math.random() < 0.5 ? -1 : 1, timer: 1,
      hurt: 0, burn: 0, attackCd: 0, age: 0, dead: false, moanCd: 2 + Math.random() * 5
    };
  }

  function spawnInitialPigs(count) {
    let made = 0, tries = 0;
    while (made < count && tries < 500) {
      tries++;
      const x = 18 + Math.floor(Math.random() * (W - 36));
      const gy = world.heights[x];
      if (world.get(x, gy) !== T.GRASS) continue;
      if (world.get(x, gy - 1) !== T.AIR || world.get(x, gy - 2) !== T.AIR) continue;
      if (Math.abs(x - world.spawnX) < 5) continue;
      entities.push(makePig(x + 0.5, gy));
      made++;
    }
  }

  function updateEntities(dt) {
    for (const e of entities) {
      if (e.dead) continue;
      e.age += dt;
      e.hurt = Math.max(0, e.hurt - dt);
      e.jumpCd = Math.max(0, (e.jumpCd || 0) - dt);
      if (e.type === "pig") updatePig(e, dt);
      else updateZombie(e, dt);
      moveBody(e, dt, 34);
      if (e.y > H + 2) e.dead = true;
    }
    entities = entities.filter(e => !e.dead);
  }

  function updatePig(e, dt) {
    e.flee = Math.max(0, e.flee - dt);
    e.timer -= dt;
    if (e.timer <= 0) {
      e.timer = 1.8 + Math.random() * 4.2;
      if (Math.random() < 0.32) e.vx = 0;
      else { e.dir = Math.random() < 0.5 ? -1 : 1; e.vx = e.dir * (1.0 + Math.random() * 1.0); }
    }
    if (e.flee > 0) {
      e.dir = player.x > e.x ? -1 : 1;
      e.vx = e.dir * 2.4;
      e.timer = 0.1;
    }
    if (e.vx !== 0) e.dir = Math.sign(e.vx);
    if (e.onGround && e.hitWall && e.jumpCd <= 0) {
      e.vy = -7.6;
      e.jumpCd = 0.8;
    }
    if (Math.abs(e.vx) < 0.02 && e.flee <= 0) e.vx = 0;
  }

  function updateZombie(e, dt) {
    const dx = player.x - e.x;
    const dy = (player.y - 0.9) - (e.y - e.h * 0.5);
    const dist = Math.hypot(dx, dy);
    e.attackCd = Math.max(0, e.attackCd - dt);
    e.moanCd -= dt;
    if (e.moanCd <= 0) {
      e.moanCd = 3.5 + Math.random() * 7;
      if (dist < 14) BH.Sound.zombie(clamp(1 - dist / 18, 0.15, 0.9));
    }
    if (dist < 18) {
      e.dir = dx >= 0 ? 1 : -1;
      e.vx = approach(e.vx, e.dir * 1.6, 8 * dt);
      if (e.onGround && (e.hitWall || (dy < -2 && Math.abs(dx) < 2.5))) {
        e.vy = -10.5;
      }
      if (Math.abs(dx) < 1.15 && Math.abs((player.y - player.h / 2) - (e.y - e.h / 2)) < 1.25 && e.attackCd <= 0) {
        e.attackCd = 1.15;
        const dmg = difficulty === "hard" ? 3 : 2;
        hurtPlayer(dmg, "A zombie got you.", dx > 0 ? -5 : 5);
        e.vx -= e.dir * 2;
      }
    } else {
      e.timer -= dt;
      if (e.timer <= 0) {
        e.timer = 2 + Math.random() * 4;
        e.dir = Math.random() < 0.5 ? -1 : 1;
      }
      e.vx = approach(e.vx, e.dir * 0.55, 4 * dt);
    }
    // Sunlight burns the restless dead.
    if (sunAltitude() > 0.02 && daylightFactor() > 0.55) {
      const headY = Math.floor(e.y - e.h + 0.2);
      const sky = world.sky[clamp(headY, 0, H - 1) * W + clamp(Math.floor(e.x), 0, W - 1)] || 0;
      if (sky > 9) {
        e.burn += dt;
        e.hp -= dt * 1.15;
        if (Math.random() < dt * 6) {
          particles.push({
            x: e.x + (Math.random() - 0.5) * 0.5, y: e.y - e.h + Math.random() * 0.8,
            vx: (Math.random() - 0.5) * 0.8, vy: -1 - Math.random(),
            life: 0.5, max: 0.5, size: 0.08, color: "#574b3b", gravity: -1
          });
        }
        if (e.hp <= 0) e.dead = true;
      }
    }
    if (dist > 48) e.dead = true;
  }

  function trySpawnZombies(dt) {
    if (difficulty === "peaceful" || !isNight() || state !== "playing") return;
    zombieTimer -= dt;
    if (zombieTimer > 0) return;
    zombieTimer = difficulty === "hard" ? 5 : 8;
    const cap = difficulty === "hard" ? 5 : 3;
    const count = entities.filter(e => e.type === "zombie" && !e.dead).length;
    if (count >= cap) return;
    for (let tries = 0; tries < 20; tries++) {
      const side = Math.random() < 0.5 ? -1 : 1;
      const dist = 11 + Math.floor(Math.random() * 19);
      const x = Math.floor(player.x) + side * dist;
      if (x < 4 || x >= W - 4) continue;
      const gy = world.heights[x];
      let ground = -1;
      for (let y = Math.max(5, gy - 8); y < H - 5; y++) {
        if (world.isSolid(x, y) && world.get(x, y) !== T.LEAVES && world.get(x, y) !== T.LOG) { ground = y; break; }
      }
      if (ground < 0) continue;
      if (world.get(x, ground - 1) !== T.AIR || world.get(x, ground - 2) !== T.AIR) continue;
      if (world.blockLight[ground * W + x] > 4) continue;
      entities.push(makeZombie(x + 0.5, ground));
      if (!hints.zombie) {
        hints.zombie = true;
        message("Something is groaning in the dark. Left-click to fight.", "#e0b18e", 4.2);
      }
      break;
    }
  }

  function trySpawnPigs(dt) {
    pigTimer -= dt;
    if (pigTimer > 0) return;
    pigTimer = 35;
    const pigs = entities.filter(e => e.type === "pig" && !e.dead).length;
    if (pigs >= 9) return;
    for (let tries = 0; tries < 8; tries++) {
      const x = Math.floor(player.x) + (Math.random() < 0.5 ? -1 : 1) * (18 + Math.floor(Math.random() * 20));
      if (x < 5 || x >= W - 5) continue;
      const gy = world.heights[x];
      if (world.get(x, gy) === T.GRASS && world.get(x, gy - 1) === T.AIR && world.get(x, gy - 2) === T.AIR) {
        entities.push(makePig(x + 0.5, gy));
        break;
      }
    }
  }

  // ---------- rendering setup ----------
  const ICON_IMG = {};
  function iconImage(id) {
    if (!ICON_IMG[id]) {
      const img = new Image();
      img.src = BH.iconOf(id);
      ICON_IMG[id] = img;
    }
    return ICON_IMG[id];
  }

  const stars = [];
  const clouds = [];
  let mapCanvas = null;
  let lightCanvas = null;
  let lightCtx = null;
  let lightImage = null;
  let caveTextures = [];
  let visibleRange = { x0: 0, x1: 0, y0: 0, y1: 0 };

  function buildSkyDecor() {
    const rng = BH.mulberry32(91357);
    stars.length = 0;
    for (let i = 0; i < 110; i++) {
      stars.push({
        x: rng(), y: rng() * 0.7, s: rng() < 0.18 ? 2 : 1,
        phase: rng() * TAU, alpha: 0.35 + rng() * 0.65
      });
    }
    clouds.length = 0;
    for (let i = 0; i < 9; i++) {
      clouds.push({
        x: rng(), y: 0.05 + rng() * 0.34, scale: 0.55 + rng() * 1.1,
        speed: 2.5 + rng() * 5.5, shade: rng()
      });
    }
  }

  function buildCaveTextures() {
    caveTextures = [];
    for (let v = 0; v < 4; v++) {
      const c = document.createElement("canvas");
      c.width = 16; c.height = 16;
      const g = c.getContext("2d");
      const rnd = BH.mulberry32(1177 + v * 97);
      g.fillStyle = v % 2 ? "#2c2721" : "#312b24";
      g.fillRect(0, 0, 16, 16);
      for (let i = 0; i < 46; i++) {
        const colors = ["#38322a", "#25211c", "#40382e", "#211e1a", "#342e27"];
        g.fillStyle = colors[(rnd() * colors.length) | 0];
        g.fillRect((rnd() * 16) | 0, (rnd() * 16) | 0, 1 + ((rnd() * 3) | 0), 1);
      }
      // faint damp streaks
      g.fillStyle = "rgba(20,28,28,.30)";
      for (let i = 0; i < 3; i++) g.fillRect((rnd() * 16) | 0, 3 + (rnd() * 9) | 0, 1, 2 + ((rnd() * 4) | 0));
      caveTextures.push(c);
    }
  }

  function buildMinimap() {
    if (!world) return;
    const mw = 320, mh = 144;
    mapCanvas = document.createElement("canvas");
    mapCanvas.width = mw; mapCanvas.height = mh;
    const g = mapCanvas.getContext("2d");
    g.imageSmoothingEnabled = false;
    const grad = g.createLinearGradient(0, 0, 0, mh);
    grad.addColorStop(0, "#1d2a31");
    grad.addColorStop(0.55, "#2b3432");
    grad.addColorStop(1, "#151513");
    g.fillStyle = grad;
    g.fillRect(0, 0, mw, mh);

    const topY = 26, botY = 142;
    for (let mx = 0; mx < mw; mx++) {
      const x = Math.floor((mx / mw) * W);
      const surface = world.heights[x];
      const y = Math.round(topY + ((surface - 34) / (H - 34)) * (botY - topY));
      const biome = world.biomes[x];
      // underground column
      g.fillStyle = biome === 2 ? "#695736" : "#493d2d";
      g.fillRect(mx, y + 2, 1, mh - y);
      g.fillStyle = biome === 2 ? "#d0b779" : biome === 1 ? "#4f8438" : "#659d42";
      g.fillRect(mx, y, 1, 2);
      // cave pinpricks
      for (let sy = 0; sy < 11; sy++) {
        const wy = Math.floor(surface + 5 + sy * 12);
        if (wy < H && world.get(x, wy) === T.AIR) {
          g.fillStyle = "rgba(14,15,16,.7)";
          g.fillRect(mx, y + 3 + Math.floor(sy * 1.5), 2, 2);
        }
      }
    }
    // soft haze + border ticks
    const haze = g.createLinearGradient(0, 0, 0, 34);
    haze.addColorStop(0, "rgba(180,211,219,.16)");
    haze.addColorStop(1, "rgba(180,211,219,0)");
    g.fillStyle = haze;
    g.fillRect(0, 0, mw, 34);
  }

  function resize() {
    view.w = Math.max(320, window.innerWidth);
    view.h = Math.max(240, window.innerHeight);
    view.dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.floor(view.w * view.dpr);
    canvas.height = Math.floor(view.h * view.dpr);
    canvas.style.width = view.w + "px";
    canvas.style.height = view.h + "px";
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    view.tile = clamp(Math.round(Math.min(view.w / 40, view.h / 23)), 26, 64);
    view.hud = clamp(view.h / 760, 0.82, 1.16);
    if (!mouse.x) { mouse.x = view.w / 2; mouse.y = view.h / 2; }
  }

  function snapCamera() {
    if (!player) return;
    const halfW = view.w / (2 * view.tile);
    const halfH = view.h / (2 * view.tile);
    cam.x = clamp(player.x, halfW + 0.2, W - halfW - 0.2);
    cam.y = clamp(player.y - 1.4, halfH + 0.2, H - halfH - 0.2);
  }

  function updateCamera(dt) {
    if (!player) return;
    const halfW = view.w / (2 * view.tile);
    const halfH = view.h / (2 * view.tile);
    let tx, ty;
    if (state === "title") {
      const drift = Math.sin(elapsed * 0.045) * 2.8 + Math.sin(elapsed * 0.013 + 2) * 1.6;
      tx = player.x + drift;
      ty = player.y - 3.2;
    } else {
      tx = player.x;
      ty = player.y - 1.7;
    }
    tx = clamp(tx, halfW + 0.2, W - halfW - 0.2);
    ty = clamp(ty, halfH * 0.25 + 2, H - halfH - 0.2);
    const smooth = state === "title" ? 1.2 : 7.5;
    const k = 1 - Math.exp(-smooth * dt);
    cam.x += (tx - cam.x) * k;
    cam.y += (ty - cam.y) * k;
  }

  const sxOf = wx => (wx - cam.x) * view.tile + view.w / 2;
  const syOf = wy => (wy - cam.y) * view.tile + view.h / 2;

  // ---------- sky ----------
  function drawSky() {
    const tod = timeOfDay();
    const sunny = sunAltitude();
    const day = daylightFactor();
    const twilight = Math.max(0, 1 - Math.abs(sunny) / 0.24) * BH.smoothstep(-0.35, 0.3, sunny + 0.14);
    const nightTop = [7, 13, 29];
    const nightBottom = [18, 28, 49];
    const dayTop = [62, 142, 205];
    const dayBottom = [169, 214, 234];
    let top = BH.mixColor(nightTop, dayTop, BH.smoothstep(0.12, 0.82, day));
    let bottom = BH.mixColor(nightBottom, dayBottom, BH.smoothstep(0.1, 0.9, day));
    const dusk = [224, 137, 85];
    const duskTop = [78, 80, 124];
    top = BH.mixColor(top, duskTop, twilight * 0.34);
    bottom = BH.mixColor(bottom, dusk, twilight * 0.66);

    const grad = ctx.createLinearGradient(0, 0, 0, view.h * 0.82);
    grad.addColorStop(0, BH.rgb(top));
    grad.addColorStop(0.58, BH.rgb(BH.mixColor(top, bottom, 0.72)));
    grad.addColorStop(1, BH.rgb(bottom));
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, view.w, view.h);

    // Stars
    const starAlpha = clamp(-sunny * 2.6, 0, 0.95);
    if (starAlpha > 0.02) {
      for (const s of stars) {
        const twinkle = 0.68 + 0.32 * Math.sin(elapsed * 1.7 + s.phase);
        ctx.fillStyle = "rgba(218,231,255," + (starAlpha * s.alpha * twinkle).toFixed(3) + ")";
        const x = Math.floor(s.x * view.w);
        ctx.fillRect(x, Math.floor(s.y * view.h * 0.68), s.s, s.s);
      }
    }

    // Sun / moon
    const horizon = view.h * 0.7;
    if (sunny > -0.11) {
      const p = BH.clamp(tod / 0.5, 0, 1);
      const x = view.w * (0.07 + 0.86 * p);
      const y = horizon - Math.sin(p * Math.PI) * view.h * 0.52;
      const r = Math.max(14, view.tile * 0.72);
      const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 5);
      glow.addColorStop(0, "rgba(255,241,185,.42)");
      glow.addColorStop(0.45, "rgba(255,210,115,.12)");
      glow.addColorStop(1, "rgba(255,190,90,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - r * 5, y - r * 5, r * 10, r * 10);
      ctx.fillStyle = "#fff0b1";
      ctx.fillRect(Math.round(x - r * 0.62), Math.round(y - r * 0.62), Math.round(r * 1.24), Math.round(r * 1.24));
      ctx.fillStyle = "rgba(255,255,235,.8)";
      ctx.fillRect(Math.round(x - r * 0.35), Math.round(y - r * 0.48), Math.round(r * 0.7), Math.round(r * 0.35));
    } else {
      const p = BH.clamp((tod - 0.5) / 0.5, 0, 1);
      const x = view.w * (0.08 + 0.84 * p);
      const y = horizon - Math.sin(p * Math.PI) * view.h * 0.42;
      const r = Math.max(12, view.tile * 0.58);
      const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 4);
      glow.addColorStop(0, "rgba(206,224,255,.22)");
      glow.addColorStop(1, "rgba(170,195,245,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - r * 4, y - r * 4, r * 8, r * 8);
      ctx.fillStyle = "#dce6ef";
      ctx.fillRect(Math.round(x - r * 0.7), Math.round(y - r * 0.7), Math.round(r * 1.4), Math.round(r * 1.4));
      ctx.fillStyle = "rgba(177,194,214,.75)";
      ctx.fillRect(Math.round(x - r * 0.3), Math.round(y - r * 0.48), Math.round(r * 0.42), Math.round(r * 0.42));
      ctx.fillRect(Math.round(x + r * 0.12), Math.round(y + r * 0.06), Math.round(r * 0.26), Math.round(r * 0.26));
    }

    // Blocky clouds
    const cloudAlpha = 0.10 + day * 0.50;
    for (const c of clouds) {
      const span = view.w + 360;
      let x = (c.x * span + elapsed * c.speed - cam.x * view.tile * 0.06) % span;
      if (x < -180) x += span;
      x -= 180;
      const y = view.h * c.y;
      const s = c.scale * view.tile;
      ctx.fillStyle = "rgba(242,246,241," + (cloudAlpha * 0.72).toFixed(3) + ")";
      ctx.fillRect(Math.round(x), Math.round(y), Math.round(s * 3.2), Math.round(s * 0.58));
      ctx.fillRect(Math.round(x + s * 0.5), Math.round(y - s * 0.36), Math.round(s * 2.2), Math.round(s * 0.56));
      ctx.fillRect(Math.round(x + s * 1.6), Math.round(y + s * 0.15), Math.round(s * 1.5), Math.round(s * 0.38));
      ctx.fillStyle = "rgba(157,175,183," + (cloudAlpha * 0.22).toFixed(3) + ")";
      ctx.fillRect(Math.round(x), Math.round(y + s * 0.42), Math.round(s * 3.2), Math.round(s * 0.18));
    }

    // Layered hills
    drawMountainLayer(0.12, view.h * 0.55, view.h * 0.22, [94, 124, 132], [31, 42, 62], 0.15);
    drawMountainLayer(0.55, view.h * 0.62, view.h * 0.18, [64, 93, 80], [25, 39, 33], 0.30);
    drawMountainLayer(1.15, view.h * 0.69, view.h * 0.12, [43, 69, 48], [17, 30, 23], 0.50);

    // Horizon haze
    const haze = ctx.createLinearGradient(0, view.h * 0.56, 0, view.h * 0.78);
    haze.addColorStop(0, "rgba(235,220,190,0)");
    haze.addColorStop(1, "rgba(214,196,160," + (0.08 + twilight * 0.12).toFixed(3) + ")");
    ctx.fillStyle = haze;
    ctx.fillRect(0, view.h * 0.56, view.w, view.h * 0.24);
  }

  function drawMountainLayer(offset, baseY, amp, colDay, colNight, parallax) {
    const day = daylightFactor();
    const sunrise = Math.max(0, 1 - Math.abs(sunAltitude()) / 0.3);
    const col = BH.mixColor(colNight, colDay, BH.smoothstep(0.05, 0.95, day));
    ctx.fillStyle = BH.rgb(BH.mixColor(col, [197, 123, 80], sunrise * 0.12));
    ctx.beginPath();
    ctx.moveTo(-20, view.h + 20);
    const step = Math.max(9, Math.round(view.tile * 0.45));
    for (let px = -20; px <= view.w + 20; px += step) {
      const wx = cam.x + (px - view.w / 2) / view.tile * parallax + offset;
      const n = BH.noise1(wx * 0.30 + offset, world.seed + 700) * 0.7 +
                BH.noise1(wx * 0.105 + offset * 2, world.seed + 800) * 0.3;
      const y = baseY - n * amp - Math.sin(wx * 0.7 + offset) * 3;
      ctx.lineTo(px, y);
    }
    ctx.lineTo(view.w + 20, view.h + 20);
    ctx.closePath();
    ctx.fill();

    // A few silhouette trees on the nearest layer.
    if (parallax > 1.2) {
      ctx.fillStyle = BH.rgb(BH.mixColor(col, [0, 0, 0], 0.12));
      for (let px = 20; px < view.w; px += 37) {
        const wx = cam.x + (px - view.w / 2) / view.tile * parallax + offset;
        const n = BH.noise1(wx * 0.30 + offset, world.seed + 700) * 0.7 +
                  BH.noise1(wx * 0.105 + offset * 2, world.seed + 800) * 0.3;
        const y = baseY - n * amp - Math.sin(wx * 0.7 + offset) * 3;
        ctx.fillRect(px, y - 10, 2, 10);
        ctx.fillRect(px - 4, y - 15, 10, 7);
      }
    }
  }

  // ---------- world rendering ----------
  function renderVisibleRange() {
    const halfW = view.w / (2 * view.tile);
    const halfH = view.h / (2 * view.tile);
    visibleRange.x0 = clamp(Math.floor(cam.x - halfW) - 1, 0, W - 1);
    visibleRange.x1 = clamp(Math.ceil(cam.x + halfW) + 1, 0, W - 1);
    visibleRange.y0 = clamp(Math.floor(cam.y - halfH) - 1, 0, H - 1);
    visibleRange.y1 = clamp(Math.ceil(cam.y + halfH) + 1, 0, H - 1);
  }

  function tileRect(x, y) {
    const x0 = Math.floor((x - cam.x) * view.tile + view.w / 2);
    const y0 = Math.floor((y - cam.y) * view.tile + view.h / 2);
    const x1 = Math.ceil((x + 1 - cam.x) * view.tile + view.w / 2);
    const y1 = Math.ceil((y + 1 - cam.y) * view.tile + view.h / 2);
    return [x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0)];
  }

  function drawCaveBackdrop() {
    const { x0, x1, y0, y1 } = visibleRange;
    for (let x = x0; x <= x1; x++) {
      const ground = world.heights[x];
      for (let y = Math.max(y0, ground); y <= y1; y++) {
        const i = y * W + x;
        if (world.sky[i] >= 12) continue;
        const [sx, sy, sw, sh] = tileRect(x, y);
        const tex = caveTextures[(BH.hash2i(x, y, world.seed + 71) & 3)];
        ctx.drawImage(tex, sx, sy, sw, sh);
        if (y > ground + 20) {
          ctx.fillStyle = "rgba(7,7,7," + Math.min(0.4, (y - ground - 20) / 150).toFixed(3) + ")";
          ctx.fillRect(sx, sy, sw, sh);
        }
      }
    }
  }

  function drawWorld() {
    const { x0, x1, y0, y1 } = visibleRange;
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const id = world.tiles[y * W + x];
        if (id === T.AIR) continue;
        const def = BH.TILE_DEFS[id];
        if (!def) continue;
        const variants = BH.TILE_TEX[id];
        if (!variants) continue;
        const v = BH.hash2i(x, y, world.seed + 17) % variants.length;
        const tex = variants[v];
        const [sx, sy, sw, sh] = tileRect(x, y);
        ctx.drawImage(tex, sx, sy, sw, sh);
        if (def.solid && sw > 8) {
          const above = world.get(x, y - 1);
          if (above === T.AIR && !BH.TILE_DEFS[above].solid) {
            ctx.fillStyle = "rgba(255,248,220,.055)";
            ctx.fillRect(sx, sy, sw, Math.max(1, Math.floor(sh * 0.08)));
          }
          const below = world.get(x, y + 1);
          if (below === T.AIR) {
            ctx.fillStyle = "rgba(0,0,0,.13)";
            ctx.fillRect(sx, sy + sh - Math.max(1, Math.floor(sh * 0.08)), sw, Math.max(1, Math.floor(sh * 0.08)));
          }
        }
      }
    }
  }

  function drawDrops() {
    for (const d of drops) {
      const img = iconImage(d.id);
      if (!img || !img.complete) continue;
      const bob = Math.sin(elapsed * 3.2 + d.x * 1.7) * view.tile * 0.06;
      const size = view.tile * 0.46;
      const x = sxOf(d.x) - size / 2;
      const y = syOf(d.y) - size - bob;
      ctx.fillStyle = "rgba(0,0,0,.24)";
      ctx.beginPath();
      ctx.ellipse(sxOf(d.x), syOf(d.y) + 1, size * 0.34, size * 0.13, 0, 0, TAU);
      ctx.fill();
      ctx.drawImage(img, Math.round(x), Math.round(y), Math.round(size), Math.round(size));
    }
  }

  function drawEntityList() {
    const list = [];
    for (const e of entities) if (!e.dead) list.push(e);
    list.push({ type: "player", y: player.y, x: player.x, player: true });
    list.sort((a, b) => a.y - b.y);
    for (const e of list) {
      if (e.player) drawPlayer();
      else if (e.type === "pig") drawPig(e);
      else drawZombie(e);
    }
  }

  function drawShadow(x, y, width, alpha) {
    ctx.fillStyle = "rgba(5,5,4," + (alpha || 0.24) + ")";
    ctx.beginPath();
    ctx.ellipse(sxOf(x), syOf(y) + 1, width, view.tile * 0.11, 0, 0, TAU);
    ctx.fill();
  }

  function drawPlayer() {
    const u = Math.max(1.4, view.tile / 17);
    const screenX = sxOf(player.x);
    const screenY = syOf(player.y);
    drawShadow(player.x, player.y, view.tile * 0.34, 0.27);
    const moving = Math.abs(player.vx) > 0.25 && player.onGround;
    const walk = moving ? Math.sin(player.walkTime * 11.5) : 0;
    const mining = mouse.down && mineTarget && state === "playing";
    const swing = mining ? 0.45 + 0.45 * Math.abs(Math.sin(elapsed * 8.5)) :
      (player.swing > 0 ? Math.sin(player.swing * Math.PI) : 0);

    ctx.save();
    ctx.translate(Math.round(screenX), Math.round(screenY));
    ctx.scale(player.face, 1);

    const outline = "#241b18";
    const skin = "#d49b66";
    const skinLight = "#e5b17b";
    const shirt = "#347f82";
    const shirtLight = "#409497";
    const pants = "#303f67";

    function box(x, y, w, h, color, edge) {
      ctx.fillStyle = edge || outline;
      ctx.fillRect(Math.round(x - u * 0.45), Math.round(y - u * 0.45), Math.round(w + u * 0.9), Math.round(h + u * 0.9));
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    }

    // legs
    const legA = walk * u * 1.5;
    box(-4 * u, -10 * u + Math.max(0, legA), 3.3 * u, 10 * u, pants);
    box(0.8 * u, -10 * u + Math.max(0, -legA), 3.3 * u, 10 * u, pants);
    box(-4.3 * u, -1.6 * u + Math.max(0, legA), 3.7 * u, 1.6 * u, "#201b1a");
    box(0.7 * u, -1.6 * u + Math.max(0, -legA), 3.7 * u, 1.6 * u, "#201b1a");

    // torso
    box(-4.6 * u, -20 * u, 9.2 * u, 10.6 * u, shirt);
    ctx.fillStyle = shirtLight;
    ctx.fillRect(Math.round(-4.2 * u), Math.round(-19.4 * u), Math.round(3.4 * u), Math.round(9 * u));
    ctx.fillStyle = "#2b686b";
    ctx.fillRect(Math.round(0.8 * u), Math.round(-19.6 * u), Math.round(3 * u), Math.round(8.4 * u));

    // arms
    const armSwing = walk * u * 2.1;
    const mineArm = swing * u * 3.4;
    box(-6.6 * u, -19.4 * u + armSwing, 2.4 * u, 9.4 * u, shirt);
    box(4.2 * u, -19.4 * u - armSwing - mineArm, 2.5 * u, 9.4 * u, shirtLight);
    box(-6.7 * u, -11.2 * u + armSwing, 2.6 * u, 2.2 * u, skin);
    box(4.1 * u, -11.2 * u - armSwing - mineArm, 2.7 * u, 2.2 * u, skinLight);

    // head
    box(-4.7 * u, -29.2 * u, 9.4 * u, 9.6 * u, skin);
    // hair / cap
    ctx.fillStyle = "#3b261a";
    ctx.fillRect(Math.round(-4.9 * u), Math.round(-29.6 * u), Math.round(9.8 * u), Math.round(3.2 * u));
    ctx.fillRect(Math.round(-4.9 * u), Math.round(-27 * u), Math.round(2 * u), Math.round(4.4 * u));
    ctx.fillStyle = "#503521";
    ctx.fillRect(Math.round(-4.7 * u), Math.round(-29.2 * u), Math.round(8.8 * u), Math.round(1.2 * u));
    // face
    ctx.fillStyle = "#e7ba83";
    ctx.fillRect(Math.round(2.1 * u), Math.round(-24.5 * u), Math.round(1.1 * u), Math.round(1.8 * u));
    ctx.fillStyle = "#2e2a31";
    ctx.fillRect(Math.round(2.2 * u), Math.round(-24.5 * u), Math.round(0.8 * u), Math.round(1.3 * u));
    ctx.fillStyle = "rgba(120,60,45,.7)";
    ctx.fillRect(Math.round(2.2 * u), Math.round(-21.6 * u), Math.round(1.8 * u), Math.round(0.55 * u));

    // held item
    const heldIt = player.inventory[player.selected];
    if (heldIt) {
      const img = iconImage(heldIt.id);
      if (img && img.complete) {
        ctx.save();
        ctx.translate(6.3 * u, -15.6 * u - mineArm - armSwing * 0.3);
        ctx.rotate(-0.35 - swing * 0.55);
        ctx.drawImage(img, -4.2 * u, -4.2 * u, 8.4 * u, 8.4 * u);
        ctx.restore();
      }
    }
    ctx.restore();
  }

  function drawZombie(e) {
    const u = Math.max(1.4, view.tile / 17);
    const screenX = sxOf(e.x);
    const screenY = syOf(e.y);
    drawShadow(e.x, e.y, view.tile * 0.32, 0.26);
    const walk = Math.abs(e.vx) > 0.15 ? Math.sin(e.age * 8) : Math.sin(elapsed * 2 + e.x) * 0.12;
    ctx.save();
    ctx.translate(Math.round(screenX), Math.round(screenY));
    ctx.scale(e.dir, 1);
    const flash = e.hurt > 0;
    const skin = flash ? "#b05c4e" : "#72945b";
    const skinDark = flash ? "#8d473b" : "#587344";
    const shirt = flash ? "#8d4c41" : "#395a54";
    const pants = flash ? "#6e413b" : "#33394f";
    function zbox(x, y, w, h, color) {
      ctx.fillStyle = "#231d1a";
      ctx.fillRect(Math.round(x - u * 0.45), Math.round(y - u * 0.45), Math.round(w + u * 0.9), Math.round(h + u * 0.9));
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    }
    const legA = walk * u * 1.3;
    zbox(-3.6 * u, -10 * u + Math.max(0, legA), 3 * u, 10 * u, pants);
    zbox(0.6 * u, -10 * u + Math.max(0, -legA), 3 * u, 10 * u, pants);
    zbox(-4.2 * u, -20 * u, 8.4 * u, 10.5 * u, shirt);
    // outstretched arms
    zbox(3.8 * u, -16 * u + Math.sin(elapsed * 5 + e.x) * u * 0.3, 6.8 * u, 2.5 * u, skinDark);
    zbox(-6.4 * u, -18 * u, 5.5 * u, 2.4 * u, skin);
    // head
    zbox(-4.5 * u, -28.5 * u, 9 * u, 8.8 * u, skin);
    ctx.fillStyle = "#2f3b25";
    ctx.fillRect(Math.round(-4.7 * u), Math.round(-28.8 * u), Math.round(9.4 * u), Math.round(2.4 * u));
    ctx.fillStyle = flash ? "#2b1c1b" : "#2e1e1b";
    ctx.fillRect(Math.round(1.5 * u), Math.round(-25.4 * u), Math.round(1.7 * u), Math.round(1.5 * u));
    ctx.fillRect(Math.round(3.6 * u), Math.round(-25.2 * u), Math.round(1.1 * u), Math.round(1.2 * u));
    ctx.fillStyle = "#55723f";
    ctx.fillRect(Math.round(2.2 * u), Math.round(-21.5 * u), Math.round(2.6 * u), Math.round(0.5 * u));
    // torn hem
    ctx.fillStyle = "#21302e";
    ctx.fillRect(Math.round(-4 * u), Math.round(-10.2 * u), Math.round(2 * u), Math.round(1.4 * u));
    ctx.restore();
    if (e.hp < e.maxHp) {
      const w = view.tile * 0.78;
      const x = screenX - w / 2;
      const y = screenY - e.h * view.tile - 7;
      ctx.fillStyle = "rgba(8,7,6,.8)";
      ctx.fillRect(x - 1, y - 1, w + 2, 5);
      ctx.fillStyle = "#b54d42";
      ctx.fillRect(x, y, w * clamp(e.hp / e.maxHp, 0, 1), 3);
    }
  }

  function drawPig(e) {
    const u = Math.max(1.4, view.tile / 17);
    const screenX = sxOf(e.x);
    const screenY = syOf(e.y);
    drawShadow(e.x, e.y, view.tile * 0.35, 0.24);
    const walk = Math.abs(e.vx) > 0.12 ? Math.sin(e.age * 9) : 0;
    const flash = e.hurt > 0;
    const pink = flash ? "#d96b61" : "#e59a96";
    const pinkDark = flash ? "#a84b47" : "#c87b7b";
    const snout = flash ? "#e58a7f" : "#f1b3ac";
    ctx.save();
    ctx.translate(Math.round(screenX), Math.round(screenY));
    ctx.scale(e.dir, 1);
    function pbox(x, y, w, h, color) {
      ctx.fillStyle = "#2a1d1b";
      ctx.fillRect(Math.round(x - u * 0.4), Math.round(y - u * 0.4), Math.round(w + u * 0.8), Math.round(h + u * 0.8));
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    }
    // legs
    pbox(-5.8 * u, -4 * u + Math.max(0, walk * u), 2.3 * u, 4 * u, pinkDark);
    pbox(-2.2 * u, -4 * u + Math.max(0, -walk * u), 2.3 * u, 4 * u, pinkDark);
    pbox(2.2 * u, -4 * u + Math.max(0, walk * u), 2.3 * u, 4 * u, pinkDark);
    pbox(4.8 * u, -4 * u + Math.max(0, -walk * u), 2.3 * u, 4 * u, pinkDark);
    // body
    pbox(-7 * u, -10 * u, 13.5 * u, 7 * u, pink);
    ctx.fillStyle = "rgba(255,211,202,.35)";
    ctx.fillRect(Math.round(-6 * u), Math.round(-9.4 * u), Math.round(10 * u), Math.round(1.4 * u));
    // head
    pbox(4.5 * u, -11 * u, 7 * u, 7.2 * u, pink);
    pbox(10 * u, -8.8 * u, 2.3 * u, 3.4 * u, snout);
    ctx.fillStyle = "#9f5d5c";
    ctx.fillRect(Math.round(10.7 * u), Math.round(-8 * u), Math.round(0.6 * u), Math.round(1.1 * u));
    ctx.fillRect(Math.round(11.5 * u), Math.round(-8 * u), Math.round(0.6 * u), Math.round(1.1 * u));
    // ear
    ctx.fillStyle = pinkDark;
    ctx.fillRect(Math.round(5.2 * u), Math.round(-12.5 * u), Math.round(2.3 * u), Math.round(2.2 * u));
    // eye
    ctx.fillStyle = "#2e2624";
    ctx.fillRect(Math.round(7.9 * u), Math.round(-10 * u), Math.round(1 * u), Math.round(1.3 * u));
    // tail
    ctx.strokeStyle = "#b86d70";
    ctx.lineWidth = Math.max(1.4, u * 0.7);
    ctx.beginPath();
    ctx.moveTo(-7 * u, -7 * u);
    ctx.quadraticCurveTo(-9 * u, -8.5 * u, -8.4 * u, -5.8 * u);
    ctx.stroke();
    ctx.restore();
    if (e.hp < e.maxHp) {
      const w = view.tile * 0.62;
      const x = screenX - w / 2;
      const y = screenY - e.h * view.tile - 7;
      ctx.fillStyle = "rgba(8,7,6,.8)";
      ctx.fillRect(x - 1, y - 1, w + 2, 5);
      ctx.fillStyle = "#cf5e55";
      ctx.fillRect(x, y, w * clamp(e.hp / e.maxHp, 0, 1), 3);
    }
  }

  function drawParticles(glowPass) {
    for (const p of particles) {
      if (!!p.glow !== glowPass) continue;
      const x = sxOf(p.x), y = syOf(p.y);
      const s = Math.max(1, p.size * view.tile);
      const alpha = clamp(p.life / p.max, 0, 1);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      if (p.glow) {
        ctx.globalCompositeOperation = "lighter";
        const g = ctx.createRadialGradient(x, y, 0, x, y, Math.max(2, s * 2.8));
        g.addColorStop(0, p.color);
        g.addColorStop(1, "rgba(90,120,40,0)");
        ctx.fillStyle = g;
        ctx.fillRect(x - s * 3, y - s * 3, s * 6, s * 6);
        ctx.globalCompositeOperation = "source-over";
      }
      ctx.fillRect(Math.round(x - s / 2), Math.round(y - s / 2), Math.ceil(s), Math.ceil(s));
      ctx.globalAlpha = 1;
    }
  }

  function drawLighting() {
    const { x0, x1, y0, y1 } = visibleRange;
    const lw = x1 - x0 + 1;
    const lh = y1 - y0 + 1;
    if (lw <= 0 || lh <= 0) return;
    if (!lightCanvas) {
      lightCanvas = document.createElement("canvas");
      lightCtx = lightCanvas.getContext("2d");
    }
    if (lightCanvas.width !== lw || lightCanvas.height !== lh) {
      lightCanvas.width = lw;
      lightCanvas.height = lh;
      lightImage = lightCtx.createImageData(lw, lh);
    }
    if (!lightImage) lightImage = lightCtx.createImageData(lw, lh);
    const data = lightImage.data;
    const skyFactor = daylightFactor();
    let p = 0;
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const l = world.lightAt(x, y, skyFactor);
        let dark = 1 - (0.075 + 0.925 * Math.pow(l, 0.62));
        dark = clamp(dark, 0, 0.82);
        data[p] = 6;
        data[p + 1] = 9;
        data[p + 2] = 18;
        data[p + 3] = Math.round(dark * 255);
        p += 4;
      }
    }
    lightCtx.putImageData(lightImage, 0, 0);
    const dx = sxOf(x0 + 0.5) - view.tile / 2;
    const dy = syOf(y0 + 0.5) - view.tile / 2;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "low";
    ctx.drawImage(lightCanvas, dx, dy, lw * view.tile, lh * view.tile);
    ctx.imageSmoothingEnabled = false;
  }

  function drawTorchGlows() {
    const { x0, x1, y0, y1 } = visibleRange;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const id = world.get(x, y);
        const def = BH.TILE_DEFS[id];
        if (!def || !def.light) continue;
        const cx = sxOf(x + 0.5);
        const cy = syOf(y + (id === T.TORCH ? 0.35 : 0.5));
        const flicker = 0.92 + Math.sin(elapsed * 11 + x * 2.3 + y) * 0.06;
        const r = view.tile * (id === T.LAMP ? 2.7 : 2.25) * flicker;
        const warm = id === T.LAMP ? [255, 244, 180] : [255, 181, 93];
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        g.addColorStop(0, "rgba(" + warm[0] + "," + warm[1] + "," + warm[2] + ",.18)");
        g.addColorStop(0.45, "rgba(" + warm[0] + "," + warm[1] + "," + warm[2] + ",.075)");
        g.addColorStop(1, "rgba(" + warm[0] + "," + warm[1] + "," + warm[2] + ",0)");
        ctx.fillStyle = g;
        ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
      }
    }
    ctx.restore();
  }

  function drawMiningAndSelection() {
    if (state !== "playing") return;
    const hit = targetTile();
    if (!hit || !canReach(hit.x, hit.y) || hit.x < 0 || hit.x >= W || hit.y < 0 || hit.y >= H) return;
    const id = world.get(hit.x, hit.y);
    if (id !== T.AIR) {
      const [sx, sy, sw, sh] = tileRect(hit.x, hit.y);
      if (mineTarget && mineTarget.x === hit.x && mineTarget.y === hit.y && mineProgress > 0.02) {
        drawCracks(sx, sy, sw, sh, mineTarget.x, mineTarget.y, mineProgress);
      }
      ctx.strokeStyle = "rgba(255,248,224,.68)";
      ctx.lineWidth = Math.max(1, Math.round(view.tile / 22));
      ctx.strokeRect(sx + 1, sy + 1, sw - 2, sh - 2);
      ctx.fillStyle = "rgba(255,248,224,.75)";
      const c = Math.max(2, Math.round(view.tile * 0.09));
      ctx.fillRect(sx - 1, sy - 1, c, 2); ctx.fillRect(sx - 1, sy - 1, 2, c);
      ctx.fillRect(sx + sw - c + 1, sy - 1, c, 2); ctx.fillRect(sx + sw - 1, sy - 1, 2, c);
      ctx.fillRect(sx - 1, sy + sh - 1, c, 2); ctx.fillRect(sx - 1, sy + sh - c + 1, 2, c);
      ctx.fillRect(sx + sw - c + 1, sy + sh - 1, c, 2); ctx.fillRect(sx + sw - 1, sy + sh - c + 1, 2, c);
    }

    // A ghost preview of the block that a right-click would place.
    const heldIt = player.inventory[player.selected];
    const heldDef = itemDef(heldIt);
    const interactive = id === T.TABLE || id === T.FURNACE;
    if (heldDef && heldDef.block && !(interactive && !keys.sprint)) {
      const dest = placementTarget(hit, heldDef.block);
      if (dest) {
        const [gx, gy, gw, gh] = tileRect(dest.x, dest.y);
        const tex = BH.TILE_TEX[heldDef.block] && BH.TILE_TEX[heldDef.block][0];
        if (tex) {
          ctx.globalAlpha = 0.42;
          ctx.drawImage(tex, gx, gy, gw, gh);
          ctx.globalAlpha = 1;
        }
        ctx.strokeStyle = "rgba(190,224,154,.85)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(gx + 1, gy + 1, gw - 2, gh - 2);
      }
    }
  }

  function drawCracks(sx, sy, sw, sh, tx, ty, progress) {
    const stage = clamp(Math.floor(progress * 6), 1, 5);
    const rnd = BH.mulberry32(BH.hash2i(tx, ty, world.seed + 999));
    ctx.save();
    ctx.beginPath();
    ctx.rect(sx, sy, sw, sh);
    ctx.clip();
    ctx.strokeStyle = "rgba(17,13,9,.70)";
    ctx.lineWidth = Math.max(1, view.tile / 18);
    for (let i = 0; i < stage + 1; i++) {
      const edge = Math.floor(rnd() * 4);
      let x = sx + sw * (0.2 + rnd() * 0.6);
      let y = sy + sh * (0.2 + rnd() * 0.6);
      ctx.beginPath();
      ctx.moveTo(x, y);
      for (let k = 0; k < 2 + stage; k++) {
        x += (rnd() - 0.5) * sw * 0.42;
        y += (rnd() - 0.5) * sh * 0.42;
        if (edge === 0) x -= sw * 0.08;
        if (edge === 1) y -= sh * 0.08;
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawFloaters() {
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const f of floaters) {
      const a = clamp(f.life / f.max, 0, 1);
      ctx.globalAlpha = a;
      ctx.font = '700 ' + Math.round(10 * view.hud) + 'px "Courier New", monospace';
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(8,7,6,.75)";
      ctx.strokeText(f.text, sxOf(f.x), syOf(f.y));
      ctx.fillStyle = f.color || "#efe4ca";
      ctx.fillText(f.text, sxOf(f.x), syOf(f.y));
      ctx.globalAlpha = 1;
    }
    ctx.textAlign = "left";
  }

  // ---------- HUD ----------
  function panel(x, y, w, h, alpha) {
    ctx.fillStyle = "rgba(9,11,10," + (alpha === undefined ? 0.7 : alpha) + ")";
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    ctx.strokeStyle = "rgba(139,118,88,.42)";
    ctx.lineWidth = 1;
    ctx.strokeRect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(w) - 1, Math.round(h) - 1);
    ctx.fillStyle = "rgba(255,244,218,.09)";
    ctx.fillRect(Math.round(x) + 1, Math.round(y) + 1, Math.round(w) - 2, 1);
  }

  function hotbarLayout() {
    const ui = view.hud;
    const gap = 4;
    const maxByWidth = Math.floor((view.w - 28 - 8 * gap) / 9);
    const s = clamp(Math.round(47 * ui), 26, Math.min(55, maxByWidth));
    const total = 9 * s + 8 * gap;
    return { s, gap, total, x: (view.w - total) / 2, y: view.h - s - Math.max(12, 16 * ui) };
  }

  function drawHUD() {
    if (state !== "playing" || !player) return;
    const ui = view.hud;
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "left";

    // coordinates / day panel
    const px = 16 * ui, py = 16 * ui;
    panel(px, py, 190 * ui, 65 * ui, 0.66);
    ctx.font = '700 ' + Math.round(8 * ui) + 'px "Courier New", monospace';
    ctx.fillStyle = "#a59a83";
    ctx.fillText("DAY " + dayNumber() + "  ·  " + world.biomeAt(player.x).toUpperCase(), px + 9 * ui, py + 14 * ui);
    ctx.font = '700 ' + Math.round(18 * ui) + 'px "Courier New", monospace';
    ctx.fillStyle = "#eee2c7";
    ctx.fillText(formatClock(timeOfDay()), px + 9 * ui, py + 34 * ui);
    ctx.font = '700 ' + Math.round(8 * ui) + 'px "Courier New", monospace';
    ctx.fillStyle = "#8f8777";
    const depth = Math.max(0, Math.floor(player.y - world.groundAt(player.x)));
    ctx.fillText("X " + Math.floor(player.x) + "   Y " + Math.floor(player.y) + (depth > 0 ? "   DEPTH " + depth : "   SURFACE"), px + 9 * ui, py + 51 * ui);

    // day/night tick
    const tod = timeOfDay();
    const barX = px + 132 * ui, barY = py + 12 * ui, barW = 46 * ui, barH = 7 * ui;
    ctx.fillStyle = "rgba(15,17,18,.8)";
    ctx.fillRect(barX, barY, barW, barH);
    ctx.fillStyle = isNight() ? "#7793c7" : "#e5bd6b";
    ctx.fillRect(barX + 1, barY + 1, (barW - 2) * tod, barH - 2);
    ctx.fillStyle = "rgba(255,248,220,.7)";
    const markerX = barX + 1 + (barW - 2) * tod;
    ctx.fillRect(markerX, barY - 1, 1.5, barH + 2);

    // minimap
    if (view.w > 720 && mapCanvas) {
      const mw = 168 * ui, mh = 93 * ui;
      const mx = view.w - mw - 16 * ui, my = 16 * ui;
      panel(mx, my, mw, mh, 0.7);
      ctx.font = '700 ' + Math.round(7.5 * ui) + 'px "Courier New", monospace';
      ctx.fillStyle = "#a89d86";
      ctx.fillText("SURFACE MAP", mx + 7 * ui, my + 11 * ui);
      const iw = mw - 12 * ui, ih = mh - 20 * ui;
      ctx.drawImage(mapCanvas, mx + 6 * ui, my + 15 * ui, iw, ih);
      // player marker
      const pmx = mx + 6 * ui + (player.x / W) * iw;
      const pmy = my + 15 * ui + ((player.y - 34) / (H - 34)) * ih;
      ctx.fillStyle = "#f7efcf";
      ctx.fillRect(pmx - 2, pmy - 3, 4, 7);
      ctx.fillStyle = "#1b1b17";
      ctx.fillRect(pmx - 1, pmy - 2, 2, 2);
      // mob markers
      for (const e of entities) {
        if (e.type !== "zombie") continue;
        const ex = mx + 6 * ui + (e.x / W) * iw;
        const ey = my + 15 * ui + ((e.y - 34) / (H - 34)) * ih;
        ctx.fillStyle = "#d36556";
        ctx.fillRect(ex - 1, ey - 1, 3, 3);
      }
      ctx.strokeStyle = "rgba(143,123,91,.5)";
      ctx.strokeRect(mx + 6 * ui + 0.5, my + 15 * ui + 0.5, iw - 1, ih - 1);
    }

    // save flash
    if (hud.saveFlash > 0) {
      const a = clamp(hud.saveFlash, 0, 1);
      ctx.globalAlpha = a;
      ctx.font = '700 ' + Math.round(8 * ui) + 'px "Courier New", monospace';
      ctx.fillStyle = "#98b77a";
      ctx.textAlign = "right";
      ctx.fillText("● SAVED", view.w - 18 * ui, view.h - 12 * ui);
      ctx.textAlign = "left";
      ctx.globalAlpha = 1;
    }

    const hb = hotbarLayout();
    hud.hotbar = [];
    const hotbarY = hb.y;
    panel(hb.x - 6, hotbarY - 6, hb.total + 12, hb.s + 12, 0.78);
    for (let i = 0; i < 9; i++) {
      const x = hb.x + i * (hb.s + hb.gap);
      const selected = i === player.selected;
      if (selected) {
        ctx.fillStyle = "rgba(232,218,176,.18)";
        ctx.fillRect(x - 2, hotbarY - 2, hb.s + 4, hb.s + 4);
      }
      ctx.fillStyle = "rgba(19,16,12,.9)";
      ctx.fillRect(x, hotbarY, hb.s, hb.s);
      ctx.strokeStyle = selected ? "#f0e1b4" : "rgba(116,95,68,.72)";
      ctx.lineWidth = selected ? 2 : 1;
      ctx.strokeRect(x + 0.5, hotbarY + 0.5, hb.s - 1, hb.s - 1);
      if (!selected) {
        ctx.fillStyle = "rgba(255,244,218,.06)";
        ctx.fillRect(x + 1, hotbarY + 1, hb.s - 2, 2);
      }
      const it = player.inventory[i];
      if (it) {
        const img = iconImage(it.id);
        if (img && img.complete) {
          const isize = Math.round(hb.s * 0.72);
          ctx.drawImage(img, Math.round(x + (hb.s - isize) / 2), Math.round(hotbarY + (hb.s - isize) / 2), isize, isize);
        }
        if (it.count > 1) {
          ctx.font = '700 ' + Math.round(hb.s * 0.25) + 'px "Courier New", monospace';
          ctx.textAlign = "right";
          drawShadowText(String(it.count), x + hb.s - 3, hotbarY + hb.s - 3, "#fff8e7", "rgba(0,0,0,.85)");
          ctx.textAlign = "left";
        }
        const def = BH.ITEM_DEFS[it.id];
        if (def && def.durability && it.dur !== undefined && it.dur < def.durability) {
          const w = hb.s - 8;
          ctx.fillStyle = "rgba(8,8,7,.9)";
          ctx.fillRect(x + 4, hotbarY + hb.s - 6, w, 3);
          ctx.fillStyle = it.dur < def.durability * 0.2 ? "#d05745" : it.dur < def.durability * 0.45 ? "#d2b14c" : "#7fc25d";
          ctx.fillRect(x + 4, hotbarY + hb.s - 6, Math.max(2, w * it.dur / def.durability), 3);
        }
      }
      ctx.font = '700 ' + Math.round(7.5 * ui) + 'px "Courier New", monospace';
      ctx.fillStyle = selected ? "#c8b98e" : "#6f6656";
      ctx.fillText(String(i + 1), x + 4, hotbarY + 9 * ui);
      hud.hotbar.push({ x, y: hotbarY, w: hb.s, h: hb.s, i });
    }

    // selected item name
    if (selectedFlash > 0) {
      const it = player.inventory[player.selected];
      if (it) {
        ctx.globalAlpha = clamp(selectedFlash, 0, 1);
        ctx.textAlign = "center";
        ctx.font = '700 ' + Math.round(11 * ui) + 'px "Courier New", monospace';
        drawShadowText(BH.itemName(it.id), view.w / 2, hotbarY - 28 * ui, "#f1e6cc", "rgba(0,0,0,.8)");
        ctx.textAlign = "left";
        ctx.globalAlpha = 1;
      }
    }

    // health & hunger
    const cell = Math.max(1.5, 1.85 * ui);
    const heartW = 7 * cell, heartH = 6 * cell;
    const leftGroup = 10 * (heartW + 2.3 * ui);
    const hx = view.w / 2 - leftGroup - 14 * ui;
    const hy = hotbarY - 22 * ui;
    panel(hx - 6 * ui, hy - 5 * ui, leftGroup + 10 * ui, heartH + 9 * ui, 0.5);
    for (let i = 0; i < 10; i++) {
      drawHeart(hx + i * (heartW + 2.3 * ui), hy, cell, clamp((player.health / 2 - i), 0, 1));
    }
    const hgx = view.w / 2 + 10 * ui;
    panel(hgx - 4 * ui, hy - 5 * ui, leftGroup + 6 * ui, heartH + 9 * ui, 0.5);
    for (let i = 0; i < 10; i++) {
      drawHunger(hgx + i * (heartW + 2.3 * ui), hy, cell, clamp(player.hunger / 2 - i, 0, 1));
    }

    // prompts
    if (nearby.furnace || nearby.table) {
      ctx.textAlign = "center";
      ctx.font = '700 ' + Math.round(8.5 * ui) + 'px "Courier New", monospace';
      const text = nearby.furnace ? "R  USE FURNACE     E  INVENTORY" : "E  CRAFTING TABLE NEARBY";
      drawShadowText(text, view.w / 2, hotbarY - 53 * ui, "#d8cba9", "rgba(0,0,0,.85)");
      ctx.textAlign = "left";
    }

    drawMessages(ui);
  }

  function drawHeart(x, y, cell, fill) {
    const shape = [
      [0,1,1,0,1,1,0],
      [1,1,1,1,1,1,1],
      [1,1,1,1,1,1,1],
      [0,1,1,1,1,1,0],
      [0,0,1,1,1,0,0],
      [0,0,0,1,0,0,0]
    ];
    for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
      if (!shape[r][c]) continue;
      ctx.fillStyle = "#553a35";
      ctx.fillRect(Math.round(x + c * cell), Math.round(y + r * cell), Math.ceil(cell), Math.ceil(cell));
    }
    if (fill <= 0) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, 7 * cell * fill, 6 * cell);
    ctx.clip();
    for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
      if (!shape[r][c]) continue;
      ctx.fillStyle = r === 1 && c < 4 ? "#ee7665" : "#c84f48";
      ctx.fillRect(Math.round(x + c * cell), Math.round(y + r * cell), Math.ceil(cell), Math.ceil(cell));
    }
    ctx.fillStyle = "rgba(255,210,190,.7)";
    ctx.fillRect(Math.round(x + 2 * cell), Math.round(y + 1 * cell), Math.ceil(cell), Math.ceil(cell));
    ctx.restore();
  }

  function drawHunger(x, y, cell, fill) {
    const shape = [
      [0,0,1,1,1,0,0],
      [0,1,1,1,1,0,0],
      [1,1,1,1,1,1,0],
      [1,1,1,1,1,1,0],
      [0,1,1,1,1,0,0],
      [0,0,1,0,1,0,0]
    ];
    for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
      if (!shape[r][c]) continue;
      ctx.fillStyle = "#574333";
      ctx.fillRect(Math.round(x + c * cell), Math.round(y + r * cell), Math.ceil(cell), Math.ceil(cell));
    }
    if (fill <= 0) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, 7 * cell * fill, 6 * cell);
    ctx.clip();
    for (let r = 0; r < 6; r++) for (let c = 0; c < 7; c++) {
      if (!shape[r][c]) continue;
      ctx.fillStyle = (r < 3 && c > 1) ? "#d8b276" : "#a87543";
      ctx.fillRect(Math.round(x + c * cell), Math.round(y + r * cell), Math.ceil(cell), Math.ceil(cell));
    }
    ctx.fillStyle = "rgba(255,239,196,.6)";
    ctx.fillRect(Math.round(x + 2 * cell), Math.round(y + 1 * cell), Math.ceil(cell), Math.ceil(cell));
    ctx.restore();
  }

  function drawShadowText(text, x, y, color, shadow) {
    ctx.fillStyle = shadow || "rgba(0,0,0,.75)";
    ctx.fillText(text, x + 2, y + 2);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }

  function drawMessages(ui) {
    if (!messages.length) return;
    ctx.textAlign = "center";
    let y = 82 * ui;
    const arr = messages.slice(-4);
    for (let i = arr.length - 1; i >= 0; i--) {
      const m = arr[i];
      const a = clamp(Math.min(m.age * 4, m.life - m.age + 0.55), 0, 1);
      ctx.globalAlpha = a;
      ctx.font = '700 ' + Math.round(10 * ui) + 'px "Courier New", monospace';
      const tw = ctx.measureText(m.text).width;
      const bx = view.w / 2 - tw / 2 - 10 * ui;
      const by = y - 13 * ui;
      ctx.fillStyle = "rgba(8,10,9,.72)";
      ctx.fillRect(bx, by, tw + 20 * ui, 20 * ui);
      ctx.strokeStyle = "rgba(139,118,88,.28)";
      ctx.strokeRect(bx + 0.5, by + 0.5, tw + 20 * ui - 1, 20 * ui - 1);
      ctx.fillStyle = m.color || "#eee2c7";
      ctx.fillText(m.text, view.w / 2, y);
      y += 24 * ui;
      ctx.globalAlpha = 1;
    }
    ctx.textAlign = "left";
  }

  function drawCrosshair() {
    if (state !== "playing") return;
    const mx = mouse.x, my = mouse.y;
    const mob = entityUnderMouse();
    const color = mob ? "#e88b78" : "#f6f0df";
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.fillRect(mx - 8, my - 1, 16, 3);
    ctx.fillRect(mx - 1, my - 8, 3, 16);
    ctx.fillStyle = color;
    ctx.fillRect(mx - 7, my, 5, 1);
    ctx.fillRect(mx + 3, my, 5, 1);
    ctx.fillRect(mx, my - 7, 1, 5);
    ctx.fillRect(mx, my + 3, 1, 5);

    const hit = targetTile();
    if (mob) {
      ctx.textAlign = "center";
      ctx.font = '700 ' + Math.round(9 * view.hud) + 'px "Courier New", monospace';
      drawShadowText(capitalize(mob.type) + "  " + Math.ceil(mob.hp) + "/" + mob.maxHp,
        mx, my + 20 * view.hud, "#f0bbae", "rgba(0,0,0,.8)");
      ctx.textAlign = "left";
      return;
    }
    if (!hit || !canReach(hit.x, hit.y) || hit.x < 0 || hit.x >= W || hit.y < 0 || hit.y >= H) return;
    const id = world.get(hit.x, hit.y);
    if (id === T.AIR) return;
    const def = BH.TILE_DEFS[id];
    if (!def) return;
    let label = def.name;
    if (id === T.BEDROCK) {
      label += "  ·  indestructible";
    } else {
      const heldIt = player.inventory[player.selected];
      const heldDef = itemDef(heldIt);
      if (def.tier > 0 && (!heldDef || heldDef.tool !== "pick" || heldDef.tier < def.tier)) {
        label += "  ·  stronger pickaxe needed";
      } else if (id === T.TABLE || id === T.FURNACE) {
        label += "  ·  right-click to use";
      }
    }
    ctx.font = '700 ' + Math.round(8.5 * view.hud) + 'px "Courier New", monospace';
    ctx.textAlign = "left";
    const tw = ctx.measureText(label).width;
    let lx = mx + 15, ly = my + 20;
    if (lx + tw + 8 > view.w) lx = mx - tw - 15;
    if (ly > view.h - 80) ly = my - 14;
    ctx.fillStyle = "rgba(8,10,9,.65)";
    ctx.fillRect(lx - 4, ly - 11, tw + 8, 15);
    drawShadowText(label, lx, ly, "#ded2b7", "rgba(0,0,0,.85)");
  }

  function drawVignette() {
    if (hud.damageFlash > 0.01 || player.health <= 6) {
      let intensity = hud.damageFlash * 0.45;
      if (player.health <= 6) intensity = Math.max(intensity, 0.14 + Math.sin(elapsed * 3) * 0.05);
      if (intensity > 0.005) {
        const g = ctx.createRadialGradient(view.w / 2, view.h / 2, Math.min(view.w, view.h) * 0.28, view.w / 2, view.h / 2, Math.max(view.w, view.h) * 0.7);
        g.addColorStop(0, "rgba(110,15,14,0)");
        g.addColorStop(1, "rgba(120,17,14," + intensity.toFixed(3) + ")");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, view.w, view.h);
      }
    }
    // Night / cave edge vignette
    const tod = timeOfDay();
    const night = clamp(-sunAltitude() * 1.8, 0, 0.35);
    if (night > 0.02) {
      const g = ctx.createRadialGradient(view.w / 2, view.h / 2, Math.min(view.w, view.h) * 0.3, view.w / 2, view.h / 2, Math.max(view.w, view.h) * 0.72);
      g.addColorStop(0, "rgba(4,8,18,0)");
      g.addColorStop(1, "rgba(3,6,15," + night.toFixed(3) + ")");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, view.w, view.h);
    }
  }

  // ---------- master render ----------
  function render() {
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, view.w, view.h);
    renderVisibleRange();

    let shakeX = 0, shakeY = 0;
    if (hud.shake > 0.005) {
      const amp = hud.shake * view.tile * 0.22;
      shakeX = (Math.random() - 0.5) * amp;
      shakeY = (Math.random() - 0.5) * amp;
    }
    ctx.save();
    ctx.translate(shakeX, shakeY);
    drawSky();
    drawCaveBackdrop();
    drawWorld();
    drawDrops();
    drawEntityList();
    drawParticles(false);
    drawLighting();
    drawTorchGlows();
    drawParticles(true);
    drawMiningAndSelection();
    drawFloaters();
    ctx.restore();

    drawVignette();
    if (state === "playing") {
      drawHUD();
      drawCrosshair();
    } else if (state === "inventory" || state === "furnace" || state === "pause" || state === "help" || state === "dead") {
      // Keep a faint HUD silhouette behind full-screen panels for orientation.
      // The overlay's blur makes it a backdrop rather than a distraction.
    } else if (state === "title") {
      // no HUD on the menu
    }
  }

  // ---------- messages ----------
  function message(text, color, life) {
    const clean = String(text);
    messages.push({ text: clean, color: color || "#eee2c7", life: life || 3.4, age: 0 });
    if (messages.length > 5) messages.shift();
    if ((state === "inventory" || state === "furnace" || state === "pause") && el.uiToast) {
      el.uiToast.textContent = clean;
      el.uiToast.style.color = color || "#eee2c7";
      el.uiToast.classList.remove("hidden");
      clearTimeout(uiToastTimer);
      uiToastTimer = setTimeout(() => {
        if (el.uiToast) el.uiToast.classList.add("hidden");
      }, Math.max(1400, (life || 3.4) * 850));
    }
  }

  function updateMessages(dt) {
    for (const m of messages) m.age += dt;
    messages = messages.filter(m => m.age < m.life);
  }

  // ---------- main update ----------
  function update(dt) {
    worldTime += dt;
    playTime += dt;

    if (world.lightDirty) world.recomputeLight();

    updatePlayer(dt);
    if (state !== "playing") return;

    updateEntities(dt);
    if (state !== "playing") return;
    updateDrops(dt);
    updateParticles(dt);

    nearbyTimer -= dt;
    if (nearbyTimer <= 0) {
      nearbyTimer = 0.25;
      updateNearby();
    }

    trySpawnZombies(dt);
    trySpawnPigs(dt);

    // Little night fireflies over the grass.
    if (isNight() && player.y - world.groundAt(player.x) < 7 && particles.length < 160 && Math.random() < dt * 2.4) {
      particles.push({
        x: player.x + (Math.random() - 0.5) * 14,
        y: player.y - 1.2 - Math.random() * 3.5,
        vx: (Math.random() - 0.5) * 0.35,
        vy: -0.05 - Math.random() * 0.18,
        life: 3 + Math.random() * 4, max: 7,
        size: 0.035 + Math.random() * 0.03,
        color: "#d7e88e", gravity: -0.02, glow: true
      });
    }

    // Ambient soundscape.
    ambientTimer -= dt;
    if (ambientTimer <= 0) {
      ambientTimer = 7 + Math.random() * 13;
      const depth = player.y - world.groundAt(player.x);
      if (depth > 9) BH.Sound.tone(150 + Math.random() * 90, 0.12, "sine", 0.008, -40);
      else BH.Sound.chirp(isNight());
    }

    if (!hints.night && timeOfDay() > 0.48 && timeOfDay() < 0.58) {
      hints.night = true;
      message("The sun is setting. Light your shelter before the dark.", "#e0b18e", 5);
    }

    hud.damageFlash = Math.max(0, hud.damageFlash - dt * 1.7);
    hud.shake = Math.max(0, hud.shake - dt * 2.6);
    hud.saveFlash = Math.max(0, hud.saveFlash - dt);
    selectedFlash = Math.max(0, selectedFlash - dt * 1.6);

    saveTimer += dt;
    if (saveTimer > 11) {
      saveTimer = 0;
      saveGame(false);
    }
  }

  function updateTitle(dt) {
    // The menu world breathes without simulating survival.
    titleCamDrift += dt;
    if (world && world.lightDirty) world.recomputeLight();
    for (const e of entities) {
      if (e.type === "pig") e.age += dt;
    }
  }

  // ---------- input ----------
  function isTypingTarget(t) {
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
  }

  function bindEvents() {
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", ev => {
      const r = canvas.getBoundingClientRect();
      mouse.x = ev.clientX - r.left;
      mouse.y = ev.clientY - r.top;
      mouse.inside = mouse.x >= 0 && mouse.y >= 0 && mouse.x <= view.w && mouse.y <= view.h;
      if (held && el.itemCursor) {
        el.itemCursor.style.left = ev.clientX + "px";
        el.itemCursor.style.top = ev.clientY + "px";
      }
      if (el.itemTooltip && !el.itemTooltip.classList.contains("hidden")) {
        const tw = 220, th = 64;
        el.itemTooltip.style.left = Math.min(window.innerWidth - tw - 12, ev.clientX + 18) + "px";
        el.itemTooltip.style.top = Math.min(window.innerHeight - th - 12, ev.clientY + 18) + "px";
      }
    });

    canvas.addEventListener("mouseenter", () => { mouse.inside = true; });
    canvas.addEventListener("mouseleave", () => { mouse.inside = false; mouse.down = false; });
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    canvas.addEventListener("mousedown", onCanvasMouseDown);
    window.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);

    document.querySelectorAll("[data-back]").forEach(b => {
      b.addEventListener("click", () => {
        BH.Sound.resume();
        BH.Sound.click();
        if (b.dataset.back === "previous") {
          if (state === "help") closeHelp();
        } else {
          setState("title");
          updateTitleUI();
        }
      });
    });
    document.querySelectorAll("[data-close-inventory]").forEach(b => b.addEventListener("click", closeInventory));
    document.querySelectorAll("[data-close-furnace]").forEach(b => b.addEventListener("click", () => {
      if (state === "furnace") setState("playing");
    }));

    el.btnContinue.addEventListener("click", () => { BH.Sound.resume(); BH.Sound.click(); continueWorld(); });
    el.btnPlay.addEventListener("click", () => { BH.Sound.resume(); BH.Sound.click(); playPreviewWorld(); });
    el.btnNewWorld.addEventListener("click", () => {
      BH.Sound.resume(); BH.Sound.click();
      el.seedInput.value = "";
      el.overwriteNotice.classList.toggle("hidden", !hasSave);
      setState("newworld");
      updateDifficultyUI();
      setTimeout(() => el.seedInput.focus(), 60);
    });
    el.btnHowTo.addEventListener("click", () => { BH.Sound.click(); openHelp("title"); });
    el.btnTitleSound.addEventListener("click", toggleSound);

    el.difficultyPicker.querySelectorAll("button").forEach(b => {
      b.addEventListener("click", () => {
        difficulty = b.dataset.difficulty;
        updateDifficultyUI();
        BH.Sound.click();
      });
    });
    el.createWorldBtn.addEventListener("click", () => {
      const seed = el.seedInput.value.trim() || randomSeed();
      startNewWorld(seed, difficulty);
    });
    el.seedInput.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        startNewWorld(el.seedInput.value.trim() || randomSeed(), difficulty);
      }
    });

    el.btnResume.addEventListener("click", () => { BH.Sound.click(); resumeGame(); });
    el.btnPauseHelp.addEventListener("click", () => { BH.Sound.click(); openHelp("pause"); });
    el.btnSaveNow.addEventListener("click", () => {
      saveGame(true);
      BH.Sound.save();
      el.btnSaveNow.textContent = "Saved ✓";
      setTimeout(() => { el.btnSaveNow.textContent = "Save Now"; }, 1400);
    });
    el.btnPauseSound.addEventListener("click", toggleSound);
    el.btnFullscreen.addEventListener("click", toggleFullscreen);
    el.btnQuit.addEventListener("click", () => {
      BH.Sound.click();
      askConfirm("Save & quit?", "Your world will be saved before you return to the title screen.", "Save & Quit", () => {
        saveGame(true);
        returnToTitle();
      });
    });

    el.btnRespawn.addEventListener("click", () => { BH.Sound.click(); respawn(); });
    el.btnDeathQuit.addEventListener("click", () => {
      BH.Sound.click();
      saveGame(false);
      returnToTitle();
    });

    el.confirmNo.addEventListener("click", () => {
      BH.Sound.click();
      setState(confirmReturn || "pause");
    });
    el.confirmYes.addEventListener("click", () => {
      BH.Sound.click();
      const cb = confirmCallback;
      confirmCallback = null;
      if (cb) cb();
    });

    // Inventory slots
    for (const grid of [el.mainGrid, el.invHotbar]) {
      grid.addEventListener("mousedown", e => {
        const slot = e.target.closest(".slot");
        if (!slot) return;
        e.preventDefault();
        BH.Sound.resume();
        const index = Number(slot.dataset.index);
        if (e.button === 0 || e.button === 2) handleSlotClick(index, e.button, e.shiftKey);
      });
      grid.addEventListener("contextmenu", e => e.preventDefault());
      grid.addEventListener("mouseover", e => {
        const slot = e.target.closest(".slot");
        if (!slot) return;
        showItemTooltip(Number(slot.dataset.index), e.clientX, e.clientY);
      });
      grid.addEventListener("mouseout", e => {
        if (!e.relatedTarget || !e.relatedTarget.closest || !e.relatedTarget.closest(".slot")) hideTooltip();
      });
    }
    el.inventoryScreen.addEventListener("mousedown", e => {
      if (e.target === el.inventoryScreen && held) returnHeldStack();
    });
    el.recipeList.addEventListener("click", e => {
      const card = e.target.closest(".recipe");
      if (!card) return;
      craftRecipe(card.dataset.recipe, e.shiftKey);
    });
    el.furnaceList.addEventListener("click", e => {
      const card = e.target.closest(".recipe");
      if (!card) return;
      smeltRecipe(card.dataset.smelt);
    });

    // Save when the tab is hidden or closed.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && world && player && started) {
        saveGame(false);
        if (state === "playing") pauseGame();
      }
    });
    window.addEventListener("blur", () => {
      keys.left = keys.right = keys.jump = keys.sprint = false;
      mouse.down = false;
      mineTarget = null;
    });
    window.addEventListener("pagehide", () => { if (world && player && started) saveGame(false); });
    window.addEventListener("beforeunload", () => { if (world && player && started) saveGame(false); });

    // Load all item images once.
    for (const key in BH.ITEM_DEFS) iconImage(Number(key));
    for (let i = 1; i < BH.TILE_DEFS.length; i++) if (BH.TILE_DEFS[i]) iconImage(i);
    buildSkyDecor();
    buildCaveTextures();
  }

  function onCanvasMouseDown(e) {
    if (state !== "playing") return;
    BH.Sound.resume();
    if (e.button === 0) {
      const hb = hotbarLayout();
      for (let i = 0; i < 9; i++) {
        const x = hb.x + i * (hb.s + hb.gap);
        if (e.clientX >= x && e.clientX <= x + hb.s && e.clientY >= hb.y && e.clientY <= hb.y + hb.s) {
          selectSlot(i);
          return;
        }
      }
      mouse.down = true;
      player.swing = 1;
      const mob = entityUnderMouse();
      if (mob && centerDistToPlayer(mob.x, mob.y - mob.h / 2) < BH.REACH + 0.8) attackMob(mob);
    } else if (e.button === 2) {
      e.preventDefault();
      useSelected();
    }
  }

  function onMouseUp() {
    mouse.down = false;
    mineTarget = null;
    mineProgress = 0;
  }

  function onWheel(e) {
    if (state !== "playing") return;
    e.preventDefault();
    const dir = e.deltaY > 0 ? 1 : -1;
    selectSlot(BH.mod(player.selected + dir, 9));
  }

  function selectSlot(i) {
    if (!player) return;
    player.selected = clamp(i, 0, 8);
    selectedFlash = 1.8;
    BH.Sound.select();
  }

  function onKeyDown(e) {
    if (isTypingTarget(e.target)) {
      if (e.key === "Escape") {
        if (state === "newworld") { setState("title"); updateTitleUI(); }
      }
      return;
    }
    const k = e.key;
    const lower = k.toLowerCase();
    BH.Sound.resume();

    if (lower === "m") {
      toggleSound();
      return;
    }

    if (state === "playing") {
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " ", "Spacebar"].includes(k)) e.preventDefault();
      if (lower === "a" || k === "ArrowLeft") keys.left = true;
      if (lower === "d" || k === "ArrowRight") keys.right = true;
      if (lower === "shift") keys.sprint = true;
      if ((lower === "w" || k === "ArrowUp" || k === " " || lower === "spacebar") && !e.repeat) {
        keys.jump = true;
        tryJump();
      }
      if (e.repeat) return;
      if (lower === "e") { e.preventDefault(); openInventory(); return; }
      if (lower === "r") { e.preventDefault(); openFurnace(); return; }
      if (lower === "q") { dropSelected(); return; }
      if (k === "Escape") { e.preventDefault(); pauseGame(); return; }
      if (/^[1-9]$/.test(k)) { selectSlot(Number(k) - 1); return; }
      return;
    }

    if (state === "inventory") {
      if (lower === "e" || k === "Escape") { e.preventDefault(); closeInventory(); }
      return;
    }
    if (state === "furnace") {
      if (lower === "r" || lower === "e" || k === "Escape") { e.preventDefault(); setState("playing"); }
      return;
    }
    if (state === "pause") {
      if (k === "Escape") { e.preventDefault(); resumeGame(); }
      return;
    }
    if (state === "help") {
      if (k === "Escape") { e.preventDefault(); closeHelp(); }
      return;
    }
    if (state === "newworld") {
      if (k === "Escape") { e.preventDefault(); setState("title"); updateTitleUI(); }
      return;
    }
    if (state === "confirm") {
      if (k === "Escape") { e.preventDefault(); setState(confirmReturn || "pause"); }
      return;
    }
    if (state === "dead") {
      if (k === "Enter" || lower === "r") { e.preventDefault(); respawn(); }
      return;
    }
    if (state === "title") {
      if (k === "Enter" && (!document.activeElement || document.activeElement.tagName !== "BUTTON")) {
        e.preventDefault();
        if (hasSave) continueWorld(); else playPreviewWorld();
      }
    }
  }

  function onKeyUp(e) {
    if (isTypingTarget(e.target)) return;
    const k = e.key, lower = k.toLowerCase();
    if (lower === "a" || k === "ArrowLeft") keys.left = false;
    if (lower === "d" || k === "ArrowRight") keys.right = false;
    if (lower === "shift") keys.sprint = false;
    if (lower === "w" || k === "ArrowUp" || k === " " || lower === "spacebar") {
      keys.jump = false;
      if (player && player.vy < -4) player.vy += 2.2;
    }
  }

  function updateDifficultyUI() {
    if (!el.difficultyPicker) return;
    el.difficultyPicker.querySelectorAll("button").forEach(b => {
      b.classList.toggle("active", b.dataset.difficulty === difficulty);
    });
    el.difficultyHelp.textContent = difficulty === "peaceful"
      ? "No hostile mobs. Take your time and build."
      : difficulty === "hard"
        ? "More zombies, faster spawns, and heavier hits. Light everything."
        : "Hostile mobs appear after dark. Bring a sword.";
  }

  function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => message("Fullscreen is blocked by the browser.", "#e1ad87", 2.5));
      } else {
        document.exitFullscreen();
      }
    } catch (e) {
      message("Fullscreen is unavailable.", "#e1ad87", 2.5);
    }
  }

  // ---------- loop ----------
  function loop(now) {
    requestAnimationFrame(loop);
    if (!world) return;
    if (!lastFrame) lastFrame = now;
    let dt = (now - lastFrame) / 1000;
    lastFrame = now;
    dt = clamp(dt, 0, 0.05);
    elapsed += dt;

    updateMessages(dt);
    if (state === "playing") {
      update(dt);
    } else if (state === "title") {
      updateTitle(dt);
    } else {
      if (world.lightDirty) world.recomputeLight();
      hud.damageFlash = Math.max(0, hud.damageFlash - dt);
      hud.shake = Math.max(0, hud.shake - dt * 2.5);
      hud.saveFlash = Math.max(0, hud.saveFlash - dt);
      selectedFlash = Math.max(0, selectedFlash - dt);
    }
    updateCamera(dt);
    render();
  }

  // ---------- public debug/testing handle ----------
  window.Blockhaven = {
    get state() { return state; },
    get world() { return world; },
    get player() { return player; },
    get entities() { return entities; },
    get time() { return { worldTime, day: dayNumber(), tod: timeOfDay() }; },
    get hasSave() { return hasSave; },
    get camera() { return { x: cam.x, y: cam.y }; },
    get viewport() { return { w: view.w, h: view.h, tile: view.tile, dpr: view.dpr }; },
    get nearby() { return { ...nearby }; },
    worldToScreen(wx, wy) { return { x: sxOf(wx), y: syOf(wy) }; },
    setTime(dayFraction) { worldTime = BH.clamp(dayFraction, 0, 100) * BH.DAY_LENGTH; },
    damagePlayer(amount, cause) { hurtPlayer(amount || 1, cause || "A test wound.", 0); },
    startNewWorld,
    continueWorld,
    saveGame,
    message,
    addItem,
    selectSlot
  };

  // ---------- go ----------
  boot();
})();
