"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowRight,
  AtSign,
  Building2,
  CalendarClock,
  ExternalLink,
  Globe,
  Lightbulb,
  MailPlus,
  MapPin,
  MessageSquare,
  Phone,
  Sparkles,
  Star,
  Target,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AuditPayload, LeadDetail } from "@/lib/types";
import {
  Bar,
  Button,
  Card,
  ErrorNote,
  ScoreRing,
  Spinner,
  TemperatureChip,
  cn,
} from "@/components/ui";

const DIM_LABELS: Record<string, string> = {
  design: "Diseño",
  mobile: "Mobile",
  seo: "SEO",
  performance: "Performance",
  conversion: "Conversión",
  cta: "CTA",
  contact: "Contacto",
  booking: "Reservas",
  trust: "Confianza",
  automation: "Automatización",
};

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: lead, isLoading, isError, error } = useQuery<LeadDetail>({
    queryKey: ["lead", id],
    queryFn: () => api.get<LeadDetail>(`/api/leads/${id}`),
  });
  const { data: auditData } = useQuery<{ audit: AuditPayload | null; pages: Array<{ url: string; kind: string }> }>({
    queryKey: ["lead-audit", id],
    queryFn: () => api.get(`/api/leads/${id}/audit`),
    enabled: !!id,
  });

  const generate = useMutation({
    mutationFn: () => api.post<{ id: number }>(`/api/leads/${id}/generate-proposal`),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      router.push(`/proposals/${res.id}`);
    },
  });

  if (isLoading) return <Spinner label="Cargando lead…" />;
  if (isError || !lead) return <ErrorNote message={error instanceof Error ? error.message : "No encontramos este lead"} />;

  const audit = auditData?.audit ?? null;
  const strengths = (lead.website_strengths ?? []).map((s) => (typeof s === "string" ? { text: s } : s));
  const weaknesses = (lead.website_weaknesses ?? []).map((s) => (typeof s === "string" ? { text: s } : s));
  const opportunities = lead.detected_opportunities ?? [];
  const breakdown = lead.score_breakdown;

  return (
    <div className="max-w-6xl space-y-6">
      {/* Header */}
      <div className="card p-7 relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-gold via-goldsoft to-gold" />
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-display text-3xl font-semibold">{lead.business_name}</h1>
              <TemperatureChip temperature={lead.lead_temperature} />
              {lead.priority && <span className="chip bg-night text-white">{lead.priority}</span>}
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-taupe mt-2">
              <span className="inline-flex items-center gap-1.5"><Star size={14} className="text-gold" fill="currentColor" /> {lead.rating ?? "—"} · {lead.reviews_count} reseñas</span>
              <span className="inline-flex items-center gap-1.5"><MapPin size={14} /> {lead.city ?? "—"}{lead.country ? `, ${lead.country}` : ""}</span>
              <span className="inline-flex items-center gap-1.5"><Building2 size={14} /> {lead.category ?? lead.primary_type ?? "—"}</span>
            </div>
            <div className="flex flex-wrap gap-2 mt-5">
              {lead.google_maps_url && (
                <a href={lead.google_maps_url} target="_blank" rel="noreferrer" className="btn-outline !py-2">
                  <ExternalLink size={14} /> Google Maps
                </a>
              )}
              {lead.website && (
                <a href={lead.website} target="_blank" rel="noreferrer" className="btn-outline !py-2">
                  <Globe size={14} /> Website
                </a>
              )}
              {lead.website && (
                <Button onClick={() => generate.mutate()} variant="gold" disabled={generate.isPending}>
                  <MailPlus size={15} /> {generate.isPending ? "Generando propuesta…" : "Generar propuesta"}
                </Button>
              )}
            </div>
          </div>
          {/* scores */}
          <div className="flex gap-4 items-center bg-sand rounded-2xl px-5 py-4">
            <div className="text-center">
              <ScoreRing value={lead.website_score} max={10} size={78} color="#B08D3E" label="website" />
            </div>
            <div className="text-center">
              <ScoreRing value={lead.opportunity_score} max={100} size={78} color="#7A6A4A" label="oportunidad" />
            </div>
            <div className="text-center">
              <ScoreRing value={lead.lead_score} max={100} size={78} color="#111111" label="lead" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Business profile */}
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4">Business Profile</h2>
          <ProfileRow icon={<Star size={14} />} label="Rating" value={lead.rating != null ? `${lead.rating} ⭐` : "—"} />
          <ProfileRow icon={<MessageSquare size={14} />} label="Reviews" value={String(lead.reviews_count)} />
          <ProfileRow icon={<Building2 size={14} />} label="Categoría" value={lead.category ?? lead.primary_type ?? "—"} />
          <ProfileRow icon={<MapPin size={14} />} label="Dirección" value={lead.address ?? "—"} />
          <ProfileRow icon={<Phone size={14} />} label="Teléfono" value={lead.phone ?? lead.international_phone ?? "—"} />
          <ProfileRow icon={<Globe size={14} />} label="Website" value={lead.website ?? "—"} link={lead.website ?? undefined} />
          <ProfileRow icon={<AtSign size={14} />} label="Email público" value={lead.email ?? "No encontramos un email público en las fuentes analizadas."} />
          {lead.email_confidence && (
            <ProfileRow icon={<span />} label="Confianza" value={lead.email_confidence} />
          )}
        </Card>

        {/* Recommended */}
        <Card className="border-gold/40">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Target size={18} className="text-gold" /> Recomendación AvaScho
          </h2>
          <div className="rounded-2xl bg-night text-white p-5">
            <div className="text-[10px] uppercase tracking-[0.2em] text-goldsoft">Servicio recomendado</div>
            <div className="font-display text-2xl font-semibold mt-1">{lead.recommended_service ?? "Custom AI Integration"}</div>
            <div className="text-xs text-white/50 mt-2">
              Acción recomendada: <b className="text-white/80">{lead.recommended_action?.replaceAll("_", " ") ?? "—"}</b>
            </div>
            {lead.confidence != null && (
              <div className="text-xs text-white/50 mt-1">Confianza del análisis: {(lead.confidence * 100).toFixed(0)}%</div>
            )}
          </div>

          <h3 className="font-display text-base font-semibold mt-6 mb-3">¿Por qué este lead?</h3>
          <p className="text-sm text-ink/80 leading-relaxed">{lead.why_this_lead ?? "Sin datos suficientes todavía."}</p>
          {lead.why_now && (
            <>
              <h3 className="font-display text-base font-semibold mt-5 mb-2">¿Por qué ahora?</h3>
              <p className="text-sm text-ink/80 leading-relaxed">{lead.why_now}</p>
            </>
          )}
          {lead.score_breakdown && (
            <div className="mt-5">
              <h3 className="font-display text-base font-semibold mb-2">¿Por qué {lead.lead_score ?? "—"}/100?</h3>
              <ScoreList title="Lead" items={breakdown?.lead ?? []} />
              <div className="mt-3" />
              <ScoreList title="Oportunidad" items={breakdown?.opportunity ?? []} />
            </div>
          )}
        </Card>
      </div>

      {/* Website audit */}
      {audit && (
        <>
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <h2 className="font-display text-2xl font-semibold flex items-center gap-2">
                <Globe size={20} className="text-gold" /> Website Audit
              </h2>
              <div className="flex items-center gap-6">
                <ScoreRing value={audit.overall_score} max={10} size={110} color="#111111" />
                <div className="text-sm text-taupe space-y-0.5">
                  <div className="flex items-center gap-2"><Globe size={13} /> {audit.url}</div>
                  <div className="flex items-center gap-2"><Sparkles size={13} /> modelo {audit.model ?? "rule-based"}</div>
                  {audit.audited_at && <div className="flex items-center gap-2"><CalendarClock size={13} /> {new Date(audit.audited_at).toLocaleString("es-UY")}</div>}
                </div>
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-x-10 gap-y-4">
              {Object.entries(DIM_LABELS).map(([key, label]) => {
                const value = audit.subscores?.[key] ?? 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <div className="w-32 text-xs text-ink/70 shrink-0">{label}</div>
                    <Bar value={value} max={10} color={value >= 7 ? "#1E8E3E" : value >= 4 ? "#B08D3E" : "#C5221F"} />
                    <div className="w-9 text-right text-sm font-semibold tabular-nums shrink-0">{audit.subscores?.[key] ?? "—"}</div>
                  </div>
                );
              })}
            </div>
            {auditData && auditData.pages.length > 0 && (
              <div className="mt-5 text-xs text-taupe">
                Páginas analizadas:{" "}
                {auditData.pages.map((p) => (
                  <span key={p.url} className="chip bg-sand mr-1 mb-1">{p.kind}</span>
                ))}
              </div>
            )}
          </Card>

          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
                <ThumbsUp size={17} className="text-[#1E8E3E]" /> Qué encontramos — fortalezas
              </h2>
              <div className="space-y-2.5">
                {(audit.strengths ?? []).map((s: any, i) => (
                  <div key={i} className="text-sm flex gap-2.5">
                    <span className="text-[#1E8E3E] mt-0.5">✓</span>
                    <div>
                      <div className="font-medium">{s.text ?? s}</div>
                      {s.evidence && <div className="text-xs text-taupe">{s.evidence}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
                <ThumbsDown size={17} className="text-[#C5221F]" /> Qué encontramos — debilidades
              </h2>
              <div className="space-y-2.5">
                {(audit.weaknesses ?? []).map((w: any, i) => (
                  <div key={i} className="text-sm flex gap-2.5">
                    <span className="text-[#C5221F] mt-0.5">✕</span>
                    <div>
                      <div className="font-medium">{w.text ?? w}</div>
                      {w.evidence && <div className="text-xs text-taupe">Evidencia: {w.evidence}</div>}
                      {w.kind && <span className="chip bg-sand mt-1">{w.kind === "FACT" ? "HECHO verificado" : "Inferencia por ausencia"}</span>}
                    </div>
                  </div>
                ))}
                {(audit.weaknesses ?? []).length === 0 && (
                  <p className="text-sm text-taupe">No se detectaron debilidades relevantes con la evidencia disponible.</p>
                )}
              </div>
            </Card>
          </div>
        </>
      )}

      {/* Opportunities */}
      {opportunities.length > 0 && (
        <Card className="border-gold/30">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Lightbulb size={18} className="text-gold" /> Oportunidades detectadas
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            {opportunities.map((opp, i) => (
              <div key={i} className="rounded-2xl border border-sandline p-5 bg-sand/40">
                <div className="text-[10px] uppercase tracking-[0.18em] text-gold font-bold">Oportunidad {i + 1}</div>
                <div className="font-semibold text-[15px] mt-1">{opp.title}</div>
                <p className="text-xs text-ink/70 mt-2 leading-relaxed">{opp.opportunity}</p>
                {opp.service && (
                  <div className="mt-3 chip bg-night text-white">{opp.service}</div>
                )}
                {opp.evidence && <div className="text-[11px] text-taupe mt-3">Por qué: {opp.evidence}</div>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* CTA */}
      {lead.website && (
        <div className="card p-6 flex flex-wrap items-center justify-between gap-4 border-gold/40">
          <div>
            <div className="font-display text-lg font-semibold">¿Siguiente paso?</div>
            <p className="text-sm text-taupe">Generá una propuesta comercial personalizada con los datos reales de este negocio.</p>
          </div>
          <Button variant="gold" onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? "Generando…" : "Generar propuesta"} <ArrowRight size={16} />
          </Button>
        </div>
      )}
    </div>
  );
}

function ProfileRow({ icon, label, value, link }: { icon: React.ReactNode; label: string; value: string; link?: string }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-sandline last:border-0">
      <div className="text-gold/70 mt-0.5 shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] uppercase tracking-[0.14em] text-taupe font-semibold">{label}</div>
        {link ? (
          <a href={link} target="_blank" rel="noreferrer" className="text-sm text-ink underline decoration-gold/50 hover:text-gold break-all">
            {value} <ExternalLink size={11} className="inline" />
          </a>
        ) : (
          <div className={cn("text-sm", label === "Email público" && !value.includes("@") ? "text-taupe italic" : "text-ink break-all")}>{value}</div>
        )}
      </div>
    </div>
  );
}

function ScoreList({ title, items }: { title: string; items: Array<{ delta?: number; label?: string; detail?: string }> }) {
  if (!items.length) return null;
  return (
    <div className="space-y-1">
      <div className="text-[10px] uppercase tracking-[0.16em] text-taupe font-bold">{title}</div>
      {items.slice(0, 8).map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-xs py-0.5">
          <span className="w-7 text-right text-[#1E8E3E] font-bold tabular-nums shrink-0">+{item.delta ?? 0}</span>
          <span className="text-ink/80">{item.label}</span>
          <span className="text-taupe truncate">{item.detail}</span>
        </div>
      ))}
    </div>
  );
}
