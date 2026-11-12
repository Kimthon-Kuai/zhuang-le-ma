import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-shimmer rounded-lg bg-[linear-gradient(90deg,#1a1f3a_25%,#252b4d_50%,#1a1f3a_75%)] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}
