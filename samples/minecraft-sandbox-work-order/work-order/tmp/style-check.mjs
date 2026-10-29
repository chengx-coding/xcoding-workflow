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
    const el = document.getElementById("minimapPanel");
    const cs = getComputedStyle(el);
    const journal = getComputedStyle(document.getElementById("journal"));
    return {
      opacity: cs.opacity,
      background: cs.background,
      backgroundColor: cs.backgroundColor,
      backdropFilter: cs.backdropFilter,
      animation: cs.animation,
      zIndex: cs.zIndex,
      journalOpacity: journal.opacity,
      journalBackground: journal.backgroundColor,
      mapOpacity: getComputedStyle(document.getElementById("minimap")).opacity,
      rect: el.getBoundingClientRect().toJSON()
    };
  })()`,
  returnByValue: true
});
console.log(JSON.stringify(result.result.value, null, 2));
ws.close();
