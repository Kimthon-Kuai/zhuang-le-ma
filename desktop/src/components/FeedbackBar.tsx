import { useState } from "react";
import { ThumbsDown, ThumbsUp, Send, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface FeedbackBarProps {
  validCount: number;
  invalidCount: number;
  onSubmit: (rating: "valid" | "invalid", content?: string) => Promise<void>;
}

export function FeedbackBar({ validCount, invalidCount, onSubmit }: FeedbackBarProps) {
  const [rating, setRating] = useState<"valid" | "invalid" | null>(null);
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"valid" | "invalid" | null>(null);

  const submit = async (r: "valid" | "invalid", text?: string) => {
    setBusy(true);
    try {
      await onSubmit(r, text);
      setDone(r);
      setOpen(false);
      setContent("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2">
      <span className="font-body text-[13px] text-slate-400">这份方案管用吗？</span>
      <Button
        size="sm"
        variant={done === "valid" ? "phosphor" : "outline"}
        disabled={busy}
        onClick={() => void submit("valid")}
      >
        {done === "valid" ? <Check /> : <ThumbsUp />}
        有效 {validCount > 0 && <span className="font-mono text-[11px] opacity-70">{validCount}</span>}
      </Button>
      <Button
        size="sm"
        variant={done === "invalid" ? "danger" : "outline"}
        disabled={busy}
        onClick={() => {
          setRating("invalid");
          setOpen(true);
        }}
      >
        {done === "invalid" ? <Check /> : <ThumbsDown />}
        无效 {invalidCount > 0 && <span className="font-mono text-[11px] opacity-70">{invalidCount}</span>}
      </Button>
      <button
        type="button"
        className="ml-auto font-body text-[12.5px] text-slate-500 underline-offset-2 hover:text-white hover:underline"
        onClick={() => {
          setRating(null);
          setOpen(true);
        }}
      >
        只提建议
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>
            {rating === "invalid" ? "哪儿出问题了？" : "说说你的建议"}
          </DialogTitle>
          <DialogDescription>
            管理员会看到这条反馈。写清楚报错信息，能帮下一个人少踩坑。
          </DialogDescription>
          <Textarea
            autoFocus
            rows={5}
            maxLength={2000}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              rating === "invalid"
                ? "例如：执行到下载那一步超时了，镜像地址连不上"
                : "例如：希望能加一个国内镜像源"
            }
            className="mt-4"
          />
          <div className="mt-4 flex items-center justify-between">
            <span className="font-mono text-[11px] text-slate-500">{content.length}/2000</span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button
                variant={rating === "invalid" ? "tape" : "label"}
                disabled={busy || content.trim().length === 0}
                onClick={() => void submit(rating ?? "valid", content.trim())}
                className={cn(busy && "opacity-70")}
              >
                <Send /> {rating === "invalid" ? "标记无效并提交" : "提交建议"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
