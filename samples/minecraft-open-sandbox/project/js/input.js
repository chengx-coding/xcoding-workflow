/* Keyboard and pointer input. Real DOM events, no synthetic shortcuts. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInput = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  const MOVE_KEYS = {
    KeyA: "left",
    ArrowLeft: "left",
    KeyD: "right",
    ArrowRight: "right",
    KeyW: "up",
    ArrowUp: "up",
    KeyS: "down",
    ArrowDown: "down",
    Space: "jump"
  };

  function createInput(canvas, options) {
    const settings = options || {};
    const state = {
      left: false,
      right: false,
      up: false,
      down: false,
      jump: false,
      sprint: false,
      mouseX: CONFIG.viewWidth / 2,
      mouseY: CONFIG.viewHeight / 2,
      mouseDown: false,
      rightDown: false,
      justPressed: new Set(),
      justReleased: new Set(),
      wheel: 0,
      lastInputAt: 0,
      keys: new Set()
    };

    function markActivity() {
      state.lastInputAt = performance.now();
      if (typeof settings.onActivity === "function") {
        settings.onActivity();
      }
    }

    function keyDown(event) {
      if (event.defaultPrevented) {
        return;
      }
      const code = event.code;
      if (code === "Space" || code === "ArrowUp" || code === "ArrowDown" || code === "ArrowLeft" || code === "ArrowRight") {
        event.preventDefault();
      }
      if (event.repeat) {
        return;
      }
      state.keys.add(code);
      state.justPressed.add(code);
      const move = MOVE_KEYS[code];
      if (move) {
        state[move] = true;
      }
      if (code === "ShiftLeft" || code === "ShiftRight") {
        state.sprint = true;
      }
      markActivity();
    }

    function keyUp(event) {
      const code = event.code;
      state.keys.delete(code);
      state.justReleased.add(code);
      const move = MOVE_KEYS[code];
      if (move) {
        state[move] = false;
      }
      if (code === "ShiftLeft" || code === "ShiftRight") {
        state.sprint = false;
      }
    }

    function pointerPosition(event) {
      const rect = canvas.getBoundingClientRect();
      const width = rect.width || CONFIG.viewWidth;
      const height = rect.height || CONFIG.viewHeight;
      return {
        x: Math.max(0, Math.min(CONFIG.viewWidth, ((event.clientX - rect.left) / width) * CONFIG.viewWidth)),
        y: Math.max(0, Math.min(CONFIG.viewHeight, ((event.clientY - rect.top) / height) * CONFIG.viewHeight))
      };
    }

    function mouseMove(event) {
      const position = pointerPosition(event);
      state.mouseX = position.x;
      state.mouseY = position.y;
    }

    function mouseDown(event) {
      if (event.button === 0) {
        state.mouseDown = true;
      } else if (event.button === 2) {
        state.rightDown = true;
      } else {
        return;
      }
      markActivity();
      event.preventDefault();
    }

    function mouseUp(event) {
      if (event.button === 0) {
        state.mouseDown = false;
      } else if (event.button === 2) {
        state.rightDown = false;
      }
    }

    function wheel(event) {
      state.wheel += Math.sign(event.deltaY);
      markActivity();
      event.preventDefault();
    }

    function contextMenu(event) {
      event.preventDefault();
    }

    function blur() {
      state.left = false;
      state.right = false;
      state.up = false;
      state.down = false;
      state.jump = false;
      state.sprint = false;
      state.mouseDown = false;
      state.rightDown = false;
      state.keys.clear();
    }

    window.addEventListener("keydown", keyDown, { passive: false });
    window.addEventListener("keyup", keyUp);
    canvas.addEventListener("mousemove", mouseMove);
    canvas.addEventListener("mousedown", mouseDown);
    window.addEventListener("mouseup", mouseUp);
    canvas.addEventListener("wheel", wheel, { passive: false });
    canvas.addEventListener("contextmenu", contextMenu);
    window.addEventListener("blur", blur);

    state.consumePress = function (code) {
      if (state.justPressed.has(code)) {
        state.justPressed.delete(code);
        return true;
      }
      return false;
    };

    state.consumeAnyPress = function (codes) {
      for (const code of codes) {
        if (state.consumePress(code)) {
          return code;
        }
      }
      return null;
    };

    state.consumeWheel = function () {
      const value = state.wheel;
      state.wheel = 0;
      return value;
    };

    state.clearFrame = function () {
      state.justPressed.clear();
      state.justReleased.clear();
      state.wheel = 0;
    };

    state.destroy = function () {
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("keyup", keyUp);
      canvas.removeEventListener("mousemove", mouseMove);
      canvas.removeEventListener("mousedown", mouseDown);
      window.removeEventListener("mouseup", mouseUp);
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("contextmenu", contextMenu);
      window.removeEventListener("blur", blur);
    };

    return state;
  }

  function toInput(state) {
    return {
      left: state.left,
      right: state.right,
      up: state.up,
      down: state.down,
      jump: state.jump,
      sprint: state.sprint
    };
  }

  return {
    createInput: createInput,
    toInput: toInput
  };
});
