// 装了吗 · Electron 主进程
// 职责：窗口管理、执行安装脚本（Windows PowerShell / macOS-Linux Bash）、流式回传日志
const { app, BrowserWindow, ipcMain, shell, clipboard, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");

const isDev = !!process.env.VITE_DEV_SERVER_URL;
const isMac = process.platform === "darwin";
const isWin = process.platform === "win32";

/** 正在运行的安装进程：id -> child */
const running = new Map();
// 用户主动取消的任务 id：退出码不应被当成安装失败
const cancelled = new Set();

function createWindow() {
  const win = new BrowserWindow({
    width: 1240,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: "#0f1220",
    title: "装了吗",
    titleBarStyle: isMac ? "hiddenInset" : "default",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  // 外部链接交给系统浏览器，绝不在应用内打开
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (isDev && url.startsWith(process.env.VITE_DEV_SERVER_URL)) return;
    if (url.startsWith("file://")) return;
    event.preventDefault();
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
  });

  return win;
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (!isMac) app.quit();
});

// ---------------------------------------------------------------- 系统信息
ipcMain.handle("app:info", () => ({
  platform: process.platform, // win32 / darwin / linux
  arch: process.arch,
  electron: process.versions.electron,
  node: process.versions.node,
  home: os.homedir(),
}));

ipcMain.handle("clipboard:write", (_e, text) => {
  clipboard.writeText(String(text ?? ""));
  return true;
});

ipcMain.handle("shell:openExternal", async (_e, url) => {
  if (!/^https?:\/\//.test(url)) return false;
  await shell.openExternal(url);
  return true;
});

// ---------------------------------------------------------------- 脚本执行
function normalizePlatform(p) {
  if (p === "darwin" || p === "macos") return "macos";
  if (p === "win32" || p === "windows") return "windows";
  return "linux";
}

function scriptFile(type, id) {
  const dir = path.join(os.tmpdir(), "zhuang-le-ma");
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${id}.${type === "powershell" ? "ps1" : "sh"}`);
}

/**
 * 写脚本文件。
 * .ps1 必须带 UTF-8 BOM：Windows PowerShell 5.1 读无 BOM 文件时会按系统 ANSI
 * 码页解码，脚本里的中文注释会变成乱码甚至引发解析错误。
 */
function writeScript(file, script) {
  if (file.endsWith(".ps1")) {
    fs.writeFileSync(file, "\uFEFF" + script, "utf-8");
  } else {
    fs.writeFileSync(file, script, "utf-8");
  }
}

/**
 * PowerShell 包装：
 * 1. UTF-8 输出（中文日志不乱码）
 * 2. $ProgressPreference=SilentlyContinue 加速 Invoke-WebRequest
 * 3. 执行策略只对本进程生效，不修改系统设置
 * 4. 错误不终止整个管道继续吐日志，最后由约定标记输出退出码
 */
function powershellArgs(file) {
  const inner = [
    "$ErrorActionPreference='Continue'",
    "$ProgressPreference='SilentlyContinue'",
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
    "$OutputEncoding=[Text.Encoding]::UTF8",
    `& '${file.replace(/'/g, "''")}'`,
    "exit $LASTEXITCODE",
  ].join("; ");
  return [
    "-NoLogo",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    inner,
  ];
}

function bashArgs(file) {
  return [file];
}

ipcMain.handle("install:start", async (event, payload) => {
  const { id, script, platform, scriptType } = payload || {};
  if (!id || !script) throw new Error("缺少脚本内容");
  if (running.has(id)) throw new Error("这个任务已经在跑了");

  const plat = normalizePlatform(platform || process.platform);
  const type = scriptType === "powershell" || plat === "windows" ? "powershell" : "bash";

  // 可信度检查：只允许脚本安装，不接受疑似提权爆破
  if (/Remove-Item\s+-Recurse\s+-Force\s+['"]?[A-Za-z]:\\?(?![^'"]*\\)/i.test(script)) {
    throw new Error("脚本包含高风险删除操作，已阻止自动执行");
  }

  const file = scriptFile(type, id);
  writeScript(file, script);

  const send = (channel, data) => {
    if (!event.sender.isDestroyed()) event.sender.send(channel, data);
  };

  let child;
  if (type === "powershell") {
    child = spawn("powershell.exe", powershellArgs(file), {
      windowsHide: true,
      cwd: os.homedir(),
      // 安装类软件（MySQL/Maven 等）输出很长，默认 1MB 缓冲会截断甚至挂起
      maxBuffer: 64 * 1024 * 1024,
    });
  } else {
    fs.chmodSync(file, 0o755);
    child = spawn("bash", bashArgs(file), {
      cwd: os.homedir(),
      env: { ...process.env, TERM: "xterm-256color" },
      maxBuffer: 64 * 1024 * 1024,
    });
  }

  running.set(id, child);
  send("install:log", { id, stream: "meta", text: `▶ 任务已启动（${type === "powershell" ? "PowerShell" : "Bash"}），脚本：${file}` });

  const pump = (stream) => (chunk) => {
    // 按行拆分，保留 \r 进度条内容
    const text = chunk.toString("utf8");
    for (const line of text.split(/\r?\n/)) {
      if (line.trim() !== "") send("install:log", { id, stream, text: line });
    }
  };
  child.stdout.on("data", pump("stdout"));
  child.stderr.on("data", pump("stderr"));

  child.on("error", (err) => {
    send("install:log", { id, stream: "stderr", text: `启动失败：${err.message}` });
    send("install:done", { id, code: -1, ok: false });
    running.delete(id);
  });

  child.on("close", (code, signal) => {
    running.delete(id);
    try { fs.unlinkSync(file); } catch { /* ignore */ }
    if (cancelled.delete(id)) {
      send("install:log", { id, stream: "meta", text: "■ 已由你取消执行" });
      send("install:done", { id, code: 130, ok: false, cancelled: true });
      return;
    }
    send("install:log", {
      id, stream: "meta",
      text: code === 0 ? "✔ 脚本执行完成" : `✖ 脚本退出码 ${code}${signal ? `（信号 ${signal}）` : ""}`,
    });
    send("install:done", { id, code: code ?? -1, ok: code === 0 });
  });

  return { ok: true, file };
});

/** 以管理员权限重新执行：Windows 用 UAC 提权，macOS 用 AppleScript do shell script with administrator privileges */
ipcMain.handle("install:startElevated", async (event, payload) => {
  const { id, script, platform, scriptType } = payload || {};
  if (!id || !script) throw new Error("缺少脚本内容");
  const plat = normalizePlatform(platform || process.platform);
  const type = scriptType === "powershell" || plat === "windows" ? "powershell" : "bash";
  const send = (channel, data) => {
    if (!event.sender.isDestroyed()) event.sender.send(channel, data);
  };

  if (isWin) {
    // 提权窗口独立运行，日志写入临时文件后由本进程轮询回传
    const logFile = path.join(os.tmpdir(), "zhuang-le-ma", `${id}.log`);
    fs.mkdirSync(path.dirname(logFile), { recursive: true });
    const psFile = scriptFile("powershell", id);
    writeScript(psFile, script);
    const outer = [
      `$log = '${logFile.replace(/'/g, "''")}'`,
      `"=== 装了吗 · 管理员模式 ===" | Out-File -FilePath $log -Encoding utf8`,
      `try { & '${psFile.replace(/'/g, "''")}' *>&1 | Tee-Object -FilePath $log -Append; $code = $LASTEXITCODE } catch { $_ | Out-File -FilePath $log -Append -Encoding utf8; $code = 1 }`,
      `if ($null -eq $code) { $code = 0 }`,
      `"__EXIT__$($code)" | Out-File -FilePath $log -Append -Encoding utf8`,
    ].join("; ");

    send("install:log", { id, stream: "meta", text: "▶ 请求管理员权限（UAC 弹窗请点「是」）…" });
    const child = spawn("powershell.exe", [
      "-NoProfile", "-ExecutionPolicy", "Bypass",
      "-Command",
      `Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-Command', ${JSON.stringify(outer)})`,
    ], { windowsHide: true });

    child.on("error", (err) => {
      send("install:log", { id, stream: "stderr", text: `提权失败：${err.message}` });
      send("install:done", { id, code: -1, ok: false });
    });
    child.on("close", () => {
      // 轮询日志文件直到出现 __EXIT__ 标记
      let offset = 0;
      let idle = 0;
      const timer = setInterval(() => {
        let content = "";
        try {
          // Out-File -Encoding utf8 会写 BOM，去掉避免日志开头出现 \uFEFF
          content = fs.readFileSync(logFile, "utf8").replace(/^\uFEFF/, "");
        } catch { /* 文件还没生成 */ }
        if (content.length > offset) {
          const fresh = content.slice(offset);
          offset = content.length;
          idle = 0;
          const exitMatch = fresh.match(/__EXIT__(-?\d+)/);
          const clean = fresh.replace(/__EXIT__-?\d+/, "").replace(/^\uFEFF/, "").trimEnd();
          if (clean.trim()) send("install:log", { id, stream: "stdout", text: clean });
          if (exitMatch) {
            clearInterval(timer);
            const code = Number(exitMatch[1]);
            send("install:done", { id, code, ok: code === 0 });
          }
          return;
        }
        idle += 1;
        // 用户取消了 UAC，60 秒无输出视为取消
        if (idle > 120) {
          clearInterval(timer);
          send("install:log", { id, stream: "stderr", text: "未检测到管理员窗口输出，可能已取消提权" });
          send("install:done", { id, code: -1, ok: false });
        }
      }, 500);
    });
    return { ok: true };
  }

  if (isMac) {
    const file = scriptFile("bash", id);
    writeScript(file, script);
    fs.chmodSync(file, 0o755);
    // 用 osascript 调用管理员权限，输出通过文件回传
    const logFile = path.join(os.tmpdir(), "zhuang-le-ma", `${id}.log`);
    const cmd = `/bin/bash '${file}' > '${logFile}' 2>&1; echo "__EXIT__$?" >> '${logFile}'`;
    const escaped = cmd.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    send("install:log", { id, stream: "meta", text: "▶ 请求管理员权限（系统弹窗请输入密码）…" });
    const child = spawn("osascript", ["-e", `do shell script "${escaped}" with administrator privileges`]);
    child.stderr.on("data", (d) => send("install:log", { id, stream: "stderr", text: d.toString().trim() }));
    child.on("close", () => {
      let content = "";
      try { content = fs.readFileSync(logFile, "utf8"); } catch { /* ignore */ }
      const match = content.match(/__EXIT__(-?\d+)/);
      const body = content.replace(/__EXIT__-?\d+/, "").trim();
      if (body) send("install:log", { id, stream: "stdout", text: body });
      const code = match ? Number(match[1]) : -1;
      send("install:done", { id, code, ok: code === 0 });
    });
    return { ok: true };
  }

  // Linux：无图形提权通道，提示用户用终端手动执行
  throw new Error("Linux 下请在终端中手动执行脚本（sudo 需要交互输入密码）");
});

ipcMain.handle("install:stop", async (_e, id) => {
  const child = running.get(id);
  if (!child) return { ok: false, reason: "没有正在运行的任务" };
  // 标记为用户主动取消，避免退出码 1 被当成「安装失败」展示
  cancelled.add(id);
  if (isWin) {
    spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true });
  } else {
    child.kill("SIGTERM");
  }
  running.delete(id);
  return { ok: true };
});

// 退出时清理残留子进程
app.on("before-quit", () => {
  for (const child of running.values()) {
    try { child.kill(); } catch { /* ignore */ }
  }
});

ipcMain.handle("dialog:message", async (_e, opts) => {
  const res = await dialog.showMessageBox(opts);
  return res.response;
});

// 生成任务 id（渲染进程也可以用，但主进程兜底）
ipcMain.handle("util:randomId", () => crypto.randomUUID());
