"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, SlidersHorizontal, X } from "lucide-react";
import type { Temperature } from "@/lib/types";
import { cn } from "@/components/ui";

const TEMPERATURES: Temperature[] = ["HOT", "WARM", "COLD", "LOW"];

// Debe coincidir con LeadStatus (backend/app/core/enums.py).
const LEAD_STATUSES = ["NEW", "CONTACTED", "REPLIED", "OPTED_OUT", "DO_NOT_CONTACT", "ARCHIVED"];

/** Estado de filtros de la pantalla de leads. La lógica de consulta vive en la página. */
export interface LeadFilterValues {
  temperature?: string;
  hasEmail?: boolean;
  hasWebsite?: boolean;
  status: string;
  minScore: string;
}

interface LeadFiltersProps {
  values: LeadFilterValues;
  onTemperatureChange: (t: string | undefined) => void;
  onHasEmailChange: (v: boolean | undefined) => void;
  onHasWebsiteChange: (v: boolean | undefined) => void;
  onStatusChange: (s: string) => void;
  onMinScoreChange: (s: string) => void;
  onClear: () => void;
}

interface ActiveFilter {
  key: string;
  label: string;
  remove: () => void;
}

export function LeadFilters({
  values,
  onTemperatureChange,
  onHasEmailChange,
  onHasWebsiteChange,
  onStatusChange,
  onMinScoreChange,
  onClear,
}: LeadFiltersProps) {
  // En mobile el panel arranca colapsado; en lg+ siempre está visible.
  const [open, setOpen] = useState(false);

  const active: ActiveFilter[] = [];
  if (values.temperature)
    active.push({ key: "temp", label: `Temp: ${values.temperature}`, remove: () => onTemperatureChange(undefined) });
  if (values.hasEmail !== undefined)
    active.push({
      key: "email",
      label: values.hasEmail ? "Con email" : "Sin email",
      remove: () => onHasEmailChange(undefined),
    });
  if (values.hasWebsite !== undefined)
    active.push({
      key: "web",
      label: values.hasWebsite ? "Con web" : "Sin web",
      remove: () => onHasWebsiteChange(undefined),
    });
  if (values.minScore)
    active.push({ key: "score", label: `Lead ≥ ${values.minScore}`, remove: () => onMinScoreChange("") });
  if (values.status)
    active.push({
      key: "status",
      label: `Estado: ${values.status.replaceAll("_", " ")}`,
      remove: () => onStatusChange(""),
    });

  const count = active.length;

  return (
    <div className="space-y-3">
      {/* Accesos rápidos: temperatura (siempre visibles, son pocos) */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={cn("chip border", !values.temperature ? "border-ink text-ink" : "border-transparent bg-white text-taupe")}
          onClick={() => onTemperatureChange(undefined)}
        >
          Todos
        </button>
        {TEMPERATURES.map((t) => (
          <button
            key={t}
            type="button"
            className={cn(
              "chip border",
              values.temperature === t ? chipActive(t) : "border-transparent bg-white text-taupe"
            )}
            onClick={() => onTemperatureChange(values.temperature === t ? undefined : t)}
          >
            {t}
          </button>
        ))}

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="lead-filters-panel"
          className="lg:hidden ml-auto btn-outline !py-1.5 !px-3 text-xs"
        >
          <SlidersHorizontal size={14} />
          Filtros
          {count > 0 && (
            <span className="rounded-full bg-ink text-white text-[10px] px-1.5 py-px tabular-nums">{count}</span>
          )}
          <ChevronDown size={14} className={cn("transition-transform", open && "rotate-180")} />
        </button>
      </div>

      {/* Chips de filtros activos, cada uno se puede quitar */}
      {count > 0 && (
        <div className="flex flex-wrap items-center gap-2" aria-label="Filtros activos">
          <span className="text-[10px] uppercase tracking-wide text-taupe">Activos:</span>
          {active.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={f.remove}
              className="chip border border-sandline bg-white text-ink gap-1 hover:border-ink"
              title="Quitar filtro"
            >
              {f.label}
              <X size={12} className="text-taupe" />
            </button>
          ))}
          <button
            type="button"
            className="text-xs text-taupe hover:text-ink underline underline-offset-2"
            onClick={onClear}
          >
            Limpiar todo
          </button>
        </div>
      )}

      {/* Panel: colapsable en mobile, siempre visible en lg+ */}
      <div
        id="lead-filters-panel"
        className={cn("grid gap-3 lg:grid lg:grid-cols-[auto_auto_1fr] lg:items-center", open ? "grid" : "hidden")}
      >
        <FilterGroup label="Email">
          <TriState
            value={values.hasEmail}
            onChange={onHasEmailChange}
            trueLabel="con email"
            falseLabel="sin email"
          />
        </FilterGroup>

        <FilterGroup label="Web">
          <TriState value={values.hasWebsite} onChange={onHasWebsiteChange} trueLabel="con web" falseLabel="sin web" />
        </FilterGroup>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 lg:justify-end">
          <select
            className="input !py-1.5 text-xs"
            value={values.minScore}
            onChange={(e) => onMinScoreChange(e.target.value)}
            aria-label="Lead score mínimo"
          >
            <option value="">Lead score: cualquiera</option>
            <option value="80">Lead ≥ 80</option>
            <option value="70">Lead ≥ 70</option>
            <option value="60">Lead ≥ 60</option>
          </select>

          <select
            className="input !py-1.5 text-xs"
            value={values.status}
            onChange={(e) => onStatusChange(e.target.value)}
            aria-label="Estado del lead"
          >
            <option value="">Estado: cualquiera</option>
            {LEAD_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] uppercase tracking-wide text-taupe w-10 shrink-0">{label}</span>
      {children}
    </div>
  );
}

function TriState({
  value,
  onChange,
  trueLabel,
  falseLabel,
}: {
  value: boolean | undefined;
  onChange: (v: boolean | undefined) => void;
  trueLabel: string;
  falseLabel: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 bg-white border border-sandline rounded-full p-0.5">
      <button
        type="button"
        className={cn("chip !py-1 !px-2 text-[11px]", value === undefined ? "bg-ink text-white" : "text-taupe")}
        onClick={() => onChange(undefined)}
      >
        todos
      </button>
      <button
        type="button"
        className={cn("chip !py-1 !px-2 text-[11px]", value === true ? "bg-ink text-white" : "text-taupe")}
        onClick={() => onChange(value === true ? undefined : true)}
      >
        {trueLabel}
      </button>
      <button
        type="button"
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
