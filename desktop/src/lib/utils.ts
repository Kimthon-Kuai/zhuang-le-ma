import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 把 Electron 的 win32/darwin/linux 归一成 API 用的 windows/macos/linux */
export function normalizePlatform(p: string): "windows" | "macos" | "linux" {
  if (p === "darwin" || p === "macos") return "macos";
  if (p === "win32" || p === "windows") return "windows";
  return "linux";
}

export const PLATFORM_LABEL: Record<string, string> = {
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
};

export function relativeTime(iso?: string | null): string {
  if (!iso) return "刚刚";
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  if (Number.isNaN(t)) return "刚刚";
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} 小时前`;
  return `${Math.floor(h / 24)} 天前`;
}
