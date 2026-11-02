(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./blocks.js"));
  } else {
    root.SandboxBackdrop = factory(root.SandboxBlocks);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (BLOCKS) {
  "use strict";

  if (!BLOCKS) {
    throw new Error("SandboxBlocks is required before SandboxBackdrop");
  }

  const KINDS = ["edit", "mode", "time", "view"];

  function createBackdrop(options) {
    const settings = options || {};
    return {
      edits: [],
      pulses: [],
      undoStack: [],
      redoStack: [],
      cap: settings.cap || 80,
      pulseCap: settings.pulseCap || 12,
      undoCap: settings.undoCap || 60
    };
  }

  function nameOf(blockId) {
    if (blockId === 0) {
      return "Air";
    }
    return BLOCKS.nameOf(blockId);
  }

  function trim(list, cap) {
    while (list.length > cap) {
      list.shift();
    }
  }

  // Records a world change and the before/after labels the HUD shows. This is
  // the single entry point for "removed or covered content" so the visual state
  // can never lose what it replaced.
  function recordEdit(backdrop, edit) {
    const entry = {
      x: edit.x,
      y: edit.y,
      before: edit.before,
      after: edit.after,
      beforeName: nameOf(edit.before),
      afterName: nameOf(edit.after),
      kind: edit.kind || "edit",
      at: edit.at || Date.now()
    };
    backdrop.edits.push(entry);
    trim(backdrop.edits, backdrop.cap);
    backdrop.undoStack.push(entry);
    trim(backdrop.undoStack, backdrop.undoCap);
    backdrop.redoStack.length = 0;
    pulse(backdrop, "edit", entry.beforeName, entry.afterName, entry.at, {
      beforeId: entry.before,
      afterId: entry.after
    });
    return entry;
  }

  function pulse(backdrop, kind, before, after, at, ids) {
    const entry = {
      kind: kind,
      before: String(before),
      after: String(after),
      at: at || Date.now()
    };
    if (ids) {
      entry.beforeId = ids.beforeId;
      entry.afterId = ids.afterId;
    }
    backdrop.pulses.push(entry);
    trim(backdrop.pulses, backdrop.pulseCap);
    return entry;
  }

  function currentPulse(backdrop) {
    return backdrop.pulses.length ? backdrop.pulses[backdrop.pulses.length - 1] : null;
  }

  function recentEdits(backdrop, limit) {
    const count = limit || 6;
    const out = [];
    for (let index = backdrop.edits.length - 1; index >= 0 && out.length < count; index -= 1) {
      out.push(backdrop.edits[index]);
    }
    return out;
  }

  function peekUndo(backdrop) {
    return backdrop.undoStack.length ? backdrop.undoStack[backdrop.undoStack.length - 1] : null;
  }

  function undo(backdrop) {
    if (!backdrop.undoStack.length) {
      return null;
    }
    const entry = backdrop.undoStack.pop();
    backdrop.redoStack.push(entry);
    return entry;
  }

  function redo(backdrop) {
    if (!backdrop.redoStack.length) {
      return null;
    }
    const entry = backdrop.redoStack.pop();
    backdrop.undoStack.push(entry);
    return entry;
  }

  function canUndo(backdrop) {
    return backdrop.undoStack.length > 0;
  }

  function canRedo(backdrop) {
    return backdrop.redoStack.length > 0;
  }

  function describeEdit(edit) {
    return {
      position: "(" + edit.x + ", " + edit.y + ")",
      before: edit.beforeName,
      after: edit.afterName,
      arrow: edit.beforeName + " -> " + edit.afterName
    };
  }

  function isKind(kind) {
    return KINDS.indexOf(kind) >= 0;
  }

  function serialize(backdrop) {
    return {
      pulses: backdrop.pulses.map(function (entry) {
        return { kind: entry.kind, before: entry.before, after: entry.after, at: entry.at };
      })
    };
  }

  return {
    KINDS: KINDS,
    createBackdrop: createBackdrop,
    recordEdit: recordEdit,
    pulse: pulse,
    currentPulse: currentPulse,
    recentEdits: recentEdits,
    peekUndo: peekUndo,
    undo: undo,
    redo: redo,
    canUndo: canUndo,
    canRedo: canRedo,
    describeEdit: describeEdit,
    isKind: isKind,
    nameOf: nameOf,
    serialize: serialize
  };
});
