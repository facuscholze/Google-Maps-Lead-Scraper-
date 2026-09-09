"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Info, Search as SearchIcon, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, ErrorNote } from "@/components/ui";

interface Preview {
  query: string;
  max_results: number;
  min_reviews: number;
  max_reviews?: number | null;
  min_rating: number;
  estimated_api_calls: number;
  disclaimer: string;
}

export default function NewSearchPage() {
  const router = useRouter();
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [maxResults, setMaxResults] = useState(100);
  const [minReviews, setMinReviews] = useState(50);
  const [maxReviews, setMaxReviews] = useState<number | null>(500);
  const [minRating, setMinRating] = useState(4.0);
  const [onlyWebsite, setOnlyWebsite] = useState(true);
  const [onlyPhone, setOnlyPhone] = useState(false);
  const [tryEmail, setTryEmail] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | undefined>();

  async function showPreview() {
    setError(undefined);
    try {
      const res = await api.post<Preview>("/api/searches/preview", {
        category, location: location || null, max_results: maxResults,
        min_reviews: minReviews, max_reviews: maxReviews,
        min_rating: minRating, only_with_website: onlyWebsite,
        only_with_phone: onlyPhone, try_find_email: tryEmail,
      });
      setPreview(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    }
  }

  async function launchSearch() {
    if (!category.trim()) return setError("Ingresá un rubro, por ejemplo «Clínicas estéticas».");
    setBusy(true);
    setError(undefined);
    try {
      const search = await api.post<{ id: number }>("/api/searches", {
        category: category.trim(), location: location.trim() || null,
        max_results: maxResults, min_reviews: minReviews, max_reviews: maxReviews,
        min_rating: minRating, only_with_website: onlyWebsite,
        only_with_phone: onlyPhone, try_find_email: tryEmail,
      });
      await api.post(`/api/searches/${search.id}/run`);
      setRunning(true);
      router.push(`/searches/${search.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar la búsqueda");
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold">Nueva búsqueda</h1>
        <p className="text-sm text-taupe mt-1">Definí qué negocios querés encontrar y con qué calidad.</p>
      </div>

      <Card className="space-y-5">
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="sm:col-span-1">
            <label className="label">Rubro</label>
            <input className="input" placeholder="Ej: Clínicas estéticas" value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>
          <div>
            <label className="label">Ubicación</label>
            <input className="input" placeholder="Ej: Montevideo, Uruguay" value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Máximo</label>
            <select className="input" value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))}>
              {[25, 50, 100, 250, 500].map((v) => <option key={v} value={v}>{v} negocios</option>)}
            </select>
          </div>
          <div>
            <label className="label">Reseñas mín.</label>
            <select className="input" value={minReviews} onChange={(e) => setMinReviews(Number(e.target.value))}>
              {[0, 25, 50, 100, 250].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Reseñas máx.</label>
            <select className="input" value={maxReviews ?? ""} onChange={(e) => setMaxReviews(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Sin límite</option>
              {[100, 250, 500, 1000].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Rating mín.</label>
            <select className="input" value={minRating} onChange={(e) => setMinRating(Number(e.target.value))}>
              {[3.0, 3.5, 4.0, 4.5].map((v) => <option key={v} value={v}>{v.toFixed(1)} ★</option>)}
            </select>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-1">
          {[
            { label: "Solo negocios con website", value: onlyWebsite, set: setOnlyWebsite },
            { label: "Solo negocios con teléfono", value: onlyPhone, set: setOnlyPhone },
            { label: "Intentar encontrar email", value: tryEmail, set: setTryEmail },
          ].map((opt) => (
            <label key={opt.label} className="flex items-center gap-2.5 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={opt.value}
                onChange={(e) => opt.set(e.target.checked)}
                className="h-4 w-4 accent-[#B08D3E]"
              />
              {opt.label}
            </label>
          ))}
        </div>

        <ErrorNote message={error} />

        <div className="flex flex-col sm:flex-row gap-3">
          <Button variant="outline" onClick={showPreview} className="flex-1">
            <SearchIcon size={16} /> Ver resumen de búsqueda
          </Button>
          <Button onClick={launchSearch} disabled={busy || running} className="flex-1 !bg-gold hover:!bg-[#997a34]">
            <Sparkles size={16} /> {busy ? "Iniciando…" : "BUSCAR LEADS"}
          </Button>
        </div>
      </Card>

      {preview && (
        <Card className="border-gold/30">
          <div className="font-display text-xl font-semibold">BUSCAR</div>
          <div className="text-lg text-ink mt-1">{preview.query}</div>
          <div className="h-px bg-sandline my-4" />
          <div className="font-display text-xl font-semibold">FILTROS</div>
          <div className="text-sm text-ink/80 mt-2 space-y-0.5">
            <div>{preview.min_reviews}–{preview.max_reviews ?? "∞"} reseñas</div>
            <div>Rating ≥ {preview.min_rating.toFixed(1)}</div>
            <div>Máximo {preview.max_results} negocios</div>
            {onlyWebsite && <div>Solo con website</div>}
            {onlyPhone && <div>Solo con teléfono</div>}
            {tryEmail && <div>Email público: intentar descubrir</div>}
          </div>
          <div className="mt-4 text-xs text-taupe flex gap-2 bg-sand rounded-lg px-3 py-2.5 items-start">
            <Info size={14} className="mt-0.5 shrink-0 text-gold" />
            <span>Esta búsqueda puede generar múltiples solicitudes a la API de Google Places. El uso de la API no es necesariamente gratuito. (~{preview.estimated_api_calls} llamadas estimadas).</span>
          </div>
        </Card>
      )}
    </div>
  );
}
