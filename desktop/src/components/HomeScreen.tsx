import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Loader2, Search, WandSparkles, Shuffle, PackageSearch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Software } from "@/lib/api";
import { Reel } from "@/components/Header";

const EXAMPLES = [
  "我想装 MySQL",
  "帮我搞个 Node.js",
  "Java 开发环境怎么装",
  "装个 Redis 玩玩",
  "Go 语言环境",
];

const CATEGORY_LABEL: Record<string, string> = {
  database: "数据库",
  runtime: "语言运行时",
  tool: "命令行工具",
  build: "构建工具",
  server: "服务器",
  editor: "编辑器",
  other: "其他",
};

// 版本来源 -> 展示文案（卡片副标题）
const SOURCE_LABEL: Record<string, string> = {
  npm: "npm 仓库",
  pypi: "PyPI",
  github: "GitHub Releases",
  maven: "Maven Central",
  nodejs: "官方发行版",
  nginx: "官方发行版",
  adoptium: "Adoptium",
  "python-build-standalone": "官方发行版",
  manual: "官方下载页",
  ai: "AI 版本列表",
};

interface HomeScreenProps {
  software: Software[];
  loadingCatalog: boolean;
  identifying: boolean;
  onSearch: (text: string) => void;
  onPickSoftware: (sw: Software) => void;
  error?: string | null;
}

export function HomeScreen({
  software,
  loadingCatalog,
  identifying,
  onSearch,
  onPickSoftware,
  error,
}: HomeScreenProps) {
  const [text, setText] = useState("");
  const [placeholder, setPlaceholder] = useState(EXAMPLES[0]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    let i = 0;
    const timer = setInterval(() => {
      i = (i + 1) % EXAMPLES.length;
      setPlaceholder(EXAMPLES[i]);
    }, 3200);
    return () => clearInterval(timer);
  }, []);

  const groups = useMemo(() => {
    const map = new Map<string, Software[]>();
    // 只展示预置目录里的软件。用户临时搜索产生的条目（category=other + manual）
    // 历史脏数据（音译成拼音的垃圾名）都不该出现在「常装清单」里。
    for (const sw of software) {
      if (sw.category === "other" && (sw.source ?? "manual") === "manual") continue;
      const k = sw.category || "other";
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(sw);
    }
    return [...map.entries()];
  }, [software]);

  const visibleCount = useMemo(
    () => groups.reduce((n, [, items]) => n + items.length, 0),
    [groups],
  );

  const submit = (value?: string) => {
    const v = (value ?? text).trim();
    if (!v || identifying) return;
    onSearch(v);
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-6 pb-16 pt-10">
      {/* HERO：整页就是一台待录制的磁带机 */}
      <section className="relative">
        <div className="mb-5 flex items-center gap-2">
          <span className="sticker">SIDE A · 安装模式</span>
          <span className="eyebrow">不必会命令行，也能装明白</span>
        </div>

        <h2 className="font-display text-[clamp(30px,4.6vw,46px)] font-bold leading-[1.08] tracking-tight text-white">
          说一句话，
          <br />
          剩下的<span className="relative mx-1 inline-block text-tape">
            交给它
            <svg
              className="absolute -bottom-1.5 left-0 w-full"
              height="8"
              viewBox="0 0 200 8"
              preserveAspectRatio="none"
              aria-hidden
            >
              <path d="M2 5.5 C 50 1.5, 150 7.5, 198 3.5" stroke="#ff4d5e" strokeWidth="2.5" fill="none" strokeLinecap="round" />
            </svg>
          </span>
          。
        </h2>
        <p className="mt-4 max-w-xl font-body text-[15px] leading-relaxed text-slate-400">
          AI 认软件、选版本、写安装脚本，一键跑完还能实时看日志。
          <span className="text-slate-300">Windows / macOS / Linux 都认得。</span>
        </p>

        <form
          className="mt-7"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div
            className={cn(
              "group flex items-center gap-2 rounded-2xl border border-white/12 bg-ink-900/90 p-2 pl-4 transition-all duration-200",
              "focus-within:border-tape/50 focus-within:shadow-[0_0_0_4px_rgba(255,77,94,.08)]",
            )}
          >
            <Search className="size-5 shrink-0 text-slate-500" />
            <input
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={placeholder}
              disabled={identifying}
              aria-label="输入想安装的软件"
              className="h-11 min-w-0 flex-1 bg-transparent font-body text-[16px] text-white placeholder:text-slate-500 focus:outline-none"
            />
            {identifying && (
              <span className="hidden items-center gap-1.5 font-mono text-[11.5px] text-label sm:flex">
                <Loader2 className="size-3.5 animate-spin" />
                正在听…
              </span>
            )}
            <Button type="submit" size="lg" variant="tape" disabled={identifying || !text.trim()}>
              {identifying ? <Loader2 className="animate-spin" /> : <WandSparkles />}
              开始装
            </Button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="font-body text-[12.5px] text-slate-500">试试：</span>
          {EXAMPLES.slice(0, 4).map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setText(ex);
                submit(ex);
              }}
              className="rounded-full border border-white/10 px-2.5 py-1 font-body text-[12px] text-slate-400 transition-colors hover:border-tape/40 hover:text-white"
            >
              {ex}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              const pick = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
              setText(pick);
              submit(pick);
            }}
            className="inline-flex items-center gap-1 rounded-full px-2 py-1 font-mono text-[11.5px] text-slate-500 transition-colors hover:text-label"
          >
            <Shuffle className="size-3" /> 随机一个
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-tape/30 bg-tape/[0.07] px-4 py-3 font-body text-[13.5px] text-tape-soft">
            {error}
          </div>
        )}
      </section>

      {/* 预置软件墙 */}
      <section className="mt-12">
        <div className="mb-4 flex items-end justify-between">
          <div className="flex items-center gap-2">
            <Reel size={18} />
            <h3 className="font-display text-[15px] font-semibold text-white">常装清单</h3>
            <Badge>{visibleCount} 个</Badge>
          </div>
          <span className="eyebrow hidden sm:block">点一下直接选版本</span>
        </div>

        {loadingCatalog ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-[62px] animate-pulse rounded-xl bg-ink-800/60" />
            ))}
          </div>
        ) : software.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-white/10 py-10 text-slate-500">
            <PackageSearch className="size-6" />
            <p className="font-body text-sm">服务端没连上，清单暂时拿不到</p>
            <p className="font-mono text-[11px] text-slate-600">上方输入框依然可以直接搜索</p>
          </div>
        ) : (
          <div className="space-y-5">
            {groups.map(([cat, items]) => (
              <div key={cat}>
                <p className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.2em] text-slate-500">
                  {CATEGORY_LABEL[cat] ?? cat}
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {items.map((sw) => (
                    <button
                      key={sw.name}
                      type="button"
                      onClick={() => onPickSoftware(sw)}
                      disabled={identifying}
                      className="group flex items-center gap-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 py-2.5 text-left transition-all hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.05] disabled:opacity-50"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-ink-950 font-display text-[13px] font-bold text-label">
                        {sw.display_name.replace(/[^A-Za-z]/g, "").slice(0, 2).toUpperCase() ||
                          sw.display_name.slice(0, 1)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-display text-[13.5px] font-semibold text-slate-100">
                          {sw.display_name}
                        </span>
                        <span className="block truncate font-mono text-[10.5px] text-slate-500">
                          {SOURCE_LABEL[sw.source ?? ""] ?? sw.source ?? "其他"}
                        </span>
                      </span>
                      <ArrowRight className="size-3.5 shrink-0 text-slate-600 transition-all group-hover:translate-x-0.5 group-hover:text-white" />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <footer className="mt-14 flex items-center justify-between border-t border-white/[0.06] pt-4 font-mono text-[11px] text-slate-600">
        <span>装了吗 v1.0 · 装完记得回来打个分</span>
        <span className="hidden sm:inline">SIDE B · 更多软件在路上</span>
      </footer>
    </div>
  );
}
