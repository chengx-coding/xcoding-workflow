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
    let captured = null;
    const listener = (e) => { captured = { code: e.code, key: e.key, target: String(e.target) }; };
    window.addEventListener("keydown", listener);
    const event = new KeyboardEvent("keydown", { code: "KeyD", key: "d", bubbles: true, cancelable: true });
    const dispatched = window.dispatchEvent(event);
    window.removeEventListener("keydown", listener);
    return { captured, dispatched, eventCode: event.code, eventKey: event.key };
  })()`,
  returnByValue: true
});
console.log(JSON.stringify(result.result.value));
ws.close();
