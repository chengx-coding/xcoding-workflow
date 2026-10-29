const targets = await (await fetch("http://127.0.0.1:9223/json")).json();
const page = targets.find((target) => target.type === "page" && target.url.startsWith("file:"));
if (!page) throw new Error("page target not found");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve);
  ws.addEventListener("error", reject);
});
let nextId = 1;
const pending = new Map();
ws.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  }
});
function send(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
async function evaluate(expression, awaitPromise = false) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "evaluation failed");
  return result.result ? result.result.value : undefined;
}
await send("Runtime.enable");
await send("Page.enable");
await send("Page.bringToFront");
await send("Page.reload", { ignoreCache: true });
await new Promise((resolve) => setTimeout(resolve, 1200));
await send("Page.bringToFront");
await evaluate(`(() => { window.__sandbox.newWorld(874213); return true; })()`);
await new Promise((resolve) => setTimeout(resolve, 250));
const initial = await evaluate(`(() => {
  const s = window.__sandbox;
  const c = window.SandboxConfig;
  const rect = document.getElementById("game").getBoundingClientRect();
  const px = Math.floor(s.player.x) + 2;
  const py = s.world.ground[px];
  return {
    ready: s.ready,
    status: document.getElementById("status").dataset.state,
    rect: { width: rect.width, height: rect.height, left: rect.left, top: rect.top },
    player: { x: s.player.x, y: s.player.y },
    camera: { x: s.camera.x, y: s.camera.y },
    seed: s.world.seed,
    mine: { x: px, y: py, block: s.world.data[py * s.world.width + px] },
    surface: py,
    hotbar: c.hotbar.length
  };
})()`);
console.log("INITIAL", JSON.stringify(initial));

const mineResult = await evaluate(`(() => {
  const s = window.__sandbox;
  const c = window.SandboxConfig;
  const canvas = document.getElementById("game");
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor(s.player.x) + 2;
  const y = s.world.ground[x];
  const sx = ((x + 0.5) * c.tileSize - s.camera.x - s.camera.shakeX) * rect.width / c.viewWidth + rect.left;
  const sy = ((y + 0.5) * c.tileSize - s.camera.y - s.camera.shakeY) * rect.height / c.viewHeight + rect.top;
  canvas.dispatchEvent(new PointerEvent("pointermove", { clientX: sx, clientY: sy, bubbles: true, pointerType: "mouse" }));
  canvas.dispatchEvent(new PointerEvent("pointerdown", { clientX: sx, clientY: sy, bubbles: true, button: 0, buttons: 1, pointerType: "mouse" }));
  return { x, y, sx, sy, after: s.world.data[y * s.world.width + x] };
})()`);
console.log("MINE", JSON.stringify(mineResult));

const placeResult = await evaluate(`(async () => {
  window.dispatchEvent(new KeyboardEvent("keydown", { code: "Digit7", bubbles: true, cancelable: true }));
  window.dispatchEvent(new KeyboardEvent("keyup", { code: "Digit7", bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 80));
  const s = window.__sandbox;
  const c = window.SandboxConfig;
  const canvas = document.getElementById("game");
  const rect = canvas.getBoundingClientRect();
  let tx = -1, ty = -1;
  for (let dx = -3; dx <= 3 && tx < 0; dx++) {
    for (let dy = -3; dy <= 1; dy++) {
      const x = Math.floor(s.player.x) + dx;
      const y = Math.floor(s.player.y) + dy;
      if (window.SandboxInteraction.canPlaceBlock(s.world, s.player, x, y, c.reach).ok) { tx = x; ty = y; break; }
    }
  }
  if (tx < 0) return { error: "no placement cell" };
  const sx = ((tx + 0.5) * c.tileSize - s.camera.x - s.camera.shakeX) * rect.width / c.viewWidth + rect.left;
  const sy = ((ty + 0.5) * c.tileSize - s.camera.y - s.camera.shakeY) * rect.height / c.viewHeight + rect.top;
  canvas.dispatchEvent(new PointerEvent("pointermove", { clientX: sx, clientY: sy, bubbles: true, pointerType: "mouse" }));
  canvas.dispatchEvent(new PointerEvent("pointerdown", { clientX: sx, clientY: sy, bubbles: true, button: 2, buttons: 2, pointerType: "mouse" }));
  return { tx, ty, sx, sy, after: s.world.data[ty * s.world.width + tx], selected: document.getElementById("selectedLabel").textContent };
})()`, true);
console.log("PLACE", JSON.stringify(placeResult));

const moveResult = await evaluate(`(async () => {
  const s = window.__sandbox;
  const start = s.player.x;
  window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyD", bubbles: true, cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 500));
  window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyD", bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 120));
  return { start, end: s.player.x, onGround: s.player.onGround, status: document.getElementById("status").dataset.state };
})()`, true);
console.log("MOVE", JSON.stringify(moveResult));

const saved = await evaluate(`(() => { window.__sandbox.save(); const raw = localStorage.getItem(window.SandboxConfig.saveKey); return { saved: !!raw, length: raw ? raw.length : 0 }; })()`);
console.log("SAVED", JSON.stringify(saved));
await send("Page.reload", { ignoreCache: true });
await new Promise((resolve) => setTimeout(resolve, 1500));
const restoredExpression = `(() => { const s = window.__sandbox; return { ready: s.ready, status: document.getElementById("status").dataset.state, x: s.player.x, y: s.player.y, selected: document.getElementById("selectedLabel").textContent, placed: s.world.data[${placeResult.ty} * s.world.width + ${placeResult.tx}] }; })()`;
const restored = await evaluate(restoredExpression);
console.log("RESTORED", JSON.stringify(restored));
ws.close();
