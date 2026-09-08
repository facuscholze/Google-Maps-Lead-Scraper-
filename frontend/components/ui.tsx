import type { ReactNode } from "react";
import clsx from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

// ---------------------------------------------------------------- primitives
export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("card p-6", className)}>{children}</div>;
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  accent,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="card p-5 relative overflow-hidden">
      {accent && <div className="absolute inset-x-0 top-0 h-0.5 bg-gold" />}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="label !mb-0.5">{label}</div>
          <div className="font-display text-[34px] leading-none font-semibold text-ink mt-1">{value}</div>
          {hint && <div className="text-xs text-taupe mt-2 truncate">{hint}</div>}
        </div>
        {icon && <div className="text-gold/80 shrink-0 mt-0.5">{icon}</div>}
      </div>
    </div>
  );
}

export function TemperatureChip({ temperature }: { temperature?: string | null }) {
  if (!temperature) return <span className="chip bg-sand text-taupe">—</span>;
  const styles: Record<string, string> = {
    HOT: "bg-[#FBE9E7] text-[#B3261E]",
    WARM: "bg-[#FFF3E0] text-[#B26A00]",
    COLD: "bg-[#E8F1FB] text-[#0B57A4]",
    LOW: "bg-sand text-taupe",
  };
  return <span className={cn("chip", styles[temperature] ?? styles.LOW)}>{temperature}</span>;
}

export function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    RUNNING: "bg-[#E8F1FB] text-[#0B57A4]",
    COMPLETED: "bg-[#E6F4EA] text-[#1E8E3E]",
    FAILED: "bg-[#FCE8E6] text-[#C5221F]",
    SENT: "bg-[#E6F4EA] text-[#1E8E3E]",
    CONTACTED: "bg-[#E6F4EA] text-[#1E8E3E]",
    QUEUED: "bg-[#FFF8E1] text-[#B26A00]",
    APPROVED: "bg-[#E6F4EA] text-[#1E8E3E]",
    READY_FOR_REVIEW: "bg-[#FFF3E0] text-[#B26A00]",
    AI_GENERATED: "bg-[#EDE7F6] text-[#5E35B1]",
    PENDING: "bg-sand text-taupe",
    CANCELLED: "bg-sand text-taupe",
    DO_NOT_CONTACT: "bg-[#FCE8E6] text-[#C5221F]",
  };
  return <span className={cn("chip", map[status] ?? "bg-sand text-taupe")}>{status.replaceAll("_", " ")}</span>;
}

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "gold" | "outline" | "ghost" }) {
  const variants = { primary: "btn-primary", gold: "btn-gold", outline: "btn-outline", ghost: "btn-ghost" };
  return (
    <button className={cn(variants[variant], className)} {...props}>
      {children}
    </button>
  );
}

export function ScoreRing({
  value,
  max = 10,
  size = 96,
  label,
  color = "#B08D3E",
}: {
  value?: number | null;
  max?: number;
  size?: number;
  label?: string;
  color?: string;
}) {
  const pct = Math.max(0, Math.min(1, (value ?? 0) / max));
  const radius = size / 2 - 7;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="#EFE9DB" strokeWidth={6} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={6}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct)}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-display font-semibold text-2xl leading-none">
          {value == null ? "—" : Number(value).toLocaleString("es-UY", { maximumFractionDigits: 1 })}
        </div>
        <div className="text-[10px] text-taupe mt-0.5 tracking-wide">/ {max}</div>
        {label && <div className="text-[9px] uppercase tracking-[0.14em] text-taupe mt-1">{label}</div>}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-taupe">
      <div className="h-7 w-7 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
      {label && <div className="text-sm">{label}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, subtitle, action }: { icon?: ReactNode; title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center py-14 text-center px-6">
      {icon && <div className="text-gold/70 mb-3">{icon}</div>}
      <div className="font-display text-xl font-semibold text-ink">{title}</div>
      {subtitle && <p className="text-sm text-taupe mt-1.5 max-w-sm">{subtitle}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div className="rounded-xl bg-[#FCE8E6] text-[#C5221F] text-sm px-4 py-3 border border-[#F5C6C0]">{message}</div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-sand", className)} />;
}

export function Bar({ value, max = 10, color = "#B08D3E", height = 6 }: { value: number; max?: number; color?: string; height?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="w-full rounded-full bg-sand" style={{ height }}>
      <div className="rounded-full transition-all duration-700" style={{ width: `${pct}%`, height, background: color }} />
    </div>
  );
}
