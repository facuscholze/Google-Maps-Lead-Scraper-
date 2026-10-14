"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowRight,
  Ban,
  CheckCircle2,
  CircleDollarSign,
  Circle,
  Loader2,
  Map as MapIcon,
  Radio,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useSearchEvents } from "@/lib/use-search-events";
import { Card, ErrorNote, Spinner, StatusChip } from "@/components/ui";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Job } from "@/lib/types";
import { cn } from "@/lib/utils";

const JOB_LABELS: Record<string, string> = {
  GOOGLE_PLACES: "Buscando en Google Places…",
  FILTER: "Filtrando resultados…",
  WEBSITE_CRAWL: "Descargando websites…",
  WEBSITE_ANALYSIS: "Analizando websites…",
  LEAD_SCORING: "Scoring de leads…",
  CONTACT_DISCOVERY: "Descubriendo contactos…",
  EMAIL_QUEUE: "Cola de emails…",
};

export default function SearchDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { search, jobs, channel, done, error } = useSearchEvents(id);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string>();

  if (!search) {
    return error ? <ErrorNote message={error} /> : <Spinner label="Conectando…" />;
  }

  const isGrid = search.mode === "grid";
  const running = search.status === "RUNNING" || search.status === "PENDING";
  const gridPct =
    isGrid && search.grid_total_cells > 0
      ? Math.min(100, Math.round((search.grid_done_cells / search.grid_total_cells) * 100))
      : null;

  async function cancelSearch() {
    setCancelling(true);
    setActionError(undefined);
    try {
      await api.post(`/api/searches/${id}/cancel`);
      toast.success("Cancelación solicitada", {
        description: "El barrido se detiene al terminar la celda actual. Lo recolectado queda guardado.",
      });
      setCancelOpen(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "No se pudo cancelar");
    } finally {
      setCancelling(false);
    }
  }

  async function rerunSearch() {
    setActionError(undefined);
    try {
      await api.post(`/api/searches/${id}/run`);
      toast.success("Búsqueda relanzada");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "No se pudo relanzar");
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
            <span>Búsqueda #{search.id}</span>
            {isGrid && (
              <span className="chip bg-accent text-accent-foreground">
                <MapIcon size={11} /> Grilla
              </span>
            )}
            {!done && channel !== "connecting" && (
              <span className="chip bg-secondary text-muted-foreground">
                <Radio size={11} className={channel === "sse" ? "text-emerald-500" : "text-amber-500"} />
                {channel === "sse" ? "en vivo" : "polling"}
              </span>
            )}
          </div>
          <h1 className="truncate font-display text-3xl font-semibold">{search.query}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {search.results_total} encontrados · {search.results_qualified} califican
            {search.status === "COMPLETED" && search.duration_seconds != null
              ? ` · ${search.duration_seconds}s`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusChip status={search.status} />
          {running && !search.cancel_requested && (
            <button type="button" className="btn-outline !min-h-[38px] !px-3 text-xs" onClick={() => setCancelOpen(true)}>
              <Ban size={14} /> Cancelar
            </button>
          )}
          {!running && search.status !== "COMPLETED" && (
            <button type="button" className="btn-outline !min-h-[38px] !px-3 text-xs" onClick={rerunSearch}>
              <RotateCcw size={14} /> Relanzar
            </button>
          )}
        </div>
      </div>

      {/* Barra de progreso de grilla */}
      {isGrid && (
        <Card className="!p-4">
          <div className="flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0">
              <div className="font-semibold">
                Celda {Math.min(search.grid_done_cells, search.grid_total_cells)} de {search.grid_total_cells || "…"}
                {search.grid_capped_cells > 0 && (
                  <span className="ml-2 text-xs font-normal text-amber-600 dark:text-amber-400">
                    {search.grid_capped_cells} zona{search.grid_capped_cells > 1 ? "s" : ""} saturada
                    {search.grid_capped_cells > 1 ? "s" : ""} (60 por celda)
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                {search.cancel_requested
                  ? "Cancelando… se detiene al terminar la celda actual"
                  : search.budget_exhausted
                    ? "Se frenó por tope de presupuesto — los resultados parciales quedaron guardados"
                    : running
                      ? "Barriendo el área dibujada, dedupeando solapamientos en vivo"
                      : "Barrido finalizado"}
              </div>
            </div>
            {gridPct != null && (
              <div className="font-display text-2xl font-extrabold tabular-nums">{gridPct}%</div>
            )}
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-well">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                search.budget_exhausted ? "bg-amber-500" : "bg-primary",
              )}
              style={{ width: `${gridPct ?? 0}%` }}
            />
          </div>
        </Card>
      )}

      {running && !isGrid && (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-4 text-sm">
          <Loader2 size={18} className="animate-spin text-primary" />
          Procesando pipeline de inteligencia… podés cerrar esta página y volver cuando quieras.
        </div>
      )}

      {/* Costo */}
      <CostCard
        apiCalls={search.api_calls}
        apiCostUsd={search.api_cost_usd}
        estimatedCalls={search.estimated_api_calls}
        estimatedCostUsd={search.estimated_cost_usd}
        budgetCapUsd={search.budget_cap_usd}
        budgetExhausted={search.budget_exhausted}
      />

      <div className="grid gap-6 md:grid-cols-2">
        <JobsCard jobs={jobs} />

        <Card>
          <h2 className="mb-4 font-display text-lg font-semibold">Resultado</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Encontrados", search.results_total],
              ["Califican", search.results_qualified],
              ["Websites analizados", search.websites_analyzed],
              ["Emails", search.emails_found],
              ["HOT", search.hot_count],
              ["WARM", search.warm_count],
              ["COLD", search.cold_count],
              isGrid ? ["Dedupeados", search.deduped_count] : ["Páginas Google", search.google_pages ?? 0],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-xl bg-well px-4 py-3">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
                <div className="font-display text-2xl font-semibold tabular-nums">{value}</div>
              </div>
            ))}
          </div>
          {search.error_message && (
            <div className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {search.error_message}
            </div>
          )}
          {search.status === "COMPLETED" && search.results_qualified > 0 && (
            <Link href={`/leads?search_id=${search.id}`} className="btn-primary mt-5 w-full">
              Ver {search.results_qualified} leads calificados <ArrowRight size={15} />
            </Link>
          )}
          {search.status === "CANCELLED" && search.results_qualified === 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              La búsqueda se canceló antes de recolectar resultados. Podés relanzarla cuando quieras.
            </p>
          )}
        </Card>
      </div>

      <ErrorNote message={actionError} />

      {/* Confirm cancel */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Cancelar la búsqueda?</DialogTitle>
            <DialogDescription>
              El barrido se detiene de forma cooperativa: termina la celda actual y guarda todo lo
              recolectado hasta ahora. No se devuelve el costo ya consumido de la API.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <DialogClose asChild>
              <button type="button" className="btn-outline">Seguir buscando</button>
            </DialogClose>
            <button
              type="button"
              className="btn-primary"
              onClick={cancelSearch}
              disabled={cancelling}
            >
              {cancelling ? <Loader2 size={15} className="animate-spin" /> : <Ban size={15} />}
              Sí, cancelar
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CostCard({
  apiCalls,
  apiCostUsd,
  estimatedCalls,
  estimatedCostUsd,
  budgetCapUsd,
  budgetExhausted,
}: {
  apiCalls: number;
  apiCostUsd: number;
  estimatedCalls: number;
  estimatedCostUsd: number | null | undefined;
  budgetCapUsd: number | null | undefined;
  budgetExhausted: boolean;
}) {
  return (
    <Card className="flex flex-wrap items-center gap-x-8 gap-y-3 !p-4">
      <div className="flex items-center gap-3">
        <CircleDollarSign size={18} className={budgetExhausted ? "text-amber-500" : "text-primary"} />
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Costo de API</div>
          <div className="font-display text-lg font-semibold tabular-nums">
            {fmtUsd(apiCostUsd)}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {apiCalls} llamada{apiCalls === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </div>
      {estimatedCostUsd != null && estimatedCostUsd > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Estimado</div>
          <div className="text-sm font-medium tabular-nums">
            {fmtUsd(estimatedCostUsd)} · ~{estimatedCalls} llamadas
          </div>
        </div>
      )}
      {budgetCapUsd != null && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Tope</div>
          <div className={cn("text-sm font-medium tabular-nums", budgetExhausted && "text-amber-500")}>
            {fmtUsd(budgetCapUsd)}{budgetExhausted ? " · alcanzado" : ""}
          </div>
        </div>
      )}
    </Card>
  );
}

function JobsCard({ jobs }: { jobs: Job[] }) {
  return (
    <Card>
      <h2 className="mb-4 font-display text-lg font-semibold">Etapas</h2>
      <div className="space-y-3">
        {jobs.length === 0 && <p className="text-sm text-muted-foreground">Sin jobs todavía.</p>}
        {jobs.map((job) => {
          const label = JOB_LABELS[job.job_type] ?? job.job_type;
          const active = job.status === "RUNNING";
          const doneJob = job.status === "COMPLETED";
          return (
            <div key={job.id} className="flex items-start gap-3">
              {doneJob ? (
                <CheckCircle2 size={17} className="mt-0.5 text-emerald-500" />
              ) : active ? (
                <Loader2 size={17} className="mt-0.5 animate-spin text-primary" />
              ) : job.status === "FAILED" ? (
                <XCircle size={17} className="mt-0.5 text-destructive" />
              ) : job.status === "CANCELLED" ? (
                <Ban size={16} className="mt-0.5 text-muted-foreground" />
              ) : (
                <Circle size={16} className="mt-0.5 text-muted-foreground" />
              )}
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{label}</div>
                {job.current_step && (
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">{job.current_step}</div>
                )}
                {job.total > 0 && (
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-well">
                    <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${job.progress}%` }} />
                  </div>
                )}
              </div>
              {job.total > 0 && (
                <div className="text-xs tabular-nums text-muted-foreground">{job.done}/{job.total}</div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function fmtUsd(v: number): string {
  if (v <= 0) return "US$ 0.00";
  if (v < 0.01) return "<US$ 0.01";
  return `US$ ${v.toFixed(v < 1 ? 3 : 2)}`;
}
