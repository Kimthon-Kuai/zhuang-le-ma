import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium tracking-wide",
  {
    variants: {
      variant: {
        default: "border-white/10 bg-white/[0.05] text-slate-300",
        latest: "border-phosphor/30 bg-phosphor/10 text-phosphor",
        warning: "border-label/40 bg-label/10 text-label",
        danger: "border-tape/40 bg-tape/10 text-tape-soft",
        info: "border-electric/30 bg-electric/10 text-electric",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
