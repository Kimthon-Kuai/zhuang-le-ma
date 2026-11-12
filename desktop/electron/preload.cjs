// 预加载：只暴露白名单 API 给渲染进程，保持 contextIsolation
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("zlm", {
  info: () => ipcRenderer.invoke("app:info"),
  copy: (text) => ipcRenderer.invoke("clipboard:write", text),
  openExternal: (url) => ipcRenderer.invoke("shell:openExternal", url),
  randomId: () => ipcRenderer.invoke("util:randomId"),
  messageBox: (opts) => ipcRenderer.invoke("dialog:message", opts),

  install: {
    start: (payload) => ipcRenderer.invoke("install:start", payload),
    startElevated: (payload) => ipcRenderer.invoke("install:startElevated", payload),
    stop: (id) => ipcRenderer.invoke("install:stop", id),
    /** 注册日志回调，返回取消订阅函数 */
    onLog: (cb) => {
      const handler = (_e, data) => cb(data);
      ipcRenderer.on("install:log", handler);
      return () => ipcRenderer.removeListener("install:log", handler);
    },
    onDone: (cb) => {
      const handler = (_e, data) => cb(data);
      ipcRenderer.on("install:done", handler);
      return () => ipcRenderer.removeListener("install:done", handler);
    },
  },
});
