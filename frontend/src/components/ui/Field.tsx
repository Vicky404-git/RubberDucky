import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const CONTROL =
  "focus-ring w-full rounded-xl border border-white/[0.09] bg-black/30 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 transition-colors hover:border-white/[0.14] disabled:cursor-not-allowed disabled:opacity-50";

interface FieldProps {
  label: string;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}

export function Field({ label, hint, htmlFor, children, className }: FieldProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={htmlFor} className="text-xs font-medium text-zinc-300">
          {label}
        </label>
        {hint ? <span className="text-[11px] text-zinc-600">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(CONTROL, className)} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cn(CONTROL, "appearance-none pr-9", className)} {...props}>
        {children}
      </select>
    );
  },
);

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, description, disabled }: ToggleProps) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start justify-between gap-4 rounded-xl border border-white/[0.07] bg-black/20 px-4 py-3 transition-colors hover:border-white/[0.12]",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <span>
        <span className="block text-xs font-medium text-zinc-200">{label}</span>
        {description ? (
          <span className="mt-1 block text-[11px] leading-relaxed text-zinc-500">
            {description}
          </span>
        ) : null}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "focus-ring relative mt-0.5 h-6 w-11 shrink-0 rounded-full border transition-colors",
          checked
            ? "border-duck-400/50 bg-duck-400/80"
            : "border-white/[0.12] bg-white/[0.06]",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow transition-transform",
            checked ? "translate-x-[22px]" : "translate-x-0.5",
          )}
          style={{ height: 18, width: 18 }}
        />
      </button>
    </label>
  );
}
