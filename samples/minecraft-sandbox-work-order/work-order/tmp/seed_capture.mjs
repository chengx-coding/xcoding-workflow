import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGE = "file:///C:/dev/xcoding-workflow-dev/wf-ablation/standard-sample/workspace/project/index.html";
const TMP = "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\tmp";
const PROFILE = `${TMP}\\chrome-seed-profile`;
const PORT = 9558;

rmSync(PROFILE, { recursive: true, force: true });
mkdirSync(PROFILE, { recursive: true });

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--window-size=960,600",
    PAGE
  ],
  { stdio: "ignore" }
);

async function getJson(path) {
  const response = await fetch(`http://127.0.0.1:${PORT}${path}`);
  return response.json();
}

let ws;
try {
  let target = null;
  for (let attempt = 0; attempt < 80 && !target; attempt += 1) {
    try {
      const list = await getJson("/json/list");
      target = list.find((item) => item.type === "page" && item.url.startsWith("file:")) || null;
    } catch (error) {
      // starting
    }
    if (!target) await sleep(250);
  }
  if (!target) throw new Error("no target");
  ws = await new Promise((resolve, reject) => {
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    socket.addEventListener("open", () => resolve(socket));
    socket.addEventListener("error", reject);
  });
  let nextId = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
      else entry.resolve(message.result);
    }
  });
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }
  await send("Runtime.enable");
  await send("Page.enable");
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (await evaluate("Boolean(window.__sandbox && window.__sandbox.ready)")) break;
    await sleep(120);
  }
  await sleep(400);
  await evaluate("document.getElementById('helpBtn').click()");
  await sleep(200);
  await evaluate("(() => { document.getElementById('seedInput').value = '31415926'; document.getElementById('seedApply').click(); })()");
  await sleep(700);
  const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(`${TMP}\\seed-31415926.png`, Buffer.from(shot.data, "base64"));
  const state = await evaluate("(() => ({ seed: window.__sandbox.world.seed, paused: window.__sandbox.state.paused, status: document.getElementById('status').dataset.state }))()");
  console.log(JSON.stringify({ ok: true, state }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exitCode = 1;
} finally {
  try {
    if (ws) ws.close();
  } catch (error) {
    // ignore
  }
  chrome.kill();
  await sleep(300);
  rmSync(PROFILE, { recursive: true, force: true });
}
