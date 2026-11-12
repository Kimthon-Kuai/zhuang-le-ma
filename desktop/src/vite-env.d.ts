/// <reference types="vite/client" />

interface InstallLog {
  id: string;
  stream: "stdout" | "stderr" | "meta";
  text: string;
}

interface InstallDone {
  id: string;
  code: number;
  ok: boolean;
  cancelled?: boolean;
}

interface Window {
  zlm?: {
    info: () => Promise<{
      platform: string;
      arch: string;
      electron: string;
      node: string;
      home: string;
    }>;
    copy: (text: string) => Promise<boolean>;
    openExternal: (url: string) => Promise<boolean>;
    randomId: () => Promise<string>;
    messageBox: (opts: {
      type?: "none" | "info" | "error" | "question" | "warning";
      title?: string;
      message: string;
      detail?: string;
      buttons?: string[];
      defaultId?: number;
      cancelId?: number;
    }) => Promise<number>;
    install: {
      start: (payload: {
        id: string;
        script: string;
        platform: string;
        scriptType: string;
      }) => Promise<{ ok: boolean; file?: string }>;
      startElevated: (payload: {
        id: string;
        script: string;
        platform: string;
        scriptType: string;
      }) => Promise<{ ok: boolean }>;
      stop: (id: string) => Promise<{ ok: boolean; reason?: string }>;
      onLog: (cb: (data: InstallLog) => void) => () => void;
      onDone: (cb: (data: InstallDone) => void) => () => void;
    };
  };
}
