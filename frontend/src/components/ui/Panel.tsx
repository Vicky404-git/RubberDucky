import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

interface PanelProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  padded?: boolean;
}

export function Panel({
  title,
  subtitle,
  action,
  padded = true,
  className,
  children,
  ...props
}: PanelProps) {
  return (
    <section className={cn("glass-panel flex flex-col", className)} {...props}>
      {title || action ? (
        <header className="flex items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-4">
          <div className="min-w-0">
            {typeof title === "string" ? (
              <h2 className="text-sm font-semibold tracking-tight text-zinc-100">{title}</h2>
            ) : (
              title
            )}
            {subtitle ? (
              <p className="mt-1 text-xs leading-relaxed text-zinc-500">{subtitle}</p>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}
      <div className={cn(padded && "p-5", "min-h-0 flex-1")}>{children}</div>
    </section>
  );
}
