// Shared API types (mirror of backend schemas).

export type Temperature = "HOT" | "WARM" | "COLD" | "LOW";

export interface SearchSummary {
  id: number;
  query: string;
  location?: string | null;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  results_total: number;
  results_qualified: number;
  websites_analyzed: number;
  emails_found: number;
  hot_count: number;
  warm_count: number;
  cold_count: number;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
}

export interface LeadSummary {
  id: number;
  place_id: string;
  business_name: string;
  category?: string | null;
  city?: string | null;
  country?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  email_confidence?: string | null;
  rating?: number | null;
  reviews_count: number;
  website_status: string;
  website_score?: number | null;
  lead_score?: number | null;
  opportunity_score?: number | null;
  lead_temperature?: Temperature | null;
  priority?: string | null;
  recommended_service?: string | null;
  recommended_action?: string | null;
  status: string;
  confidence?: number | null;
}

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

export interface Job {
  id: number;
  search_id?: number | null;
  job_type: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  current_step?: string | null;
  total: number;
  done: number;
  error_message?: string | null;
}

export interface EmailAccount {
  id: number;
  email: string;
  provider: string;
  status: string;
  daily_limit: number;
  sent_today: number;
  sent_date?: string | null;
  last_sent_at?: string | null;
  display_name?: string | null;
}

export interface EmailOut {
  id: number;
  lead_id: number;
  proposal_id?: number | null;
  to_email: string;
  from_email?: string | null;
  subject?: string | null;
  status: string;
  scheduled_at?: string | null;
  sent_at?: string | null;
  error?: string | null;
  created_at: string;
}

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
