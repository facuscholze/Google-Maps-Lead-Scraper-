"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Calculator, RotateCcw, Save, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button, Card, ErrorNote, Spinner, cn } from "@/components/ui";

interface CategoryMeta { key: string; label: string; description: string }
interface ScoringConfig {
  id: number | null;
  weights: Record<string, number>;
  hot_min: number;
  warm_min: number;
  cold_min: number;
  is_default: boolean;
  updated_at?: string | null;
}

const CATEGORY_ORDER = [
  "reputation", "reviews", "website_presence", "website_quality",
  "opportunities", "phone", "email",
] as const;

export default function ScoringSettingsPage() {
  const queryClient = useQueryClient();
  const { data: categories } = useQuery<CategoryMeta[]>({
    queryKey: ["scoring-categories"],
    queryFn: async () => (await api.get<{ categories: CategoryMeta[] }>("/api/scoring-config/categories")).categories,
    staleTime: Infinity,
  });
  const configQuery = useQuery<ScoringConfig>({
    queryKey: ["scoring-config"],
    queryFn: () => api.get<ScoringConfig>("/api/scoring-config"),
  });

  const [weights, setWeights] = useState<Record<string, number>>({});
  const [hot, setHot] = useState(80);
  const [warm, setWarm] = useState(60);
  const [cold, setCold] = useState(40);
  const [saving, setSaving] = useState(false);
  const [rescoring, setRescoring] = useState<"all" | null>(null);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (!configQuery.data) return;
    setWeights(configQuery.data.weights);
    setHot(configQuery.data.hot_min);
    setWarm(configQuery.data.warm_min);
    setCold(configQuery.data.cold_min);
  }, [configQuery.data]);

  const thresholdsError = !(hot > warm && warm > cold)
    ? "Los umbrales deben ser estrictamente HOT > WARM > COLD."
    : undefined;

  async function save() {
    if (thresholdsError) return;
    setSaving(true);
    setError(undefined);
    try {
      const saved = await api.put<ScoringConfig>("/api/scoring-config", {
        weights,
        hot_min: hot,
        warm_min: warm,
        cold_min: cold,
      });
      queryClient.setQueryData(["scoring-config"], saved);
      toast.success("Configuración guardada", {
        description: "Los scores existentes no cambian hasta que apliques el rescore (acción explícita).",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuración");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      await api.del("/api/scoring-config");
      await configQuery.refetch();
      toast.success("Configuración restablecida a los valores por defecto");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo restablecer");
    } finally {
      setSaving(false);
    }
  }

  async function rescoreAll() {
    if (!window.confirm(
      "Recalcular el score de TODOS los leads con la configuración vigente.\n\n" +
      "El cálculo es determinista y local (usa los datos ya guardados; no llama a Google Places ni cobra nada). ¿Continuar?"
    )) return;
    setRescoring("all");
    try {
      const res = await api.post<{ rescored: number }>("/api/scoring-config/rescore", {});
      toast.success(`${res.rescored} leads re-puntuados con la configuración vigente`);
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo aplicar el rescore");
    } finally {
      setRescoring(null);
    }
  }

  if (configQuery.isLoading) return <Spinner label="Cargando configuración de scoring…" />;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/settings" className="text-sm text-gold inline-flex items-center gap-1 underline underline-offset-2">
          <ArrowLeft size={14} /> Volver a ajustes
        </Link>
        <h1 className="font-display text-3xl font-semibold mt-2">Scoring de leads</h1>
        <p className="text-sm text-taupe mt-1">
          El score es determinista y explicable: cada lead muestra exactamente cómo se calculó. Acá ajustás
          cuánto pesa cada señal y desde qué puntaje clasifica cada temperatura.
        </p>
      </div>

      <ErrorNote message={error} />

      <Card>
        <h2 className="font-display text-lg font-semibold mb-1 flex items-center gap-2">
          <SlidersHorizontal size={18} className="text-gold" /> Peso de cada señal
        </h2>
        <p className="text-xs text-taupe mb-5">
          Multiplicador sobre los puntos base (1.0 = default). Poné 0 si una señal no te interesa, o subilo a 3 si
          es crítica para vos. Nada cambia sin guardar.
        </p>
        <div className="space-y-4">
          {CATEGORY_ORDER.map((key) => {
            const meta = categories?.find((c) => c.key === key);
            const value = weights[key] ?? 1;
            return (
              <div key={key}>
                <div className="flex items-center justify-between text-sm">
                  <div className="font-medium">{meta?.label ?? key}</div>
                  <div className="flex items-center gap-2">
                    <span className={cn("tabular-nums font-bold text-sm", value !== 1 ? "text-gold" : "text-ink")}>
                      ×{value.toFixed(2)}
                    </span>
                    {value !== 1 && (
                      <button type="button" className="text-[11px] text-taupe underline" onClick={() => setWeights((p) => ({ ...p, [key]: 1 }))}>
                        default
                      </button>
                    )}
                  </div>
                </div>
                {meta?.description && <div className="text-[11px] text-taupe">{meta.description}</div>}
                <input
                  type="range"
                  min={0}
                  max={3}
                  step={0.25}
                  value={value}
                  onChange={(e) => setWeights((p) => ({ ...p, [key]: Number(e.target.value) }))}
                  className="mt-1.5 w-full accent-[#B08D3E]"
                  aria-label={`Peso de ${meta?.label ?? key}`}
                />
              </div>
            );
          })}
        </div>
      </Card>

      <Card>
        <h2 className="font-display text-lg font-semibold mb-1 flex items-center gap-2">
          <Calculator size={18} className="text-gold" /> Umbrales de temperatura
        </h2>
        <p className="text-xs text-taupe mb-4">El lead score va de 0 a 100. ¿Desde qué valor empieza cada temperatura?</p>
        {thresholdsError && <p className="mb-3 text-xs text-[#C5221F]">{thresholdsError}</p>}
        <div className="grid grid-cols-3 gap-3">
          {([
            ["HOT", hot, setHot],
            ["WARM", warm, setWarm],
            ["COLD", cold, setCold],
          ] as const).map(([label, value, setter]) => (
            <label key={label} className="text-xs font-semibold text-taupe">
              {label} ≥ {value}
              <input
                type="range"
                min={1}
                max={99}
                value={value}
                onChange={(e) => setter(Number(e.target.value))}
                className="mt-1.5 w-full accent-[#B08D3E]"
                aria-label={`Umbral ${label}`}
              />
            </label>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-taupe">LOW: debajo de COLD.</p>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="gold" onClick={save} disabled={saving || !!thresholdsError}>
          <Save size={15} /> {saving ? "Guardando…" : "Guardar configuración"}
        </Button>
        {configQuery.data && !configQuery.data.is_default && (
          <Button variant="outline" onClick={reset} disabled={saving}>
            <RotateCcw size={15} /> Restablecer defaults
          </Button>
        )}
      </div>

      <Card className="border-gold/40 bg-sand/40">
        <h2 className="font-display text-lg font-semibold">Aplicar a leads existentes</h2>
        <p className="text-sm text-taupe mt-1 leading-relaxed">
          Guardar la configuración <b>sólo la guarda</b> — ningún score cambia todavía. Cuando quieras ver el efecto,
          ejecutá el rescore global: recomputa el score de cada lead con los datos ya guardados (determinista,
          sin llamadas a Google Places). También podés re-puntuar individuales en el detalle de cada lead.
        </p>
        <div className="mt-4">
          <Button variant="gold" onClick={rescoreAll} disabled={rescoring !== null}>
            {rescoring ? "Re-puntuando…" : "Re-puntuar todos los leads"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
