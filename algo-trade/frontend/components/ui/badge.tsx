import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "danger" | "warning" | "neutral";
}

const variants = {
  default: "bg-zinc-800 text-zinc-300",
  success: "bg-emerald-500/10 text-emerald-400",
  danger: "bg-red-500/10 text-red-400",
  warning: "bg-amber-500/10 text-amber-400",
  neutral: "bg-zinc-800/60 text-zinc-400",
};

export function Badge({ className, variant = "default", children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
