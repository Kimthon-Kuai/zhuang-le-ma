import { useMemo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy, Terminal, Play } from "lucide-react";
import { cn } from "@/lib/utils";

interface MarkdownViewProps {
  markdown: string;
  /** 主脚本所在代码块的序号（从 0 开始），会高亮并显示执行按钮 */
  primaryScriptIndex?: number;
  onRunScript?: (script: string) => void;
  runningScript?: boolean;
  className?: string;
}

const LANG_LABEL: Record<string, string> = {
  powershell: "PowerShell",
  ps1: "PowerShell",
  bash: "Bash",
  sh: "Bash",
  shell: "Shell",
  zsh: "Zsh",
  json: "JSON",
  yaml: "YAML",
  cmd: "CMD",
  bat: "BAT",
  text: "Text",
  markdown: "Markdown",
  md: "Markdown",
};

function extractText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (typeof node === "object" && "props" in (node as never)) {
    return extractText((node as { props: { children?: React.ReactNode } }).props.children);
  }
  return "";
}

function CodeBlock({
  code,
  lang,
  index,
  isPrimary,
  onRun,
  running,
}: {
  code: string;
  lang: string;
  index: number;
  isPrimary: boolean;
  onRun?: (script: string) => void;
  running?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      if (window.zlm) await window.zlm.copy(code);
      else await navigator.clipboard.writeText(code);
    } catch {
      /* 忽略剪贴板权限问题 */
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div
      className={cn(
        "group my-3 overflow-hidden rounded-xl border bg-ink-950/80",
        isPrimary ? "border-tape/40 shadow-[0_0_0_1px_rgba(255,77,94,.12)]" : "border-white/10",
      )}
      data-script-index={index}
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/10 bg-white/[0.03] px-3 py-1.5">
        <div className="flex items-center gap-2">
          <Terminal className="size-3.5 text-slate-500" />
          <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
            {LANG_LABEL[lang] ?? lang ?? "code"}
          </span>
          {isPrimary && (
            <span className="sticker !rotate-0 !px-1.5 !text-[10px]">安装脚本</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {isPrimary && onRun && (
            <button
              type="button"
              onClick={() => onRun(code)}
              disabled={running}
              className="inline-flex items-center gap-1 rounded-md bg-tape/15 px-2 py-1 font-display text-[11.5px] font-semibold text-tape-soft transition-colors hover:bg-tape/25 disabled:opacity-50"
            >
              <Play className="size-3" />
              执行
            </button>
          )}
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-display text-[11.5px] font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="复制代码"
          >
            {copied ? <Check className="size-3 text-phosphor" /> : <Copy className="size-3" />}
            {copied ? "已复制" : "复制"}
          </button>
        </div>
      </div>
      <pre className="max-h-[560px] overflow-auto p-3.5 text-[12.5px] leading-[1.65]">
        <code className={cn("font-mono", lang ? `language-${lang}` : "")}>{code}</code>
      </pre>
    </div>
  );
}

export function MarkdownView({
  markdown,
  primaryScriptIndex = 0,
  onRunScript,
  runningScript,
  className,
}: MarkdownViewProps) {
  // 统计代码块出现顺序，以便识别主脚本
  const blockCounter = useMemo(() => ({ n: -1 }), [markdown]);
  const hasInstallSection = useMemo(() => /##\s*一键安装脚本/.test(markdown), [markdown]);

  const components: Components = {
    pre({ children }) {
      // 拿到 <pre><code> 的真实文本与语言
      const child = Array.isArray(children) ? children[0] : children;
      const props = (child as { props?: { className?: string; children?: React.ReactNode } })?.props;
      const className = props?.className ?? "";
      const lang = /language-([\w-]+)/.exec(className)?.[1] ?? "";
      const code = extractText(props?.children).replace(/\n$/, "");
      blockCounter.n += 1;
      const index = blockCounter.n;
      const isExec = ["powershell", "ps1", "bash", "sh", "shell"].includes(lang);
      // 只有「一键安装脚本」小节下的那块才是主脚本；验证命令块只复制不执行
      const isPrimary = isExec && index === primaryScriptIndex && hasInstallSection;
      return (
        <CodeBlock
          code={code}
          lang={lang}
          index={index}
          isPrimary={isPrimary}
          onRun={isPrimary ? onRunScript : undefined}
          running={runningScript}
        />
      );
    },
    code({ className, children, ...props }) {
      // 行内代码（块级代码已经在 pre 里渲染）
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
    a({ href, children }) {
      return (
        <a
          href={href}
          onClick={(e) => {
            e.preventDefault();
            if (href && window.zlm) void window.zlm.openExternal(href);
            else if (href) window.open(href, "_blank");
          }}
        >
          {children}
        </a>
      );
    },
  };

  return (
    <div className={cn("prose-install", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
