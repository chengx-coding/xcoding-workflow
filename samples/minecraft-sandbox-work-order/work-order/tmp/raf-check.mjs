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
async function evaluate(expression, awaitPromise = false) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "evaluation failed");
  return result.result.value;
}
console.log("visibility", await evaluate(`JSON.stringify({hidden: document.hidden, state: document.visibilityState, focus: document.hasFocus()})`));
await send("Page.bringToFront");
await send("Emulation.setFocusEmulationEnabled", { enabled: true });
await send("Page.setWebLifecycleState", { state: "active" });
console.log("focus-after", await evaluate(`JSON.stringify({hidden: document.hidden, state: document.visibilityState, focus: document.hasFocus()})`));
const raf = await evaluate(`new Promise((resolve) => { const t = setTimeout(() => resolve("timeout"), 1200); requestAnimationFrame(() => { clearTimeout(t); resolve("raf"); }); })`, true);
console.log("raf", raf);
const before = await evaluate(`window.__sandbox.player.x`);
await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyD", key: "d", bubbles: true, cancelable: true }))`);
await new Promise((resolve) => setTimeout(resolve, 600));
const after = await evaluate(`(() => { const p = window.__sandbox.player; return { x: p.x, vx: p.vx, y: p.y }; })()`);
await evaluate(`window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyD", key: "d", bubbles: true }))`);
console.log("move", JSON.stringify({ before, after }));
ws.close();
