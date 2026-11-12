import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const TOKEN_KEY = "zlm.admin.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(msg: string, status: number) {
    super(msg);
    this.status = status;
  }
}

export async function req<T>(
  path: string,
  init?: RequestInit & { auth?: boolean },
): Promise<T> {
  const { auth = true, ...rest } = init || {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((rest.headers as Record<string, string>) || {}),
  };
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(path, { ...rest, headers });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    if (res.status === 401 && auth) setToken(null);
    const detail = (data as { detail?: string })?.detail;
    throw new ApiError(typeof detail === "string" ? detail : `请求失败 (${res.status})`, res.status);
  }
  return data as T;
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
  regenerate_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Feedback {
  id: number;
  plan_id: number | null;
  software_name: string | null;
  version: string | null;
  platform: string | null;
  rating: "valid" | "invalid";
  content: string | null;
  handled: number;
  created_at: string;
  handled_at: string | null;
}

export interface StatRow {
  kind: string;
  key: string;
  software_name: string | null;
  platform: string | null;
  count: number;
  updated_at: string;
}

export interface Stats {
  totals: { plans: number; software: number; feedbacks: number; pending_feedbacks: number };
  software: StatRow[];
  version: StatRow[];
  platform: StatRow[];
  install_run: StatRow[];
  plan_generate: StatRow[];
  plans: {
    software_name: string;
    version: string;
    platform: string;
    valid_count: number;
    invalid_count: number;
    updated_at: string;
  }[];
}

export const PLATFORM_LABEL: Record<string, string> = {
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
};

export function fmtTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}
