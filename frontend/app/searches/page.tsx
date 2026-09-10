"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, FileSpreadsheet, Loader2, SearchX } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchSummary } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip } from "@/components/ui";
import { SheetsResultNote } from "@/components/sheets-note";
import { useExportToSheets } from "@/lib/use-export-to-sheets";

export default function SearchesPage() {
  const { data, isLoading, isError, error } = useQuery<SearchSummary[]>({
    queryKey: ["searches"],
    queryFn: () => api.get<SearchSummary[]>("/api/searches"),
    refetchInterval: 8000,
  });

  const { sendToSheets, isSending, error: sheetsError, outcome: sheetsOutcome } =
    useExportToSheets();

  if (isLoading) return <Spinner label="Cargando búsquedas…" />;
  if (isError) return <ErrorNote message={error instanceof Error ? error.message : "Error"} />;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold">Historial de búsquedas</h1>
          <p className="text-sm text-taupe mt-1">Cada búsqueda dispara el pipeline: Places → filtros → websites → scoring.</p>
        </div>
        <Link href="/searches/new" className="btn-primary hidden sm:inline-flex">+ Nueva búsqueda</Link>
      </div>

      <ErrorNote message={sheetsError ?? undefined} />

      {!data || data.length === 0 ? (
        <EmptyState icon={<SearchX size={32} />} title="Sin búsquedas todavía" subtitle="Creá una búsqueda de prueba, por ejemplo «Clínicas estéticas en Montevideo»." action={<Link href="/searches/new" className="btn-primary">Nueva búsqueda</Link>} />
      ) : (
        <div className="space-y-3">
          {data.map((s) => {
            const sheetsKey = `search-${s.id}`;
            const sending = isSending(sheetsKey);
            return (
              <div key={s.id} className="space-y-2">
                {/*
                  La card entera lleva al detalle vía un <Link> estirado
                  (after:absolute after:inset-0) en vez de envolver todo en el
                  <Link>: así el botón queda FUERA del <a> (un <button> dentro
                  de un <a> es HTML inválido) y el click nunca navega.
                */}
                <Card className="relative p-5 hover:shadow-lift transition">
                  <div className="flex flex-wrap items-center gap-3">
                    <Link
                      href={`/searches/${s.id}`}
                      className="min-w-0 flex-1 after:absolute after:inset-0 after:content-['']"
                    >
                      <div className="font-semibold truncate">{s.query}</div>
                      <div className="text-xs text-taupe mt-0.5">
                        {new Date(s.created_at).toLocaleString("es-UY")} ·{" "}
                        {s.results_qualified} qualified · {s.websites_analyzed} websites · {s.emails_found} emails
                      </div>
                    </Link>
                    <div className="flex items-center gap-4 text-xs text-taupe">
                      <span title="hot"><b className="text-[#B3261E]">{s.hot_count}</b> HOT</span>
                      <span title="warm"><b className="text-[#B26A00]">{s.warm_count}</b> WARM</span>
                      <span title="cold">{s.cold_count} COLD</span>
                    </div>
                    <StatusChip status={s.status} />
                    {s.status === "COMPLETED" && (
                      <button
                        type="button"
                        className="btn-outline relative z-10 !py-1.5 !px-3 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={sending}
                        title="Enviar todos los leads de esta búsqueda a Google Sheets"
                        onClick={(e) => {
                          // El botón vive fuera del <a>, pero frenamos el
                          // bubbling por si la card vuelve a envolverlo.
                          e.preventDefault();
                          e.stopPropagation();
                          sendToSheets(sheetsKey, { selection: "all", search_id: s.id });
                        }}
                      >
                        {sending ? (
                          <Loader2 size={15} className="animate-spin" />
                        ) : (
                          <FileSpreadsheet size={15} />
                        )}
                        {sending ? "Enviando…" : "Enviar a Sheets"}
                      </button>
                    )}
                    <ArrowRight size={16} className="text-taupe" />
                  </div>
                </Card>
                {sheetsOutcome?.key === sheetsKey && <SheetsResultNote outcome={sheetsOutcome} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
