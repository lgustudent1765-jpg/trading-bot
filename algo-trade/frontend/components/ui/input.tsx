import { cn } from "@/lib/utils";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  suffix?: string;
  prefix?: string;
}

export function Input({ className, label, error, suffix, prefix, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-zinc-400">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {prefix && (
          <span className="absolute left-3 text-sm text-zinc-500 pointer-events-none select-none">
            {prefix}
          </span>
        )}
        <input
          id={inputId}
          className={cn(
            "w-full h-9 rounded-lg border border-zinc-800 bg-zinc-950 text-sm text-zinc-100",
            "px-3 placeholder:text-zinc-600",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/60",
            "disabled:opacity-40 disabled:cursor-not-allowed",
            error && "border-red-500/50 focus:ring-red-500/30",
            prefix && "pl-7",
            suffix && "pr-12",
            className
          )}
          {...props}
        />
        {suffix && (
          <span className="absolute right-3 text-xs text-zinc-500 pointer-events-none select-none">
            {suffix}
          </span>
        )}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
