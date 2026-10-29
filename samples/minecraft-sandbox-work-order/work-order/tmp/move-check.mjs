const targets = await (await fetch("http://127.0.0.1:9223/json")).json();
const page = targets.find((target) => target.type === "page" && target.url.startsWith("file:"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.addEventListener("open", resolve); ws.addEventListener("error", reject); });
let id = 1;
const pending = new Map();
ws.addEventListener("message", (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const entry = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? entry.reject(new Error(JSON.stringify(msg.error))) : entry.resolve(msg.result);
  }
});
function send(method, params = {}) {
  const messageId = id++;
  ws.send(JSON.stringify({ id: messageId, method, params }));
  return new Promise((resolve, reject) => pending.set(messageId, { resolve, reject }));
}
const result = await send("Runtime.evaluate", {
  expression: `(() => {
    const s = window.__sandbox;
    const p = s.player;
    const w = s.world;
    const overlaps = window.SandboxPlayer.overlapsSolid(w, p.x, p.y, p.width, p.height);
    const blocks = [];
    for (let dx = -3; dx <= 3; dx++) {
      for (let dy = -2; dy <= 1; dy++) {
        const x = Math.floor(p.x) + dx;
        const y = Math.floor(p.y) + dy;
        blocks.push([x, y, w.data[y * w.width + x]]);
      }
    }
    const startX = p.x;
    window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyD", key: "d", bubbles: true, cancelable: true }));
    return { x: p.x, y: p.y, vx: p.vx, vy: p.vy, onGround: p.onGround, overlaps, blocks, startX };
  })()`,
  returnByValue: true
});
console.log(JSON.stringify(result.result.value, null, 2));
await new Promise((resolve) => setTimeout(resolve, 700));
const after = await send("Runtime.evaluate", {
  expression: `(() => { const p = window.__sandbox.player; return { x: p.x, vx: p.vx, y: p.y, onGround: p.onGround }; })()`,
  returnByValue: true
});
console.log("AFTER", JSON.stringify(after.result.value));
await send("Runtime.evaluate", { expression: `window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyD", key: "d", bubbles: true }))` });
ws.close();
