import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  Search,
  RefreshCw,
  Trash2,
  WandSparkles,
  Save,
  Eye,
  Pencil,
  Loader2,
  SlidersHorizontal,
  Plus,
} from "lucide-react";
import { cn, fmtTime, PLATFORM_LABEL, req, type Plan } from "./lib";

interface PlansViewProps {
  onToast: (msg: string, kind?: "ok" | "err") => void;
  reloadKey: number;
}

export function PlansView({ onToast, reloadKey }: PlansViewProps) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Plan | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [create, setCreate] = useState({ software: "", version: "", platform: "windows" });
  const detailRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await req<Plan[]>("/api/admin/plans?limit=300");
      setPlans(list);
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setLoading(false);
    }
  }, [onToast]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const filtered = useMemo(() => {
    const k = q.trim().toLowerCase();
    if (!k) return plans;
    return plans.filter(
      (p) =>
        p.software_name.toLowerCase().includes(k) ||
        p.version.toLowerCase().includes(k) ||
        p.platform.includes(k),
    );
  }, [plans, q]);

  const open = async (plan: Plan) => {
    setBusy(`open-${plan.id}`);
    try {
      const full = await req<Plan>(`/api/admin/plans/${plan.id}`);
      setSelected(full);
      setDraft(full.markdown);
      setEditing(false);
      detailRef.current?.scrollTo({ top: 0 });
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    if (!selected) return;
    setBusy("save");
    try {
      const updated = await req<Plan>(`/api/admin/plans/${selected.id}`, {
        method: "PUT",
        body: JSON.stringify({ markdown: draft }),
      });
      setSelected(updated);
      setEditing(false);
      onToast("已保存，客户端下次请求就会拿到新内容");
      void load();
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const regenerate = async (plan: Plan) => {
    setBusy(`regen-${plan.id}`);
    try {
      const updated = await req<Plan>(`/api/admin/plans/${plan.id}/regenerate`, { method: "POST" });
      setSelected(updated);
      setDraft(updated.markdown);
      setEditing(false);
      onToast("AI 已重新生成");
      void load();
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (plan: Plan) => {
    if (!window.confirm(`删除「${plan.software_name} ${plan.version} · ${plan.platform}」的方案？\n删除后用户再请求会重新生成。`))
      return;
    setBusy(`del-${plan.id}`);
    try {
      await req(`/api/admin/plans/${plan.id}`, { method: "DELETE" });
      if (selected?.id === plan.id) setSelected(null);
      onToast("已删除");
      void load();
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const createPlan = async () => {
    if (!create.software.trim() || !create.version.trim()) {
      onToast("软件名和版本都要填", "err");
      return;
    }
    setBusy("create");
    try {
      const p = await req<Plan>("/api/admin/plans/generate", {
        method: "POST",
        body: JSON.stringify(create),
      });
      setShowCreate(false);
      setCreate({ software: "", version: "", platform: "windows" });
      onToast("新方案已生成");
      await load();
      setSelected(p);
      setDraft(p.markdown);
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(380px,44%)_1fr] gap-4">
      {/* 列表 */}
      <section className="panel flex min-h-0 flex-col overflow-hidden">
        <header className="space-y-2 border-b border-white/10 p-3">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-600" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="搜软件 / 版本 / 平台"
                className="field !h-9 !pl-9 !text-[13px]"
              />
            </div>
            <button className="btn-ghost" onClick={() => void load()} title="刷新">
              <RefreshCw className={cn(loading && "animate-spin")} />
            </button>
            <button className="btn-primary" onClick={() => setShowCreate((s) => !s)} title="新建方案">
              <Plus />
            </button>
          </div>

          {showCreate && (
            <div className="space-y-2 rounded-lg border border-white/10 bg-ink-950/60 p-2.5">
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={create.software}
                  onChange={(e) => setCreate({ ...create, software: e.target.value })}
                  placeholder="软件名，如 Redis"
                  className="field !h-8 !text-[12.5px]"
                />
                <input
                  value={create.version}
                  onChange={(e) => setCreate({ ...create, version: e.target.value })}
                  placeholder="版本，如 7.4.1"
                  className="field !h-8 !text-[12.5px]"
                />
              </div>
              <div className="flex gap-2">
                <select
                  value={create.platform}
                  onChange={(e) => setCreate({ ...create, platform: e.target.value })}
                  className="field !h-8 flex-1 !text-[12.5px]"
                >
                  <option value="windows">Windows</option>
                  <option value="macos">macOS</option>
                  <option value="linux">Linux</option>
                </select>
                <button className="btn-outline !h-8" onClick={() => void createPlan()} disabled={busy === "create"}>
                  {busy === "create" ? <Loader2 className="animate-spin" /> : <WandSparkles />} 生成
                </button>
              </div>
            </div>
          )}
        </header>

        <div className="min-h-0 flex-1 overflow-auto">
          {loading && plans.length === 0 ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-12 animate-pulse rounded-lg bg-ink-800/60" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center text-slate-600">
              <SlidersHorizontal className="size-6" />
              <p className="text-[13px]">还没有方案</p>
              <p className="font-mono text-[11px]">桌面端生成后会出现在这里</p>
            </div>
          ) : (
            <ul>
              {filtered.map((p) => (
                <li key={p.id}>
                  <div
                    className={cn(
                      "group flex cursor-pointer items-center gap-2.5 border-b border-white/[0.05] px-3 py-2.5 transition-colors",
                      selected?.id === p.id ? "bg-tape/[0.08]" : "hover:bg-white/[0.04]",
                    )}
                    onClick={() => void open(p)}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-display text-[13.5px] font-semibold text-slate-100">
                          {p.software_name}
                        </span>
                        <span className="font-mono text-[11.5px] text-label">{p.version}</span>
                        <span className="tag">{PLATFORM_LABEL[p.platform] ?? p.platform}</span>
                        {p.install_mode === "official-link" && (
                          <span className="tag border-electric/30 text-electric">官方</span>
                        )}
                      </div>
                      <div className="mt-0.5 flex gap-3 font-mono text-[10.5px] text-slate-500">
                        <span>👍 {p.valid_count}</span>
                        <span>👎 {p.invalid_count}</span>
                        <span># {p.id}</span>
                        <span>{fmtTime(p.updated_at)}</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        className="rounded p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
                        title="让 AI 重新生成"
                        onClick={(e) => {
                          e.stopPropagation();
                          void regenerate(p);
                        }}
                        disabled={busy === `regen-${p.id}`}
                      >
                        {busy === `regen-${p.id}` ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <WandSparkles className="size-3.5" />
                        )}
                      </button>
                      <button
                        className="rounded p-1.5 text-slate-400 hover:bg-tape/20 hover:text-tape-soft"
                        title="删除"
                        onClick={(e) => {
                          e.stopPropagation();
                          void remove(p);
                        }}
                        disabled={busy === `del-${p.id}`}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <footer className="border-t border-white/10 px-3 py-1.5 font-mono text-[10.5px] text-slate-600">
          共 {filtered.length} 条方案
        </footer>
      </section>

      {/* 详情 */}
      <section ref={detailRef} className="panel flex min-h-0 flex-col overflow-hidden">
        {!selected ? (
          <div className="grid h-full place-items-center text-slate-600">
            <div className="text-center">
              <Eye className="mx-auto size-7" />
              <p className="mt-2 text-[13px]">左边选一条方案查看</p>
            </div>
          </div>
        ) : (
          <>
            <header className="flex flex-wrap items-center gap-2 border-b border-white/10 px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-display text-[15px] font-bold text-white">
                    {selected.software_name}
                  </h2>
                  <span className="font-mono text-[12px] text-label">{selected.version}</span>
                  <span className="tag">{PLATFORM_LABEL[selected.platform]}</span>
                </div>
                <p className="mt-0.5 font-mono text-[10.5px] text-slate-500">
                  #{selected.id} · {selected.model ?? "fallback"} · 更新于 {fmtTime(selected.updated_at)}
                </p>
              </div>
              <div className="ml-auto flex items-center gap-1.5">
                {editing ? (
                  <>
                    <button className="btn-outline" onClick={() => setEditing(false)}>
                      取消
                    </button>
                    <button className="btn-primary" onClick={() => void save()} disabled={busy === "save"}>
                      {busy === "save" ? <Loader2 className="animate-spin" /> : <Save />} 保存
                    </button>
                  </>
                ) : (
                  <>
                    <button className="btn-outline" onClick={() => setEditing(true)}>
                      <Pencil /> 编辑
                    </button>
                    <button
                      className="btn-outline"
                      onClick={() => void regenerate(selected)}
                      disabled={busy === `regen-${selected.id}`}
                    >
                      {busy === `regen-${selected.id}` ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <WandSparkles />
                      )}
                      重新生成
                    </button>
                    <button className="btn-danger" onClick={() => void remove(selected)}>
                      <Trash2 />
                    </button>
                  </>
                )}
              </div>
            </header>

            <div className="min-h-0 flex-1 overflow-auto p-4">
              {editing ? (
                <div className="flex h-full flex-col gap-2">
                  <p className="font-mono text-[11px] text-slate-500">
                    Markdown 源码 · 保存后桌面端立即生效（主脚本会被重新提取）
                  </p>
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    spellCheck={false}
                    className="min-h-0 flex-1 resize-none rounded-lg border border-white/10 bg-ink-950 p-3 font-mono text-[12px] leading-relaxed text-slate-300 focus:border-tape/50 focus:outline-none"
                  />
                </div>
              ) : (
                <article className="md mx-auto max-w-3xl">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                    components={{
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noreferrer">
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {selected.markdown}
                  </ReactMarkdown>
                </article>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
