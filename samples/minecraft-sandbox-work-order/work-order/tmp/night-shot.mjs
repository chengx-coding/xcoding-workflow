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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "evaluation failed");
  return result.result.value;
}
await send("Runtime.enable");
await send("Page.enable");
await send("Page.reload", { ignoreCache: true });
await new Promise((resolve) => setTimeout(resolve, 1200));
await evaluate(`(() => { window.__sandbox.setDayTime(0.81); const canvas = document.getElementById("game"); canvas.dispatchEvent(new PointerEvent("pointerleave", { bubbles: true })); return true; })()`);
await new Promise((resolve) => setTimeout(resolve, 350));
const shot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/dev/xcoding-workflow-dev/wf-ablation/sample-create/workshop/.xcoding/work-orders/20261029-1219-2d-sandbox-game/tmp/night-render.png", Buffer.from(shot.data, "base64"));
console.log("captured night");
ws.close();
