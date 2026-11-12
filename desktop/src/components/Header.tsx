import { Settings, Wifi, WifiOff, Disc3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface HeaderProps {
  online: boolean | null;
  aiConfigured: boolean;
  model?: string | null;
  onOpenSettings: () => void;
  onNewSession: () => void;
}

/** 磁带转轴：签名元素，转动表示正在生成 */
export function Reel({ spinning, size = 34 }: { spinning?: boolean; size?: number }) {
  return (
    <Disc3
      style={{ width: size, height: size }}
      className={cn(
        "text-label/90",
        spinning ? "animate-spin-slow" : "opacity-80",
      )}
      strokeWidth={1.4}
    />
  );
}

export function Header({
  online,
  aiConfigured,
  model,
  onOpenSettings,
  onNewSession,
}: HeaderProps) {
  return (
    <header className="flex items-center gap-4 border-b border-white/[0.07] px-6 py-3.5">
      <button
        type="button"
        onClick={onNewSession}
        className="group flex items-center gap-3 text-left"
        title="回到首页"
      >
        <div className="relative flex h-11 w-[74px] items-center justify-center rounded-md border border-white/15 bg-ink-800 tape-stripe">
          <Reel size={26} />
          <div className="mx-1 h-3 w-6 rounded-sm bg-tape shadow-[0_0_12px_rgba(255,77,94,.7)]" />
          <Reel size={26} />
          <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 rounded-sm bg-label px-1.5 font-mono text-[9px] font-bold text-ink-950">
            C-60
          </span>
        </div>
        <div className="leading-none">
          <h1 className="font-display text-[22px] font-bold tracking-tight text-white">
            装了吗<span className="text-tape">.</span>
          </h1>
          <p className="mt-1 font-body text-[12.5px] text-slate-400">今天你装了吗？</p>
        </div>
      </button>

      <div className="ml-auto flex items-center gap-2">
        {online === null ? (
          <Badge>连接中…</Badge>
        ) : online ? (
          <Badge variant="latest">
            <Wifi className="size-3" /> 服务在线
          </Badge>
        ) : (
          <Badge variant="danger">
            <WifiOff className="size-3" /> 服务离线
          </Badge>
        )}
        {online && (
          <Badge variant={aiConfigured ? "info" : "warning"}>
            {aiConfigured ? `AI · ${model ?? "已就绪"}` : "AI 未配置"}
          </Badge>
        )}
        <Button variant="ghost" size="icon" onClick={onOpenSettings} title="设置">
          <Settings />
        </Button>
      </div>
    </header>
  );
}
