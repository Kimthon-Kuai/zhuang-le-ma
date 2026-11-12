import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-display text-sm font-semibold tracking-tight transition-all duration-150 disabled:pointer-events-none disabled:opacity-45 active:translate-y-px [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // 录音键：主操作
        tape: "bg-tape text-white shadow-[0_2px_0_#8e1b2a,0_8px_24px_-8px_rgba(255,77,94,.6)] hover:bg-[#ff6472]",
        label: "bg-label text-ink-950 shadow-[0_2px_0_#a98f4a] hover:bg-[#ffeec4]",
        phosphor:
          "bg-phosphor text-ink-950 shadow-[0_2px_0_#2f9d5b,0_8px_24px_-10px_rgba(125,255,168,.55)] hover:bg-[#9bffbe]",
        outline: "border border-white/15 bg-white/[0.03] text-slate-200 hover:border-white/30 hover:bg-white/[0.07]",
        ghost: "text-slate-300 hover:bg-white/[0.06] hover:text-white",
        danger: "border border-tape/40 bg-tape/10 text-tape-soft hover:bg-tape/20",
        link: "text-electric underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-[15px]",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "outline", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
