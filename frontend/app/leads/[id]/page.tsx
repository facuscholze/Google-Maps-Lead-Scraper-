"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowRight,
  AtSign,
  Building2,
  CalendarClock,
  ExternalLink,
  FileSignature,
  Globe,
  History,
  Lightbulb,
  MailPlus,
  MapPin,
  MessageSquare,
  Phone,
  Plus,
  RefreshCw,
  Sparkles,
  Star,
  Tag,
  Target,
  ThumbsDown,
  ThumbsUp,
  UserRound,
  X,
} from "lucide-react";
import { toast } from "sonner";
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

// Fase 5: tipos locales para evidencia de auditoría
interface AuditFinding {
  problem: string;
  evidence: string;
  source_url?: string | null;
  kind: string;
  dimension?: string;
}
interface AuditShot {
  index: number;
  url?: string | null;
  kind?: string | null;
  width?: number | null;
  height?: number | null;
  captured_at?: string | null;
}

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
  automation: "Canales de consulta",
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
  const { data: activity } = useQuery<{ items: ActivityItem[] }>({
    queryKey: ["lead-activity", id],
    queryFn: () => api.get(`/api/leads/${id}/activity`),
    enabled: !!id,
  });
  const { data: proposals } = useQuery<ProposalSummary[]>({
    queryKey: ["proposals", "lead", id],
    queryFn: () => api.get(`/api/proposals?lead_id=${id}`),
    enabled: !!id,
  });

  const generate = useMutation({
    mutationFn: () => api.post<{ id: number }>(`/api/leads/${id}/generate-proposal`),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Propuesta generada — la revisás antes de enviarla");
      router.push(`/proposals/${res.id}`);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "No se pudo generar"),
  });

  const reaudit = useMutation({
    mutationFn: () => api.post(`/api/leads/${id}/audit`),
    onSuccess: () => {
      toast.success("Re-auditoría lanzada", { description: "Tarda unos segundos; se actualiza sola al volver." });
      queryClient.invalidateQueries({ queryKey: ["lead-audit", id] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "No se pudo reauditar"),
  });

  async function updateLead(action: string, extra?: Record<string, string>) {
    try {
      await api.post("/api/leads/bulk", { ids: [Number(id)], action, ...extra });
      await queryClient.invalidateQueries({ queryKey: ["lead", id] });
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Lead actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo actualizar");
    }
  }

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

        {/* Ownership + tags (Fase 4) */}
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <UserRound size={18} className="text-gold" /> Gestión
          </h2>
          <div className="space-y-4">
            <div>
              <div className="text-[10px] uppercase tracking-[0.14em] text-taupe font-semibold mb-1.5">Responsable</div>
              <div className="flex items-center gap-2">
                <span className="chip bg-sand">{lead.owner_name ?? "sin asignar"}</span>
                <button
                  type="button"
                  className="text-xs text-gold underline underline-offset-2"
                  onClick={() => {
                    const o = window.prompt("Responsable (dejá vacío para quitar):", lead.owner_name ?? "");
                    if (o == null) return;
                    if (o.trim()) void updateLead("assign_owner", { owner: o });
                    else void updateLead("clear_owner");
                  }}
                >
                  editar
                </button>
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.14em] text-taupe font-semibold mb-1.5">Etiquetas</div>
              <div className="flex flex-wrap items-center gap-1.5">
                {(lead.tags ?? []).map((t) => (
                  <span key={t} className="chip border border-sandline bg-sand">
                    <Tag size={10} className="text-gold" /> {t}
                    <button
                      type="button"
                      aria-label={`Quitar tag ${t}`}
                      className="text-taupe hover:text-[#C5221F]"
                      onClick={() => void updateLead("remove_tag", { tag: t })}
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
                <button
                  type="button"
                  className="chip border border-dashed border-sandline text-taupe hover:text-ink"
                  onClick={() => {
                    const t = window.prompt("Nueva etiqueta:");
                    if (t?.trim()) void updateLead("add_tag", { tag: t });
                  }}
                >
                  <Plus size={11} /> agregar
                </button>
              </div>
            </div>
            {lead.website && (
              <button
                type="button"
                className="btn-outline !py-2 text-xs"
                onClick={() => reaudit.mutate()}
                disabled={reaudit.isPending}
              >
                <RefreshCw size={13} className={reaudit.isPending ? "animate-spin" : ""} /> Re-auditar website
              </button>
            )}
          </div>
        </Card>

        {/* Recommended */}
        <Card className="border-gold/40">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Target size={18} className="text-gold" /> Recomendación AvaScho
          </h2>
          <div className="rounded-2xl bg-night text-white p-5">
            <div className="text-[10px] uppercase tracking-[0.2em] text-goldsoft">Servicio recomendado</div>
            <div className="font-display text-2xl font-semibold mt-1">{lead.recommended_service ?? "Propuesta web por definir"}</div>
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

          {/* F5 · Captura de evidencia */}
          {((audit as { screenshots?: AuditShot[] }).screenshots ?? []).length > 0 && (
            <Card>
              <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
                <Globe size={18} className="text-gold" /> Captura del sitio
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                {((audit as { screenshots?: AuditShot[] }).screenshots ?? []).map((shot) => (
                  <AuditScreenshot key={shot.index} leadId={id} shot={shot} />
                ))}
              </div>
            </Card>
          )}

          {/* F5 · Findings clasificados */}
          {((audit as { findings?: AuditFinding[] }).findings ?? []).length > 0 && (
            <FindingsCard findings={(audit as { findings?: AuditFinding[] }).findings ?? []} />
          )}
        </>
      )}

      {/* Proposals for this lead */}
      {proposals && proposals.length > 0 && (
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <FileSignature size={18} className="text-gold" /> Propuestas
          </h2>
          <div className="space-y-2">
            {proposals.map((p) => (
              <Link key={p.id} href={`/proposals/${p.id}`} className="flex items-center justify-between gap-3 rounded-xl border border-sandline px-4 py-3 transition hover:border-gold/50">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{p.subject}</div>
                  <div className="text-xs text-taupe">{new Date(p.created_at).toLocaleDateString("es-UY")}</div>
                </div>
                <span className="chip bg-night text-white shrink-0">{p.status.replaceAll("_", " ")}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* Activity timeline */}
      {activity && activity.items.length > 0 && (
        <Card>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <History size={18} className="text-gold" /> Historial
          </h2>
          <ol className="relative space-y-4 border-l border-sandline pl-5">
            {activity.items.map((item, i) => (
              <li key={i} className="relative">
                <span
                  className="absolute -left-[27px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white"
                  style={{ background: item.kind === "email" ? "#B08D3E" : item.kind === "proposal" ? "#7A6A4A" : item.kind === "audited" ? "#1E8E3E" : "#111111" }}
                />
                <div className="text-sm font-medium">{item.label}</div>
                {item.detail && <div className="text-xs text-taupe">{item.detail}</div>}
                <div className="text-[11px] text-taupe/70">{item.ts ? new Date(item.ts).toLocaleString("es-UY") : ""}</div>
              </li>
            ))}
          </ol>
        </Card>
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

// Fase 4: tipos locales para timeline/propuestas
interface ActivityItem { ts: string | null; kind: string; label: string; detail?: string | null }
interface ProposalSummary { id: number; subject: string; status: string; created_at: string }

function AuditScreenshot({ leadId, shot }: { leadId: string; shot: AuditShot }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    api
      .getBlob(`/api/leads/${leadId}/audit/screenshots/${shot.index}`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [leadId, shot.index]);

  return (
    <figure className="rounded-xl border border-sandline overflow-hidden bg-sand/40">
      {failed ? (
        <div className="grid h-48 place-items-center p-4 text-center text-xs text-taupe">
          La captura no está disponible en este entorno (sin navegador headless).
        </div>
      ) : src ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={src}
          alt={`Captura del sitio ${shot.url ?? ""}`}
          width={shot.width ?? 1280}
          height={shot.height ?? 800}
          className="h-auto w-full"
        />
      ) : (
        <div className="grid h-48 place-items-center text-xs text-taupe">Cargando captura…</div>
      )}
      <figcaption className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-[11px] text-taupe">
        <span className="truncate">{shot.url}</span>
        {shot.captured_at && <span>{new Date(shot.captured_at).toLocaleString("es-UY")}</span>}
      </figcaption>
    </figure>
  );
}

function FindingsCard({ findings }: { findings: AuditFinding[] }) {
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold mb-1 flex items-center gap-2">
        <Sparkles size={18} className="text-gold" /> Findings de la auditoría
      </h2>
      <p className="text-xs text-taupe mb-4">
        Cada ítem se observó en las páginas analizadas (<b className="text-[#1E8E3E]">FACT</b>) o se
        dedujo por ausencia (<b className="text-[#B08D3E]">INFERENCE</b>). Nada se asume sin evidencia.
      </p>
      <div className="space-y-2.5">
        {findings.map((f, i) => (
          <div key={i} className="flex flex-wrap items-start gap-2 rounded-xl border border-sandline px-3 py-2.5">
            <span
              className={cn(
                "chip shrink-0 text-[10px]",
                f.kind === "FACT" ? "bg-[#1E8E3E]/10 text-[#1E8E3E]" : "bg-gold/10 text-gold",
              )}
              title={f.kind === "FACT" ? "Observado directamente en el sitio" : "Deducido por ausencia de señales"}
            >
              {f.kind}
            </span>
            {f.dimension && <span className="chip bg-sand text-[10px] text-taupe shrink-0">{DIM_LABELS[f.dimension] ?? f.dimension}</span>}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{f.problem}</div>
              <div className="text-xs text-taupe mt-0.5">{f.evidence}</div>
              {f.source_url && (
                <a href={f.source_url} target="_blank" rel="noreferrer" className="mt-0.5 block truncate text-[11px] text-gold underline underline-offset-2">
                  {f.source_url} <ExternalLink size={10} className="inline" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
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
