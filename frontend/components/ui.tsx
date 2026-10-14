/**
 * Componentes de la iteración inicial, re-skinneados sobre los tokens innblock.
 * Se conservan sus exports para que las páginas existentes sigan compilando
 * mientras se reescriben por fases sobre `components/ui/*` (shadcn/ui).
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export { cn };

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
      {accent && <div className="absolute inset-x-0 top-0 h-0.5 bg-primary" />}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="label !mb-0.5">{label}</div>
          <div className="font-display text-[34px] leading-none font-extrabold tracking-tight text-foreground mt-1">
            {value}
          </div>
          {hint && <div className="text-xs text-muted-foreground mt-2 truncate">{hint}</div>}
        </div>
        {icon && <div className="text-accent-foreground/80 shrink-0 mt-0.5">{icon}</div>}
      </div>
    </div>
  );
}

export function TemperatureChip({ temperature }: { temperature?: string | null }) {
  if (!temperature)
    return <span className="chip bg-muted text-muted-foreground">—</span>;
  const styles: Record<string, string> = {
    HOT: "bg-red-500/15 text-red-500 dark:text-red-400",
    WARM: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    COLD: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
    LOW: "bg-muted text-muted-foreground",
  };
  return <span className={cn("chip", styles[temperature] ?? styles.LOW)}>{temperature}</span>;
}

export function StatusChip({ status }: { status: string }) {
  const positive = "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400";
  const warning = "bg-amber-500/15 text-amber-600 dark:text-amber-400";
  const info = "bg-sky-500/15 text-sky-600 dark:text-sky-400";
  const danger = "bg-destructive/15 text-destructive";
  const neutral = "bg-muted text-muted-foreground";
  const map: Record<string, string> = {
    RUNNING: info,
    PROCESSING: info,
    COMPLETED: positive,
    SENT: positive,
    CONTACTED: positive,
    REPLIED: positive,
    APPROVED: positive,
    CONNECTED: positive,
    QUEUED: warning,
    PENDING: neutral,
    READY_FOR_REVIEW: warning,
    AI_GENERATED: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
    FAILED: danger,
    DO_NOT_CONTACT: danger,
    OPTED_OUT: danger,
    BOUNCED: danger,
    CANCELLED: neutral,
    ARCHIVED: neutral,
    NEW: info,
  };
  return (
    <span className={cn("chip", map[status] ?? neutral)}>{status.replaceAll("_", " ")}</span>
  );
}

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "gold" | "outline" | "ghost";
}) {
  const variants = {
    primary: "btn-primary",
    gold: "btn-gold",
    outline: "btn-outline",
    ghost: "btn-ghost",
  };
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
  color = "#D90000",
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
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="hsl(var(--muted))"
          strokeWidth={6}
          fill="none"
        />
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
        <div className="font-display font-extrabold text-2xl leading-none">
          {value == null
            ? "—"
            : Number(value).toLocaleString("es-AR", { maximumFractionDigits: 1 })}
        </div>
        <div className="text-[10px] text-muted-foreground mt-0.5 tracking-wide">/ {max}</div>
        {label && (
          <div className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground mt-1">
            {label}
          </div>
        )}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-muted-foreground" role="status">
      <div className="h-7 w-7 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
      {label && <div className="text-sm">{label}</div>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  subtitle,
  action,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center justify-center py-14 text-center px-6">
      {icon && <div className="text-accent-foreground/70 mb-3">{icon}</div>}
      <div className="font-display text-xl font-extrabold tracking-tight text-foreground">
        {title}
      </div>
      {subtitle && <p className="text-sm text-muted-foreground mt-1.5 max-w-sm">{subtitle}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {message}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} />;
}

export function Bar({
  value,
  max = 10,
  color = "#D90000",
  height = 6,
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="w-full rounded-full bg-muted" style={{ height }}>
      <div
        className="rounded-full transition-all duration-700"
        style={{ width: `${pct}%`, height, background: color }}
      />
    </div>
  );
}
