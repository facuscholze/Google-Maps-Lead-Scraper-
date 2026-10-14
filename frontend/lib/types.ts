// Shared API types.
//
// Los tipos de respuesta están **generados desde el OpenAPI del backend**
// (`lib/api-types.ts`, regenerar con `npm run gen:types`). Este archivo los
// re-exporta con refinamientos de unión donde el schema queda demasiado
// laxo (p. ej. `lead_temperature`), y mantiene a mano solo los tipos que el
// OpenAPI no describe con precisión (Dashboard, detalles con JSON libre).

import type { components } from "./api-types";

export type { paths, components } from "./api-types";

export type Temperature = "HOT" | "WARM" | "COLD" | "LOW";

export type SearchSummary = components["schemas"]["SearchOut"] & {
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
};

export type LeadSummary = Omit<components["schemas"]["LeadSummary"], "lead_temperature"> & {
  lead_temperature?: Temperature | null;
};

export interface LeadDetail extends LeadSummary {
  primary_type?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  international_phone?: string | null;
  email_source_url?: string | null;
  google_maps_url?: string | null;
  business_status?: string | null;
  why_this_lead?: string | null;
  why_now?: string | null;
  score_breakdown?: { lead?: BreakdownItem[]; opportunity?: BreakdownItem[] } | null;
  website_strengths?: Array<{ text?: string; evidence?: string; kind?: string } | string> | null;
  website_weaknesses?: Array<{ text?: string; evidence?: string; kind?: string } | string> | null;
  detected_opportunities?: Opportunity[] | null;
  contact_channels?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface BreakdownItem {
  delta?: number;
  label?: string;
  detail?: string;
}

export interface Opportunity {
  title?: string;
  opportunity?: string;
  service?: string;
  evidence?: string;
  service_reason?: string;
  source_url?: string;
  confidence?: number;
}

export interface AuditPayload {
  id?: number;
  url?: string;
  overall_score?: number;
  subscores?: Record<string, number>;
  strengths?: Array<{ text?: string; evidence?: string; kind?: string }>;
  weaknesses?: Array<{ text?: string; evidence?: string; kind?: string }>;
  opportunities?: Opportunity[];
  extracted?: Record<string, unknown>;
  title?: string | null;
  services?: string[];
  model?: string | null;
  audited_at?: string | null;
}

export interface ProposalSummary {
  id: number;
  lead_id: number;
  lead_name?: string | null;
  status: string;
  subject?: string | null;
  opening?: string | null;
  personalized_observation?: string | null;
  strengths?: Array<string | { text?: string }>;
  opportunities?: Opportunity[];
  recommended_solution?: string | null;
  call_to_action?: string | null;
  signature?: string | null;
  body_html?: string | null;
  body_plain?: string | null;
  ai_model?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export type Job = Omit<components["schemas"]["JobOut"], "status"> & {
  status: "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
};

export type EmailAccount = components["schemas"]["EmailAccountOut"];

export type EmailOut = components["schemas"]["EmailOut"];

export interface Dashboard {
  cards: {
    total_leads: number;
    potential_clients: number;
    hot_leads: number;
    warm_leads: number;
    websites_audited: number;
    emails_found: number;
    proposals_ready: number;
    emails_sent: number;
    replies: number;
  };
  averages: {
    avg_lead_score?: number | null;
    avg_website_score?: number | null;
    avg_opportunity_score?: number | null;
  };
  funnel: Record<string, number>;
  recent_searches: Array<Record<string, unknown>>;
  top_leads: Array<Record<string, unknown>>;
  review_queue: Array<Record<string, unknown>>;
}

export interface SuppressionEntry {
  id: number;
  email: string;
  reason: string;
  note?: string | null;
  active: boolean;
  created_at: string;
}
