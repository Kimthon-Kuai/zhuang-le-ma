import { useMemo, useState } from "react";
import { ChevronDown, RefreshCw, Search, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { VersionItem } from "@/lib/api";

const SOURCE_LABEL: Record<string, string> = {
  cache: "服务端缓存",
  npm: "npm registry",
  pypi: "PyPI",
  github: "GitHub Releases",
  maven: "Maven Central",
  "python-build-standalone": "python-build-standalone",
  ai: "AI 提供",
  fallback: "暂无版本数据",
  seed: "预置数据",
};

interface VersionPickerProps {
  versions: VersionItem[];
  value: string | null;
  onChange: (v: string) => void;
  source?: string;
  cached?: boolean;
  loading?: boolean;
  onRefresh?: () => void;
}

export function VersionPicker({
  versions,
  value,
  onChange,
  source,
  cached,
  loading,
  onRefresh,
}: VersionPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim();
    if (!q) return versions;
    return versions.filter((v) => v.version.includes(q));
  }, [versions, query]);

  const current = versions.find((v) => v.version === value) ?? versions[0];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <label className="eyebrow">选择版本</label>
        <div className="flex items-center gap-1.5">
          {source && (
            <Badge variant={source === "ai" ? "info" : source === "fallback" ? "warning" : "default"}>
              {source === "cache" ? <Sparkles className="size-3" /> : null}
              {SOURCE_LABEL[source] ?? source}
              {cached ? " · 已缓存" : ""}
            </Badge>
          )}
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 font-mono text-[11px] text-slate-400 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-50"
              title="重新拉取版本列表"
            >
              <RefreshCw className={cn("size-3", loading && "animate-spin")} />
              刷新
            </button>
          )}
        </div>
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={loading || versions.length === 0}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            "flex h-12 w-full items-center justify-between rounded-xl border border-white/10 bg-ink-950/60 px-4 text-left transition-colors",
            "hover:border-white/20 disabled:opacity-50",
            open && "border-tape/60",
          )}
        >
          <span className="flex items-center gap-2.5">
            {loading && !current ? (
              <span className="font-body text-sm text-slate-500">正在找版本…</span>
            ) : (
              <>
                <span className="font-mono text-[15px] font-semibold text-white">
                  {current?.version ?? "—"}
                </span>
                {current?.is_latest
                  ? <Badge variant="latest">最新稳定版</Badge>
                  : <Badge variant="default">指定版本</Badge>}
              </>
            )}
          </span>
          <ChevronDown className={cn("size-4 text-slate-400 transition-transform", open && "rotate-180")} />
        </button>

        {open && (
          <div className="absolute z-30 mt-2 w-full overflow-hidden rounded-xl border border-white/15 bg-ink-900 shadow-2xl">
            {versions.length > 8 && (
              <div className="relative border-b border-white/10 p-2">
                <Search className="pointer-events-none absolute left-4 top-1/2 size-3.5 -translate-y-1/2 text-slate-500" />
                <Input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索版本，如 3.12"
                  className="h-8 pl-8 text-[13px]"
                />
              </div>
            )}
            <ul role="listbox" className="max-h-64 overflow-auto p-1.5">
              {filtered.length === 0 && (
                <li className="px-3 py-6 text-center font-body text-sm text-slate-500">
                  没找到这个版本，换个数字试试
                </li>
              )}
              {filtered.map((v) => (
                <li key={v.version}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={v.version === value}
                    onClick={() => {
                      onChange(v.version);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left font-mono text-[13.5px] transition-colors",
                      v.version === value
                        ? "bg-tape/15 text-white"
                        : "text-slate-300 hover:bg-white/[0.06]",
                    )}
                  >
                    <span>{v.version}</span>
                    {v.is_latest && <Badge variant="latest">最新</Badge>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {versions.length > 0 && versions.length <= 12 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {versions.slice(0, 8).map((v) => (
            <button
              key={v.version}
              type="button"
              onClick={() => onChange(v.version)}
              className={cn(
                "rounded-md border px-2 py-1 font-mono text-[11.5px] transition-colors",
                v.version === value
                  ? "border-tape/50 bg-tape/10 text-tape-soft"
                  : "border-white/10 text-slate-400 hover:border-white/25 hover:text-white",
              )}
            >
              {v.version}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export { SOURCE_LABEL };
