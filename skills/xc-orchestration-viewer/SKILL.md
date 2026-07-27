---
name: "xc-orchestration-viewer"
description: "Opens, monitors, or visualizes managed runtime trees through the runtime-owned local viewer. Invoke when a user asks to inspect orchestration progress visually."
---

# XC Orchestration Viewer

This script-free facade provides a precise entry point for human-readable tree inspection. It owns no XML parser, state machine, server, or frontend assets; all implementation belongs to the sibling `xc-orchestration-runtime` Skill.

## Dependency Contract

The default runtime directory is `$SKILL_DIR/../xc-orchestration-runtime`. A non-sibling installation must provide `runtime_skill_dir`.

Before launch, verify these runtime public interfaces:

```text
<runtime_skill_dir>/scripts/orchestration.py
<runtime_skill_dir>/scripts/viewer_server.py
<runtime_skill_dir>/viewer/static/index.html
```

The viewer consumes only the runtime snapshot protocol. It MUST NOT directly parse, edit, or reformat managed XML.

## Launch

```powershell
python <runtime_skill_dir>\scripts\viewer_server.py `
  --tree <tree_ref> `
  --allow-root <additional_runtime_directory>
```

The server binds to `127.0.0.1`, prefers port `20668`, falls back to an available local port, opens it in the default browser, and returns immediately after a detached background server is ready. Standard output contains exactly one JSON result with `ok`, `mode`, `pid`, `url`, and `trees`; background mode does not write logs. Pass `--foreground` when manually launching the Viewer to keep it in the terminal and receive JSON-line lifecycle, client, and refresh events. Pass `--no-browser` only for automated verification.

Explicit `--tree` paths are automatically allowed. Manual registration from the page is limited to explicit `--allow-root` paths, so the viewer cannot become an arbitrary local file reader.

## Behavior

- The viewer is read-only and exposes no lifecycle or blackboard mutation endpoints.
- Runtime trees render as a connected horizontal node graph, not a nested list.
- A collapsible sidebar registers, selects, and removes viewer-local runtime-tree instances. Removing an instance never modifies its runtime tree or files.
- Drag the graph canvas to pan and use the mouse wheel to zoom; graph expansion controls affect browser presentation only.
- Blackboard values render as collapsible key-value rows with the runtime tree's last update time.
- Browser pages use independent heartbeats, display fixed `Connecting`, `Connected`, or `Disconnected` Viewer connection state, and retry registration after a connection loss.
- The server closes after the configured idle period without active clients, including when it runs in the default background mode.
- The server polls for changes, preserves the last valid snapshot after parse errors, and reports tree health to the page.

User-editable defaults are loaded from the nearest `.xcoding/xc-orchestration-runtime.toml`. See `xc-orchestration-runtime/assets/xc-orchestration-runtime.toml` for the supported configuration.
