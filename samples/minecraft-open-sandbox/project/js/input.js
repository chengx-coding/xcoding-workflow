(function (root) {
  "use strict";

  function createInput(canvas, handlers) {
    const state = {
      left: false,
      right: false,
      jump: false,
      jumpPressed: false,
      mouseX: 0,
      mouseY: 0,
      inside: false,
      leftButton: false,
      rightButton: false
    };
    const callbacks = handlers || {};
    let attached = false;

    function toCanvas(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        return { x: 0, y: 0 };
      }
      return {
        x: ((clientX - rect.left) / rect.width) * canvas.width,
        y: ((clientY - rect.top) / rect.height) * canvas.height
      };
    }

    function handleKeyDown(event) {
      if (event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) {
        return;
      }
      const code = event.code;
      if (code === "KeyA" || code === "ArrowLeft") {
        state.left = true;
        event.preventDefault();
      } else if (code === "KeyD" || code === "ArrowRight") {
        state.right = true;
        event.preventDefault();
      } else if (code === "KeyW" || code === "Space" || code === "ArrowUp") {
        if (!state.jump) {
          state.jumpPressed = true;
        }
        state.jump = true;
        event.preventDefault();
      }
      if (event.repeat) {
        return;
      }
      if (typeof callbacks.onKeyDown === "function") {
        callbacks.onKeyDown(code, event);
      }
    }

    function handleKeyUp(event) {
      const code = event.code;
      if (code === "KeyA" || code === "ArrowLeft") {
        state.left = false;
      } else if (code === "KeyD" || code === "ArrowRight") {
        state.right = false;
      } else if (code === "KeyW" || code === "Space" || code === "ArrowUp") {
        state.jump = false;
      }
    }

    function handlePointerMove(event) {
      const point = toCanvas(event.clientX, event.clientY);
      state.mouseX = point.x;
      state.mouseY = point.y;
      state.inside = true;
    }

    function handlePointerDown(event) {
      const point = toCanvas(event.clientX, event.clientY);
      state.mouseX = point.x;
      state.mouseY = point.y;
      state.inside = true;
      if (event.button === 0) {
        state.leftButton = true;
      } else if (event.button === 2) {
        state.rightButton = true;
      }
      if (typeof callbacks.onMouseDown === "function") {
        callbacks.onMouseDown(event.button);
      }
    }

    function handlePointerUp(event) {
      if (event.button === 0) {
        state.leftButton = false;
      } else if (event.button === 2) {
        state.rightButton = false;
      }
    }

    function handleWheel(event) {
      event.preventDefault();
      if (typeof callbacks.onWheel === "function") {
        callbacks.onWheel(event.deltaY > 0 ? 1 : -1);
      }
    }

    function handleBlur() {
      state.left = false;
      state.right = false;
      state.jump = false;
      state.jumpPressed = false;
      state.leftButton = false;
      state.rightButton = false;
    }

    function handleContextMenu(event) {
      event.preventDefault();
    }

    function handlePointerLeave() {
      state.inside = false;
      state.leftButton = false;
      state.rightButton = false;
    }

    function attach() {
      if (attached) {
        return;
      }
      attached = true;
      root.addEventListener("keydown", handleKeyDown);
      root.addEventListener("keyup", handleKeyUp);
      root.addEventListener("blur", handleBlur);
      canvas.addEventListener("pointermove", handlePointerMove);
      canvas.addEventListener("pointerdown", handlePointerDown);
      root.addEventListener("pointerup", handlePointerUp);
      canvas.addEventListener("pointerleave", handlePointerLeave);
      canvas.addEventListener("contextmenu", handleContextMenu);
      canvas.addEventListener("wheel", handleWheel, { passive: false });
    }

    function detach() {
      if (!attached) {
        return;
      }
      attached = false;
      root.removeEventListener("keydown", handleKeyDown);
      root.removeEventListener("keyup", handleKeyUp);
      root.removeEventListener("blur", handleBlur);
      canvas.removeEventListener("pointermove", handlePointerMove);
      canvas.removeEventListener("pointerdown", handlePointerDown);
      root.removeEventListener("pointerup", handlePointerUp);
      canvas.removeEventListener("pointerleave", handlePointerLeave);
      canvas.removeEventListener("contextmenu", handleContextMenu);
      canvas.removeEventListener("wheel", handleWheel);
    }

    function consumeJumpPressed() {
      const pressed = state.jumpPressed;
      state.jumpPressed = false;
      return pressed;
    }

    function consumeRightButton() {
      const pressed = state.rightButton;
      state.rightButton = false;
      return pressed;
    }

    attach();

    return {
      state: state,
      toCanvas: toCanvas,
      consumeJumpPressed: consumeJumpPressed,
      consumeRightButton: consumeRightButton,
      detach: detach
    };
  }

  if (typeof module === "object" && module.exports) {
    module.exports = { createInput: createInput };
  } else {
    root.SandboxInput = { createInput: createInput };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
