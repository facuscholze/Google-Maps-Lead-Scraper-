"use client";

/**
 * Mapa con dibujo de área para búsquedas por grilla (Fase 3).
 *
 * Usa los handlers de leaflet-draw *sin* su toolbar default (en inglés y sin
 * estilo de marca): herramientas propias en es-AR — Rectángulo / Círculo /
 * Polígono / Borrar. El formato que emite matchea el schema `GeoArea` del
 * backend (app/schemas/api.py).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Circle as CircleIcon, Pentagon, Square, Trash2 } from "lucide-react";
import BaseMap from "./base-map";
import { cn } from "@/lib/utils";
import type * as LeafletNS from "leaflet";

export type GeoSpec =
  | { rect: { sw: [number, number]; ne: [number, number] } }
  | { circle: { center: [number, number]; radius_km: number } }
  | { polygon: { points: [number, number][] } };

type Tool = "rect" | "circle" | "polygon";

const SHAPE_STYLE = {
  color: "#D90000",
  weight: 2,
  fillColor: "#D90000",
  fillOpacity: 0.08,
};

const HINTS: Record<Tool, string> = {
  rect: "Tocá una esquina y arrastrá hasta la opuesta.",
  circle: "Tocá el centro y arrastrá hasta el borde del área.",
  polygon: "Tocá cada vértice; doble click (o click en el primero) para cerrar.",
};

interface AreaEditorProps {
  center: [number, number];
  zoom?: number;
  className?: string;
  onChange: (geo: GeoSpec | null) => void;
}

function round(n: number, digits = 6): number {
  return Number(n.toFixed(digits));
}

export default function AreaEditor({ center, zoom = 13, className, onChange }: AreaEditorProps) {
  const [map, setMap] = useState<LeafletNS.Map | null>(null);
  const [L, setL] = useState<typeof LeafletNS | null>(null);
  const [tool, setTool] = useState<Tool | null>(null);
  const [hasArea, setHasArea] = useState(false);
  const drawnRef = useRef<LeafletNS.FeatureGroup | null>(null);
  const handlerRef = useRef<LeafletNS.Draw.Feature | null>(null);
  const leafletRef = useRef<typeof LeafletNS | null>(null);
  leafletRef.current = L;

  const onReady = useCallback((m: LeafletNS.Map, lib: typeof LeafletNS) => {
    setMap(m);
    setL(lib);
  }, []);

  // Load the draw plugin + CSS once the map exists.
  useEffect(() => {
    if (!map || !L) return;
    let cancelled = false;
    void (async () => {
      await import("leaflet-draw/dist/leaflet.draw.css");
      await import("leaflet-draw");
      if (cancelled) return;
      const group = new L.FeatureGroup();
      group.addTo(map);
      drawnRef.current = group;
      map.on((L as unknown as { Draw: { Event: { CREATED: string } } }).Draw.Event.CREATED, (e: unknown) => {
        const event = e as { layer: LeafletNS.Layer };
        const g = drawnRef.current;
        if (!g || !leafletRef.current) return;
        g.clearLayers();
        g.addLayer(event.layer);
        setHasArea(true);
        setTool(null);
        onChange(layerToGeo(event.layer, leafletRef.current));
      });
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, L]);

  // Activate the selected draw handler.
  useEffect(() => {
    if (!map || !L || !tool) return;
    const Draw = (L as unknown as { Draw: typeof LeafletNS.Draw }).Draw;
    const drawMap = map as unknown as LeafletNS.DrawMap;
    let handler: LeafletNS.Draw.Feature;
    if (tool === "rect") {
      handler = new Draw.Rectangle(drawMap, { shapeOptions: SHAPE_STYLE, showArea: true, metric: true });
    } else if (tool === "circle") {
      handler = new Draw.Circle(drawMap, { shapeOptions: SHAPE_STYLE, showRadius: true, metric: true });
    } else {
      handler = new Draw.Polygon(drawMap, {
        shapeOptions: SHAPE_STYLE,
        allowIntersection: false,
        showArea: true,
        metric: true,
      });
    }
    handler.enable();
    handlerRef.current = handler;
    return () => {
      handlerRef.current = null;
      handler.disable();
    };
  }, [map, L, tool]);

  function clearArea() {
    drawnRef.current?.clearLayers();
    setHasArea(false);
    onChange(null);
  }

  const tools: { id: Tool; label: string; icon: typeof Square }[] = [
    { id: "rect", label: "Rectángulo", icon: Square },
    { id: "circle", label: "Círculo", icon: CircleIcon },
    { id: "polygon", label: "Polígono", icon: Pentagon },
  ];

  return (
    <div className={cn("relative overflow-hidden rounded-xl border border-border", className)}>
      <BaseMap center={center} zoom={zoom} onReady={onReady} />
      {/* Toolbar propia (la default de leaflet-draw no va con la marca) */}
      <div className="absolute left-3 top-3 z-[500] flex flex-col gap-1.5">
        {tools.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTool((t) => (t === id ? null : id))}
            aria-pressed={tool === id}
            className={cn(
              "flex min-h-[40px] items-center gap-2 rounded-md border px-3 text-xs font-semibold shadow-card backdrop-blur transition",
              tool === id
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card/95 text-foreground hover:bg-secondary",
            )}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
        <button
          type="button"
          onClick={clearArea}
          disabled={!hasArea}
          className="flex min-h-[40px] items-center gap-2 rounded-md border border-border bg-card/95 px-3 text-xs font-semibold text-foreground shadow-card backdrop-blur transition hover:bg-secondary disabled:opacity-40"
        >
          <Trash2 size={15} /> Borrar área
        </button>
      </div>
      {tool && (
        <div className="absolute inset-x-3 bottom-3 z-[500] rounded-md border border-border bg-card/95 px-3 py-2 text-xs text-muted-foreground shadow-card backdrop-blur">
          {HINTS[tool]}
        </div>
      )}
      {!tool && !hasArea && (
        <div className="pointer-events-none absolute inset-x-3 bottom-3 z-[500] text-center">
          <span className="rounded-md bg-card/90 px-3 py-1.5 text-xs text-muted-foreground backdrop-blur">
            Elegí una herramienta y dibujá el área a barrender
          </span>
        </div>
      )}
    </div>
  );
}

function layerToGeo(layer: LeafletNS.Layer, L: typeof LeafletNS): GeoSpec | null {
  // Rectangle → rect (backend cells_for_bounds expects sw/ne [lat,lng])
  if (layer instanceof L.Rectangle) {
    const b = layer.getBounds();
    return {
      rect: {
        sw: [round(b.getSouth()), round(b.getWest())],
        ne: [round(b.getNorth()), round(b.getEast())],
      },
    };
  }
  if (layer instanceof L.Circle) {
    const c = layer.getLatLng();
    return {
      circle: {
        center: [round(c.lat), round(c.lng)],
        radius_km: round(layer.getRadius() / 1000, 3),
      },
    };
  }
  if (layer instanceof L.Polygon) {
    const rings = layer.getLatLngs()[0] as LeafletNS.LatLng[];
    const points = rings.map((p) => [round(p.lat), round(p.lng)] as [number, number]);
    if (points.length < 3) return null;
    return { polygon: { points } };
  }
  return null;
}
