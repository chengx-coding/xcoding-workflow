**Language:** **English** | [简体中文](../zh-CN/orchestration/viewer.md)

# Local Orchestration Viewer

The Viewer provides human-readable inspection of managed runtime trees without adding another state owner. [`xc-orchestration-viewer`](../../skills/xc-orchestration-viewer/SKILL.md) is a script-free facade; [`xc-orchestration-runtime`](../../skills/xc-orchestration-runtime/SKILL.md) owns snapshots, the server, the registry, SVG rendering, and static frontend assets.

This one-way dependency prevents schema and state semantics from drifting between a runtime and a second visualization implementation.

## Snapshot Boundary

The Viewer never parses or edits managed runtime XML. Runtime's `snapshot` operation produces the stable read-only JSON model consumed by the server and browser. It includes runtime metadata, the node hierarchy, status counts, blackboard values, ready nodes, integrity information, and a version.

The server retains the last valid snapshot for each registered tree. If a refresh encounters a missing or temporarily invalid source, the UI can continue showing the last valid data while reporting health and the current error.

The Viewer API contains registry, snapshot, refresh, SVG download, client, heartbeat, and native-picker operations. It does not expose `start`, `complete`, `fail`, `block`, `set`, or any other orchestration mutation.

## Launch and Defaults

Launch the runtime-owned server:

```powershell
python <runtime-skill-dir>/scripts/viewer_server.py --tree <tree-ref>
```

The server binds only to `127.0.0.1`. Its preferred default port is `20668`;
if occupied, it uses an available ephemeral port. Defaults come from the
nearest `.xcoding/xc-orchestration-runtime.json`, with the runtime's shipped
JSON configuration as the reference:

```text
watch interval: 1 second
heartbeat: 15 seconds
idle shutdown: 120 seconds
```

Default launch creates a detached background process, opens the browser, and returns one JSON result containing `ok`, `mode`, `pid`, `url`, and `trees`. Background mode writes no logs. `--foreground` keeps the server in the terminal and emits JSON-line lifecycle, client, and refresh events. `--no-browser` is intended for automated verification.

The local Viewer server is an inspection tool, not an orchestration daemon or remote runtime API.

## Viewer Versus Package Daemon

The prerelease package's `xc daemon serve` is a separate local tool API. It
defaults to port `20669`, requires a process-lifetime bearer token plus exact
Host/Origin checks, accepts only runtime files supplied at launch, exposes nine
typed read-only queries, and provides bounded, non-replayable summary SSE.

The Viewer remains the browser interface on port `20668`. It owns its UI,
Viewer-local registry, refresh controls, native picker and SVG download. It
does not share the daemon token or registry. Native browser `EventSource`
cannot supply the daemon bearer header and is not the daemon's intended
client. Neither server exposes orchestration mutation, remote binding, a
durable event log, discovery, or automatic startup.

## Registry and Refresh

Repeated `--tree` arguments register initial trees. Explicit tree paths are allowed automatically. Additional direct path registration is limited to directories supplied through `--allow-root`.

The server watches registered sources at the configured interval. The browser checks the selected snapshot every 20 seconds and rerenders only when the version changes. Manual forced refresh remains available.

Each browser page has its own client registration and heartbeat. The server shuts down after the configured idle period with no active clients, including in background mode. Foreground mode is available for lifecycle diagnosis.

## Native Picker Security

The native picker is intentionally narrower than arbitrary local-file access:

- Requests must use the server's actual bound loopback Host.
- A browser Origin, when present, must match that Viewer origin.
- Picker requests are serialized; a second request is rejected while one dialog is active.
- The dialog runs in a helper process whose main thread owns the UI.
- On Windows, the helper opens without a console window.
- Cancellation is a normal result.
- Selecting one valid runtime file authorizes only that file's parent directory.

Direct path registration does not expand allow roots. The server does not bind to LAN or public interfaces and provides no remote authentication model.

## User Interface

The static HTML, CSS, and browser JavaScript render a connected horizontal tree. The implementation uses custom browser code and has no D3 dependency.

The interface provides:

- A collapsible sidebar for registering, selecting, and removing Viewer-local instances.
- Node status, executor, role, timing, results, artifacts, and details.
- Blackboard key/value rows and runtime update time.
- Per-tree collapse state, pan, wheel zoom, and synchronized range-slider zoom.
- A tall resizable graph viewport with pointer and keyboard resizing.
- Manual refresh, connection state, health reporting, and automatic reconnection.
- Complete standalone SVG download.

Removing an instance affects only the Viewer registry. Browser collapse, pan, zoom, and viewport state never mutate the runtime tree. SVG download includes the full snapshot, even if nodes are collapsed in the browser.

## Operational Boundaries

Use the Viewer to understand progress and health. Use runtime public commands for any state transition, integrity repair, recovery, or artifact query.

The Viewer does not provide worker management, forced cancellation, historical event sourcing, arbitrary filesystem browsing, or a writable workflow dashboard. Those are not hidden UI features; they are outside the current contract.
