"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import {
  Archive,
  ArrowDownNarrowWide,
  ArrowUpWideNarrow,
  BookmarkPlus,
  Columns3,
  Download,
  FileSignature,
  FileSpreadsheet,
  List,
  Loader2,
  Map as MapIcon,
  SearchX,
  Tag,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { LeadSummary, Temperature } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip, TemperatureChip, cn } from "@/components/ui";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SheetsResultNote } from "@/components/sheets-note";
import { useExportToSheets } from "@/lib/use-export-to-sheets";

const LeadMap = dynamic(() => import("@/components/map/lead-map"), {
  ssr: false,
  loading: () => (
    <div className="grid h-[380px] w-full place-items-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
      Cargando mapa…
    </div>
  ),
});

const TEMPERATURES: Temperature[] = ["HOT", "WARM", "COLD", "LOW"];
const LEAD_STATUSES = ["NEW", "CONTACTED", "REPLIED", "OPTED_OUT", "DO_NOT_CONTACT", "ARCHIVED"];
const SHEETS_KEY = "leads";

// ---------------------------------------------------------------- columns ---
const ALL_COLUMNS = [
  "sel", "business_name", "category", "city", "tags", "owner_name", "reviews_count",
  "rating", "website_score", "opportunity_score", "lead_score", "email",
  "lead_temperature", "status",
] as const;
type ColId = (typeof ALL_COLUMNS)[number];

const COL_LABELS: Record<ColId, string> = {
  sel: "", business_name: "Empresa", category: "Categoría", city: "Ciudad",
  tags: "Tags", owner_name: "Responsable", reviews_count: "Reseñas", rating: "Rating",
  website_score: "Website", opportunity_score: "Opp", lead_score: "Lead",
  email: "Email", lead_temperature: "Temp", status: "Estado",
};

// columnas que el backend puede ordenar server-side (whitelist de la API)
const SORTABLE: Partial<Record<ColId, string>> = {
  business_name: "business_name", category: "category", city: "city",
  reviews_count: "reviews_count", rating: "rating", website_score: "website_score",
  opportunity_score: "opportunity_score", lead_score: "lead_score",
};

const DEFAULT_VISIBLE: ColId[] = [
  "sel", "business_name", "category", "city", "reviews_count", "rating",
  "website_score", "opportunity_score", "lead_score", "email", "lead_temperature", "status",
];

interface SavedViewConfig {
  temperature?: string;
  hasEmail?: boolean;
  hasWebsite?: boolean;
  status?: string;
  minScore?: string;
  q?: string;
  city?: string;
  category?: string;
  tag?: string;
  owner?: string;
  sort?: string;
  order?: string;
  columns?: ColId[];
}
interface BackendView { id: number; name: string; config_json: SavedViewConfig }

export default function LeadsPage() {
  return (
    <Suspense fallback={<Spinner label="Cargando leads…" />}>
      <LeadsPageInner />
    </Suspense>
  );
}

function LeadsPageInner() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const searchId = searchParams.get("search_id") ?? undefined;
  // filtros
  const [temperature, setTemperature] = useState<string | undefined>(undefined);
  const [queryText, setQueryText] = useState("");
  const [hasEmail, setHasEmail] = useState<boolean | undefined>(undefined);
  const [hasWebsite, setHasWebsite] = useState<boolean | undefined>(undefined);
  const [status, setStatus] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [owner, setOwner] = useState("");
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  // orden/visibilidad/paginación/vista
  const [sort, setSort] = useState<string | undefined>(undefined);
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [visibleCols, setVisibleCols] = useState<ColId[]>(DEFAULT_VISIBLE);
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<"list" | "map">("list");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const hasActiveFilters =
    !!temperature || hasEmail !== undefined || hasWebsite !== undefined || !!status ||
    !!minScore || !!queryText.trim() || !!city.trim() || !!category.trim() || !!tag.trim() || !!owner.trim();

  function clearFilters() {
    setTemperature(undefined); setHasEmail(undefined); setHasWebsite(undefined);
    setStatus(""); setMinScore(""); setQueryText(""); setCity(""); setCategory("");
    setTag(""); setOwner("");
  }

  function currentViewConfig(): SavedViewConfig {
    return {
      temperature, hasEmail, hasWebsite,
      status: status || undefined, minScore: minScore || undefined,
      q: queryText.trim() || undefined,
      city: city.trim() || undefined, category: category.trim() || undefined,
      tag: tag.trim() || undefined, owner: owner.trim() || undefined,
      sort, order, columns: visibleCols,
    };
  }

  function applyViewConfig(cfg: SavedViewConfig) {
    setTemperature(cfg.temperature);
    setHasEmail(cfg.hasEmail);
    setHasWebsite(cfg.hasWebsite);
    setStatus(cfg.status ?? "");
    setMinScore(cfg.minScore ?? "");
    setQueryText(cfg.q ?? "");
    setCity(cfg.city ?? "");
    setCategory(cfg.category ?? "");
    setTag(cfg.tag ?? "");
    setOwner(cfg.owner ?? "");
    setSort(cfg.sort);
    setOrder(cfg.order === "asc" ? "asc" : "desc");
    if (Array.isArray(cfg.columns) && cfg.columns.length) {
      setVisibleCols(cfg.columns.filter((c): c is ColId => ALL_COLUMNS.includes(c as ColId)));
    }
  }

  // ---- vistas guardadas (backend; migro las locales si existen — D4.1) ----
  const viewsQuery = useQuery<BackendView[]>({
    queryKey: ["lead-views"],
    queryFn: () => api.get<BackendView[]>("/api/lead-views"),
  });
  const migratedRef = useRef(false);
  useEffect(() => {
    if (migratedRef.current || !viewsQuery.data) return;
    migratedRef.current = true;
    let local: { name: string }[] | null = null;
    try {
      const raw = window.localStorage.getItem("avascho_lead_views");
      if (raw) local = JSON.parse(raw);
    } catch { /* json roto → ignorar */ }
    if (!local?.length) return;
    void (async () => {
      let n = 0;
      for (const lv of local!) {
        try {
          await api.post("/api/lead-views", { name: lv.name, config: lv });
          n += 1;
        } catch { /* si falla una, sigue la otra */ }
      }
      window.localStorage.removeItem("avascho_lead_views");
      await queryClient.invalidateQueries({ queryKey: ["lead-views"] });
      if (n > 0) toast.success(`${n} vista${n > 1 ? "s" : ""} local${n > 1 ? "es" : ""} migradas a tu cuenta`);
    })();
  }, [viewsQuery.data, queryClient]);

  async function saveCurrentView() {
    const name = window.prompt("Nombre de la vista (ej: «HOT con email, score ≥70»)");
    if (!name?.trim()) return;
    try {
      await api.post("/api/lead-views", { name: name.trim(), config: currentViewConfig() });
      await queryClient.invalidateQueries({ queryKey: ["lead-views"] });
      toast.success("Vista guardada", { description: name.trim() });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo guardar la vista");
    }
  }
  async function deleteView(v: BackendView) {
    try {
      await api.del(`/api/lead-views/${v.id}`);
      await queryClient.invalidateQueries({ queryKey: ["lead-views"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo borrar la vista");
    }
  }

  // reset a página 1 al cambiar filtros/orden
  const filterKey = [
    searchId, temperature, hasEmail, hasWebsite, status, minScore, pageSize,
    queryText.trim(), city.trim(), category.trim(), tag.trim(), owner.trim(), sort, order,
  ].join("|");
  const prevFilterKey = useRef(filterKey);
  if (prevFilterKey.current !== filterKey) {
    prevFilterKey.current = filterKey;
    if (page !== 0) setPage(0);
    if (selected.size) setSelected(new Set());
  }

  const filterParams = useMemo(() => {
    const p = new URLSearchParams();
    if (searchId) p.set("search_id", searchId);
    if (temperature) p.set("temperature", temperature);
    if (hasEmail !== undefined) p.set("has_email", String(hasEmail));
    if (hasWebsite !== undefined) p.set("has_website", String(hasWebsite));
    if (status) p.set("status", status);
    if (minScore) p.set("min_lead_score", minScore);
    if (queryText.trim()) p.set("q", queryText.trim());
    if (city.trim()) p.set("city", city.trim());
    if (category.trim()) p.set("category", category.trim());
    if (tag.trim()) p.set("tag", tag.trim());
    if (owner.trim()) p.set("owner", owner.trim());
    if (sort) { p.set("sort", sort); p.set("order", order); }
    return p;
  }, [searchId, temperature, hasEmail, hasWebsite, status, minScore, queryText, city, category, tag, owner, sort, order]);

  const params = useMemo(() => {
    const p = new URLSearchParams(filterParams);
    p.set("page_size", String(pageSize));
    p.set("page", String(page + 1));
    return p.toString();
  }, [filterParams, pageSize, page]);

  const { data, isLoading, isError, error } = useQuery<{ items: LeadSummary[]; total: number }>({
    queryKey: ["leads", params],
    queryFn: () => api.get<{ items: LeadSummary[]; total: number }>(`/api/leads?${params}`),
    placeholderData: (prev) => prev,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  // mapa: hasta 500 del filtro (cap backend D3.5)
  const mapParams = useMemo(() => {
    const p = new URLSearchParams(filterParams);
    p.set("page_size", "500");
    p.set("page", "1");
    return p.toString();
  }, [filterParams]);
  const mapQuery = useQuery<{ items: LeadSummary[]; total: number }>({
    queryKey: ["leads-map", mapParams],
    queryFn: () => api.get<{ items: LeadSummary[]; total: number }>(`/api/leads?${mapParams}`),
    enabled: view === "map",
  });

  // ---- export CSV ------------------------------------------------------------
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  async function exportCsv(ids?: number[]) {
    setIsExporting(true);
    setExportError(null);
    let objectUrl: string | null = null;
    try {
      const sel = ids?.length
        ? `selection=selected&ids=${ids.join(",")}`
        : filterParams.toString();
      const blob = await api.getBlob(`/api/leads/export?fmt=csv&${sel}`);
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "leads_innblock.csv";
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

  // ---- Google Sheets ---------------------------------------------------------
  const { sendToSheets, isSending, error: sheetsError, outcome: sheetsOutcome } = useExportToSheets();
  const isSendingToSheets = isSending(SHEETS_KEY);
  function handleSendToSheets(ids?: number[]) {
    sendToSheets(SHEETS_KEY, {
      selection: ids?.length ? "selected" : "all",
      ids: ids?.length ? ids : undefined,
      search_id: searchId ? Number(searchId) : undefined,
      temperature, q: queryText.trim() || undefined,
      has_email: hasEmail, min_lead_score: minScore ? Number(minScore) : undefined,
    });
  }

  // ---- bulk actions -----------------------------------------------------------
  const [bulkBusy, setBulkBusy] = useState<string | null>(null);
  async function bulkAction(action: string, extra?: Record<string, string>) {
    if (!selected.size) return;
    setBulkBusy(action);
    try {
      const res = await api.post<{ updated: number }>("/api/leads/bulk", {
        ids: [...selected], action, ...extra,
      });
      toast.success(`${res.updated} lead${res.updated === 1 ? "" : "s"} actualizados`);
      setSelected(new Set());
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo aplicar la acción");
    } finally {
      setBulkBusy(null);
    }
  }
  async function bulkProposals() {
    if (!selected.size) return;
    setBulkBusy("proposals");
    try {
      const res = await api.post<{ created: number[]; skipped: { lead_id: number; reason: string }[] }>(
        "/api/leads/bulk-proposals",
        { ids: [...selected], action: "set_status" },
      );
      if (res.created.length)
        toast.success(`${res.created.length} propuesta${res.created.length === 1 ? "" : "s"} generadas — quedan para revisión humana`);
      if (res.skipped.length)
        toast.warning(`${res.skipped.length} saltadas`, {
          description: res.skipped.slice(0, 2).map((s) => `#${s.lead_id}: ${s.reason}`).join(" · "),
        });
      setSelected(new Set());
      await queryClient.invalidateQueries({ queryKey: ["proposals"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudieron generar las propuestas");
    } finally {
      setBulkBusy(null);
    }
  }

  // ---- selección ---------------------------------------------------------------
  const pageIds = (data?.items ?? []).map((l) => l.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  function toggleAll() {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  }
  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // ---- columnas ----------------------------------------------------------------
  function toggleSort(colId: ColId) {
    const key = SORTABLE[colId];
    if (!key) return;
    if (sort === key) setOrder(order === "desc" ? "asc" : "desc");
    else { setSort(key); setOrder("desc"); }
  }

  const columns = useMemo<ColumnDef<LeadSummary>[]>(() => {
    const builder: Record<ColId, ColumnDef<LeadSummary>> = {
      sel: {
        id: "sel",
        header: () => (
          <input
            type="checkbox"
            aria-label="Seleccionar página"
            checked={allSelected}
            onChange={toggleAll}
            className="h-4 w-4 accent-[#D90000]"
          />
        ),
        cell: (c) => (
          <input
            type="checkbox"
            aria-label={`Seleccionar ${c.row.original.business_name}`}
            checked={selected.has(c.row.original.id)}
            onChange={() => toggleOne(c.row.original.id)}
            onClick={(e) => e.stopPropagation()}
            className="h-4 w-4 accent-[#D90000]"
          />
        ),
      },
      business_name: { accessorKey: "business_name", cell: (c) => <BusinessCell lead={c.row.original} /> },
      category: { accessorKey: "category", cell: (c) => <span className="text-xs text-muted-foreground">{(c.getValue() as string) || "—"}</span> },
      city: { accessorKey: "city", cell: (c) => <span className="text-xs">{(c.getValue() as string) || "—"}</span> },
      tags: {
        accessorKey: "tags",
        cell: (c) => {
          const tags = (c.getValue() as string[] | undefined) ?? [];
          if (!tags.length) return <span className="text-xs text-muted-foreground">—</span>;
          return (
            <span className="flex max-w-[160px] flex-wrap gap-1">
              {tags.slice(0, 3).map((t) => (
                <span key={t} className="chip border border-border bg-well text-muted-foreground">{t}</span>
              ))}
              {tags.length > 3 && <span className="text-xs text-muted-foreground">+{tags.length - 3}</span>}
            </span>
          );
        },
      },
      owner_name: { accessorKey: "owner_name", cell: (c) => <span className="text-xs">{(c.getValue() as string) || "—"}</span> },
      reviews_count: { accessorKey: "reviews_count", cell: (c) => <span className="tabular-nums">{c.getValue() as number}</span> },
      rating: { accessorKey: "rating", cell: (c) => (c.getValue() == null ? <span>—</span> : <span className="tabular-nums">{(c.getValue() as number).toFixed(1)} ★</span>) },
      website_score: { accessorKey: "website_score", cell: (c) => (c.getValue() == null ? <span className="text-muted-foreground">—</span> : <span className="tabular-nums">{(c.getValue() as number).toFixed(1)}/10</span>) },
      opportunity_score: { accessorKey: "opportunity_score", cell: (c) => (c.getValue() == null ? <span className="text-muted-foreground">—</span> : <span className="tabular-nums">{c.getValue() as number}</span>) },
      lead_score: { accessorKey: "lead_score", cell: (c) => <b className="tabular-nums text-[15px]">{(c.getValue() as number | null) ?? "—"}</b> },
      email: { accessorKey: "email", cell: (c) => <EmailCell value={c.getValue() as string | null} confidence={c.row.original.email_confidence as string | null} /> },
      lead_temperature: { accessorKey: "lead_temperature", cell: (c) => <TemperatureChip temperature={c.getValue() as string} /> },
      status: { accessorKey: "status", cell: (c) => <StatusChip status={c.getValue() as string} /> },
    };
    return visibleCols.filter((id) => id in builder).map((id) => ({
      ...builder[id],
      id,
      header: () => <HeaderCell colId={id} sort={sort} order={order} onSort={toggleSort} />,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleCols, sort, order, selected, allSelected, pageIds.length]);

  const table = useReactTable({ data: data?.items ?? [], columns, getCoreRowModel: getCoreRowModel() });
  const views = viewsQuery.data ?? [];

  return (
    <div className="space-y-5 pb-24">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold">Leads</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data ? `${data.total} leads calificados` : "Cargando…"}
            {searchId ? " · filtrados por una búsqueda" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ViewToggle view={view} onChange={setView} />
          <input
            className="input !w-44 sm:!w-56"
            placeholder="Buscar empresa…"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
          />
          <ColumnsDropdown visible={visibleCols} onToggle={(c) => {
            setVisibleCols((prev) => {
              if (prev.includes(c)) {
                const next = prev.filter((x) => x !== c);
                return next.length > 2 ? next : prev;
              }
              const next = [...prev, c];
              return ALL_COLUMNS.filter((x) => next.includes(x));
            });
          }} />
          <button type="button" className="btn-outline disabled:cursor-not-allowed disabled:opacity-50" onClick={() => exportCsv()} disabled={isExporting} title="Exportar los leads filtrados a CSV">
            {isExporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            <span className="hidden md:inline">{isExporting ? "Exportando…" : "CSV"}</span>
          </button>
          <button type="button" className="btn-outline disabled:cursor-not-allowed disabled:opacity-50" onClick={() => handleSendToSheets()} disabled={isSendingToSheets} title="Agregar los leads filtrados a la spreadsheet configurada">
            {isSendingToSheets ? <Loader2 size={15} className="animate-spin" /> : <FileSpreadsheet size={15} />}
            <span className="hidden md:inline">{isSendingToSheets ? "Enviando…" : "Sheets"}</span>
          </button>
        </div>
      </div>

      {/* quick filters */}
      <div className="flex flex-wrap items-center gap-2">
        <button className={cn("chip border", !temperature ? "border-foreground text-foreground" : "border-transparent bg-card text-muted-foreground")} onClick={() => setTemperature(undefined)}>
          Todos
        </button>
        {TEMPERATURES.map((t) => (
          <button
            key={t}
            className={cn("chip border", temperature === t ? "border-primary bg-accent text-accent-foreground" : "border-transparent bg-card text-muted-foreground")}
            onClick={() => setTemperature(temperature === t ? undefined : t)}
          >
            {t}
          </button>
        ))}
        <div className="mx-1 h-5 w-px bg-border" />
        <TriStateFilter label="Email" value={hasEmail} onChange={setHasEmail} trueLabel="con email" falseLabel="sin email" />
        <TriStateFilter label="Web" value={hasWebsite} onChange={setHasWebsite} trueLabel="con web" falseLabel="sin web" />
        <div className="mx-1 h-5 w-px bg-border" />
        <select className="input !w-44 !py-1.5 text-xs" value={minScore} onChange={(e) => setMinScore(e.target.value)}>
          <option value="">Lead score: cualquiera</option>
          <option value="80">Lead ≥ 80</option>
          <option value="70">Lead ≥ 70</option>
          <option value="60">Lead ≥ 60</option>
        </select>
        <select className="input !w-44 !py-1.5 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Estado: cualquiera</option>
          {LEAD_STATUSES.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
        </select>
        <button type="button" className={cn("chip border", showMoreFilters || city || category || tag || owner ? "border-primary text-accent-foreground" : "border-border text-muted-foreground")} onClick={() => setShowMoreFilters((v) => !v)}>
          + filtros
        </button>
        {hasActiveFilters && (
          <button className="chip border border-transparent text-muted-foreground underline underline-offset-2 hover:text-foreground" onClick={clearFilters}>
            Limpiar filtros
          </button>
        )}
        <button type="button" className="chip border border-border bg-card text-muted-foreground hover:text-foreground" onClick={saveCurrentView} title="Guardar filtros + orden + columnas como vista">
          <BookmarkPlus size={12} /> Guardar vista
        </button>
      </div>

      {showMoreFilters && (
        <div className="grid grid-cols-2 gap-2 rounded-xl border border-border bg-card p-3 sm:grid-cols-4">
          <input className="input !py-1.5 text-xs" placeholder="Ciudad…" value={city} onChange={(e) => setCity(e.target.value)} />
          <input className="input !py-1.5 text-xs" placeholder="Categoría…" value={category} onChange={(e) => setCategory(e.target.value)} />
          <input className="input !py-1.5 text-xs" placeholder="Tag exacto…" value={tag} onChange={(e) => setTag(e.target.value)} />
          <input className="input !py-1.5 text-xs" placeholder="Responsable…" value={owner} onChange={(e) => setOwner(e.target.value)} />
        </div>
      )}

      {views.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Vistas</span>
          {views.map((v) => (
            <span key={v.id} className="group chip border border-border bg-card text-foreground">
              <button type="button" className="hover:text-primary" onClick={() => applyViewConfig(v.config_json)}>
                {v.name}
              </button>
              <button
                type="button"
                aria-label={`Eliminar vista ${v.name}`}
                className="text-muted-foreground opacity-0 transition hover:text-destructive group-hover:opacity-100"
                onClick={() => deleteView(v)}
              >
                <Trash2 size={11} />
              </button>
            </span>
          ))}
        </div>
      )}

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
          title={hasActiveFilters ? "No hay leads que cumplan esos filtros" : "Todavía no tenés leads"}
          subtitle="Probá relajar los filtros o lanzá una nueva búsqueda."
          action={<Link href="/searches/new" className="btn-primary">Nueva búsqueda</Link>}
        />
      ) : view === "map" ? (
        <div className="space-y-2">
          {mapQuery.isLoading ? (
            <Spinner label="Cargando leads…" />
          ) : mapQuery.isError ? (
            <ErrorNote message="No pudimos cargar los leads del mapa." />
          ) : (
            <>
              <LeadMap leads={mapQuery.data?.items ?? []} className="h-[420px] w-full overflow-hidden rounded-xl border border-border" />
              <p className="text-xs text-muted-foreground">
                {countPins(mapQuery.data?.items ?? [])} de {mapQuery.data?.items.length ?? 0} leads tienen coordenadas
                {(mapQuery.data?.total ?? 0) > 500 ? " · se muestran los primeros 500 del filtro" : ""}
                · el color marca la temperatura.
              </p>
            </>
          )}
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <Card className="!p-0 overflow-hidden hidden lg:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  {table.getHeaderGroups().map((hg) => (
                    <tr key={hg.id} className="border-b border-border bg-well/60 text-left">
                      {hg.headers.map((header) => (
                        <th key={header.id} className="whitespace-nowrap px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      className={cn(
                        "cursor-pointer border-b border-border transition last:border-0 hover:bg-well/50",
                        selected.has(row.original.id) && "bg-accent/50",
                      )}
                      onClick={() => (window.location.href = `/leads/${row.original.id}`)}
                    >
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
              <div key={lead.id} className="relative">
                <input
                  type="checkbox"
                  aria-label={`Seleccionar ${lead.business_name}`}
                  checked={selected.has(lead.id)}
                  onChange={() => toggleOne(lead.id)}
                  className="absolute right-3 top-3 z-10 h-4 w-4 accent-[#D90000]"
                />
                <Link href={`/leads/${lead.id}`}>
                  <Card className="p-4">
                    <div className="flex items-start justify-between gap-2 pr-7">
                      <div className="min-w-0">
                        <div className="truncate font-semibold">{lead.business_name}</div>
                        <div className="mt-0.5 text-xs text-muted-foreground">{lead.city ?? "—"} · {lead.category ?? ""}</div>
                      </div>
                      <TemperatureChip temperature={lead.lead_temperature} />
                    </div>
                    <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
                      <div className="rounded-lg bg-well py-1.5">{lead.reviews_count}<span className="text-muted-foreground"> rev</span></div>
                      <div className="rounded-lg bg-well py-1.5">{lead.rating?.toFixed(1) ?? "—"} ★</div>
                      <div className="rounded-lg bg-well py-1.5">{lead.website_score?.toFixed(1) ?? "—"}<span className="text-muted-foreground"> web</span></div>
                      <div className="rounded-lg bg-well py-1.5 font-semibold">{lead.lead_score ?? "—"}<span className="text-muted-foreground"> lead</span></div>
                    </div>
                    {lead.email && <div className="mt-2 truncate text-xs text-muted-foreground">{lead.email}</div>}
                  </Card>
                </Link>
              </div>
            ))}
          </div>

          {/* Paginación */}
          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-xs text-muted-foreground">
              Página {page + 1} de {totalPages}
              {data ? ` · ${data.total} leads en total` : ""}
            </p>
            <div className="flex items-center gap-2">
              <button className="btn-outline !px-3 !py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-40" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
                Anterior
              </button>
              <button className="btn-outline !px-3 !py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-40" onClick={() => setPage((p) => (p + 1 < totalPages ? p + 1 : p))} disabled={page + 1 >= totalPages}>
                Siguiente
              </button>
              <select className="input !w-28 !py-1.5 text-xs" value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
                <option value={25}>25 / pág</option>
                <option value={50}>50 / pág</option>
                <option value={100}>100 / pág</option>
              </select>
            </div>
          </div>
        </>
      )}

      {/* ---- bulk bar flotante ---- */}
      {selected.size > 0 && (
        <div className="fixed inset-x-0 bottom-[max(env(safe-area-inset-bottom),3.25rem)] z-40 mx-auto w-[min(96vw,560px)] lg:bottom-4">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-popover px-4 py-3 shadow-lift">
            <div className="flex items-center gap-3">
              <span className="font-display text-lg font-extrabold tabular-nums">{selected.size}</span>
              <span className="text-xs text-muted-foreground">seleccionado{selected.size > 1 ? "s" : ""}</span>
              <button type="button" className="text-muted-foreground hover:text-foreground" aria-label="Limpiar selección" onClick={() => setSelected(new Set())}>
                <X size={15} />
              </button>
            </div>
            <div className="flex items-center gap-1.5">
              <BulkIcon icon={Download} label="CSV" busy={bulkBusy === "csv"} onClick={() => exportCsv([...selected])} />
              <BulkIcon icon={FileSpreadsheet} label="Sheets" busy={isSendingToSheets} onClick={() => handleSendToSheets([...selected])} title="Enviar selección a Sheets" />
              <BulkIcon icon={FileSignature} label="Propuestas" busy={bulkBusy === "proposals"} onClick={bulkProposals} title="Generar propuestas para revisión humana" />
              <BulkMenu
                icon={Tag}
                label="Tag"
                actions={[
                  { label: "Agregar tag…", onClick: () => {
                    const t = window.prompt("Tag a agregar (sin espacios al principio/fin):");
                    if (t?.trim()) bulkAction("add_tag", { tag: t }) as unknown as void;
                  }},
                  { label: "Quitar tag…", onClick: () => {
                    const t = window.prompt("Tag a quitar:");
                    if (t?.trim()) bulkAction("remove_tag", { tag: t }) as unknown as void;
                  }},
                ]}
              />
              <BulkMenu
                icon={UserRound}
                label="Asignar"
                actions={[
                  { label: "Asignar responsable…", onClick: () => {
                    const o = window.prompt("Responsable (nombre):");
                    if (o?.trim()) bulkAction("assign_owner", { owner: o }) as unknown as void;
                  }},
                  { label: "Quitar responsable", onClick: () => { bulkAction("clear_owner") as unknown as void; }},
                ]}
              />
              <BulkMenu
                icon={Archive}
                label="Estado"
                actions={[
                  ...LEAD_STATUSES.filter((s) => s !== "ARCHIVED").map((s) => ({
                    label: `Estado: ${s.replaceAll("_", " ")}`,
                    onClick: () => { bulkAction("set_status", { status: s }) as unknown as void; },
                  })),
                  { label: "Archivar", onClick: () => { bulkAction("archive") as unknown as void; } },
                  { label: "Desarchivar (vuelve a Nuevo)", onClick: () => { bulkAction("unarchive") as unknown as void; } },
                ]}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ========================================================== sub-components ===

function ViewToggle({ view, onChange }: { view: "list" | "map"; onChange: (v: "list" | "map") => void }) {
  return (
    <div className="flex rounded-md border border-border bg-card p-0.5" role="tablist" aria-label="Vista">
      {([["list", List, "Lista"], ["map", MapIcon, "Mapa"]] as const).map(([id, Icon, label]) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={view === id}
          onClick={() => onChange(id)}
          className={cn(
            "flex min-h-[36px] items-center gap-1.5 rounded px-3 text-xs font-semibold transition",
            view === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon size={14} /> {label}
        </button>
      ))}
    </div>
  );
}

function ColumnsDropdown({ visible, onToggle }: { visible: ColId[]; onToggle: (c: ColId) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="btn-outline !px-3" title="Elegir columnas visibles">
          <Columns3 size={15} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Columnas visibles</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {ALL_COLUMNS.filter((c) => c !== "sel").map((c) => (
          <DropdownMenuItem key={c} className="justify-between" onSelect={(e) => { e.preventDefault(); onToggle(c); }}>
            {COL_LABELS[c]}
            <input type="checkbox" readOnly checked={visible.includes(c)} className="h-3.5 w-3.5 accent-[#D90000]" />
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function HeaderCell({ colId, sort, order, onSort }: { colId: ColId; sort: string | undefined; order: string; onSort: (c: ColId) => void }) {
  const label = COL_LABELS[colId];
  if (!label) return null;
  const sortKey = SORTABLE[colId];
  if (!sortKey) return <span>{label}</span>;
  const active = sort === sortKey;
  return (
    <button type="button" onClick={() => onSort(colId)} className={cn("flex items-center gap-1 uppercase tracking-[0.12em] transition", active ? "text-foreground" : "hover:text-foreground")} title={`Ordenar por ${label}`}>
      {label}
      {active ? (order === "desc" ? <ArrowDownNarrowWide size={11} /> : <ArrowUpWideNarrow size={11} />) : <ArrowDownNarrowWide size={11} className="opacity-30" />}
    </button>
  );
}

function BulkIcon({ icon: Icon, label, busy, onClick, title }: { icon: typeof Download; label: string; busy?: boolean; onClick: () => void; title?: string }) {
  return (
    <button type="button" className="btn-ghost !min-h-[36px] flex-col !gap-0.5 !px-2 !py-1 text-[10px]" onClick={onClick} disabled={busy} title={title ?? label}>
      {busy ? <Loader2 size={15} className="animate-spin" /> : <Icon size={15} />}
      {label}
    </button>
  );
}

function BulkMenu({ icon: Icon, label, actions }: { icon: typeof Tag; label: string; actions: { label: string; onClick: () => void }[] }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="btn-ghost !min-h-[36px] flex-col !gap-0.5 !px-2 !py-1 text-[10px]" title={label}>
          <Icon size={15} />
          {label}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actions.map((a) => (
          <DropdownMenuItem key={a.label} onSelect={a.onClick}>{a.label}</DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function TriStateFilter({ label, value, onChange, trueLabel, falseLabel }: {
  label: string; value: boolean | undefined; onChange: (v: boolean | undefined) => void; trueLabel: string; falseLabel: string;
}) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-card p-0.5">
      <span className="pl-2 pr-1 text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <button className={cn("chip !px-2 !py-1 text-[11px]", value === undefined ? "bg-foreground text-background" : "text-muted-foreground")} onClick={() => onChange(undefined)}>todos</button>
      <button className={cn("chip !px-2 !py-1 text-[11px]", value === true ? "bg-foreground text-background" : "text-muted-foreground")} onClick={() => onChange(value === true ? undefined : true)}>{trueLabel}</button>
      <button className={cn("chip !px-2 !py-1 text-[11px]", value === false ? "bg-foreground text-background" : "text-muted-foreground")} onClick={() => onChange(value === false ? undefined : false)}>{falseLabel}</button>
    </div>
  );
}

function BusinessCell({ lead }: { lead: LeadSummary }) {
  return (
    <div className="min-w-0">
      <div className="max-w-[220px] truncate font-semibold text-foreground">{lead.business_name}</div>
      <div className="max-w-[220px] truncate text-[11px] text-muted-foreground">{lead.recommended_service ?? ""}</div>
    </div>
  );
}

function EmailCell({ value, confidence }: { value: string | null; confidence: string | null }) {
  if (!value)
    return <span className="chip bg-well text-muted-foreground" title="No encontramos un email público">sin email</span>;
  return (
    <div className="flex items-center gap-1.5">
      <span className="max-w-[150px] truncate text-xs" title={value}>{value}</span>
      <span
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full",
          confidence === "HIGH" ? "bg-emerald-500" : confidence === "MEDIUM" ? "bg-amber-500" : "bg-destructive",
        )}
        title={`Confianza ${confidence}`}
      />
    </div>
  );
}

function countPins(items: LeadSummary[]): number {
  return items.filter((l) => typeof l.latitude === "number" && typeof l.longitude === "number").length;
}
