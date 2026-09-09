"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, SearchX } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchSummary } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip } from "@/components/ui";

export default function SearchesPage() {
  const { data, isLoading, isError, error } = useQuery<SearchSummary[]>({
    queryKey: ["searches"],
    queryFn: () => api.get<SearchSummary[]>("/api/searches"),
    refetchInterval: 8000,
  });

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

      {!data || data.length === 0 ? (
        <EmptyState icon={<SearchX size={32} />} title="Sin búsquedas todavía" subtitle="Creá una búsqueda de prueba, por ejemplo «Clínicas estéticas en Montevideo»." action={<Link href="/searches/new" className="btn-primary">Nueva búsqueda</Link>} />
      ) : (
        <div className="space-y-3">
          {data.map((s) => (
            <Link key={s.id} href={`/searches/${s.id}`} className="block">
              <Card className="p-5 hover:shadow-lift transition">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold truncate">{s.query}</div>
                    <div className="text-xs text-taupe mt-0.5">
                      {new Date(s.created_at).toLocaleString("es-UY")} ·{" "}
                      {s.results_qualified} qualified · {s.websites_analyzed} websites · {s.emails_found} emails
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-taupe">
                    <span title="hot"><b className="text-[#B3261E]">{s.hot_count}</b> HOT</span>
                    <span title="warm"><b className="text-[#B26A00]">{s.warm_count}</b> WARM</span>
                    <span title="cold">{s.cold_count} COLD</span>
                  </div>
                  <StatusChip status={s.status} />
                  <ArrowRight size={16} className="text-taupe" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
