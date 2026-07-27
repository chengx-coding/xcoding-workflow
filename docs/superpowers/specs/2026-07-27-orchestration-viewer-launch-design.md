# Orchestration Viewer Launch and Connection Design

**Date:** 2026-07-27
**Status:** Approved for implementation

## Purpose

Make the local orchestration viewer reliable when launched by hosts that time out or reap foreground shell commands. Clarify the browser's connection state and remove a misleading graph-control decoration.

## Scope

The change affects the canonical `xc-orchestration-runtime` viewer server and static browser application, plus the public runtime and viewer Skill launch instructions. It also adds focused server and browser-behavior verification.

It does not change the runtime-tree snapshot protocol, managed XML access rules, loopback-only binding policy, or the browser's read-only permissions.

## Accepted Decisions

- The default server launch mode is background.
- `--foreground` starts the server in the current terminal for manual observation and sends necessary runtime events to the console.
- A successful background launch writes exactly one JSON object to standard output. It includes `ok`, `mode`, `pid`, `url`, and `trees`; it does not include a log-file path.
- The background child does not write runtime logs to a file or terminal.
- The server retains its existing `idle_shutdown_seconds` lifecycle: it exits after the configured idle period with no active browser clients.
- The browser uses a fixed header connection badge with `Connecting`, `Connected`, and `Disconnected` states.
- The graph's decorative crosshair is removed. Empty graph space remains the panning surface and uses the grab/grabbing cursor affordance.

## Launch Architecture

`viewer_server.py` remains the public executable and retains its existing tree, allow-root, configuration, host, port, and browser arguments. Its default invocation becomes a short-lived launcher:

```text
python viewer_server.py --tree <tree_ref>
```

The launcher creates an internal readiness record, starts the same script in a private server-child mode, waits for the child to bind and publish its URL, then exits after writing one JSON result:

```json
{
  "ok": true,
  "mode": "background",
  "pid": 12345,
  "url": "http://127.0.0.1:20668/",
  "trees": []
}
```

The private child mode is not documented as a public interface. It receives the complete resolved launch configuration, starts the HTTP server, and atomically publishes readiness only after binding succeeds. The launcher removes the readiness record after consuming it. If the child exits or does not become ready within a bounded startup interval, the launcher returns a nonzero exit code with a concise error on standard error.

The background child is independent of its calling shell. On Windows it uses the appropriate detached-process creation flags; on POSIX systems it starts a new session. In both cases, its standard input, output, and error are discarded. This ensures OpenCode or a similar host cannot close the Viewer by timing out its launch shell and ensures background mode produces no log file.

Unless `--no-browser` is supplied, the launcher opens the ready URL after successful startup. The private child never opens a browser. Existing loopback-only host validation, preferred-port fallback, initial-tree registration, and idle-shutdown behavior remain unchanged.

`--foreground` bypasses the launcher and runs the server in the current terminal. Foreground mode writes newline-delimited JSON events with an `event` field. The required event names are `viewer_started`, `viewer_stopped`, `tree_refresh_failed`, `tree_refresh_recovered`, `client_connected`, `client_expired`, and `idle_shutdown`. It does not emit an event for every heartbeat or ordinary static request.

## Browser Connection State

The static page replaces the top-bar text node with a status badge that is always visible and announced to assistive technology. Its state model is:

| State | Meaning | Visual treatment |
| --- | --- | --- |
| `Connecting` | The page is registering or re-registering its browser client. | Neutral indicator |
| `Connected` | Client registration and subsequent heartbeats succeed. | Green indicator |
| `Disconnected` | A registration, heartbeat, or Viewer API request cannot reach the server. | Red indicator |

On connection failure, the page clears its stale client identifier, stops the current heartbeat timer, updates the badge immediately, and schedules one registration retry after two seconds. It never schedules concurrent retries. A successful registration creates a new client identifier, starts its heartbeat timer, and returns the badge to `Connected`. This also covers a Viewer restart that invalidates the browser's previous client ID.

The existing tree refresh loop continues to update runtime-tree presentation. Its transport failures also set the badge to `Disconnected`; they do not erase the last successfully rendered snapshot. No reconnect logic directly parses or modifies managed runtime XML.

The graph HTML, JavaScript, and CSS remove `graph-pan-handle` and its associated element reference and style. Panning behavior remains attached to empty graph viewport space, so the cursor is the only visible panning affordance and does not move with the graph content.

## Public Documentation

Update both `xc-orchestration-runtime` and `xc-orchestration-viewer` Skill launch examples and behavior guarantees:

- Document that background startup is the default.
- Document `--foreground` for manual logging.
- Document the background JSON result fields and lack of background logs.
- Preserve `--no-browser` as the automated-verification option.
- State that browser pages display the Viewer connection state and retry after a loss of connection.

These are canonical Skill changes, so `python build_agents.py` must synchronize the updated packages into `.agents/skills/`.

## Verification

Focused automated coverage must prove:

1. A background launch returns a single parseable JSON object, exits promptly, leaves its child reachable through `/api/health`, and reports the actual fallback port.
2. The child remains reachable after the launcher process has exited, then shuts down according to a temporary `idle_shutdown_seconds` configuration.
3. `--foreground --no-browser` keeps the process running, emits the expected startup and shutdown event records, and serves the health endpoint.
4. Existing tree registration, snapshot, heartbeat, allow-root, and read-only API behavior remain valid.
5. The browser has no graph panning decoration, displays each connection state, and changes to `Disconnected` when the server is stopped. Restarting the server lets the page reconnect and return to `Connected`.

Run the relevant Viewer tests, `python build_agents.py`, the complete repository test suite, and `git diff --check`. Browser-state verification may use the local browser automation capability when available; an unavailable browser environment must be reported as a coverage limitation.

## Risks and Compatibility

The default command changes from blocking to returning after startup. Callers that need the previous terminal-attached behavior must pass `--foreground`. The Viewer facade will use the new default, so agent tools receive the background JSON rather than a long-running command.

Subprocess detachment differs by operating system; focused tests cover the current Windows environment, and the implementation isolates platform-specific creation flags to a small launcher helper. The Viewer remains local-only and continues to enforce existing allowed-root controls.
