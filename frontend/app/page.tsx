"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  ArrowUpRight,
  Flame,
  FileText,
  MailCheck,
  MessageCircle,
  Target,
  Users,
  Globe,
  AtSign,
  CheckCircle2,
  Eye,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Skeleton, Spinner, StatCard, TemperatureChip, Button, cn } from "@/components/ui";

const FUNNEL_STEPS = [
  { key: "businesses_found", label: "Negocios encontrados" },
  { key: "businesses_qualified", label: "Negocios calificados" },
  { key: "websites_analyzed", label: "Websites analizados" },
  { key: "emails_found", label: "Emails encontrados" },
  { key: "potential_clients", label: "Clientes potenciales" },
  { key: "proposals_generated", label: "Propuestas generadas" },
  { key: "approved", label: "Aprobadas" },
  { key: "sent", label: "Enviadas" },
  { key: "replied", label: "Respuestas" },
];

export default function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useQuery<Dashboard>({
    queryKey: ["dashboard"],
    queryFn: () => api.get<Dashboard>("/api/dashboard"),
    refetchInterval: 15000,
  });

  if (isLoading) return <Spinner label="Cargando dashboard…" />;
  if (isError) return <ErrorNote message={error instanceof Error ? error.message : "Error" } />;
  if (!data) return null;

  const { cards, averages, funnel, top_leads, review_queue } = data;
  const funnelMax = Math.max(1, funnel.businesses_found || 1);

  return (
    <div className="space-y-8">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="Total leads" value={cards.total_leads} icon={<Users size={20} />} />
        <StatCard label="Potential clients" value={cards.potential_clients} icon={<Target size={20} />} accent />
        <StatCard label="HOT leads" value={cards.hot_leads} icon={<Flame size={20} />} hint={`${cards.warm_leads} warm`} />
        <StatCard label="Websites audited" value={cards.websites_audited} icon={<Globe size={20} />} />
        <StatCard label="Emails found" value={cards.emails_found} icon={<AtSign size={20} />} />
        <StatCard label="Proposals ready" value={cards.proposals_ready} icon={<FileText size={20} />} />
        <StatCard label="Emails sent" value={cards.emails_sent} icon={<MailCheck size={20} />} />
        <StatCard label="Replies" value={cards.replies} icon={<MessageCircle size={20} />} />
        <StatCard label="Avg. scores" value="—" icon={<Eye size={20} />} hint={scoreHint(data)} />
      </div>

      {/* Averages row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Average Lead Score", value: data.averages.avg_lead_score },
          { label: "Average Website Score", value: data.averages.avg_website_score },
          { label: "Average Opportunity Score", value: data.averages.avg_opportunity_score },
        ].map((item) => (
          <div key={item.label} className="card p-4 flex items-center justify-between">
            <span className="text-xs uppercase tracking-[0.14em] text-taupe font-semibold">{item.label}</span>
            <span className="font-display text-2xl font-semibold">{item.value ?? "—"}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Funnel */}
        <Card className="xl:col-span-1">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display text-lg font-semibold">Pipeline</h2>
            <Link href="/searches" className="text-xs text-gold hover:underline">ver búsquedas</Link>
          </div>
          <div className="space-y-2.5">
            {FUNNEL_STEPS.map((step, idx) => {
              const value = funnel[step.key] ?? 0;
              const width = Math.max(4, Math.round((value / funnelMax) * 100));
              return (
                <div key={step.key} className="flex items-center gap-3">
                  <div className="w-40 shrink-0 text-xs text-ink/70 truncate">{step.label}</div>
                  <div className="flex-1 h-5 rounded-md bg-sand overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-md transition-all duration-700",
                        idx >= funnel.potential_clients === false ? "bg-gold/60" : "bg-ink/80",
                        step.key === "potential_clients" && "bg-gold",
                        step.key === "replied" && "bg-[#1E8E3E]/70"
                      )}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <div className="w-8 text-right text-sm font-semibold tabular-nums">{value}</div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Top leads */}
        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-lg font-semibold">Leads destacados</h2>
            <Link href="/leads?temperature=HOT" className="text-xs text-gold hover:underline">ver todos</Link>
          </div>
          {top_leads.length === 0 ? (
            <EmptyState title="Todavía no hay leads" subtitle="Creá tu primera búsqueda para comenzar." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {top_leads.map((lead: any) => (
                <Link key={lead.id} href={`/leads/${lead.id}`} className="card p-5 hover:shadow-lift transition group">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold text-[15px] truncate group-hover:text-gold transition">
                        {lead.business_name}
                      </div>
                      <div className="text-xs text-taupe mt-0.5">
                        ⭐ {lead.rating} · {lead.reviews_count} reseñas
                      </div>
                    </div>
                    <TemperatureChip temperature={lead.lead_temperature} />
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                    {[
                      ["Website", lead.website_score, "/10"],
                      ["Opportunity", lead.opportunity_score, "/100"],
                      ["Lead", lead.lead_score, "/100"],
                    ].map(([label, value, suffix]: any) => (
                      <div key={label} className="rounded-xl bg-sand px-2 py-2">
                        <div className="text-[9px] uppercase tracking-wider text-taupe">{label}</div>
                        <div className="font-display text-lg font-semibold leading-tight">
                          {value == null ? "—" : value}
                          <span className="text-[10px] text-taupe font-normal">{suffix}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {lead.why_this_lead && (
                    <p className="text-xs text-taupe mt-3 line-clamp-2">{lead.why_this_lead}</p>
                  )}
                  <div className="mt-3 text-xs text-gold inline-flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                    Ver lead <ArrowUpRight size={13} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Review queue */}
      {review_queue.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-lg font-semibold flex items-center gap-2">
              <CheckCircle2 size={18} className="text-gold" /> Revisión humana pendiente
            </h2>
            <Link href="/proposals" className="text-xs text-gold hover:underline">ir a propuestas</Link>
          </div>
          <div className="divide-y divide-sandline">
            {review_queue.map((item: any) => (
              <div key={item.proposal_id} className="py-3.5 flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-sm truncate">{item.business_name || `Lead #${item.lead_id}`}</div>
                  <div className="text-xs text-taupe truncate mt-0.5">{item.subject}</div>
                </div>
                <div className="flex items-center gap-2 text-xs text-taupe">
                  <span>Lead {item.lead_score ?? "—"}</span>·
                  <span>Opp {item.opportunity_score ?? "—"}</span>
                  <span className="chip bg-sand">{item.status.replaceAll("_", " ")}</span>
                </div>
                <Link href={`/proposals/${item.proposal_id}`} className="btn-outline !px-3.5 !py-1.5 !text-xs">
                  Revisar
                </Link>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function scoreHint(d: Dashboard) {
  const parts: string[] = [];
  if (d.averages.avg_lead_score != null) parts.push(`Lead ${d.averages.avg_lead_score}`);
  if (d.averages.avg_website_score != null) parts.push(`Web ${d.averages.avg_website_score}`);
  if (d.averages.avg_opportunity_score != null) parts.push(`Opp ${d.averages.avg_opportunity_score}`);
  return parts.join(" · ");
}
