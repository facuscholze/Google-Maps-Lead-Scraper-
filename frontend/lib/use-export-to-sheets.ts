"use client";

// Shared state for the "Enviar a Sheets" buttons (leads list + searches list).
// `key` identifies which button fired the request so a list can show a
// per-row loading state and result.

import { useCallback, useState } from "react";
import { api } from "@/lib/api";

export interface SheetsExportBody {
  selection?: "all" | "selected" | "HOT" | "WARM" | "READY_TO_CONTACT";
  search_id?: number;
  ids?: number[];
  temperature?: string;
  q?: string;
  has_email?: boolean;
  min_lead_score?: number;
  spreadsheet_id?: string;
  sheet_name?: string;
}

export interface SheetsExportResponse {
  rows_written: number;
  sheet_name?: string | null;
  spreadsheet_url: string;
}

export interface SheetsExportOutcome extends SheetsExportResponse {
  key: string;
}

export function useExportToSheets() {
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<SheetsExportOutcome | null>(null);

  const sendToSheets = useCallback(async (key: string, body: SheetsExportBody) => {
    setPendingKey(key);
    setError(null);
    setOutcome(null);
    try {
      // `api` agrega el header Authorization; los undefined se caen al
      // serializar, así que el backend recibe solo los filtros activos.
      const result = await api.post<SheetsExportResponse>("/api/leads/export-to-sheets", body);
      setOutcome({ ...result, key });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pudimos enviar los leads a Google Sheets.");
    } finally {
      setPendingKey(null);
    }
  }, []);

  const dismiss = useCallback(() => {
    setError(null);
    setOutcome(null);
  }, []);

  return {
    sendToSheets,
    /** True while the button identified by `key` is waiting on the backend. */
    isSending: (key: string) => pendingKey === key,
    error,
    outcome,
    dismiss,
  };
}
