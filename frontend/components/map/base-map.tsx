"use client";

/**
 * Envoltorio Leaflet imperativo (sin react-leaflet): control total del ciclo de
 * vida y cero fricción con React 19 / Next 15. El CSS y el JS de Leaflet se
 * cargan acá; los mapas nunca se renderizan en SSR.
 *
 * Tiles: OSM estándar en claro · CartoDB Dark Matter en oscuro (ambas gratis,
 * con atribución visible — obligatoria por la licencia ODbL).
 */
import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useTheme } from "next-themes";
import type * as LeafletNS from "leaflet";

export const TILES = {
  light: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
} as const;

export interface BaseMapProps {
  center: [number, number];
  zoom?: number;
  className?: string;
  style?: CSSProperties;
  /** Called once when the map instance exists, and again if re-created. */
  onReady?: (map: LeafletNS.Map, L: typeof LeafletNS) => void;
  /** Edit tools draw inside an overlay with brand styles. */
  showZoomControl?: boolean;
}

export default function BaseMap({
  center,
  zoom = 12,
  className,
  style,
  onReady,
  showZoomControl = true,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletNS.Map | null>(null);
  const tilesRef = useRef<LeafletNS.TileLayer | null>(null);
  const leafletRef = useRef<typeof LeafletNS | null>(null);
  const [ready, setReady] = useState(false);
  const { resolvedTheme } = useTheme();
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;

    void (async () => {
      // Leaflet needs `window`: dynamic import keeps this component SSR-safe.
      await import("leaflet/dist/leaflet.css");
      const L = await import("leaflet");
      if (cancelled || !containerRef.current || mapRef.current) return;

      const map = L.map(containerRef.current, {
        center,
        zoom,
        zoomControl: showZoomControl,
        attributionControl: true,
      });
      mapRef.current = map;
      leafletRef.current = L;
      tilesRef.current = L.tileLayer(TILES.light.url, {
        attribution: TILES.light.attribution,
        maxZoom: 19,
      });
      setReady(true);
      onReadyRef.current?.(map, L);
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      tilesRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Theme-aware tile swap.
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!map || !L || !ready) return;
    const theme = resolvedTheme === "dark" ? "dark" : "light";
    const spec = TILES[theme];
    if (tilesRef.current) tilesRef.current.remove();
    tilesRef.current = L.tileLayer(spec.url, { attribution: spec.attribution, maxZoom: 19 });
    tilesRef.current.addTo(map);
  }, [resolvedTheme, ready]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: "100%", height: "100%", ...style }}
      role="application"
      aria-label="Mapa"
    />
  );
}
