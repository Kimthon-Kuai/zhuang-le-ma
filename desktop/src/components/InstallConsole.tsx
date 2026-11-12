import { useEffect, useRef } from "react";
import { CircleStop, ShieldAlert, TerminalSquare, RefreshCw, GripHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface LogLine {
  stream: "stdout" | "stderr" | "meta";
  text: string;
}

export type RunState = "idle" | "running" | "success" | "error" | "stopped";

interface InstallConsoleProps {
  logs: LogLine[];
  state: RunState;
  onStop: () => void;
  onRetryElevated: () => void;
  onClear: () => void;
  canElevate: boolean;
  platformLabel: string;
}

const STATE_META: Record<RunState, { label: string; className: string; dot: string }> = {
  idle: { label: "待命", className: "text-slate-400", dot: "bg-slate-500" },
  running: { label: "正在安装", className: "text-phosphor", dot: "bg-phosphor animate-blink" },
  success: { label: "安装成功", className: "text-phosphor", dot: "bg-phosphor" },
  error: { label: "执行失败", className: "text-tape-soft", dot: "bg-tape" },
  stopped: { label: "已停止", className: "text-label", dot: "bg-label" },
};

export function InstallConsole({
  logs,
  state,
  onStop,
  onRetryElevated,
  onClear,
  canElevate,
  platformLabel,
}: InstallConsoleProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [logs]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  const meta = STATE_META[state];
  const shieldHint = /管理员|拒绝访问|Access is denied|权限|permission denied|EACCES|EPERM|must be run as administrator/i.test(
    logs.slice(-40).map((l) => l.text).join("\n"),
  );

  return (
    <section className="tape-panel flex h-full min-h-0 flex-col overflow-hidden" aria-label="安装日志">
      <header className="flex items-center gap-3 border-b border-white/10 bg-ink-950/50 px-4 py-2.5">
        <GripHorizontal className="size-4 text-slate-600" />
        <TerminalSquare className="size-4 text-slate-400" />
        <div className="flex items-center gap-2">
          <span className={cn("size-2 rounded-full", meta.dot)} />
          <span className={cn("font-display text-[13px] font-semibold", meta.className)}>
            {meta.label}
          </span>
        </div>
        <Badge className="ml-1">{platformLabel}</Badge>
        <div className="ml-auto flex items-center gap-1.5">
          {state === "running" && (
            <Button size="sm" variant="danger" onClick={onStop}>
              <CircleStop /> 停止
            </Button>
          )}
          {(shieldHint || state === "error") && canElevate && state !== "stopped" && (
            <Button size="sm" variant="label" onClick={onRetryElevated}>
              <ShieldAlert /> 以管理员身份重试
            </Button>
          )}
          {logs.length > 0 && state !== "running" && (
            <Button size="sm" variant="ghost" onClick={onClear}>
              <RefreshCw /> 清空
            </Button>
          )}
        </div>
      </header>

      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="min-h-0 flex-1 overflow-auto bg-[#070912] p-4 font-mono text-[12.5px] leading-[1.7]"
      >
        {logs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-600">
            <div className="text-3xl">⌨️</div>
            <p className="font-body text-sm text-slate-500">
              点「一键安装」，脚本就在这里跑给你看
            </p>
            <p className="font-mono text-[11px] text-slate-600">
              $ 日志会实时滚动 · 不需要你开终端
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {logs.map((line, i) => (
              <div
                key={i}
                className={cn(
                  "term-line",
                  line.stream === "stderr" && "text-tape-soft",
                  line.stream === "meta" && "mt-2 rounded bg-white/[0.04] px-2 py-1 text-label",
                  line.stream === "stdout" && "text-slate-300",
                )}
              >
                {line.stream === "meta" ? (
                  line.text
                ) : (
                  <>
                    <span className="mr-2 select-none text-slate-700">
                      {line.stream === "stderr" ? "!" : "›"}
                    </span>
                    {line.text}
                  </>
                )}
              </div>
            ))}
            {state === "running" && (
              <div className="term-line text-phosphor">
                <span className="animate-blink">▌</span>
              </div>
            )}
          </div>
        )}
      </div>

      {(state === "success" || state === "error" || state === "stopped") && (
        <footer
          className={cn(
            "border-t px-4 py-2.5 font-body text-[13px]",
            state === "success" && "border-phosphor/20 bg-phosphor/[0.06] text-phosphor",
            state === "error" && "border-tape/20 bg-tape/[0.06] text-tape-soft",
            state === "stopped" && "border-white/10 bg-white/[0.03] text-slate-400",
          )}
        >
          {state === "success"
            ? "搞定！记得新开一个终端，让环境变量生效，再跑一遍方案里的验证命令。"
            : state === "stopped"
              ? "已停止执行。装了一半也没关系，环境变量没生效的话重跑一次即可。"
              : "别慌：先看日志最后几行。常见原因是网络超时或缺少管理员权限，点右上角「以管理员身份重试」多半能过。"}
        </footer>
      )}
    </section>
  );
}
