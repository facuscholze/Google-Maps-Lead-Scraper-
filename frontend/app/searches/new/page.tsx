"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CircleDollarSign,
  Info,
  Map as MapIcon,
  Search as SearchIcon,
  Sparkles,
  Type,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button, Card, ErrorNote } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { GeoSpec } from "@/components/map/area-editor";
import type { components } from "@/lib/api-types";

// El editor de área toca `window` (Leaflet): jamás en SSR.
const AreaEditor = dynamic(() => import("@/components/map/area-editor"), {
  ssr: false,
  loading: () => (
    <div className="grid h-[420px] w-full place-items-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
      Cargando mapa…
    </div>
  ),
});

type SearchPreview = components["schemas"]["SearchPreview"];

const DEFAULT_CENTER: [number, number] = [-34.9011, -56.1645]; // Montevideo

export default function NewSearchPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"text" | "map">("map");
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [geo, setGeo] = useState<GeoSpec | null>(null);
  const [maxResults, setMaxResults] = useState(100);
  const [minReviews, setMinReviews] = useState(50);
  const [maxReviews, setMaxReviews] = useState<number | null>(500);
  const [minRating, setMinRating] = useState(4.0);
  const [onlyWebsite, setOnlyWebsite] = useState(true);
  const [onlyPhone, setOnlyPhone] = useState(false);
  const [tryEmail, setTryEmail] = useState(true);
  const [budgetCap, setBudgetCap] = useState<string>("");
  const [preview, setPreview] = useState<SearchPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const budget = useMemo(() => {
    const v = Number(budgetCap);
    return Number.isFinite(v) && v > 0 ? v : undefined;
  }, [budgetCap]);

  function buildPayload() {
    return {
      category: category.trim(),
      location: mode === "text" ? location.trim() || null : null,
      geo: mode === "map" ? geo : null,
      budget_cap_usd: budget ?? null,
      max_results: maxResults,
      min_reviews: minReviews,
      max_reviews: maxReviews,
      min_rating: minRating,
      only_with_website: onlyWebsite,
      only_with_phone: onlyPhone,
      try_find_email: tryEmail,
    };
  }

  function validate(): string | null {
    if (!category.trim()) return "Ingresá un rubro, por ejemplo «Clínicas estéticas».";
    if (mode === "map" && !geo) return "Dibujá un área en el mapa (rectángulo, círculo o polígono).";
    if (mode === "text" && !location.trim())
      return "Ingresá una ubicación, por ejemplo «Montevideo, Uruguay».";
    return null;
  }

  async function showPreview() {
    const msg = validate();
    if (msg) return setError(msg);
    setError(undefined);
    try {
      const res = await api.post<SearchPreview>("/api/searches/preview", buildPayload());
      setPreview(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al calcular el resumen");
    }
  }

  async function launchSearch() {
    const msg = validate();
    if (msg) return setError(msg);
    setBusy(true);
    setError(undefined);
    try {
      const search = await api.post<{ id: number }>("/api/searches", buildPayload());
      await api.post(`/api/searches/${search.id}/run`);
      toast.success("Búsqueda iniciada", {
        description: "Podés seguir el barrido en vivo o volver después.",
      });
      router.push(`/searches/${search.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar la búsqueda");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold">Nueva búsqueda</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Definí qué negocios querés encontrar: por texto o dibujando un área en el mapa.
        </p>
      </div>

      {/* Modo */}
      <div className="grid grid-cols-2 gap-2 sm:max-w-md">
        {(
          [
            { id: "map", label: "Por mapa", icon: MapIcon, hint: "Área dibujada → grilla" },
            { id: "text", label: "Por texto", icon: Type, hint: "Ciudad + rubro" },
          ] as const
        ).map(({ id, label, icon: Icon, hint }) => (
          <button
            key={id}
            type="button"
            onClick={() => setMode(id)}
            aria-pressed={mode === id}
            className={cn(
              "rounded-xl border p-3 text-left transition",
              mode === id
                ? "border-primary bg-accent text-foreground"
                : "border-border bg-card text-muted-foreground hover:bg-secondary",
            )}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Icon size={16} className={mode === id ? "text-primary" : ""} /> {label}
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">{hint}</div>
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_minmax(320px,380px)]">
        <div className="space-y-6">
          <Card className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-1">
                <label className="label" htmlFor="category">Rubro</label>
                <input
                  id="category"
                  className="input"
                  placeholder="Ej: Clínicas estéticas"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                />
              </div>
              {mode === "text" && (
                <div>
                  <label className="label" htmlFor="location">Ubicación</label>
                  <input
                    id="location"
                    className="input"
                    placeholder="Ej: Montevideo, Uruguay"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div>
                <label className="label" htmlFor="max-results">Máximo</label>
                <select
                  id="max-results"
                  className="input"
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                >
                  {[25, 50, 100, 250, 500].map((v) => (
                    <option key={v} value={v}>{v} negocios</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="min-reviews">Reseñas mín.</label>
                <select
                  id="min-reviews"
                  className="input"
                  value={minReviews}
                  onChange={(e) => setMinReviews(Number(e.target.value))}
                >
                  {[0, 25, 50, 100, 250].map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="max-reviews">Reseñas máx.</label>
                <select
                  id="max-reviews"
                  className="input"
                  value={maxReviews ?? ""}
                  onChange={(e) => setMaxReviews(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Sin límite</option>
                  {[100, 250, 500, 1000].map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="min-rating">Rating mín.</label>
                <select
                  id="min-rating"
                  className="input"
                  value={minRating}
                  onChange={(e) => setMinRating(Number(e.target.value))}
                >
                  {[3.0, 3.5, 4.0, 4.5].map((v) => (
                    <option key={v} value={v}>{v.toFixed(1)} ★</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-3 pt-1 sm:flex-row">
              {([
                { label: "Solo negocios con website", value: onlyWebsite, set: setOnlyWebsite },
                { label: "Solo negocios con teléfono", value: onlyPhone, set: setOnlyPhone },
                { label: "Intentar encontrar email", value: tryEmail, set: setTryEmail },
              ] as const).map((opt) => (
                <label key={opt.label} className="flex cursor-pointer select-none items-center gap-2.5 text-sm">
                  <input
                    type="checkbox"
                    checked={opt.value}
                    onChange={(e) => opt.set(e.target.checked)}
                    className="h-4 w-4 accent-[#D90000]"
                  />
                  {opt.label}
                </label>
              ))}
            </div>

            <div className="grid gap-2 sm:max-w-xs">
              <label className="label" htmlFor="budget">
                Tope de presupuesto <span className="normal-case tracking-normal">(opcional)</span>
              </label>
              <div className="relative">
                <CircleDollarSign
                  size={15}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  id="budget"
                  className="input pl-9"
                  inputMode="decimal"
                  placeholder="Ej: 2.50 USD — frena el barrido al llegar"
                  value={budgetCap}
                  onChange={(e) => setBudgetCap(e.target.value.replace(",", "."))}
                />
              </div>
            </div>

            <ErrorNote message={error} />

            <div className="flex flex-col gap-3 sm:flex-row">
              <Button variant="outline" onClick={showPreview} className="flex-1">
                <SearchIcon size={16} /> Ver resumen de búsqueda
              </Button>
              <Button onClick={launchSearch} disabled={busy} className="flex-1">
                <Sparkles size={16} /> {busy ? "Iniciando…" : "BUSCAR LEADS"}
              </Button>
            </div>
          </Card>
        </div>

        {/* Columna derecha: mapa (modo mapa) + preview */}
        <div className="space-y-6">
          {mode === "map" && (
            <AreaEditor
              center={DEFAULT_CENTER}
              className="h-[420px] w-full"
              onChange={(g) => {
                setGeo(g);
                setPreview(null);
              }}
            />
          )}

          {preview && (
            <Card className="border-primary/40">
              <div className="flex items-center justify-between gap-2">
                <div className="font-display text-lg font-semibold">
                  {preview.mode === "grid" ? "Barrido por grilla" : "Búsqueda por texto"}
                </div>
                <span className="chip bg-accent text-accent-foreground">
                  {preview.mode === "grid" ? `${preview.grid_cells} celdas` : "1 consulta"}
                </span>
              </div>
              <div className="mt-1 truncate text-sm text-muted-foreground">{preview.query}</div>
              <div className="my-3 h-px bg-border" />
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Resultados máx.</dt>
                <dd className="text-right font-semibold tabular-nums">{preview.max_results}</dd>
                <dt className="text-muted-foreground">Llamadas API estimadas</dt>
                <dd className="text-right font-semibold tabular-nums">
                  {preview.estimated_api_calls === preview.estimated_api_calls_max
                    ? preview.estimated_api_calls
                    : `${preview.estimated_api_calls}–${preview.estimated_api_calls_max}`}
                </dd>
                <dt className="text-muted-foreground">Costo estimado</dt>
                <dd className="text-right font-semibold tabular-nums">
                  {fmtUsd(preview.estimated_cost_usd)}
                  {preview.estimated_cost_max_usd > preview.estimated_cost_usd &&
                    `–${fmtUsd(preview.estimated_cost_max_usd)}`}
                </dd>
                {preview.budget_cap_usd != null && (
                  <>
                    <dt className="text-muted-foreground">Tope de presupuesto</dt>
                    <dd className="text-right font-semibold tabular-nums">
                      {fmtUsd(preview.budget_cap_usd)}
                    </dd>
                  </>
                )}
              </dl>

              {(preview.warnings ?? []).length > 0 && (
                <div className="mt-4 space-y-2">
                  {(preview.warnings ?? []).map((w, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
                    >
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4 flex items-start gap-2 rounded-lg bg-well px-3 py-2.5 text-xs text-muted-foreground">
                <Info size={14} className="mt-0.5 shrink-0 text-primary" />
                <span>{preview.disclaimer}</span>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function fmtUsd(v: number): string {
  if (v < 0.01) return "<US$ 0.01";
  return `US$ ${v.toFixed(v < 1 ? 3 : 2)}`;
}
