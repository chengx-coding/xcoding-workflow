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
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) return { exception: result.exceptionDetails.text, description: result.exceptionDetails.exception && result.exceptionDetails.exception.description };
  return { value: result.result.value };
}
console.log("worldApi", await evaluate(`JSON.stringify({ seed: window.SandboxWorld.createWorld(123456).seed, current: window.__sandbox.world.seed, fn: String(window.__sandbox.newWorld).slice(0, 130) })`));
console.log("call", await evaluate(`(() => { window.__sandbox.newWorld(123456); return JSON.stringify({ seed: window.__sandbox.world.seed, x: window.__sandbox.player.x, y: window.__sandbox.player.y }); })()`));
console.log("after", await evaluate(`new Promise((resolve) => setTimeout(() => resolve(JSON.stringify({ seed: window.__sandbox.world.seed, x: window.__sandbox.player.x })), 300))`));
ws.close();
