import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ChevronRight,
  Copy,
  Download,
  Loader2,
  Monitor,
  Play,
  RefreshCw,
  Rocket,
  Check,
  ExternalLink,
} from "lucide-react";
import { Header } from "@/components/Header";
import { HomeScreen } from "@/components/HomeScreen";
import { VersionPicker } from "@/components/VersionPicker";
import { MarkdownView } from "@/components/MarkdownView";
import { FeedbackBar } from "@/components/FeedbackBar";
import { InstallConsole, type LogLine, type RunState } from "@/components/InstallConsole";
import { SettingsDialog } from "@/components/SettingsDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  api,
  type Platform,
  type Plan,
  type Software,
  type VersionItem,
} from "@/lib/api";
import { cn, normalizePlatform, PLATFORM_LABEL } from "@/lib/utils";

const PLATFORM_ICON: Record<Platform, string> = { windows: "🪟", macos: "", linux: "🐧" };

type Stage = "home" | "config" | "plan";

export default function App() {
  const [stage, setStage] = useState<Stage>("home");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [online, setOnline] = useState<boolean | null>(null);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [model, setModel] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<Software[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);

  const [platform, setPlatform] = useState<Platform>("windows");
  const [software, setSoftware] = useState<Software | null>(null);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [versionSource, setVersionSource] = useState<string>("");
  const [versionCached, setVersionCached] = useState(false);
  const [version, setVersion] = useState<string | null>(null);

  const [identifying, setIdentifying] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [logs, setLogs] = useState<LogLine[]>([]);
  const [runState, setRunState] = useState<RunState>("idle");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  const [tab, setTab] = useState("plan");

  const runIdRef = useRef<string | null>(null);
  const planRef = useRef<Plan | null>(null);
  planRef.current = plan;

  // ---------------------------------------------------------------- 初始化
  useEffect(() => {
    void window.zlm?.info().then((i) => setPlatform(normalizePlatform(i.platform)));
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setOnline(true);
      setAiConfigured(h.ai_configured);
      setModel(h.model);
    } catch {
      setOnline(false);
    }
  }, []);

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    try {
      setCatalog(await api.software());
    } catch {
      setCatalog([]);
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    void loadCatalog();
  }, [refreshHealth, loadCatalog]);

  // ---------------------------------------------------------------- 安装进程事件
  useEffect(() => {
    if (!window.zlm) return;
    const offLog = window.zlm.install.onLog((d) => {
      if (d.id !== runIdRef.current) return;
      setLogs((prev) => [...prev.slice(-1200), { stream: d.stream, text: d.text }]);
    });
    const offDone = window.zlm.install.onDone((d) => {
      if (d.id !== runIdRef.current) return;
      // 用户主动取消 ≠ 安装失败，避免误报红并统计一次「安装执行」
      setRunState(d.cancelled ? "stopped" : d.ok ? "success" : "error");
      setRunningId(null);
      if (d.cancelled) return;
      // 记录一次安装执行，供后台统计
      const p = planRef.current;
      if (p) {
        void api.stat({
          kind: "install_run",
          key: `${p.software_name}@${p.version}@${p.platform}`,
          software_name: p.software_name,
          platform: p.platform,
        });
      }
    });
    return () => {
      offLog();
      offDone();
    };
  }, []);

  // ---------------------------------------------------------------- 流程动作
  const resetToHome = () => {
    setStage("home");
    setSoftware(null);
    setVersions([]);
    setVersion(null);
    setVersionSource("");
    setPlan(null);
    setError(null);
    setLogs([]);
    setRunState("idle");
    setConsoleOpen(false);
    setTab("plan");
  };

  const loadVersions = async (sw: Software, force = false) => {
    if (!sw.id) return;
    setVersionsLoading(true);
    setError(null);
    try {
      const res = await api.versions(sw.id, platform, force);
      setVersions(res.versions);
      setVersionSource(res.source);
      setVersionCached(res.cached);
      const latest = res.versions.find((v) => v.is_latest) ?? res.versions[0];
      setVersion(latest?.version ?? null);
    } catch (e) {
      setError((e as Error).message);
      setVersions([]);
    } finally {
      setVersionsLoading(false);
    }
  };

  const openSoftware = async (sw: Software) => {
    setSoftware(sw);
    setStage("config");
    setPlan(null);
    setError(null);
    setVersions([]);
    setVersion(null);
    void api.stat({ kind: "software", key: sw.display_name, software_name: sw.display_name });
    await loadVersions(sw);
  };

  const search = async (text: string) => {
    setIdentifying(true);
    setError(null);
    try {
      const res = await api.identify(text);
      await openSoftware(res.software);
      if (!res.matched) {
        setError(`没在清单里找到，已按「${res.software.display_name}」继续处理。`);
        // 识别过程可能新建了软件条目，刷新一下首页清单
        void loadCatalog();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIdentifying(false);
    }
  };

  const generatePlan = async (force = false) => {
    if (!software || !version) {
      setError("先选一个版本吧");
      return;
    }
    setPlanLoading(true);
    setError(null);
    setTab("plan");
    try {
      const p = await api.createPlan({
        software: software.name,
        version,
        platform,
        display_name: software.display_name,
        homepage: software.homepage,
        force,
      });
      setPlan(p);
      setStage("plan");
      setLogs([]);
      setRunState("idle");
      void api.stat({
        kind: "version",
        key: `${p.software_name}@${version}`,
        software_name: p.software_name,
        platform,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPlanLoading(false);
    }
  };

  const startInstall = async (script: string, elevated = false) => {
    if (!software || !window.zlm) {
      setError("当前不在 Electron 环境里，无法直接执行。请用「复制脚本」到终端手动运行。");
      return;
    }
    const id = `run-${Date.now()}-${Math.floor(Math.random() * 1e4)}`;
    runIdRef.current = id;
    setRunningId(id);
    setRunState("running");
    setLogs([]);
    setConsoleOpen(true);
    setTab("console");
    try {
      const payload = {
        id,
        script,
        platform,
        scriptType: scriptTypeOf(script, planRef.current?.script_type),
      };
      if (elevated) await window.zlm.install.startElevated(payload);
      else await window.zlm.install.start(payload);
      void api.stat({
        kind: "install_run",
        key: `${software.display_name}@${version}@${platform}`,
        software_name: software.display_name,
        platform,
      });
    } catch (e) {
      setRunState("error");
      setRunningId(null);
      setLogs((prev) => [...prev, { stream: "stderr", text: (e as Error).message }]);
    }
  };

  const stopInstall = async () => {
    if (runningId && window.zlm) {
      await window.zlm.install.stop(runningId);
      setRunState("stopped");
      setRunningId(null);
    }
  };

  const copyAll = async () => {
    if (!plan) return;
    const text = plan.markdown;
    if (window.zlm) await window.zlm.copy(text);
    else await navigator.clipboard.writeText(text);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 1800);
  };

  const submitFeedback = async (rating: "valid" | "invalid", content?: string) => {
    if (!plan) return;
    await api.feedback({
      plan_id: plan.id,
      rating,
      content,
      software_name: plan.software_name,
      version: plan.version,
      platform: plan.platform,
    });
    setPlan((p) =>
      p
        ? {
            ...p,
            valid_count: p.valid_count + (rating === "valid" ? 1 : 0),
            invalid_count: p.invalid_count + (rating === "invalid" ? 1 : 0),
          }
        : p,
    );
  };

  const platformLabel = PLATFORM_LABEL[platform];

  // ---------------------------------------------------------------- 渲染
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header
        online={online}
        aiConfigured={aiConfigured}
        model={model}
        onOpenSettings={() => setSettingsOpen(true)}
        onNewSession={resetToHome}
      />

      <main className="min-h-0 flex-1 overflow-hidden">
        {stage === "home" && (
          <div className="h-full overflow-y-auto">
            <HomeScreen
              software={catalog}
              loadingCatalog={catalogLoading}
              identifying={identifying}
              onSearch={(t) => void search(t)}
              onPickSoftware={(sw) => void openSoftware(sw)}
              error={error}
            />
          </div>
        )}

        {stage === "config" && software && (
          <div className="h-full overflow-y-auto">
            <div className="mx-auto w-full max-w-3xl animate-slide-up px-6 pb-16 pt-7">
              <button
                type="button"
                onClick={resetToHome}
                className="mb-6 inline-flex items-center gap-1.5 font-body text-[13px] text-slate-400 transition-colors hover:text-white"
              >
                <ArrowLeft className="size-3.5" /> 换个软件
              </button>

              <div className="flex items-start gap-4">
                <div className="grid size-14 shrink-0 place-items-center rounded-2xl border border-white/12 bg-ink-800 font-display text-[19px] font-bold text-label">
                  {software.display_name.replace(/[^A-Za-z]/g, "").slice(0, 2).toUpperCase() || "?"}
                </div>
                <div className="min-w-0">
                  <h2 className="font-display text-[27px] font-bold leading-tight text-white">
                    {software.display_name}
                  </h2>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {software.category && <Badge>{software.category}</Badge>}
                    {software.source && <Badge variant="info">{software.source}</Badge>}
                    {software.repo && (
                      <span className="font-mono text-[11px] text-slate-500">{software.repo}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="tape-panel mt-7 space-y-6 p-5">
                <div>
                  <label className="eyebrow">装在哪台机器</label>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {(["windows", "macos", "linux"] as Platform[]).map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => {
                          setPlatform(p);
                          if (software) void loadVersions(software);
                        }}
                        className={cn(
                          "flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 font-display text-[13.5px] font-medium transition-all",
                          platform === p
                            ? "border-tape/60 bg-tape/10 text-white"
                            : "border-white/10 text-slate-400 hover:border-white/25 hover:text-white",
                        )}
                      >
                        <span aria-hidden>{PLATFORM_ICON[p]}</span>
                        {PLATFORM_LABEL[p]}
                        {normalizePlatform(currentHostPlatform()) === p && (
                          <span className="font-mono text-[9.5px] text-slate-500">本机</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                <VersionPicker
                  versions={versions}
                  value={version}
                  onChange={setVersion}
                  source={versionSource}
                  cached={versionCached}
                  loading={versionsLoading}
                  onRefresh={() => software && void loadVersions(software, true)}
                />

                {error && (
                  <div className="rounded-lg border border-label/25 bg-label/[0.06] px-3 py-2 font-body text-[12.5px] text-label">
                    {error}
                  </div>
                )}

                <div className="flex items-center justify-between gap-3 border-t border-white/10 pt-5">
                  <p className="font-body text-[12.5px] leading-relaxed text-slate-500">
                    {planLoading ? (
                      <span className="inline-flex items-center gap-1.5 text-label">
                        <Loader2 className="size-3.5 animate-spin" />
                        AI 正在写安装脚本，大约 20–60 秒…
                      </span>
                    ) : (
                      <>会生成脚本、说明、验证命令和常见问题</>
                    )}
                  </p>
                  <Button
                    size="lg"
                    variant="tape"
                    disabled={!version || planLoading}
                    onClick={() => void generatePlan()}
                  >
                    {planLoading ? <Loader2 className="animate-spin" /> : <Rocket />}
                    {planLoading ? "生成中" : "生成安装方案"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {stage === "plan" && (
          <div className="flex h-full min-h-0">
            {/* 左：方案 */}
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="flex items-center gap-3 border-b border-white/[0.07] px-6 py-3">
                <button
                  type="button"
                  onClick={() => setStage("config")}
                  className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 font-body text-[13px] text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                >
                  <ArrowLeft className="size-3.5" /> 返回
                </button>
                <ChevronRight className="size-3.5 text-slate-700" />
                <span className="font-display text-[14px] font-semibold text-white">
                  {software?.display_name ?? plan?.software_name}
                </span>
                <Badge variant="default">
                  <Monitor className="size-3" /> {version}
                </Badge>
                <Badge variant="info">{platformLabel}</Badge>
                {plan?.cached && <Badge variant="latest">命中缓存</Badge>}
                {plan?.install_mode === "official-link" && <Badge variant="warning">官方下载</Badge>}
                <div className="ml-auto flex items-center gap-1.5">
                  {plan?.model && (
                    <span className="hidden font-mono text-[10.5px] text-slate-600 lg:inline">
                      {plan.model}
                    </span>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => void copyAll()}>
                    {copiedAll ? <Check /> : <Copy />} {copiedAll ? "已复制全文" : "复制全文"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={planLoading}
                    onClick={() => void generatePlan(true)}
                  >
                    <RefreshCw className={cn(planLoading && "animate-spin")} /> 重新生成
                  </Button>
                </div>
              </div>

              <div className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
                {planLoading && !plan ? (
                  <div className="mx-auto max-w-2xl space-y-3">
                    <div className="flex items-center gap-2 font-body text-[13px] text-label">
                      <Loader2 className="size-4 animate-spin" /> 正在生成…
                    </div>
                    <Skeleton className="h-6 w-2/3" />
                    <Skeleton className="h-40 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                ) : plan ? (
                  <div className="mx-auto max-w-3xl animate-slide-up">
                    <Tabs value={tab} onValueChange={setTab}>
                      <TabsList>
                        <TabsTrigger value="plan">安装方案</TabsTrigger>
                        <TabsTrigger value="raw">Markdown 源码</TabsTrigger>
                        <TabsTrigger value="console">
                          执行日志{logs.length > 0 && <span className="ml-1 text-phosphor">●</span>}
                        </TabsTrigger>
                      </TabsList>

                      <TabsContent value="plan">
                        {plan.markdown.includes("这是本地兜底稿") ? (
                          <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-label/30 bg-label/[0.07] px-3.5 py-3">
                            <RefreshCw className="mt-0.5 size-4 shrink-0 text-label" />
                            <div className="min-w-0 flex-1 font-body text-[12.5px] leading-relaxed text-slate-300">
                              AI 还没接上，这是通用兜底指引。
                              <span className="text-label">服务端配置好 AI Key 后点「重新生成」</span>
                              ，就能拿到针对你系统的完整脚本。
                            </div>
                          </div>
                        ) : plan.install_mode === "official-link" ? (
                          <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-electric/25 bg-electric/[0.06] px-3.5 py-3">
                            <ExternalLink className="mt-0.5 size-4 shrink-0 text-electric" />
                            <p className="font-body text-[12.5px] leading-relaxed text-slate-300">
                              这个软件官方给了图形安装包，脚本装容易装歪，所以直接给你官方入口，按步骤走最稳。
                            </p>
                          </div>
                        ) : null}
                        <MarkdownView
                          markdown={plan.markdown}
                          onRunScript={(s) => void startInstall(s)}
                          runningScript={runState === "running"}
                        />
                        <div className="mt-6">
                          <FeedbackBar
                            validCount={plan.valid_count}
                            invalidCount={plan.invalid_count}
                            onSubmit={submitFeedback}
                          />
                        </div>
                        {(plan.script || plan.install_mode === "script") && (
                          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-tape/25 bg-tape/[0.05] p-3">
                            <div className="min-w-0 flex-1">
                              <p className="font-display text-[13.5px] font-semibold text-white">
                                不想复制？让它直接装
                              </p>
                              <p className="font-body text-[12px] text-slate-400">
                                在 App 里跑脚本，日志实时显示，不用开终端
                              </p>
                            </div>
                            {plan.script ? (
                              <Button
                                variant="phosphor"
                                disabled={runState === "running"}
                                onClick={() => void startInstall(plan.script!)}
                              >
                                <Play /> 一键安装
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                onClick={() => {
                                  const url = /\((https?:\/\/[^)]+)\)/.exec(plan.markdown)?.[1];
                                  if (url && window.zlm) void window.zlm.openExternal(url);
                                }}
                              >
                                <Download /> 打开下载页
                              </Button>
                            )}
                          </div>
                        )}
                      </TabsContent>

                      <TabsContent value="raw">
                        <div className="rounded-xl border border-white/10 bg-ink-950/80 p-4">
                          <pre className="max-h-[62vh] overflow-auto font-mono text-[12px] leading-relaxed text-slate-400">
                            {plan.markdown}
                          </pre>
                        </div>
                      </TabsContent>

                      <TabsContent value="console">
                        <div className="h-[62vh]">
                          <InstallConsole
                            logs={logs}
                            state={runState}
                            platformLabel={platformLabel}
                            canElevate={platform === "windows" || platform === "macos"}
                            onStop={() => void stopInstall()}
                            onClear={() => {
                              setLogs([]);
                              setRunState("idle");
                            }}
                            onRetryElevated={() => plan.script && void startInstall(plan.script, true)}
                          />
                        </div>
                      </TabsContent>
                    </Tabs>
                  </div>
                ) : (
                  <div className="grid h-full place-items-center">
                    <p className="font-body text-sm text-slate-500">方案没生成出来，返回重试一次</p>
                  </div>
                )}
              </div>
            </div>

            {/* 右：固定日志面板（宽屏才显示） */}
            {consoleOpen && (
              <aside className="hidden w-[40%] min-w-[380px] flex-col border-l border-white/[0.07] p-4 xl:flex">
                <InstallConsole
                  logs={logs}
                  state={runState}
                  platformLabel={platformLabel}
                  canElevate={platform === "windows" || platform === "macos"}
                  onStop={() => void stopInstall()}
                  onClear={() => {
                    setLogs([]);
                    setRunState("idle");
                  }}
                  onRetryElevated={() => plan?.script && void startInstall(plan.script, true)}
                />
              </aside>
            )}
          </div>
        )}
      </main>

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onSaved={() => {
          void refreshHealth();
          void loadCatalog();
        }}
      />
    </div>
  );
}

/** 根据本机平台猜脚本类型（在渲染进程里没有 process，用 UA 兜底） */
function currentHostPlatform(): string {
  return navigator.userAgent.includes("Windows") ? "win32" : "darwin";
}

function scriptTypeOf(script: string, preferred?: string | null): "powershell" | "bash" {
  // 服务端已识别过脚本语言时以它为准（用户可能选的平台与本机不同）
  if (preferred === "powershell" || preferred === "bash") return preferred;
  if (/^\s*#!.*\b(bash|sh)\b/.test(script) || /set -euo pipefail/.test(script)) return "bash";
  if (/\bparam\s*\(|New-Item\s+-ItemType|\$env:/i.test(script)) return "powershell";
  return currentHostPlatform() === "win32" ? "powershell" : "bash";
}
