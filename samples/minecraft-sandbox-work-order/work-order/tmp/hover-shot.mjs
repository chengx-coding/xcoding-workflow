import { writeFileSync } from "node:fs";
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
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true });
  return result.result.value;
}
await send("Runtime.enable");
await send("Page.enable");
await evaluate(`(() => {
  const s = window.__sandbox;
  const c = window.SandboxConfig;
  const canvas = document.getElementById("game");
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor(s.player.x) + 2;
  const y = s.world.ground[x];
  const sx = ((x + 0.5) * c.tileSize - s.camera.x - s.camera.shakeX) * rect.width / c.viewWidth + rect.left;
  const sy = ((y + 0.5) * c.tileSize - s.camera.y - s.camera.shakeY) * rect.height / c.viewHeight + rect.top;
  canvas.dispatchEvent(new PointerEvent("pointermove", { clientX: sx, clientY: sy, bubbles: true, pointerType: "mouse" }));
  return { sx, sy };
})()`);
await new Promise((resolve) => setTimeout(resolve, 300));
const shot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/dev/xcoding-workflow-dev/wf-ablation/sample-create/workshop/.xcoding/work-orders/20261029-1219-2d-sandbox-game/tmp/hover-render.png", Buffer.from(shot.data, "base64"));
console.log("captured");
ws.close();
