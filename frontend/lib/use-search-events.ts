"use client";

/**
 * Live progress de una búsqueda: SSE `/api/searches/{id}/events?token=` con
 * fallback a polling (`/status`) cuando EventSource no conecta (proxies que
 * cortan streams, pestaña dormida, etc.).
 *
 * El backend emite `event: snapshot` con {search, jobs} cada vez que algo
 * cambia, `: heartbeat` cada 15 s y `event: done` al terminar.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken } from "@/lib/api";
import type { Job, SearchSummary } from "@/lib/types";

export interface SearchEventsState {
  search: SearchSummary | null;
  jobs: Job[];
  /** "sse" en vivo · "polling" degradado · "connecting" todavía no hay datos */
  channel: "connecting" | "sse" | "polling";
  done: boolean;
  error: string | null;
}

interface Snapshot {
  search: SearchSummary;
  jobs: Job[];
}

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function useSearchEvents(searchId: string | null): SearchEventsState {
  const [state, setState] = useState<SearchEventsState>({
    search: null,
    jobs: [],
    channel: "connecting",
    done: false,
    error: null,
  });
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applySnapshot = useCallback((snapshot: Snapshot) => {
    setState((prev) => ({
      ...prev,
      search: snapshot.search,
      jobs: snapshot.jobs,
      done: TERMINAL.has(snapshot.search.status),
      error: null,
    }));
  }, []);

  useEffect(() => {
    if (!searchId) return;
    let source: EventSource | null = null;
    let stopped = false;
    let sseFailed = false;

    const startPolling = () => {
      if (stopped || pollTimer.current) return;
      setState((prev) => ({ ...prev, channel: "polling" }));
      const tick = async () => {
        if (stopped) return;
        try {
          const res = await api.get<{ search: SearchSummary; jobs: Job[] }>(
            `/api/searches/${searchId}/status`,
          );
          applySnapshot({ search: res.search, jobs: res.jobs });
          if (TERMINAL.has(res.search.status)) return;
        } catch (err) {
          setState((prev) => ({
            ...prev,
            error: err instanceof Error ? err.message : "Error de conexión",
          }));
        }
        pollTimer.current = setTimeout(tick, 2500);
      };
      pollTimer.current = setTimeout(tick, 400);
    };

    const token = getToken();
    if (token && typeof EventSource !== "undefined") {
      source = new EventSource(
        `/api/searches/${searchId}/events?token=${encodeURIComponent(token)}`,
      );
      source.addEventListener("snapshot", (e) => {
        try {
          applySnapshot(JSON.parse((e as MessageEvent).data));
          sseFailed = false;
          setState((prev) => ({ ...prev, channel: "sse" }));
        } catch {
          /* malformed frame — ignore */
        }
      });
      source.addEventListener("done", () => {
        source?.close();
        if (pollTimer.current) {
          clearTimeout(pollTimer.current);
          pollTimer.current = null;
        }
      });
      source.addEventListener("error", () => {
        // EventSource reintenta solo; si nunca abrió, pasamos a polling.
        if (!sseFailed && source?.readyState === EventSource.CLOSED) {
          sseFailed = true;
          source?.close();
          startPolling();
        }
      });
    } else {
      startPolling();
    }

    return () => {
      stopped = true;
      source?.close();
      if (pollTimer.current) {
        clearTimeout(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [searchId, applySnapshot]);

  return state;
}
