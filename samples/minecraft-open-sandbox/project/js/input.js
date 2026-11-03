(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./config.js"));
  } else {
    root.SandboxInput = factory(root.SandboxConfig);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (CONFIG) {
  "use strict";

  if (!CONFIG) {
    throw new Error("SandboxConfig is required before SandboxInput");
  }

  const GAME_KEYS = {
    ArrowLeft: "left",
    ArrowRight: "right",
    KeyA: "left",
    KeyD: "right"
  };

  function createInput(canvas, handlers) {
    const api = handlers || {};
    const state = {
      left: false,
      right: false,
      jump: false,
      jumpPressed: false
    };
    const pointer = {
      clientX: 0,
      clientY: 0,
      tx: 0,
      ty: 0,
      valid: false,
      down: false,
      inside: false
    };
    let jumpQueued = false;

    function camera() {
      return api.getCamera ? api.getCamera() : { x: 0, y: 0 };
    }

    function tileFromClient(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return { tx: 0, ty: 0, valid: false };
      }
      const viewWidth = canvas.width || CONFIG.viewWidth;
      const viewHeight = canvas.height || CONFIG.viewHeight;
      const scaleX = viewWidth / rect.width;
      const scaleY = viewHeight / rect.height;
      const viewX = (clientX - rect.left) * scaleX;
      const viewY = (clientY - rect.top) * scaleY;
      const cam = camera();
      const tx = Math.floor((viewX + cam.x) / CONFIG.tileSize);
      const ty = Math.floor((viewY + cam.y) / CONFIG.tileSize);
      const world = api.getWorld ? api.getWorld() : null;
      const valid = world
        ? tx >= 0 && ty >= 0 && tx < world.width && ty < world.height
        : viewX >= 0 && viewY >= 0 && viewX < viewWidth && viewY < viewHeight;
      return { tx: tx, ty: ty, valid: valid };
    }

    function updatePointer(clientX, clientY) {
      pointer.clientX = clientX;
      pointer.clientY = clientY;
      const tile = tileFromClient(clientX, clientY);
      pointer.tx = tile.tx;
      pointer.ty = tile.ty;
      pointer.valid = tile.valid;
      if (api.onPointerMove) {
        api.onPointerMove(tile);
      }
    }

    function onKeyDown(event) {
      if (event.defaultPrevented) {
        return;
      }
      const code = event.code;
      if (GAME_KEYS[code]) {
        if (!api.isBlocked || !api.isBlocked()) {
          state[GAME_KEYS[code]] = true;
          event.preventDefault();
        }
        return;
      }
      if (code === "Space") {
        if (!api.isBlocked || !api.isBlocked()) {
          state.jump = true;
          if (!event.repeat) {
            jumpQueued = true;
            state.jumpPressed = true;
          }
          event.preventDefault();
        }
        return;
      }
      if (code.indexOf("Digit") === 0) {
        const index = Number(code.slice(5)) - 1;
        if (index >= 0 && index < CONFIG.hotbarSize && api.onSelectSlot) {
          api.onSelectSlot(index);
          event.preventDefault();
        }
        return;
      }
      switch (code) {
        case "KeyE":
          if (api.onToggleInventory) {
            api.onToggleInventory();
            event.preventDefault();
          }
          break;
        case "Escape":
          if (api.onEscape) {
            api.onEscape();
            event.preventDefault();
          }
          break;
        case "KeyH":
          if (api.onHelp) {
            api.onHelp();
            event.preventDefault();
          }
          break;
        case "KeyM":
          if (api.onMute) {
            api.onMute();
            event.preventDefault();
          }
          break;
        default:
          break;
      }
    }

    function onKeyUp(event) {
      if (GAME_KEYS[event.code]) {
        state[GAME_KEYS[event.code]] = false;
      } else if (event.code === "Space") {
        state.jump = false;
      }
    }

    function onPointerMove(event) {
      updatePointer(event.clientX, event.clientY);
    }

    function onPointerDown(event) {
      if (event.button === 2) {
        event.preventDefault();
        if (api.onPlace) {
          api.onPlace(tileFromClient(event.clientX, event.clientY));
        }
        return;
      }
      if (event.button !== 0) {
        return;
      }
      updatePointer(event.clientX, event.clientY);
      pointer.down = true;
      pointer.inside = true;
      if (canvas.setPointerCapture) {
        try {
          canvas.setPointerCapture(event.pointerId);
        } catch (error) {
          // Pointer capture is optional.
        }
      }
      if (api.onPointerDown) {
        api.onPointerDown(tileFromClient(event.clientX, event.clientY));
      }
      event.preventDefault();
    }

    function onPointerUp(event) {
      if (!pointer.down) {
        return;
      }
      pointer.down = false;
      if (canvas.releasePointerCapture && event && event.pointerId !== undefined) {
        try {
          canvas.releasePointerCapture(event.pointerId);
        } catch (error) {
          // Ignore capture release errors.
        }
      }
      if (api.onPointerUp) {
        api.onPointerUp();
      }
    }

    function onPointerLeave() {
      pointer.inside = false;
      if (pointer.down) {
        pointer.down = false;
        if (api.onPointerUp) {
          api.onPointerUp();
        }
      }
    }

    function onWheel(event) {
      if (api.isBlocked && api.isBlocked()) {
        return;
      }
      event.preventDefault();
      if (api.onWheel) {
        api.onWheel(event.deltaY > 0 ? 1 : -1);
      }
    }

    function onContextMenu(event) {
      event.preventDefault();
    }

    function attach() {
      window.addEventListener("keydown", onKeyDown);
      window.addEventListener("keyup", onKeyUp);
      canvas.addEventListener("pointermove", onPointerMove);
      canvas.addEventListener("pointerdown", onPointerDown);
      window.addEventListener("pointerup", onPointerUp);
      canvas.addEventListener("pointerleave", onPointerLeave);
      canvas.addEventListener("wheel", onWheel, { passive: false });
      canvas.addEventListener("contextmenu", onContextMenu);
    }

    function detach() {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointerleave", onPointerLeave);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("contextmenu", onContextMenu);
    }

    function consumeJump() {
      const pressed = jumpQueued || state.jumpPressed;
      jumpQueued = false;
      state.jumpPressed = false;
      return pressed;
    }

    function releaseAll() {
      state.left = false;
      state.right = false;
      state.jump = false;
      jumpQueued = false;
      pointer.down = false;
    }

    return {
      state: state,
      pointer: pointer,
      tileFromClient: tileFromClient,
      updatePointer: updatePointer,
      consumeJump: consumeJump,
      releaseAll: releaseAll,
      attach: attach,
      detach: detach
    };
  }

  return { createInput: createInput };
});
