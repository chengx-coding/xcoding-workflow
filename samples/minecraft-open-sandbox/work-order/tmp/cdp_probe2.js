"use strict";
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const profile = path.resolve(process.argv[2]);
fs.mkdirSync(profile, { recursive: true });
const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
console.log("launching", profile);
const child = spawn(
  chrome,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-allow-origins=*",
    "--remote-debugging-port=0",
    "--user-data-dir=" + profile,
    "--window-size=1280,900",
    "about:blank"
  ],
  { stdio: "ignore" }
);
child.on("exit", (code) => console.log("chrome exit", code));

function get(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => resolve(body));
    });
    req.on("error", reject);
    req.setTimeout(3000, () => req.destroy(new Error("http timeout")));
  });
}

(async () => {
  const file = path.join(profile, "DevToolsActivePort");
  const start = Date.now();
  while (!fs.existsSync(file)) {
    if (Date.now() - start > 15000) throw new Error("no port file");
    await new Promise((r) => setTimeout(r, 100));
  }
  const lines = fs.readFileSync(file, "utf8").trim().split(/\r?\n/);
  console.log("port", lines[0], "browser path", lines[1]);
  const list = JSON.parse(await get("http://127.0.0.1:" + lines[0] + "/json/list"));
  console.log("targets", list.map((t) => t.type + " " + t.url));
  const page = list.find((t) => t.type === "page");
  console.log("ws", page.webSocketDebuggerUrl);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("ws open timeout")), 5000);
    ws.addEventListener("open", () => {
      clearTimeout(timer);
      console.log("ws open");
      resolve();
    });
    ws.addEventListener("error", (e) => {
      clearTimeout(timer);
      reject(new Error("ws error " + String(e.message || e.type)));
    });
  });
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    } else {
      console.log("event", msg.method);
    }
  });
  function send(method, params) {
    return new Promise((resolve) => {
      const callId = ++id;
      pending.set(callId, resolve);
      ws.send(JSON.stringify({ id: callId, method, params: params || {} }));
      setTimeout(() => {
        if (pending.has(callId)) {
          pending.delete(callId);
          resolve({ error: "timeout " + method });
        }
      }, 5000);
    });
  }
  console.log("enable", await send("Page.enable"));console.log("runtime", JSON.stringify(await send("Runtime.enable")));console.log("log", JSON.stringify(await send("Log.enable")));console.log("emu", JSON.stringify(await send("Emulation.setDeviceMetricsOverride",{width:1280,height:900,deviceScaleFactor:1,mobile:false})));
  console.log("eval", JSON.stringify(await send("Runtime.evaluate", { expression: "1+1", returnByValue: true })));
  console.log("navigate", JSON.stringify(await send("Page.navigate", { url: "file:///C:/dev/xcoding-workflow-dev/wf-iterations/open-sample-047/xc/project/index.html" })));
  await new Promise((r) => setTimeout(r, 1500));
  console.log("eval2", JSON.stringify(await send("Runtime.evaluate", { expression: "document.readyState + '|' + !!(window.__game && window.__game.ready)", returnByValue: true })));
  ws.close();
  child.kill();
  setTimeout(() => process.exit(0), 500);
})().catch((error) => {
  console.error("FAIL", error);
  child.kill();
  process.exit(1);
});

