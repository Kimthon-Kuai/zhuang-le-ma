import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-12 w-full rounded-xl border border-white/10 bg-ink-950/60 px-4 font-body text-[15px] text-white",
        "placeholder:text-slate-500",
        "transition-colors hover:border-white/20 focus:border-tape/60 focus:outline-none",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-xl border border-white/10 bg-ink-950/60 p-4 font-body text-[14px] text-white",
      "placeholder:text-slate-500 transition-colors hover:border-white/20 focus:border-tape/60 focus:outline-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
