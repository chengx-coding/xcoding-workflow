(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./config.js"),
      require("./blocks.js"),
      require("./world.js"),
      require("./crafting.js"),
      require("./progression.js"),
      require("./save.js"),
      require("./render.js")
    );
  } else {
    root.SandboxUI = factory(
      root.SandboxConfig,
      root.SandboxBlocks,
      root.SandboxWorld,
      root.SandboxCrafting,
      root.SandboxProgression,
      root.SandboxSave,
      root.SandboxRender
    );
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (
  CONFIG,
  BLOCKS,
  WORLD,
  CRAFTING,
  PROGRESSION,
  SAVE,
  RENDER
) {
  "use strict";

  if (!CONFIG || !BLOCKS || !WORLD || !CRAFTING || !PROGRESSION || !SAVE || !RENDER) {
    throw new Error("SandboxUI dependencies are missing");
  }

  const B = CONFIG.blocks;
  const I = CONFIG.items;

  const CONTROLS = [
    ["A / D  or  ← / →", "Walk left and right."],
    ["Space", "Jump. Hold briefly for a higher hop; the game forgives a late jump by a few frames."],
    ["Hold left mouse", "Mine the block under the pointer. The block must be in reach and touching air."],
    ["Left mouse on a hollow", "Attack the night hollow under the pointer."],
    ["Right mouse", "Place the selected block into an empty tile next to solid ground."],
    ["1 – 9  or  mouse wheel", "Choose a hotbar slot."],
    ["E", "Open or close the inventory and crafting."],
    ["Esc", "Pause the game."],
    ["H", "Open or close this controls panel."],
    ["M", "Mute or unmute the procedural sound."]
  ];

  function createUI(callbacks) {
    const api = callbacks || {};
    const refs = {};
    const state = {
      screen: null,
      helpReturn: "pause",
      pickedSlot: -1,
      snapshot: null,
      hotbarSignature: [],
      heartsSignature: "",
      hintTimer: 0,
      mapTimer: 0,
      saveSignature: "",
      newWorldArmed: false,
      muted: false
    };

    function init() {
      refs.hud = document.getElementById("hud");
      refs.hotbar = document.getElementById("hotbar");
      refs.overlay = document.getElementById("overlay");
      refs.toasts = document.getElementById("toasts");
      refs.hint = document.getElementById("hint");
      refs.game = document.getElementById("game");
      buildHud();
      buildHotbar();
      bindEvents();
    }

    function buildHud() {
      const pips = [];
      for (let i = 0; i < PROGRESSION.STAGES.length; i += 1) {
        pips.push("<i" + (i === PROGRESSION.STAGES.length - 1 ? ' class="is-last"' : "") + "></i>");
      }
      refs.hud.innerHTML = [
        '<div class="hud-top">',
        '  <section class="panel quest-panel" aria-label="Journey progress">',
        '    <div class="quest-head"><span class="quest-eyebrow"><i class="quest-gem"></i>Journey</span><span id="quest-stage">1 / 8</span></div>',
        '    <div class="quest-title" id="quest-title">Gather wood</div>',
        '    <div class="quest-hint" id="quest-hint"></div>',
        '    <div class="quest-pips" id="quest-pips" aria-hidden="true">' + pips.join("") + "</div>",
        "  </section>",
        '  <div class="panel clock-panel" id="clock-panel" aria-label="Day and time">',
        '    <span class="clock-orb" aria-hidden="true"></span>',
        "    <div>",
        '      <div class="clock-day" id="clock-day">Day 1</div>',
        '      <div class="clock-phase" id="clock-phase">Morning</div>',
        "    </div>",
        "  </div>",
        '  <section class="panel map-panel" aria-label="World map">',
        '    <canvas id="minimap" width="228" height="136"></canvas>',
        '    <div class="map-meta"><span id="coords">X 24 · Y 91</span><span id="depth">Surface</span></div>',
        "  </section>",
        "</div>",
        '<button class="help-button" id="help-button" type="button" title="Controls (H)" aria-label="Controls">?</button>',
        '<div class="hearts" id="hearts" aria-label="Health"></div>',
        '<div class="save-state" id="save-state" data-kind="dirty"><span class="dot"></span><span id="save-text">Not saved yet</span></div>'
      ].join("");
      refs.questStage = document.getElementById("quest-stage");
      refs.questTitle = document.getElementById("quest-title");
      refs.questHint = document.getElementById("quest-hint");
      refs.questPips = document.getElementById("quest-pips");
      refs.questPipItems = refs.questPips
        ? Array.prototype.slice.call(refs.questPips.children)
        : [];
      refs.clockPanel = document.getElementById("clock-panel");
      refs.clockDay = document.getElementById("clock-day");
      refs.clockPhase = document.getElementById("clock-phase");
      refs.minimap = document.getElementById("minimap");
      refs.minimapCtx = refs.minimap.getContext("2d");
      refs.coords = document.getElementById("coords");
      refs.depth = document.getElementById("depth");
      refs.hearts = document.getElementById("hearts");
      refs.saveState = document.getElementById("save-state");
      refs.saveText = document.getElementById("save-text");
      refs.helpButton = document.getElementById("help-button");
    }

    function buildHotbar() {
      const slots = [];
      for (let i = 0; i < CONFIG.hotbarSize; i += 1) {
        slots.push(
          '<button class="slot is-empty" type="button" data-select="' +
            i +
            '" aria-label="Hotbar slot ' +
            (i + 1) +
            '">' +
            '<canvas width="76" height="76"></canvas>' +
            '<span class="count"></span>' +
            '<span class="key">' +
            (i + 1) +
            "</span>" +
            "</button>"
        );
      }
      refs.hotbar.innerHTML = slots.join("");
      refs.hotbarSlots = Array.prototype.slice.call(refs.hotbar.querySelectorAll(".slot"));
      refs.hotbarIcons = refs.hotbarSlots.map(function icon(slot) {
        return slot.querySelector("canvas");
      });
      refs.hotbarCounts = refs.hotbarSlots.map(function count(slot) {
        return slot.querySelector(".count");
      });
    }

    function bindEvents() {
      refs.helpButton.addEventListener("click", function helpClick() {
        if (api.action) {
          api.action("help");
        }
      });
      refs.hotbar.addEventListener("click", function hotbarClick(event) {
        const button = event.target.closest("[data-select]");
        if (button && api.selectSlot) {
          api.selectSlot(Number(button.dataset.select));
        }
      });
      refs.overlay.addEventListener("click", function overlayClick(event) {
        const actionButton = event.target.closest("[data-action]");
        if (actionButton) {
          const name = actionButton.dataset.action;
          if (api.action) {
            api.action(name, actionButton.dataset.value || "");
          }
          return;
        }
        const craftButton = event.target.closest("[data-craft]");
        if (craftButton && api.craft) {
          api.craft(craftButton.dataset.craft);
          return;
        }
        const slotButton = event.target.closest("[data-slot]");
        if (slotButton) {
          handleInventorySlot(Number(slotButton.dataset.slot));
        }
      });
    }

    function handleInventorySlot(index) {
      if (state.pickedSlot === -1) {
        state.pickedSlot = index;
        paintInventorySelection();
        return;
      }
      if (state.pickedSlot === index) {
        state.pickedSlot = -1;
        paintInventorySelection();
        return;
      }
      if (api.moveSlot) {
        api.moveSlot(state.pickedSlot, index);
      }
      state.pickedSlot = -1;
      refreshInventory();
    }

    function paintInventorySelection() {
      if (!state.screen || state.screen !== "inventory") {
        return;
      }
      const nodes = refs.overlay.querySelectorAll("[data-slot]");
      for (let i = 0; i < nodes.length; i += 1) {
        const node = nodes[i];
        if (node.classList.contains("is-picked")) {
          node.classList.remove("is-picked");
        }
        if (Number(node.dataset.slot) === state.pickedSlot) {
          node.classList.add("is-picked");
        }
      }
    }

    function phaseName(time) {
      const value = ((time % 1) + 1) % 1;
      if (value < 0.045) {
        return "Dawn";
      }
      if (value < 0.3) {
        return "Morning";
      }
      if (value < 0.5) {
        return "Afternoon";
      }
      if (value < 0.62) {
        return "Dusk";
      }
      if (value < 0.94) {
        return "Night";
      }
      return "Dawn";
    }

    function depthLabel(y) {
      const ground = WORLD.GROUND_ROW;
      if (y < ground - 3) {
        return "Sky";
      }
      if (y <= ground + 5) {
        return "Surface";
      }
      if (y <= ground + 18) {
        return "Shallow caves";
      }
      if (y <= CONFIG.worldHeight - 26) {
        return "Deep caves";
      }
      return "Ember band";
    }

    function updateHud(snapshot) {
      const progress = PROGRESSION.summary(snapshot.progress);
      refs.questStage.textContent = progress.done
        ? "COMPLETE"
        : progress.index + 1 + " / " + progress.total;
      refs.questTitle.textContent = progress.title;
      refs.questHint.textContent = progress.hint;
      for (let i = 0; i < refs.questPipItems.length; i += 1) {
        const pip = refs.questPipItems[i];
        pip.classList.toggle("is-done", i < progress.index);
        pip.classList.toggle("is-now", i === progress.index && !progress.done);
      }

      const phase = phaseName(snapshot.clock.time);
      refs.clockDay.textContent = "Day " + snapshot.clock.day;
      refs.clockPhase.textContent = phase;
      if (refs.clockPanel) {
        refs.clockPanel.dataset.phase = phase;
      }

      refs.coords.textContent =
        "X " + Math.round(snapshot.player.x) + " · Y " + Math.round(snapshot.player.y);
      refs.depth.textContent = depthLabel(snapshot.player.y);

      const hearts = [];
      for (let i = 0; i < 10; i += 1) {
        const value = snapshot.player.health - i * 2;
        if (value >= 2) {
          hearts.push('<span class="heart"></span>');
        } else if (value === 1) {
          hearts.push('<span class="heart half"></span>');
        } else {
          hearts.push('<span class="heart empty"></span>');
        }
      }
      const heartsHtml = hearts.join("");
      if (heartsHtml !== state.heartsSignature) {
        state.heartsSignature = heartsHtml;
        refs.hearts.innerHTML = heartsHtml;
      }
      refs.hearts.setAttribute(
        "aria-label",
        "Health " + Math.max(0, Math.round(snapshot.player.health)) + " of " + CONFIG.maxHealth
      );

      updateHotbar(snapshot);
      updateSaveState(snapshot);

      if (Date.now() - state.mapTimer > 260 && snapshot.world) {
        state.mapTimer = Date.now();
        drawMinimap(snapshot);
      }
    }

    function updateSaveState(snapshot) {
      const status = snapshot.saveStatus || { kind: "dirty", text: "Not saved yet" };
      const signature = status.kind + "|" + status.text;
      if (signature !== state.saveSignature) {
        state.saveSignature = signature;
        refs.saveState.dataset.kind = status.kind;
        refs.saveText.textContent = status.text;
      }
    }

    function updateHotbar(snapshot) {
      const inventory = snapshot.inventory;
      for (let i = 0; i < CONFIG.hotbarSize; i += 1) {
        const stack = inventory.slots[i] || null;
        const id = stack ? stack.id : 0;
        const signature = id + ":" + (stack ? stack.count : 0);
        const slot = refs.hotbarSlots[i];
        if (stack) {
          slot.classList.remove("is-empty");
        } else {
          slot.classList.add("is-empty");
        }
        if (inventory.selected === i) {
          slot.classList.add("is-selected");
          slot.setAttribute("aria-pressed", "true");
        } else {
          slot.classList.remove("is-selected");
          slot.setAttribute("aria-pressed", "false");
        }
        refs.hotbarCounts[i].textContent = stack && stack.count > 1 ? String(stack.count) : "";
        if (state.hotbarSignature[i] !== signature) {
          state.hotbarSignature[i] = signature;
          const canvas = refs.hotbarIcons[i];
          const ctx = canvas.getContext("2d");
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          if (stack) {
            RENDER.drawItemIcon(ctx, stack.id, canvas.width);
          }
        }
        slot.setAttribute(
          "aria-label",
          stack ? BLOCKS.itemName(stack.id) + " x" + stack.count : "Empty hotbar slot " + (i + 1)
        );
      }
    }

    function drawMinimap(snapshot) {
      const ctx = refs.minimapCtx;
      const width = refs.minimap.width;
      const height = refs.minimap.height;
      const world = snapshot.world;
      const columns = WORLD.sampleColumns(world, 0, world.width, width);
      const sky = ctx.createLinearGradient(0, 0, 0, height);
      sky.addColorStop(0, "#08111c");
      sky.addColorStop(0.45, "#0d1826");
      sky.addColorStop(0.72, "#142334");
      sky.addColorStop(1, "#1b2c3f");
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, width, height);

      // A thin grid makes the overview read as a surveyed map instead of a
      // strip of colour.
      ctx.fillStyle = "rgba(180, 205, 230, 0.055)";
      for (let gx = 0; gx < width; gx += Math.round(width / 8)) {
        ctx.fillRect(gx, 0, 1, height);
      }
      for (let gy = 0; gy < height; gy += Math.round(height / 5)) {
        ctx.fillRect(0, gy, width, 1);
      }

      // Stars in the map's sky band, deterministic from the seed.
      ctx.fillStyle = "rgba(226, 238, 250, 0.4)";
      for (let s = 0; s < 26; s += 1) {
        const sx = (s * 37 + 11) % width;
        const sy = (s * 13 + 5) % Math.round(height * 0.32);
        ctx.fillRect(sx, sy, 1, 1);
      }

      for (let i = 0; i < columns.length; i += 1) {
        const column = columns[i];
        const y = Math.round((column.surface / world.height) * height);
        const def = BLOCKS.get(column.top);
        const color = def ? def.palette.base : "#555";
        const dark = def ? def.palette.dark : "#333";

        // Subsoil is stone-dark, not the top block's colour, so the map reads
        // as a depth section rather than a coloured bar chart.
        ctx.fillStyle = i % 3 === 0 ? "#111923" : "#0d151e";
        ctx.fillRect(i, y + 2, 1, height - y - 2);
        ctx.fillStyle = dark;
        ctx.globalAlpha = 0.34;
        ctx.fillRect(i, y + 2, 1, 4);
        ctx.globalAlpha = 1;

        // Surface cap: a bright pixel row with a darker lip below it.
        ctx.fillStyle = color;
        ctx.fillRect(i, y, 1, 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.17)";
        ctx.fillRect(i, y, 1, 1);
      }

      // Ember band warmth and a thin survey line.
      const emberY = Math.round(((world.height - 26) / world.height) * height);
      const ember = ctx.createLinearGradient(0, emberY - 10, 0, height);
      ember.addColorStop(0, "rgba(255, 138, 76, 0)");
      ember.addColorStop(0.55, "rgba(255, 138, 76, 0.16)");
      ember.addColorStop(1, "rgba(255, 106, 46, 0.34)");
      ctx.fillStyle = ember;
      ctx.fillRect(0, emberY - 10, width, height - emberY + 10);
      ctx.fillStyle = "rgba(255, 178, 110, 0.55)";
      ctx.fillRect(0, emberY, width, 1);

      // A soft bottom shadow keeps the map inside its frame.
      const bottom = ctx.createLinearGradient(0, height - 14, 0, height);
      bottom.addColorStop(0, "rgba(0, 0, 0, 0)");
      bottom.addColorStop(1, "rgba(0, 0, 0, 0.45)");
      ctx.fillStyle = bottom;
      ctx.fillRect(0, height - 14, width, 14);

      // The chart is an instrument, but it should still agree with the clock.
      const time = snapshot.clock ? ((snapshot.clock.time % 1) + 1) % 1 : 0.3;
      if (time >= 0.62 && time < 0.94) {
        ctx.fillStyle = "rgba(8, 14, 30, 0.34)";
        ctx.fillRect(0, 0, width, height);
      }

      const playerX = Math.round((snapshot.player.x / world.width) * width);
      const playerY = Math.round((snapshot.player.y / world.height) * height);
      ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
      ctx.beginPath();
      ctx.arc(playerX, playerY, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(255, 210, 122, 0.7)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(playerX, playerY, 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "#ffd27a";
      ctx.beginPath();
      ctx.moveTo(playerX, playerY - 4);
      ctx.lineTo(playerX + 4, playerY + 3);
      ctx.lineTo(playerX - 4, playerY + 3);
      ctx.closePath();
      ctx.fill();

      if (snapshot.stationPoints) {
        for (let s = 0; s < snapshot.stationPoints.length; s += 1) {
          const point = snapshot.stationPoints[s];
          const sx = Math.round((point.x / world.width) * width);
          const sy = Math.round((point.y / world.height) * height);
          const isBeacon = point.kind === "beacon";
          ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
          ctx.fillRect(sx - 3, sy - 3, 7, 7);
          ctx.fillStyle = isBeacon ? "#ffb066" : "#8fe3b0";
          ctx.fillRect(sx - 2, sy - 2, 4, 4);
          if (isBeacon) {
            ctx.fillStyle = "rgba(255, 176, 102, 0.35)";
            ctx.fillRect(sx - 4, sy - 4, 8, 8);
          }
        }
      }

      ctx.fillStyle = "rgba(244, 234, 216, 0.55)";
      ctx.font = "9px Consolas, monospace";
      ctx.fillText("W", 4, height - 5);
      ctx.textAlign = "right";
      ctx.fillText("E", width - 4, height - 5);
      ctx.textAlign = "left";
    }

    function saveSummaryMarkup(snapshot) {
      const summary = snapshot.saveSummary;
      if (!summary) {
        return '<p class="save-summary is-empty">No saved meadow yet — this world starts fresh and saves as you play.</p>';
      }
      return (
        '<p class="save-summary">Saved meadow · Day ' +
        summary.day +
        " · " +
        summary.blocksMined +
        " blocks mined · " +
        SAVE.formatDuration(summary.playtime) +
        " played · " +
        SAVE.formatAgo(summary.savedAt) +
        "</p>"
      );
    }

    function controlsMarkup() {
      const rows = CONTROLS.map(function row(pair) {
        return "<tr><td>" + pair[0] + "</td><td>" + pair[1] + "</td></tr>";
      }).join("");
      return (
        '<table class="help-table"><thead><tr><th>Input</th><th>Action</th></tr></thead><tbody>' +
        rows +
        "</tbody></table>" +
        '<ul class="help-tips">' +
        "<li>Blocks break faster with a better pickaxe. Stone needs a wooden pickaxe, iron ore needs stone, and ember ore needs iron.</li>" +
        "<li>Craft a workbench and place it near you to unlock tools and a furnace. A furnace smelts ore with coal.</li>" +
        "<li>Hollows appear in darkness at night. Torches light the caves and stop them spawning nearby.</li>" +
        "<li>Your world, inventory and journey save automatically every 20 seconds and when you pause.</li>" +
        "</ul>"
      );
    }

    function titleScreen(snapshot) {
      const hasSave = !!snapshot.saveSummary;
      const primaryLabel = hasSave ? "Continue" : "Enter world";
      return [
        '<div class="screen" data-screen="title">',
        '  <div class="title-screen">',
        '    <p class="title-kicker">A small 2D sandbox</p>',
        "    <h1>EMBERDEEP</h1>",
        '    <p class="title-tagline">Mine, craft, build — and light the deep.</p>',
        '    <div class="title-actions">',
        '      <button class="btn btn-primary" type="button" id="btn-primary" data-action="primary">' +
          primaryLabel +
          "</button>",
        hasSave
          ? '      <button class="btn" type="button" data-action="newWorld">New world</button>'
          : '      <button class="btn btn-ghost" type="button" data-action="help">Controls</button>',
        "    </div>",
        saveSummaryMarkup(snapshot),
        '    <div class="control-cards">',
        '      <div class="control-card"><strong>Move</strong><span>A / D or arrow keys, Space to jump. Walk to the trees.</span></div>',
        '      <div class="control-card"><strong>Mine &amp; build</strong><span>Hold left mouse to mine, right mouse to place. 1–9 selects a hotbar slot.</span></div>',
        '      <div class="control-card"><strong>Craft &amp; survive</strong><span>Press E to craft. Place a torch before night falls.</span></div>',
        "    </div>",
        '    <p class="title-offline">Runs offline from file:// · no build step · progress saves locally</p>',
        "  </div>",
        "</div>"
      ].join("");
    }

    function inventoryScreen(snapshot) {
      const slots = [];
      for (let i = 0; i < snapshot.inventory.slots.length; i += 1) {
        const stack = snapshot.inventory.slots[i];
        slots.push(
          '<button class="slot' +
            (stack ? "" : " is-empty") +
            (i < CONFIG.hotbarSize ? " in-hotbar" : "") +
            '" type="button" data-slot="' +
            i +
            '" aria-label="' +
            (i < CONFIG.hotbarSize ? "Hotbar slot " : "Inventory slot ") +
            (i + 1) +
            '"><canvas width="64" height="64"></canvas><span class="count">' +
            (stack && stack.count > 1 ? stack.count : "") +
            "</span></button>"
        );
      }
      const stations = snapshot.stationNames || [];
      const nearby = stations.length
        ? "Nearby station" + (stations.length > 1 ? "s" : "") + ": <b>" + stations.join(", ") + "</b>"
        : "No station nearby — place a workbench to unlock tools.";
      return [
        '<div class="screen" data-screen="inventory">',
        '  <div class="sheet inventory-sheet">',
        "    <header>",
        "      <h2>Inventory &amp; Crafting</h2>",
        '      <button class="btn btn-ghost" type="button" data-action="close">Close (E)</button>',
        "    </header>",
        '    <div class="inv-body">',
        '      <section class="inv-column">',
        '        <h3 class="section-title">Pack</h3>',
        '        <div class="inv-grid">' +
          slots.join("") +
          "</div>",
        '        <p class="inv-note">The first row is your hotbar. Click one slot, then another, to move or merge items. Number keys and the mouse wheel select the active slot.</p>',
        '        <div class="inv-legend"><span><i></i>Hotbar row</span><span><i class="cool"></i>Backpack</span></div>',
        "      </section>",
        '      <section class="recipes">',
        "        <h3>Crafting</h3>",
        '        <div class="nearby">' + nearby + "</div>",
        '        <div class="recipe-list">' + recipeRows(snapshot) + "</div>",
        "      </section>",
        "    </div>",
        "  </div>",
        "</div>"
      ].join("");
    }

    function recipeRows(snapshot) {
      const stations = snapshot.stations || new Set();
      return CRAFTING.list()
        .map(function row(recipe) {
          const availability = CRAFTING.availability(recipe, snapshot.inventory, stations);
          const inputs = recipe.inputs
            .map(function input(item) {
              const have = countItem(snapshot.inventory, item.id);
              const ok = have >= item.count;
              return (
                '<span class="' +
                (ok ? "ok" : "missing") +
                '">' +
                item.count +
                "× " +
                BLOCKS.itemName(item.id) +
                " (" +
                have +
                ")</span>"
              );
            })
            .join(" · ");
          const stationLabel = recipe.station ? recipe.station : "hand";
          const reason =
            availability.reason === "station"
              ? "Needs a nearby " + recipe.station
              : availability.reason === "materials"
                ? "Missing materials"
                : "Craft";
          return [
            '<div class="recipe' + (availability.ok ? "" : " is-locked") + '">',
            '  <div class="recipe-icon"><canvas width="60" height="60" data-icon="' +
              recipe.output.id +
              '"></canvas></div>',
            "  <div>",
            '    <div class="recipe-name">' + recipe.name + " × " + recipe.output.count + "</div>",
            '    <div class="recipe-meta">' + inputs + ' · <span class="station">' + stationLabel + "</span></div>",
            "  </div>",
            '  <button class="btn" type="button" data-craft="' +
              recipe.id +
              '"' +
              (availability.ok ? "" : " disabled") +
              ' title="' +
              reason +
              '">' +
              (availability.ok ? "Craft" : "Locked") +
              "</button>",
            "</div>"
          ].join("");
        })
        .join("");
    }

    function countItem(inventory, id) {
      let total = 0;
      for (let i = 0; i < inventory.slots.length; i += 1) {
        const stack = inventory.slots[i];
        if (stack && stack.id === id) {
          total += stack.count;
        }
      }
      return total;
    }

    function paintInventory() {
      const icons = refs.overlay.querySelectorAll("[data-slot] canvas");
      for (let i = 0; i < icons.length; i += 1) {
        const button = icons[i].closest("[data-slot]");
        const index = Number(button.dataset.slot);
        const stack = state.snapshot.inventory.slots[index];
        const ctx = icons[i].getContext("2d");
        ctx.clearRect(0, 0, icons[i].width, icons[i].height);
        if (stack) {
          RENDER.drawItemIcon(ctx, stack.id, icons[i].width);
        }
      }
      const recipeIcons = refs.overlay.querySelectorAll("[data-icon]");
      for (let i = 0; i < recipeIcons.length; i += 1) {
        const canvas = recipeIcons[i];
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        RENDER.drawItemIcon(ctx, Number(canvas.dataset.icon), canvas.width);
      }
      paintInventorySelection();
    }

    function refreshInventory() {
      if (state.screen !== "inventory" || !state.snapshot) {
        return;
      }
      refs.overlay.innerHTML = inventoryScreen(state.snapshot);
      paintInventory();
    }

    function pauseScreen(snapshot) {
      const summary = PROGRESSION.summary(snapshot.progress);
      return [
        '<div class="screen" data-screen="pause">',
        '  <div class="menu-card">',
        "    <h2>Paused</h2>",
        "    <p>Day " + snapshot.clock.day + " · " + phaseName(snapshot.clock.time) + "</p>",
        '    <p class="stat-line"><span>Journey</span><b>' +
          (summary.done ? "Complete" : summary.title) +
          "</b></p>",
        '    <p class="stat-line"><span>Blocks mined</span><b>' +
          snapshot.progress.stats.blocksMined +
          "</b></p>",
        '    <p class="stat-line"><span>Play time</span><b>' +
          SAVE.formatDuration(snapshot.progress.stats.playtime) +
          "</b></p>",
        '    <div class="menu-actions">',
        '      <button class="btn btn-primary" type="button" data-action="resume">Resume</button>',
        '      <button class="btn" type="button" data-action="save">Save now</button>',
        '      <button class="btn" type="button" data-action="help">Controls</button>',
        '      <button class="btn" type="button" data-action="mute">' +
          (state.muted ? "Unmute sound (M)" : "Mute sound (M)") +
          "</button>",
        state.newWorldArmed
          ? '      <button class="btn" type="button" data-action="newWorldConfirm" style="border-color:#e05c5c;color:#ffb3b3">Erase save and restart</button>'
          : '      <button class="btn btn-ghost" type="button" data-action="newWorld">New world…</button>',
        '      <button class="btn btn-ghost" type="button" data-action="quit">Quit to title</button>',
        "    </div>",
        '    <p class="menu-note">' +
          (snapshot.saveStatus ? snapshot.saveStatus.text : "Not saved yet") +
          "</p>",
        "  </div>",
        "</div>"
      ].join("");
    }

    function helpScreen() {
      return [
        '<div class="screen" data-screen="help">',
        '  <div class="sheet help-sheet">',
        "    <header>",
        "      <h2>Controls</h2>",
        '      <button class="btn btn-ghost" type="button" data-action="helpClose">Back</button>',
        "    </header>",
        controlsMarkup(),
        "  </div>",
        "</div>"
      ].join("");
    }

    function deathScreen(snapshot) {
      return [
        '<div class="screen" data-screen="death">',
        '  <div class="menu-card death-card">',
        "    <h2>You collapsed</h2>",
        "    <p>The hollows found you in the dark.</p>",
        '    <p class="stat-line"><span>Day</span><b>' + snapshot.clock.day + "</b></p>",
        '    <p class="stat-line"><span>Blocks mined</span><b>' +
          snapshot.progress.stats.blocksMined +
          "</b></p>",
        '    <div class="menu-actions">',
        '      <button class="btn btn-primary" type="button" data-action="respawn">Wake at the meadow</button>',
        "    </div>",
        '    <p class="menu-note">Your inventory is kept. Place more torches before the next night.</p>',
        "  </div>",
        "</div>"
      ].join("");
    }

    function victoryScreen(snapshot) {
      const summary = PROGRESSION.summary(snapshot.progress);
      return [
        '<div class="screen" data-screen="victory">',
        '  <div class="menu-card victory-card">',
        "    <h2>The Ember Beacon burns</h2>",
        "    <p>" + (summary.done ? "The deep is lit and the journey is complete." : "") + "</p>",
        '    <p class="stat-line"><span>Day</span><b>' + snapshot.clock.day + "</b></p>",
        '    <p class="stat-line"><span>Blocks mined</span><b>' +
          snapshot.progress.stats.blocksMined +
          "</b></p>",
        '    <p class="stat-line"><span>Play time</span><b>' +
          SAVE.formatDuration(snapshot.progress.stats.playtime) +
          "</b></p>",
        '    <div class="menu-actions">',
        '      <button class="btn btn-primary" type="button" data-action="victoryContinue">Keep building</button>',
        "    </div>",
        '    <p class="menu-note">Your world stays saved. The sandbox is yours.</p>',
        "  </div>",
        "</div>"
      ].join("");
    }

    function open(name, snapshot) {
      state.snapshot = snapshot || state.snapshot;
      state.screen = name;
      state.newWorldArmed = false;
      refs.overlay.classList.add("is-open");
      refs.overlay.dataset.screen = name;
      document.getElementById("app").dataset.screen = name;
      render();
    }

    function render() {
      if (!state.screen || !state.snapshot) {
        return;
      }
      switch (state.screen) {
        case "title":
          refs.overlay.innerHTML = titleScreen(state.snapshot);
          break;
        case "inventory":
          refs.overlay.innerHTML = inventoryScreen(state.snapshot);
          paintInventory();
          break;
        case "pause":
          refs.overlay.innerHTML = pauseScreen(state.snapshot);
          break;
        case "help":
          refs.overlay.innerHTML = helpScreen();
          break;
        case "death":
          refs.overlay.innerHTML = deathScreen(state.snapshot);
          break;
        case "victory":
          refs.overlay.innerHTML = victoryScreen(state.snapshot);
          break;
        default:
          refs.overlay.innerHTML = "";
      }
    }

    function close() {
      state.screen = null;
      state.pickedSlot = -1;
      state.newWorldArmed = false;
      refs.overlay.classList.remove("is-open");
      refs.overlay.removeAttribute("data-screen");
      refs.overlay.innerHTML = "";
      document.getElementById("app").dataset.screen = "playing";
    }

    function isBlocking() {
      return state.screen !== null;
    }

    function currentScreen() {
      return state.screen;
    }

    function handleHelp() {
      if (state.screen === "help") {
        open(state.helpReturn || "pause", state.snapshot);
        return;
      }
      state.helpReturn = state.screen || "pause";
      open("help", state.snapshot);
    }

    function setMuted(muted) {
      state.muted = !!muted;
    }

    function armNewWorld() {
      state.newWorldArmed = true;
      render();
    }

    function setSnapshot(snapshot) {
      state.snapshot = snapshot;
    }

    function refresh() {
      if (!state.snapshot) {
        return;
      }
      updateHud(state.snapshot);
      if (state.screen === "title") {
        render();
      }
    }

    function toast(text, kind) {
      const node = document.createElement("div");
      node.className = "toast" + (kind ? " kind-" + kind : "");
      node.textContent = text;
      refs.toasts.appendChild(node);
      while (refs.toasts.children.length > 4) {
        refs.toasts.removeChild(refs.toasts.firstChild);
      }
      window.setTimeout(function remove() {
        if (node.parentNode) {
          node.parentNode.removeChild(node);
        }
      }, 3600);
    }

    function showHint(text, duration) {
      refs.hint.textContent = text;
      refs.hint.classList.add("is-visible");
      window.clearTimeout(state.hintTimer);
      state.hintTimer = window.setTimeout(function hide() {
        refs.hint.classList.remove("is-visible");
      }, duration || 5200);
    }

    function clearHint() {
      window.clearTimeout(state.hintTimer);
      refs.hint.classList.remove("is-visible");
    }

    return {
      init: init,
      open: open,
      close: close,
      render: render,
      refresh: refresh,
      refreshInventory: refreshInventory,
      isBlocking: isBlocking,
      currentScreen: currentScreen,
      updateHud: updateHud,
      setSnapshot: setSnapshot,
      toast: toast,
      showHint: showHint,
      clearHint: clearHint,
      handleHelp: handleHelp,
      setMuted: setMuted,
      armNewWorld: armNewWorld,
      drawMinimap: drawMinimap
    };
  }

  return { createUI: createUI, CONTROLS: CONTROLS };
});
