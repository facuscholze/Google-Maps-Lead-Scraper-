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
import { Download, SearchX } from "lucide-react";
import { api } from "@/lib/api";
import type { LeadSummary, Temperature } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip, TemperatureChip, cn } from "@/components/ui";

const TEMPERATURES: Temperature[] = ["HOT", "WARM", "COLD", "LOW"];

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

  const hasActiveFilters =
    !!temperature || hasEmail !== undefined || hasWebsite !== undefined || !!status || !!minScore || !!queryText.trim();

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
  const exportHref = `/api/leads/export?format=csv&${filterParams.toString()}`;

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
          <a href={exportHref} className="btn-outline" title="Exportar los leads filtrados a CSV">
            <Download size={15} /> CSV
          </a>
        </div>
      </div>

      {/* quick filters */}
      <div className="flex flex-wrap items-center gap-2">
        <button className={cn("chip border", !temperature ? "border-ink text-ink" : "border-transparent bg-white text-taupe")} onClick={() => { setTemperature(undefined); }}>
          Todos
        </button>
        {TEMPERATURES.map((t) => (
          <button
            key={t}
            className={cn("chip border", temperature === t ? chipActive(t) : "border-transparent bg-white text-taupe")}
            onClick={() => setTemperature(temperature === t ? undefined : t)}
          >
            {t}
          </button>
        ))}

        <div className="h-5 w-px bg-sandline mx-1" />

        <TriStateFilter
          label="Email"
          value={hasEmail}
          onChange={setHasEmail}
          trueLabel="con email"
          falseLabel="sin email"
        />

        <TriStateFilter
          label="Web"
          value={hasWebsite}
          onChange={setHasWebsite}
          trueLabel="con web"
          falseLabel="sin web"
        />

        <div className="h-5 w-px bg-sandline mx-1" />

        <select className="input !w-44 !py-1.5 text-xs" value={minScore} onChange={(e) => setMinScore(e.target.value)}>
          <option value="">Lead score: cualquiera</option>
          <option value="80">Lead ≥ 80</option>
          <option value="70">Lead ≥ 70</option>
          <option value="60">Lead ≥ 60</option>
        </select>

        <select className="input !w-40 !py-1.5 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Estado: cualquiera</option>
          <option value="NEW">NEW</option>
          <option value="CONTACTED">CONTACTED</option>
          <option value="REPLIED">REPLIED</option>
          <option value="WON">WON</option>
          <option value="LOST">LOST</option>
        </select>

        {hasActiveFilters && (
          <button className="chip border border-transparent text-taupe hover:text-ink underline underline-offset-2" onClick={clearFilters}>
            Limpiar filtros
          </button>
        )}
      </div>

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

function TriStateFilter({
  label,
  value,
  onChange,
  trueLabel,
  falseLabel,
}: {
  label: string;
  value: boolean | undefined;
  onChange: (v: boolean | undefined) => void;
  trueLabel: string;
  falseLabel: string;
}) {
  return (
    <div className="flex items-center gap-1 bg-white border border-sandline rounded-full p-0.5">
      <span className="text-[10px] uppercase tracking-wide text-taupe pl-2 pr-1">{label}</span>
      <button
        className={cn("chip !py-1 !px-2 text-[11px]", value === undefined ? "bg-ink text-white" : "text-taupe")}
        onClick={() => onChange(undefined)}
      >
        todos
      </button>
      <button
        className={cn("chip !py-1 !px-2 text-[11px]", value === true ? "bg-ink text-white" : "text-taupe")}
        onClick={() => onChange(value === true ? undefined : true)}
      >
        {trueLabel}
      </button>
      <button
        className={cn("chip !py-1 !px-2 text-[11px]", value === false ? "bg-ink text-white" : "text-taupe")}
        onClick={() => onChange(value === false ? undefined : false)}
      >
        {falseLabel}
      </button>
    </div>
  );
}

function chipActive(t: string) {
  const map: Record<string, string> = {
    HOT: "!bg-[#FBE9E7] !text-[#B3261E] !border-[#F5C6C0]",
    WARM: "!bg-[#FFF3E0] !text-[#B26A00] !border-[#F5D9A8]",
    COLD: "!bg-[#E8F1FB] !text-[#0B57A4] !border-[#C3DCF5]",
    LOW: "!bg-sand !text-taupe !border-sandline",
  };
  return map[t] ?? "";
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