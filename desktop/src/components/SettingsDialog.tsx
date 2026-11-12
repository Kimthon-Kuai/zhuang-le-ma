import { useEffect, useState } from "react";
import { ServerCog, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api, getServerBase, setServerBase } from "@/lib/api";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

export function SettingsDialog({ open, onOpenChange, onSaved }: SettingsDialogProps) {
  const [url, setUrl] = useState(getServerBase());
  const [status, setStatus] = useState<"idle" | "checking" | "ok" | "fail">("idle");
  const [message, setMessage] = useState("");
  const [info, setInfo] = useState<{ platform: string; arch: string; electron: string } | null>(null);

  useEffect(() => {
    if (open) {
      setUrl(getServerBase());
      setStatus("idle");
      void window.zlm?.info().then(setInfo);
    }
  }, [open]);

  const test = async () => {
    setStatus("checking");
    setServerBase(url.trim());
    try {
      const h = await api.health();
      setStatus("ok");
      setMessage(`${h.slogan} · AI ${h.ai_configured ? `已配置（${h.model}）` : "未配置"}`);
    } catch (e) {
      setStatus("fail");
      setMessage((e as Error).message);
    }
  };

  const save = () => {
    setServerBase(url.trim());
    onSaved();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle className="flex items-center gap-2">
          <ServerCog className="size-5 text-label" /> 设置
        </DialogTitle>
        <DialogDescription>
          桌面端所有请求都发往下面这个服务端。AI Key 只放在服务端，App 手里没有密钥。
        </DialogDescription>

        <div className="mt-5 space-y-2">
          <label className="eyebrow" htmlFor="server-url">
            服务端地址
          </label>
          <Input
            id="server-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://127.0.0.1:8017"
            onKeyDown={(e) => e.key === "Enter" && void test()}
          />
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void test()} disabled={status === "checking"}>
            {status === "checking" ? "测试中…" : "测试连接"}
          </Button>
          {status === "ok" && (
            <span className="inline-flex items-center gap-1 font-body text-[12.5px] text-phosphor">
              <CheckCircle2 className="size-3.5" /> {message}
            </span>
          )}
          {status === "fail" && (
            <span className="inline-flex items-center gap-1 font-body text-[12.5px] text-tape-soft">
              <XCircle className="size-3.5" /> {message}
            </span>
          )}
        </div>

        <div className="mt-6 rounded-lg border border-white/10 bg-ink-950/60 px-3 py-2 font-mono text-[11px] leading-relaxed text-slate-500">
          <div>启动服务端：</div>
          <div className="text-slate-400">cd server &amp;&amp; .venv\Scripts\python -m uvicorn app.main:app --port 8017</div>
          {info && (
            <div className="mt-2 text-slate-600">
              本机 {info.platform}/{info.arch} · Electron {info.electron}
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button variant="label" onClick={save}>
            保存
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
