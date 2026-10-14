"use client"

/**
 * Pines de leads sobre Leaflet con clustering (divIcons de marca, nada de PNGs
 * de Leaflet rotos por bundler). Color por temperatura; popup con nombre,
 * rating y link al detalle.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import BaseMap from "./base-map";
import type * as LeafletNS from "leaflet";

export interface PinLead {
  id: number;
  business_name: string;
  latitude?: number | null;
  longitude?: number | null;
  rating?: number | null;
  lead_temperature?: string | null;
  category?: string | null;
}

const TEMP_COLORS: Record<string, string> = {
  HOT: "#D90000",
  WARM: "#F59E0B",
  COLD: "#38BDF8",
  LOW: "#9CA3AF",
};

interface MarkerClusterGroup extends LeafletNS.FeatureGroup {
  addLayers(layers: LeafletNS.Layer[]): this;
  clearLayers(): this;
}

interface LeadMapProps {
  leads: PinLead[];
  className?: string;
}

export default function LeadMap({ leads, className }: LeadMapProps) {
  const [map, setMap] = useState<LeafletNS.Map | null>(null);
  const [L, setL] = useState<typeof LeafletNS | null>(null);
  const router = useRouter();

  const onReady = useCallback((m: LeafletNS.Map, lib: typeof LeafletNS) => {
    setMap(m);
    setL(lib);
  }, []);

  const pins = useMemo(
    () => leads.filter((l) => typeof l.latitude === "number" && typeof l.longitude === "number"),
    [leads],
  );

  useEffect(() => {
    if (!map || !L) return;
    let cancelled = false;
    let cluster: MarkerClusterGroup | null = null;

    void (async () => {
      await import("leaflet.markercluster/dist/MarkerCluster.css");
      await import("leaflet.markercluster/dist/MarkerCluster.Default.css");
      await import("leaflet.markercluster");
      if (cancelled) return;

      cluster = (
        L as unknown as { markerClusterGroup: (opts?: object) => MarkerClusterGroup }
      ).markerClusterGroup({
        showCoverageOnHover: false,
        chunkedLoading: true,
        maxClusterRadius: 36,
        iconCreateFunction: (c: { getChildCount(): number }) =>
          L.divIcon({
            html: `<div class="lead-cluster">${c.getChildCount()}</div>`,
            className: "lead-cluster-wrap",
            iconSize: [36, 36],
          }),
      });

      const markers = pins.map((lead) => {
        const color = TEMP_COLORS[lead.lead_temperature ?? "LOW"] ?? TEMP_COLORS.LOW;
        const marker = L.marker([lead.latitude as number, lead.longitude as number], {
          icon: L.divIcon({
            html: `<div class="lead-pin" style="background:${color}"></div>`,
            className: "lead-pin-wrap",
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          }),
        });
        const rating = lead.rating ? `${Number(lead.rating).toFixed(1)} ★ · ` : "";
        marker.bindPopup(
          `<div class="lead-popup">
             <strong>${escapeHtml(lead.business_name)}</strong>
             <span>${rating}${escapeHtml(lead.category ?? "")}</span>
             <a href="/leads/${lead.id}" data-pin-id="${lead.id}">Ver detalle →</a>
           </div>`,
          { closeButton: false, className: "lead-popup-wrap" },
        );
        return marker;
      });

      cluster.addLayers(markers);
      map.addLayer(cluster);
      if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15), { maxZoom: 14 });
      }
    })();

    return () => {
      cancelled = true;
      if (cluster) {
        cluster.clearLayers();
        map.removeLayer(cluster);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, L, pins]);

  // Popup links: delegate clicks (popups live outside React).
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const a = (e.target as HTMLElement).closest("a[data-pin-id]") as HTMLAnchorElement | null;
      if (!a) return;
      e.preventDefault();
      router.push(a.getAttribute("href") ?? "/leads");
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [router]);

  return <BaseMap center={[-34.9011, -56.1645]} zoom={12} onReady={onReady} className={className} />;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c);
}
