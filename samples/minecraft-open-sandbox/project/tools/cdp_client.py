#!/usr/bin/env python3
"""Minimal Chrome DevTools Protocol client for offline game verification.

Standard library only. It launches headless Chrome with a workspace profile,
opens a page, evaluates JavaScript, dispatches real input events, and captures
screenshots. This is a verification tool, not part of the game runtime.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


def find_chrome(explicit: str | Path | None = None) -> str:
    if explicit:
        return str(explicit)
    for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
        from shutil import which

        found = which(name)
        if found:
            return found
    raise RuntimeError("no Chrome executable found")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class WebSocket:
    def __init__(self, host: str, port: int, path: str, origin: str) -> None:
        self.sock = socket.create_connection((host, port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: {origin}\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake failed")
            response += chunk
        header, _, self.buffer = response.partition(b"\r\n\r\n")
        status = header.split(b"\r\n", 1)[0]
        if b"101" not in status:
            raise RuntimeError("websocket upgrade rejected: " + status.decode("latin-1", "replace"))

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _read_exact(self, size: int) -> bytes:
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise RuntimeError("websocket closed")
            data += chunk
        return data

    def read_frame(self) -> tuple[int, bytes]:
        header = self._read_exact(2)
        first, second = header[0], header[1]
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def recv_text(self) -> str:
        while True:
            opcode, payload = self.read_frame()
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise RuntimeError("websocket closed by peer")
            if opcode == 0x9:
                # pong
                pong = bytearray([0x8A, 0x80])
                mask = os.urandom(4)
                pong.extend(mask)
                pong.extend(bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload)))
                self.sock.sendall(bytes(pong))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class Chrome:
    def __init__(self, page: Path, profile_dir: Path, home_dir: Path, width: int = 960, height: int = 600) -> None:
        self.chrome = find_chrome()
        self.port = free_port()
        self.page = page
        self.profile_dir = profile_dir
        self.home_dir = home_dir
        profile_dir.mkdir(parents=True, exist_ok=True)
        home_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["HOME"] = str(home_dir)
        self.process = subprocess.Popen(
            [
                self.chrome,
                "--headless=new",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-crash-reporter",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-allow-origins=*",
                "--hide-scrollbars",
                f"--window-size={width},{height}",
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={profile_dir}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self.ws: WebSocket | None = None
        self.width = width
        self.height = height
        self.next_id = 1
        self.events: list[dict[str, Any]] = []
        self._connect()

    def _connect(self) -> None:
        deadline = time.time() + 20
        version = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/version", timeout=1
                ) as response:
                    version = json.loads(response.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(0.1)
        if not version:
            self.close()
            raise RuntimeError("Chrome did not expose a debugging endpoint")
        deadline = time.time() + 10
        target = None
        while time.time() < deadline:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as response:
                targets = json.loads(response.read().decode("utf-8"))
            for item in targets:
                if item.get("type") == "page":
                    target = item
                    break
            if target:
                break
            time.sleep(0.1)
        if not target:
            self.close()
            raise RuntimeError("Chrome exposed no page target")
        path = target["webSocketDebuggerUrl"].split(f"127.0.0.1:{self.port}", 1)[-1]
        origin = f"http://127.0.0.1:{self.port}"
        self.ws = WebSocket("127.0.0.1", self.port, path, origin)
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("Log.enable")
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": self.width,
            "height": self.height,
            "deviceScaleFactor": 1,
            "mobile": False,
        })

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.ws is not None
        request_id = self.next_id
        self.next_id += 1
        self.ws.send_text(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        deadline = time.time() + 20
        while time.time() < deadline:
            message = json.loads(self.ws.recv_text())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result", {})
            if "method" in message:
                self.events.append(message)
        raise RuntimeError(f"timed out waiting for {method}")

    def navigate(self) -> None:
        marker = len(self.events)
        self.send("Page.navigate", {"url": self.page.resolve().as_uri()})
        deadline = time.time() + 15
        loaded = False
        while time.time() < deadline:
            if any(event.get("method") == "Page.loadEventFired" for event in self.events[marker:]):
                loaded = True
                break
            try:
                message = json.loads(self.ws.recv_text())  # type: ignore[union-attr]
            except Exception:
                break
            if "method" in message:
                self.events.append(message)
        if not loaded:
            # The document may already have loaded before enable; still allow
            # callers to inspect the page after a bounded settle period.
            time.sleep(0.8)
        else:
            time.sleep(0.5)

    def eval(self, expression: str, await_promise: bool = False) -> Any:
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        )
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            text = details.get("exception", {}).get("description") or details.get("text")
            raise RuntimeError("JavaScript error: " + str(text))
        remote = result.get("result", {})
        if "value" in remote:
            return remote["value"]
        return remote.get("description")

    def screenshot(self, path: Path) -> None:
        result = self.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(result["data"]))

    def key(self, code: str, key: str = "", age_ms: int = 80) -> None:
        self.send("Input.dispatchKeyEvent", {"type": "keyDown", "code": code, "key": key or code})
        time.sleep(age_ms / 1000)
        self.send("Input.dispatchKeyEvent", {"type": "keyUp", "code": code, "key": key or code})

    def hold_key(self, code: str, key: str, hold_ms: int) -> None:
        self.send("Input.dispatchKeyEvent", {"type": "keyDown", "code": code, "key": key})
        time.sleep(hold_ms / 1000)
        self.send("Input.dispatchKeyEvent", {"type": "keyUp", "code": code, "key": key})

    def click(self, x: float, y: float, button: str = "left", dwell_ms: int = 120) -> None:
        self.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": 1})
        time.sleep(dwell_ms / 1000)
        self.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": 1})
        time.sleep(0.12)

    def close(self) -> None:
        if self.ws:
            self.ws.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
