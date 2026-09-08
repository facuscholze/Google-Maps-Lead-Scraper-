"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Card, ErrorNote, Spinner, StatusChip } from "@/components/ui";
import type { Job } from "@/lib/types";

const JOB_LABELS: Record<string, string> = {
  GOOGLE_PLACES: "Buscando en Google Places…",
  FILTER: "Filtrando resultados…",
  WEBSITE_CRAWL: "Descargando websites…",
  WEBSITE_ANALYSIS: "Analizando websites…",
  LEAD_SCORING: "Scoring de leads…",
  CONTACT_DISCOVERY: "Descubriendo contactos…",
  EMAIL_QUEUE: "Cola de emails…",
};

interface StatusResponse {
  search: any;
  jobs: Job[];
  running: boolean;
}

export default function SearchDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, isLoading, isError, error } = useQuery<StatusResponse>({
    queryKey: ["search-status", id],
    queryFn: () => api.get<StatusResponse>(`/api/searches/${id}/status`),
    refetchInterval: (query) => (query.state.data?.running ? 2000 : false),
  });

  if (isLoading) return <Spinner label="Cargando…" />;
  if (isError) return <ErrorNote message={error instanceof Error ? error.message : "Error"} />;
  if (!data) return null;

  const { search, jobs, running } = data;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-4 justify-between">
        <div className="min-w-0">
          <div className="text-xs text-taupe mb-1">Búsqueda #{search.id}</div>
          <h1 className="font-display text-3xl font-semibold truncate">{search.query}</h1>
          <p className="text-sm text-taupe mt-1">
            {search.results_total} encontrados · {search.results_qualified} qualified ·{" "}
            {search.status === "COMPLETED" && search.duration_seconds != null ? `${search.duration_seconds}s` : ""}
          </p>
        </div>
        <StatusChip status={search.status} />
      </div>

      {running && (
        <div className="rounded-xl bg-night text-white px-5 py-4 flex items-center gap-3 text-sm">
          <Loader2 size={18} className="animate-spin text-goldsoft" />
          Procesando pipeline de inteligencia… podés cerrar esta página y volver cuando quieras.
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Live jobs */}
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4">Jobs</h2>
          <div className="space-y-3">
            {jobs.length === 0 && <p className="text-sm text-taupe">Sin jobs todavía.</p>}
            {jobs.map((job) => {
              const label = JOB_LABELS[job.job_type] ?? job.job_type;
              const active = job.status === "RUNNING";
              const done = job.status === "COMPLETED";
              return (
                <div key={job.id} className="flex items-start gap-3">
                  {done ? (
                    <CheckCircle2 size={17} className="text-[#1E8E3E] mt-0.5" />
                  ) : active ? (
                    <Loader2 size={17} className="animate-spin text-gold mt-0.5" />
                  ) : job.status === "FAILED" ? (
                    <XCircle size={17} className="text-[#C5221F] mt-0.5" />
                  ) : (
                    <Circle size={16} className="text-sandline mt-0.5" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{label}</div>
                    {job.current_step && (
                      <div className="text-xs text-taupe truncate mt-0.5">{job.current_step}</div>
                    )}
                    {job.total > 0 && (
                      <div className="h-1.5 bg-sand rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full bg-gold rounded-full transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {job.total > 0 && (
                    <div className="text-xs text-taupe tabular-nums">
                      {job.done}/{job.total}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* Results */}
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4">Resultado</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Encontrados", search.results_total],
              ["Qualified", search.results_qualified],
              ["Websites analizados", search.websites_analyzed],
              ["Emails", search.emails_found],
              ["HOT", search.hot_count],
              ["WARM", search.warm_count],
              ["COLD", search.cold_count],
              ["Páginas Google", search.google_pages ?? 0],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-xl bg-sand px-4 py-3">
                <div className="text-[10px] uppercase tracking-wider text-taupe">{label}</div>
                <div className="font-display text-2xl font-semibold">{value}</div>
              </div>
            ))}
          </div>
          {search.error_message && (
            <div className="mt-4 rounded-lg bg-[#FCE8E6] text-[#C5221F] text-xs px-3 py-2">{search.error_message}</div>
          )}
          {search.status === "COMPLETED" && search.results_qualified > 0 && (
            <Link href={`/leads?search_id=${search.id}`} className="btn-primary mt-5 w-full">
              Ver {search.results_qualified} leads calificados <ArrowRight size={15} />
            </Link>
          )}
        </Card>
      </div>
    </div>
  );
}
