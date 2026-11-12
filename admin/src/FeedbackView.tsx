import { useCallback, useEffect, useState } from "react";
import { CheckCheck, Inbox, MessageSquareWarning, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import { cn, fmtTime, PLATFORM_LABEL, req, type Feedback } from "./lib";

type Filter = "pending" | "handled" | "all";

export function FeedbackView({
  onToast,
  reloadKey,
}: {
  onToast: (m: string, k?: "ok" | "err") => void;
  reloadKey: number;
}) {
  const [items, setItems] = useState<Feedback[]>([]);
  const [filter, setFilter] = useState<Filter>("pending");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filter === "all" ? "" : `?handled=${filter === "handled" ? "true" : "false"}`;
      setItems(await req<Feedback[]>(`/api/admin/feedbacks${qs}`));
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setLoading(false);
    }
  }, [filter, onToast]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const mark = async (f: Feedback, handled: boolean) => {
    setBusy(f.id);
    try {
      await req(`/api/admin/feedbacks/${f.id}?handled=${handled}`, { method: "PATCH" });
      onToast(handled ? "已标记处理" : "已恢复为待处理");
      void load();
    } catch (e) {
      onToast((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const tabs: { key: Filter; label: string }[] = [
    { key: "pending", label: "待处理" },
    { key: "handled", label: "已处理" },
    { key: "all", label: "全部" },
  ];

  return (
    <div className="panel flex h-full min-h-0 flex-col overflow-hidden">
      <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
        <div className="flex gap-1 rounded-lg border border-white/10 bg-ink-950/50 p-0.5">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={cn(
                "rounded-md px-3 py-1 font-display text-[12.5px] font-medium transition-colors",
                filter === t.key ? "bg-white/10 text-white" : "text-slate-400 hover:text-white",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="ml-auto font-mono text-[11px] text-slate-500">{items.length} 条</span>
      </header>

      <div className="min-h-0 flex-1 overflow-auto">
        {loading && items.length === 0 ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-ink-800/60" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="grid h-full place-items-center text-center text-slate-600">
            <div>
              <Inbox className="mx-auto size-7" />
              <p className="mt-2 text-[13px]">这个列表是空的</p>
              <p className="font-mono text-[11px]">用户提交的反馈会出现在这里</p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-white/[0.05]">
            {items.map((f) => (
              <li key={f.id} className={cn("px-4 py-3", f.handled && "opacity-60")}>
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "mt-0.5 grid size-7 shrink-0 place-items-center rounded-md",
                      f.rating === "valid"
                        ? "bg-phosphor/10 text-phosphor"
                        : "bg-tape/10 text-tape-soft",
                    )}
                  >
                    {f.rating === "valid" ? <ThumbsUp className="size-3.5" /> : <ThumbsDown className="size-3.5" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-display text-[13px] font-semibold text-slate-100">
                        {f.software_name ?? "未知软件"}
                      </span>
                      {f.version && <span className="font-mono text-[11px] text-label">{f.version}</span>}
                      {f.platform && <span className="tag">{PLATFORM_LABEL[f.platform] ?? f.platform}</span>}
                      <span className="font-mono text-[10.5px] text-slate-600">
                        #{f.id} · 方案 #{f.plan_id ?? "—"} · {fmtTime(f.created_at)}
                      </span>
                      {f.handled ? (
                        <span className="tag border-phosphor/30 text-phosphor">已处理</span>
                      ) : (
                        <span className="tag border-label/30 text-label">待处理</span>
                      )}
                    </div>
                    {f.content ? (
                      <p className="mt-1.5 whitespace-pre-wrap rounded-md bg-ink-950/60 px-2.5 py-1.5 text-[12.5px] leading-relaxed text-slate-300">
                        {f.content}
                      </p>
                    ) : (
                      <p className="mt-1.5 text-[12px] italic text-slate-600">（只点了{ f.rating === "valid" ? "有效" : "无效"}，没写文字）</p>
                    )}
                  </div>
                  <button
                    className={cn(f.handled ? "btn-outline" : "btn-primary", "shrink-0")}
                    onClick={() => void mark(f, !f.handled)}
                    disabled={busy === f.id}
                  >
                    {f.handled ? <RotateCcw /> : <CheckCheck />}
                    {f.handled ? "撤销" : "标记已处理"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className="flex items-center gap-1.5 border-t border-white/10 px-4 py-2 font-mono text-[10.5px] text-slate-600">
        <MessageSquareWarning className="size-3" />
        用户点「无效」时多半是脚本执行失败，建议对照日志修改后点「重新生成」
      </footer>
    </div>
  );
}
