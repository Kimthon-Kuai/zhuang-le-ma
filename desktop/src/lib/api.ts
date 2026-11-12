/** 服务端 API 客户端。服务地址可在设置里改，默认 127.0.0.1:8017 */

export type Platform = "windows" | "macos" | "linux";

export interface Software {
  id: number | null;
  name: string;
  display_name: string;
  category?: string | null;
  source?: string | null;
  repo?: string | null;
  homepage?: string | null;
  platforms?: string[];
  aliases?: string[];
}

export interface IdentifyResult {
  software: Software;
  matched: boolean;
  ai_used: boolean;
}

export interface VersionItem {
  version: string;
  is_latest: boolean;
}

export interface VersionsResult {
  software: Software;
  versions: VersionItem[];
  source: string;
  cached: boolean;
}

export interface Plan {
  id: number;
  software_name: string;
  version: string;
  platform: string;
  markdown: string;
  script: string | null;
  script_type: string | null;
  install_mode: string;
  model?: string | null;
  valid_count: number;
  invalid_count: number;
  cached: boolean;
  created_at?: string;
  updated_at?: string;
}

const BASE_KEY = "zlm.serverBase";

export function getServerBase(): string {
  const custom = localStorage.getItem(BASE_KEY);
  return (custom || "http://127.0.0.1:8017").replace(/\/+$/, "");
}

export function setServerBase(url: string) {
  if (url) localStorage.setItem(BASE_KEY, url.replace(/\/+$/, ""));
  else localStorage.removeItem(BASE_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = 200_000, ...rest } = init || {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${getServerBase()}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(rest.headers || {}) },
    });
    const text = await res.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const detail =
        (data as { detail?: unknown })?.detail ?? (typeof data === "string" ? data : "请求失败");
      throw new ApiError(
        typeof detail === "string" ? detail : JSON.stringify(detail),
        res.status,
      );
    }
    return data as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") {
      throw new ApiError("服务端响应太慢，超过 200 秒，稍后再试", 408);
    }
    throw new ApiError(
      "连不上服务端。请确认 server 已启动（默认 http://127.0.0.1:8017）",
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () =>
    request<{ ok: boolean; ai_configured: boolean; model: string | null; slogan: string }>(
      "/api/health",
      { timeoutMs: 5000 },
    ),
  software: () => request<Software[]>("/api/software", { timeoutMs: 8000 }),
  identify: (text: string) =>
    request<IdentifyResult>("/api/identify", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  versions: (id: number, platform: Platform, refresh = false) =>
    request<VersionsResult>(
      `/api/software/${id}/versions?platform=${platform}&refresh=${refresh}`,
    ),
  createPlan: (body: {
    software: string;
    version: string;
    platform: Platform;
    display_name?: string;
    homepage?: string | null;
    force?: boolean;
  }) => request<Plan>("/api/plans", { method: "POST", body: JSON.stringify(body) }),
  lookupPlan: (softwareId: number, version: string, platform: Platform) =>
    request<Plan>(
      `/api/plans/lookup?software_id=${softwareId}&version=${encodeURIComponent(version)}&platform=${platform}`,
    ),
  feedback: (body: {
    plan_id?: number;
    software_name?: string;
    version?: string;
    platform?: string;
    rating: "valid" | "invalid";
    content?: string;
  }) => request<{ id: number }>("/api/feedback", { method: "POST", body: JSON.stringify(body) }),
  stat: (body: { kind: string; key: string; software_name?: string; platform?: string }) =>
    request<{ ok: boolean }>("/api/stats", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 5000,
    }).catch(() => ({ ok: false })),
};
