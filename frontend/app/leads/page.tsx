"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { Download, FileSpreadsheet, Loader2, SearchX } from "lucide-react";
import { api } from "@/lib/api";
import type { LeadSummary } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip, TemperatureChip, cn } from "@/components/ui";
import { SheetsResultNote } from "@/components/sheets-note";
import { LeadFilters } from "@/components/lead-filters";
import { useExportToSheets } from "@/lib/use-export-to-sheets";

const SHEETS_KEY = "leads";

export default function LeadsPage() {
  return (
    <Suspense fallback={<Spinner label="Cargando leads…" />}>
      <LeadsPageInner />
    </Suspense>
  );
}

function LeadsPageInner() {
  const searchParams = useSearchParams();
  const searchId = searchParams.get("search_id") ?? undefined;
  const [temperature, setTemperature] = useState<string | undefined>(undefined);
  const [queryText, setQueryText] = useState("");
  const [hasEmail, setHasEmail] = useState<boolean | undefined>(undefined); // undefined = cualquiera
  const [hasWebsite, setHasWebsite] = useState<boolean | undefined>(undefined); // undefined = cualquiera
  const [status, setStatus] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0); // 0-indexed

  function clearFilters() {
    setTemperature(undefined);
    setHasEmail(undefined);
    setHasWebsite(undefined);
    setStatus("");
    setMinScore("");
    setQueryText("");
  }

  // Volver a la primera página cada vez que cambian los filtros/búsqueda
  const filterKey = `${searchId ?? ""}|${temperature ?? ""}|${hasEmail}|${hasWebsite}|${status}|${minScore}|${pageSize}|${queryText.trim()}`;
  const prevFilterKey = useRef(filterKey);
  if (prevFilterKey.current !== filterKey) {
    prevFilterKey.current = filterKey;
    if (page !== 0) setPage(0);
  }

  // Filtros sin paginación (se reusan para el export CSV)
  const filterParams = useMemo(() => {
    const p = new URLSearchParams();
    if (searchId) p.set("search_id", searchId);
    if (temperature) p.set("temperature", temperature);
    if (hasEmail !== undefined) p.set("has_email", String(hasEmail));
    if (hasWebsite !== undefined) p.set("has_website", String(hasWebsite));
    if (status) p.set("status", status);
    if (minScore) p.set("min_lead_score", minScore);
    if (queryText.trim()) p.set("q", queryText.trim());
    return p;
  }, [searchId, temperature, hasEmail, hasWebsite, status, minScore, queryText]);

  const params = useMemo(() => {
    const p = new URLSearchParams(filterParams);
    p.set("page_size", String(pageSize));
    p.set("page", String(page + 1)); // backend espera páginas 1-indexed
    p.set("offset", String(page * pageSize)); // por si el backend usa offset en vez de page
    return p.toString();
  }, [filterParams, pageSize, page]);

  const { data, isLoading, isError, error } = useQuery<{ items: LeadSummary[]; total: number }>({
    queryKey: ["leads", params],
    queryFn: () => api.get<{ items: LeadSummary[]; total: number }>(`/api/leads?${params}`),
    placeholderData: (prev) => prev, // evita el parpadeo/salto al cambiar de página
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  // ---- export CSV (FIX 5) -------------------------------------------------
  // El <a> no sirve: /api/leads/export exige `Authorization: Bearer <token>` y
  // un link común no lo manda. Bajamos el blob con el cliente `api`.
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExportCsv() {
    setIsExporting(true);
    setExportError(null);
    let objectUrl: string | null = null;
    try {
      // filterParams trae todos los filtros activos SIN page/page_size, así el
      // CSV incluye la población filtrada completa y no solo la página actual.
      const blob = await api.getBlob(`/api/leads/export?fmt=csv&${filterParams.toString()}`);
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "avascho_leads.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      setExportError(e instanceof Error ? e.message : "No pudimos exportar los leads.");
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setIsExporting(false);
    }
  }

  // ---- export a Google Sheets (FIX 7) --------------------------------------
  const {
    sendToSheets,
    isSending,
    error: sheetsError,
    outcome: sheetsOutcome,
  } = useExportToSheets();
  const isSendingToSheets = isSending(SHEETS_KEY);

  function handleSendToSheets() {
    sendToSheets(SHEETS_KEY, {
      selection: "all",
      search_id: searchId ? Number(searchId) : undefined,
      temperature,
      q: queryText.trim() || undefined,
      has_email: hasEmail,
      min_lead_score: minScore ? Number(minScore) : undefined,
    });
  }

  const columns = useMemo<ColumnDef<LeadSummary>[]>(
    () => [
      { accessorKey: "business_name", header: "Empresa", cell: (c) => <BusinessCell lead={c.row.original} /> },
      { accessorKey: "category", header: "Categoría", cell: (c) => <span className="text-xs text-taupe">{c.getValue() as string || "—"}</span> },
      { accessorKey: "city", header: "Ciudad", cell: (c) => <span className="text-xs">{c.getValue() as string || "—"}</span> },
      { accessorKey: "reviews_count", header: "Reviews", cell: (c) => <span className="tabular-nums">{c.getValue() as number}</span> },
      { accessorKey: "rating", header: "Rating", cell: (c) => (c.getValue() == null ? <span>—</span> : <span className="tabular-nums">{(c.getValue() as number).toFixed(1)} ⭐</span>) },
      { accessorKey: "website_score", header: "Website", cell: (c) => (c.getValue() == null ? <span className="text-taupe">—</span> : <span className="tabular-nums">{(c.getValue() as number).toFixed(1)}/10</span>) },
      { accessorKey: "opportunity_score", header: "Opp", cell: (c) => (c.getValue() == null ? <span className="text-taupe">—</span> : <span className="tabular-nums">{c.getValue() as number}</span>) },
      { accessorKey: "lead_score", header: "Lead", cell: (c) => <b className="tabular-nums text-[15px]">{(c.getValue() as number | null) ?? "—"}</b> },
      { accessorKey: "email", header: "Email", cell: (c) => <EmailCell value={c.getValue() as string | null} confidence={(c.row.original.email_confidence) as string | null} /> },
      { accessorKey: "lead_temperature", header: "Temp", cell: (c) => <TemperatureChip temperature={c.getValue() as string} /> },
      { accessorKey: "status", header: "Estado", cell: (c) => <StatusChip status={c.getValue() as string} /> },
    ],
    []
  );

  const table = useReactTable({ data: data?.items ?? [], columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold">Leads</h1>
          <p className="text-sm text-taupe mt-1">
            {data ? `${data.total} leads calificados` : "Cargando…"}
            {searchId ? " · filtrados por una búsqueda" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="input !w-56"
            placeholder="Buscar empresa…"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
          />
          <button
            type="button"
            className="btn-outline disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleExportCsv}
            disabled={isExporting}
            title="Exportar los leads filtrados a CSV"
          >
            {isExporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            {isExporting ? "Exportando…" : "CSV"}
          </button>
          <button
            type="button"
            className="btn-outline disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleSendToSheets}
            disabled={isSendingToSheets}
            title="Agregar los leads filtrados a la spreadsheet configurada"
          >
            {isSendingToSheets ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={15} />
            )}
            {isSendingToSheets ? "Enviando…" : "Enviar a Sheets"}
          </button>
        </div>
      </div>

      {/* filtros: panel colapsable en mobile, chips de activos, misma lógica de consulta */}
      <LeadFilters
        values={{ temperature, hasEmail, hasWebsite, status, minScore }}
        onTemperatureChange={setTemperature}
        onHasEmailChange={setHasEmail}
        onHasWebsiteChange={setHasWebsite}
        onStatusChange={setStatus}
        onMinScoreChange={setMinScore}
        onClear={clearFilters}
      />

      {/* avisos de exportación (CSV / Google Sheets) */}
      <ErrorNote message={exportError ?? undefined} />
      <ErrorNote message={sheetsError ?? undefined} />
      {sheetsOutcome?.key === SHEETS_KEY && <SheetsResultNote outcome={sheetsOutcome} />}

      {isLoading ? (
        <Spinner label="Cargando leads…" />
      ) : isError ? (
        <ErrorNote message={error instanceof Error ? error.message : "Error"} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          icon={<SearchX size={30} />}
          title={temperature ? `No hay leads ${temperature}` : "No encontramos negocios que cumplan tus filtros"}
          subtitle="Probá relajar los filtros o lanzá una nueva búsqueda."
          action={<Link href="/searches/new" className="btn-primary">Nueva búsqueda</Link>}
        />
      ) : (
        <>
          {/* Desktop table */}
          <Card className="!p-0 overflow-hidden hidden lg:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  {table.getHeaderGroups().map((hg) => (
                    <tr key={hg.id} className="border-b border-sandline bg-sand/50 text-left">
                      {hg.headers.map((header) => (
                        <th key={header.id} className="px-4 py-3 text-[10px] uppercase tracking-[0.12em] text-taupe font-semibold whitespace-nowrap">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="border-b border-sandline last:border-0 hover:bg-sand/40 transition cursor-pointer" onClick={() => (window.location.href = `/leads/${row.original.id}`)}>
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-3 align-middle">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Mobile cards */}
          <div className="space-y-3 lg:hidden">
            {data!.items.map((lead) => (
              <Link key={lead.id} href={`/leads/${lead.id}`}>
                <Card className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-semibold truncate">{lead.business_name}</div>
                      <div className="text-xs text-taupe mt-0.5">{lead.city ?? "—"} · {lead.category ?? ""}</div>
                    </div>
                    <TemperatureChip temperature={lead.lead_temperature} />
                  </div>
                  <div className="grid grid-cols-4 gap-2 mt-3 text-center text-xs">
                    <div className="bg-sand rounded-lg py-1.5">{lead.reviews_count}<span className="text-taupe"> rev</span></div>
                    <div className="bg-sand rounded-lg py-1.5">{lead.rating?.toFixed(1) ?? "—"} ⭐</div>
                    <div className="bg-sand rounded-lg py-1.5">{lead.website_score?.toFixed(1) ?? "—"}<span className="text-taupe"> web</span></div>
                    <div className="bg-sand rounded-lg py-1.5 font-semibold">{lead.lead_score ?? "—"}<span className="text-taupe"> lead</span></div>
                  </div>
                  {lead.email && <div className="text-xs text-taupe mt-2 truncate">{lead.email}</div>}
                </Card>
              </Link>
            ))}
          </div>

          {/* Paginación */}
          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-xs text-taupe">
              Página {page + 1} de {totalPages}
              {data ? ` · ${data.total} leads en total` : ""}
            </p>
            <div className="flex items-center gap-2">
              <button
                className="btn-outline !py-1.5 !px-3 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                Anterior
              </button>
              <button
                className="btn-outline !py-1.5 !px-3 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
                onClick={() => setPage((p) => (p + 1 < totalPages ? p + 1 : p))}
                disabled={page + 1 >= totalPages}
              >
                Siguiente
              </button>
              <select
                className="input !w-28 !py-1.5 text-xs"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                <option value={25}>25 / pág</option>
                <option value={50}>50 / pág</option>
                <option value={100}>100 / pág</option>
              </select>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BusinessCell({ lead }: { lead: LeadSummary }) {
  return (
    <div className="min-w-0">
      <div className="font-semibold text-ink truncate max-w-[220px]">{lead.business_name}</div>
      <div className="text-[11px] text-taupe truncate max-w-[220px]">
        {lead.recommended_service ?? ""}
      </div>
    </div>
  );
}

function EmailCell({ value, confidence }: { value: string | null; confidence: string | null }) {
  if (!value)
    return (
      <span className="chip bg-sand text-taupe" title="No encontramos un email público">
        sin email
      </span>
    );
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs truncate max-w-[150px]" title={value}>{value}</span>
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full shrink-0",
          confidence === "HIGH" ? "bg-[#1E8E3E]" : confidence === "MEDIUM" ? "bg-[#F9A825]" : "bg-[#C5221F]"
        )}
        title={`Confianza ${confidence}`}
      />
    </div>
  );
}