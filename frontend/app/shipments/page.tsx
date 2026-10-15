"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Ban, Clock, MailCheck, MailX, Send, ShieldBan, Inbox } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusChip, EmptyState, ErrorNote } from "@/components/ui";

type EmailOut = components["schemas"]["EmailOut"];
type SuppressionOut = components["schemas"]["SuppressionOut"];

const fmt = new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" });

function when(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : fmt.format(d);
}

export default function ShipmentsPage() {
  const queryClient = useQueryClient();
  const {
    data: emails,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["emails"],
    queryFn: () => api.get<EmailOut[]>("/api/emails"),
  });
  const { data: suppression } = useQuery({
    queryKey: ["suppression"],
    queryFn: () => api.get<SuppressionOut[]>("/api/suppression"),
  });

  const stats = useMemo(() => {
    const list = emails ?? [];
    return {
      queued: list.filter((e) => e.status === "QUEUED").length,
      sent: list.filter((e) => e.status === "SENT").length,
      failed: list.filter((e) => e.status === "FAILED").length,
      suppressed: (suppression ?? []).filter((s) => s.active).length,
    };
  }, [emails, suppression]);

  const cancelMutation = useMutation({
    mutationFn: (emailId: number) => api.post<EmailOut>(`/api/emails/${emailId}/cancel`),
    onSuccess: () => {
      toast.success("Envío cancelado", { description: "El correo quedó fuera de la cola." });
      queryClient.invalidateQueries({ queryKey: ["emails"] });
    },
    onError: (err) => {
      toast.error("No se pudo cancelar", {
        description: err instanceof ApiError ? err.message : "Error inesperado",
      });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-extrabold tracking-tight">Envíos</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cola y historial de correos. Nada sale sin tu aprobación previa en Propuestas.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi icon={<Clock size={18} />} label="En cola" value={stats.queued} loading={isLoading} />
        <Kpi icon={<MailCheck size={18} />} label="Enviados" value={stats.sent} loading={isLoading} />
        <Kpi icon={<MailX size={18} />} label="Fallidos" value={stats.failed} loading={isLoading} />
        <Kpi
          icon={<ShieldBan size={18} />}
          label="No contactar"
          value={stats.suppressed}
          loading={isLoading}
          href="/settings"
        />
      </div>

      {isError && <ErrorNote message={error instanceof Error ? error.message : "Error"} />}

      {/* Lista */}
      {isLoading ? (
        <Card>
          <CardContent className="space-y-3 pt-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : !emails || emails.length === 0 ? (
        <EmptyState
          icon={<Inbox size={30} />}
          title="Todavía no hay envíos"
          subtitle="Cuando apruebes propuestas y las encoles, las vas a ver acá con su estado y horario."
          action={
            <Button asChild>
              <Link href="/proposals">Ir a propuestas</Link>
            </Button>
          }
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Correos</CardTitle>
            <CardDescription>
              Los envíos respetan límites diarios, horario laboral y delays aleatorios por cuenta.
            </CardDescription>
          </CardHeader>
          <CardContent className="divide-y divide-border !p-0">
            {emails.map((email) => (
              <div
                key={email.id}
                className="flex flex-wrap items-center gap-3 px-5 py-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Send size={13} className="shrink-0 text-accent-foreground" />
                    <span className="truncate text-sm font-semibold">{email.to_email}</span>
                    <StatusChip status={email.status} />
                    {email.status === "SENT" && email.message_id?.startsWith("mock-") && (
                      <span
                        title="Envío simulado: la cuenta no tiene Gmail real conectado (modo demo). Nada salió a internet."
                        className="rounded border border-amber-300/60 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700"
                      >
                        Simulado
                      </span>
                    )}
                    {typeof email.attempts === "number" && email.attempts > 1 && (
                      <span
                        title={`Se necesitaron ${email.attempts} intentos (reintentos automáticos tras errores transitorios)`}
                        className="rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
                      >
                        {email.attempts} intentos
                      </span>
                    )}
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {email.subject ?? "(sin asunto)"}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {email.status === "SENT"
                      ? `Enviado ${when(email.sent_at)}`
                      : email.scheduled_at
                        ? `Programado ${when(email.scheduled_at)}`
                        : `Creado ${when(email.created_at)}`}
                    {email.from_email ? ` · desde ${email.from_email}` : ""}
                  </div>
                  {email.error && (
                    <div className="mt-1 truncate text-xs text-destructive">{email.error}</div>
                  )}
                </div>
                {email.status === "QUEUED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={cancelMutation.isPending}
                    onClick={() => cancelMutation.mutate(email.id)}
                  >
                    <Ban size={14} />
                    Cancelar
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  loading,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  loading?: boolean;
  href?: string;
}) {
  const body = (
    <Card className={href ? "transition hover:shadow-lift" : ""}>
      <CardContent className="flex items-center gap-3 !p-4">
        <div className="text-accent-foreground">{icon}</div>
        <div className="min-w-0">
          {loading ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <div className="font-display text-2xl font-extrabold leading-none">{value}</div>
          )}
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            {label}
          </div>
        </div>
      </CardContent>
    </Card>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
