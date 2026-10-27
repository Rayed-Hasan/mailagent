const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const http = require("http");
const path = require("path");

const port = Number(process.env.MAILAGENT_PORT || 8765);
const token = crypto.randomBytes(32).toString("hex");
let backend;

function checkBackend() {
  return new Promise((resolve) => {
    const request = http.get(`http://127.0.0.1:${port}/`, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on("error", () => resolve(false));
    request.setTimeout(800, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function waitForBackend() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (await checkBackend()) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Mail Agent backend did not start on the local port");
}

function startBackend() {
  const python = process.env.MAILAGENT_PYTHON || "python";
  const backendRoot = app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.resolve(__dirname, "..");
  backend = spawn(
    python,
    ["-m", "uvicorn", "mailagent.dashboard.app:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: backendRoot,
      env: {
        ...process.env,
        DASHBOARD_HOST: "127.0.0.1",
        DASHBOARD_PORT: String(port),
        DASHBOARD_API_TOKEN: token,
        DASHBOARD_USER_ID: process.env.MAILAGENT_USER_ID || "local-user",
        STORAGE_BACKEND: "sqlite",
        TASK_QUEUE_BACKEND: "local",
      },
      windowsHide: true,
    },
  );
  backend.stderr.on("data", (data) => {
    if (process.env.MAILAGENT_DESKTOP_DEBUG) process.stderr.write(data);
  });
  backend.on("error", (error) => dialog.showErrorBox("Mail Agent startup failed", error.message));
}

async function createWindow() {
  startBackend();
  await waitForBackend();
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 960,
    minHeight: 700,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  const query = new URLSearchParams({
    api: `http://127.0.0.1:${port}`,
    token,
  });
  await window.loadURL(`http://127.0.0.1:${port}/app/index.html?${query}`);
}

app.whenReady().then(() => createWindow().catch((error) => {
  dialog.showErrorBox("Mail Agent could not start", error.message);
  app.quit();
}));
app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  if (backend && !backend.killed) backend.kill();
});
