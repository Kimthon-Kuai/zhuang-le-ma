import { useState } from "react";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { req, setToken } from "./lib";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return;
    setBusy(true);
    setError(null);
    try {
      const res = await req<{ token: string }>("/api/admin/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ password }),
      });
      setToken(res.token);
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-full place-items-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-xl border border-white/15 bg-ink-800">
            <ShieldCheck className="size-5 text-label" />
          </div>
          <div>
            <h1 className="font-display text-lg font-bold text-white">装了吗 · 后台</h1>
            <p className="font-mono text-[11px] text-slate-500">ADMIN CONSOLE</p>
          </div>
        </div>

        <form onSubmit={(e) => void submit(e)} className="panel p-5">
          <label htmlFor="pwd" className="mb-2 block font-mono text-[11px] uppercase tracking-wider text-slate-500">
            管理密码
          </label>
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-600" />
            <input
              id="pwd"
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="在 server/.env 里配置的 ADMIN_PASSWORD"
              className="field !pl-9"
            />
          </div>
          {error && (
            <p className="mt-3 rounded-md border border-tape/30 bg-tape/[0.08] px-2.5 py-1.5 text-[12.5px] text-tape-soft">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy || !password} className="btn-primary mt-4 w-full">
            {busy ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
            进入后台
          </button>
        </form>
        <p className="mt-4 text-center font-mono text-[11px] text-slate-600">
          今天你装了吗？· 管理后台 v1.0
        </p>
      </div>
    </div>
  );
}
