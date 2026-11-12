import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  FileText,
  LogOut,
  MessageSquare,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Login } from "./Login";
import { PlansView } from "./PlansView";
import { FeedbackView } from "./FeedbackView";
import { StatsView } from "./StatsView";
import { cn, getToken, req, setToken } from "./lib";

type Tab = "plans" | "feedback" | "stats";

interface Toast {
  id: number;
  msg: string;
  kind: "ok" | "err";
}

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("plans");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [aiInfo, setAiInfo] = useState<{ ai_configured: boolean; model: string } | null>(null);
  const [pending, setPending] = useState(0);

  const toast = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const boot = useCallback(async () => {
    if (!getToken()) {
      setAuthed(false);
      return;
    }
    try {
      const me = await req<{ ai_configured: boolean; model: string }>("/api/admin/me");
      setAiInfo(me);
      setAuthed(true);
    } catch {
      setToken(null);
      setAuthed(false);
    }
  }, []);

  useEffect(() => {
    void boot();
  }, [boot]);

  // 轮询待处理反馈数，做侧栏小红点
  useEffect(() => {
    if (!authed) return;
    let alive = true;
    const tick = async () => {
      try {
        const list = await req<{ handled: number }[]>("/api/admin/feedbacks?handled=false");
        if (alive) setPending(list.length);
      } catch {
        /* 忽略轮询失败 */
      }
    };
    void tick();
    const t = setInterval(tick, 20000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [authed, reloadKey]);

  if (authed === null) {
    return <div className="grid min-h-full place-items-center font-mono text-[12px] text-slate-600">连接后台…</div>;
  }

  if (!authed) return <Login onSuccess={() => void boot()} />;

  const nav: { key: Tab; label: string; icon: React.ElementType; badge?: number }[] = [
    { key: "plans", label: "安装方案", icon: FileText },
    { key: "feedback", label: "用户反馈", icon: MessageSquare, badge: pending },
    { key: "stats", label: "数据统计", icon: BarChart3 },
  ];

  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-white/[0.07] bg-ink-950/60">
        <div className="flex items-center gap-2.5 px-4 py-4">
          <div className="grid size-9 place-items-center rounded-lg border border-white/15 bg-ink-800">
            <ShieldCheck className="size-4 text-label" />
          </div>
          <div className="leading-tight">
            <p className="font-display text-[15px] font-bold text-white">装了吗</p>
            <p className="font-mono text-[10px] tracking-wider text-slate-500">ADMIN</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-2">
          {nav.map((n) => (
            <button
              key={n.key}
              onClick={() => setTab(n.key)}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left font-display text-[13px] font-medium transition-colors",
                tab === n.key
                  ? "bg-tape/12 text-white shadow-[inset_2px_0_0_#ff4d5e]"
                  : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200",
              )}
            >
              <n.icon className="size-4" />
              {n.label}
              {!!n.badge && (
                <span className="ml-auto rounded-full bg-tape px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
                  {n.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="space-y-2 border-t border-white/[0.07] p-3">
          <div
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2 py-1.5 font-mono text-[10.5px]",
              aiInfo?.ai_configured ? "bg-phosphor/[0.07] text-phosphor" : "bg-label/[0.07] text-label",
            )}
          >
            {aiInfo?.ai_configured ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
            {aiInfo?.ai_configured ? `AI · ${aiInfo.model}` : "AI 未配置"}
          </div>
          <div className="flex gap-1">
            <button className="btn-ghost flex-1" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw /> 刷新
            </button>
            <button
              className="btn-ghost"
              title="退出登录"
              onClick={() => {
                setToken(null);
                setAuthed(false);
              }}
            >
              <LogOut />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-white/[0.07] px-5 py-3">
          <h1 className="font-display text-[16px] font-semibold text-white">
            {tab === "plans" ? "安装方案管理" : tab === "feedback" ? "用户反馈" : "数据统计"}
          </h1>
          <span className="font-body text-[12px] text-slate-500">
            {tab === "plans"
              ? "查看 / 编辑 / 删除 / 让 AI 重新生成"
              : tab === "feedback"
                ? "查看并标记用户反馈"
                : "软件、版本、平台的选择热度"}
          </span>
        </header>

        <div className="min-h-0 flex-1 p-4">
          {tab === "plans" && <PlansView onToast={toast} reloadKey={reloadKey} />}
          {tab === "feedback" && <FeedbackView onToast={toast} reloadKey={reloadKey} />}
          {tab === "stats" && <StatsView onToast={(m) => toast(m, "err")} reloadKey={reloadKey} />}
        </div>
      </main>

      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-2 rounded-lg border px-3 py-2 font-body text-[13px] shadow-lg",
              t.kind === "ok"
                ? "border-phosphor/30 bg-ink-800 text-phosphor"
                : "border-tape/40 bg-ink-800 text-tape-soft",
            )}
          >
            {t.kind === "ok" ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />}
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
