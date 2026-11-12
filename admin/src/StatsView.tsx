import { useCallback, useEffect, useState } from "react";
import { BarChart3, Download, FileText, Package, MessageSquare } from "lucide-react";
import { cn, PLATFORM_LABEL, req, type StatRow, type Stats } from "./lib";

const PLATFORM_COLOR: Record<string, string> = {
  windows: "bg-electric",
  macos: "bg-label",
  linux: "bg-phosphor",
};

function Bar({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div className={cn("h-full rounded-full", className ?? "bg-tape")} style={{ width: `${pct}%` }} />
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-slate-500">{label}</span>
        <Icon className={cn("size-4", accent)} />
      </div>
      <p className="mt-2 font-display text-[28px] font-bold leading-none text-white">{value}</p>
      <p className="mt-1.5 text-[11.5px] text-slate-500">{hint}</p>
    </div>
  );
}

function RankList({
  title,
  rows,
  color,
  formatKey,
}: {
  title: string;
  rows: StatRow[];
  color?: string;
  formatKey?: (key: string) => string;
}) {
  const max = rows[0]?.count ?? 0;
  return (
    <section className="panel p-4">
      <h3 className="mb-3 font-display text-[13px] font-semibold text-white">{title}</h3>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-[12px] text-slate-600">还没有数据</p>
      ) : (
        <ul className="space-y-2.5">
          {rows.slice(0, 10).map((r) => (
            <li key={`${r.kind}-${r.key}`}>
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <span className="truncate text-[12.5px] text-slate-300">
                  {formatKey ? formatKey(r.key) : r.key}
                </span>
                <span className="shrink-0 font-mono text-[11.5px] text-slate-400">{r.count}</span>
              </div>
              <Bar
                value={r.count}
                max={max}
                className={color ?? (r.platform ? PLATFORM_COLOR[r.platform] : undefined)}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function StatsView({ onToast, reloadKey }: { onToast: (m: string) => void; reloadKey: number }) {
  const [data, setData] = useState<Stats | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await req<Stats>("/api/admin/stats"));
    } catch (e) {
      onToast((e as Error).message);
    }
  }, [onToast]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  if (!data) {
    return (
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 animate-pulse rounded-xl bg-ink-800/60" />
        ))}
      </div>
    );
  }

  const platformTotal = data.platform.reduce((s, r) => s + r.count, 0);

  return (
    <div className="space-y-4 overflow-auto pb-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="安装方案" value={data.totals.plans} hint="覆盖软件×版本×平台" icon={FileText} accent="text-label" />
        <StatCard label="软件条目" value={data.totals.software} hint="含预置与 AI 新增" icon={Package} accent="text-electric" />
        <StatCard
          label="待处理反馈"
          value={data.totals.pending_feedbacks}
          hint={`累计 ${data.totals.feedbacks} 条反馈`}
          icon={MessageSquare}
          accent="text-tape-soft"
        />
        <StatCard
          label="安装执行"
          value={data.install_run.reduce((s, r) => s + r.count, 0)}
          hint="桌面端一键安装次数"
          icon={Download}
          accent="text-phosphor"
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <RankList title="软件选择次数" rows={data.software} />
        <RankList
          title="版本选择次数"
          rows={data.version}
          color="bg-label"
          formatKey={(k) => k.replace("@", " @ ")}
        />
        <section className="panel p-4">
          <h3 className="mb-3 font-display text-[13px] font-semibold text-white">平台分布</h3>
          {platformTotal === 0 ? (
            <p className="py-6 text-center text-[12px] text-slate-600">还没有数据</p>
          ) : (
            <>
              <div className="flex h-3 overflow-hidden rounded-full">
                {data.platform.map((p) => (
                  <div
                    key={p.key}
                    className={cn(PLATFORM_COLOR[p.key] ?? "bg-slate-500")}
                    style={{ width: `${(p.count / platformTotal) * 100}%` }}
                    title={`${PLATFORM_LABEL[p.key] ?? p.key}: ${p.count}`}
                  />
                ))}
              </div>
              <ul className="mt-3 space-y-1.5">
                {data.platform.map((p) => (
                  <li key={p.key} className="flex items-center gap-2 text-[12.5px]">
                    <span className={cn("size-2 rounded-sm", PLATFORM_COLOR[p.key] ?? "bg-slate-500")} />
                    <span className="text-slate-300">{PLATFORM_LABEL[p.key] ?? p.key}</span>
                    <span className="ml-auto font-mono text-slate-400">
                      {p.count}
                      <span className="ml-1.5 text-slate-600">
                        {Math.round((p.count / platformTotal) * 100)}%
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      <section className="panel overflow-hidden">
        <h3 className="flex items-center gap-2 border-b border-white/10 px-4 py-3 font-display text-[13px] font-semibold text-white">
          <BarChart3 className="size-4 text-tape" /> 方案口碑排行
        </h3>
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">软件</th>
              <th className="th">版本</th>
              <th className="th">平台</th>
              <th className="th">有效</th>
              <th className="th">无效</th>
              <th className="th">有效率</th>
            </tr>
          </thead>
          <tbody>
            {data.plans.length === 0 ? (
              <tr>
                <td className="td text-center text-slate-600" colSpan={6}>
                  暂无方案
                </td>
              </tr>
            ) : (
              data.plans.map((p, i) => {
                const total = p.valid_count + p.invalid_count;
                const rate = total ? Math.round((p.valid_count / total) * 100) : null;
                return (
                  <tr key={i} className="hover:bg-white/[0.03]">
                    <td className="td font-medium text-slate-100">{p.software_name}</td>
                    <td className="td font-mono text-[12px] text-label">{p.version}</td>
                    <td className="td text-slate-400">{PLATFORM_LABEL[p.platform] ?? p.platform}</td>
                    <td className="td font-mono text-phosphor">{p.valid_count}</td>
                    <td className="td font-mono text-tape-soft">{p.invalid_count}</td>
                    <td className="td">
                      {rate === null ? (
                        <span className="text-slate-600">—</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="w-16">
                            <Bar value={rate} max={100} className="bg-phosphor" />
                          </div>
                          <span className="font-mono text-[11.5px] text-slate-400">{rate}%</span>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
