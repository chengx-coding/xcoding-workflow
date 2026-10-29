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
async function evaluate(expression, awaitPromise = true) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise });
  if (result.exceptionDetails) return { exception: result.exceptionDetails.text, description: result.exceptionDetails.exception && result.exceptionDetails.exception.description };
  return result.result.value;
}
await send("Runtime.enable");
await send("Page.enable");
await send("Page.bringToFront");
await send("Page.reload", { ignoreCache: true });
await new Promise((resolve) => setTimeout(resolve, 1200));
await send("Page.bringToFront");
const dialogs = await evaluate(`(async () => {
  document.getElementById("newWorldButton").click();
  const opened = !document.getElementById("seedPanel").hidden;
  document.getElementById("seedInput").value = "12345";
  document.getElementById("generateWorld").click();
  await new Promise((resolve) => setTimeout(resolve, 350));
  const seed = document.getElementById("seedValue").textContent;
  const closed = document.getElementById("seedPanel").hidden;
  const gameSeed = window.__sandbox.world.seed;
  document.getElementById("helpButton").click();
  const helpOpen = !document.getElementById("helpPanel").hidden;
  window.dispatchEvent(new KeyboardEvent("keydown", { code: "Escape", bubbles: true, cancelable: true }));
  const helpClosed = document.getElementById("helpPanel").hidden;
  window.dispatchEvent(new KeyboardEvent("keydown", { code: "Digit9", bubbles: true, cancelable: true }));
  await new Promise((resolve) => setTimeout(resolve, 50));
  const selected = document.getElementById("selectedLabel").textContent;
  const selectedIndex = Array.prototype.findIndex.call(document.querySelectorAll("#hotbarSlots .slot"), (slot) => slot.classList.contains("is-selected"));
  return { opened, seed, closed, gameSeed, helpOpen, helpClosed, selected, selectedIndex, status: document.getElementById("status").dataset.state };
})()`);
console.log(JSON.stringify(dialogs, null, 2));
ws.close();
