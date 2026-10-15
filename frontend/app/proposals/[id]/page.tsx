"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Check,
  Clock,
  Eye,
  FileText,
  MessageSquare,
  Monitor,
  RefreshCw,
  Send,
  ShieldCheck,
  Smartphone,
  Trash2,
  PenLine,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { EmailAccount, Opportunity, ProposalSummary } from "@/lib/types";
import { Button, Card, ErrorNote, Spinner, StatusChip, cn } from "@/components/ui";

type Tab = "desktop" | "mobile" | "html" | "plain";

export default function ProposalDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("desktop");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [notice, setNotice] = useState<string | undefined>();
  const [accountId, setAccountId] = useState<string>("");
  const [sendNow, setSendNow] = useState(true);
  const [scheduleAt, setScheduleAt] = useState<string>("");
  // editor state
  const [subject, setSubject] = useState("");
  const [opening, setOpening] = useState("");
  const [observation, setObservation] = useState("");
  const [solution, setSolution] = useState("");
  const [cta, setCta] = useState("");
  const [signature, setSignature] = useState("");

  const { data: proposal, isLoading, isError, refetch } = useQuery<ProposalSummary>({
    queryKey: ["proposal", id],
    queryFn: () => api.get<ProposalSummary>(`/api/proposals/${id}`),
  });
  const { data: accounts } = useQuery<EmailAccount[]>({
    queryKey: ["email-accounts"],
    queryFn: () => api.get<EmailAccount[]>("/api/email-accounts"),
  });

  useEffect(() => {
    if (proposal) {
      setSubject(proposal.subject ?? "");
      setOpening(proposal.opening ?? "");
      setObservation(proposal.personalized_observation ?? "");
      setSolution(proposal.recommended_solution ?? "");
      setCta(proposal.call_to_action ?? "");
      setSignature(proposal.signature ?? "");
    }
  }, [proposal]);

  const runAction = (fn: () => Promise<unknown>, okMessage?: string) => async () => {
    setError(undefined);
    setNotice(undefined);
    try {
      await fn();
      await queryClient.invalidateQueries({ queryKey: ["proposal", id] });
      await queryClient.invalidateQueries({ queryKey: ["proposals"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (okMessage) setNotice(okMessage);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    }
  };

  const saveEdit = runAction(async () => {
    await api.put(`/api/proposals/${id}`, {
      subject, opening, personalized_observation: observation,
      recommended_solution: solution, call_to_action: cta, signature,
    });
    setEditing(false);
  }, "Propuesta guardada.");

  const approve = runAction(async () => {
    await api.post(`/api/proposals/${id}/approve`);
  }, "Aprobada. Podés elegir cuenta y enviarla.");

  const discard = runAction(async () => {
    await api.post(`/api/proposals/${id}/discard`);
  }, "Propuesta descartada.");

  const regenerate = runAction(async () => {
    await api.post(`/api/proposals/${id}/regenerate`);
  }, "Propuesta regenerada con la plantilla Innblock y el enfoque de venta web. Revisala antes de aprobar.");

  const send = runAction(async () => {
    await api.post(`/api/proposals/${id}/send`, {
      account_id: accountId ? Number(accountId) : null,
      strategy: "ROUND_ROBIN",
      send_now: sendNow,
      scheduled_at: !sendNow && scheduleAt ? new Date(scheduleAt).toISOString() : null,
    });
    setEditing(false);
  }, "Email encolado correctamente.");

  if (isLoading) return <Spinner label="Cargando propuesta…" />;
  if (isError || !proposal) return <ErrorNote message="No encontramos esta propuesta." />;

  const isApproved = proposal.status === "APPROVED";
  const canEdit = !["SENT", "QUEUED"].includes(proposal.status);

  const previewProps = {
    html: proposal.body_html ?? "",
    plain: proposal.body_plain ?? "",
    className: tab === "desktop" ? "w-full" : "w-[390px]",
  };

  return (
    <div className="max-w-5xl space-y-6 mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="min-w-0">
          <Link href={`/leads/${proposal.lead_id}`} className="text-xs text-gold hover:underline">
            ← {proposal.lead_name ?? `Lead #${proposal.lead_id}`}
          </Link>
          <h1 className="font-display text-2xl font-semibold mt-1 truncate">{proposal.subject}</h1>
          <div className="flex items-center gap-2 mt-1.5">
            <StatusChip status={proposal.status} />
            <span className="text-xs text-taupe">v{proposal.version} · {proposal.ai_model}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <>
              <Button variant="outline" onClick={() => setEditing(!editing)}>
                <PenLine size={15} /> {editing ? "Ver preview" : "Editar"}
              </Button>
              <Button variant="ghost" onClick={regenerate}>
                <RefreshCw size={15} /> Regenerar con Innblock
              </Button>
              {proposal.status !== "CANCELLED" && proposal.status !== "SENT" && (
                <>
                  {proposal.status !== "APPROVED" && (
                    <Button onClick={approve} className="!bg-[#1E8E3E]">
                      <Check size={15} /> Aprobar
                    </Button>
                  )}
                  <Button variant="ghost" onClick={discard}>
                    <Trash2 size={15} /> Descartar
                  </Button>
                </>
              )}
            </>
          )}
          {isApproved && (
            <Button variant="gold" onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })}>
              <Send size={15} /> Enviar
            </Button>
          )}
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {notice && <div className="rounded-xl bg-[#E6F4EA] text-[#1E8E3E] text-sm px-4 py-3">{notice}</div>}

      {editing ? (
        /* ----------------------------- Editor ---------------------------- */
        <Card className="space-y-4">
          <div>
            <label className="label">Asunto</label>
            <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div>
            <label className="label">Saludo</label>
            <input className="input" value={opening} onChange={(e) => setOpening(e.target.value)} />
          </div>
          <div>
            <label className="label">Observación personalizada</label>
            <textarea className="input min-h-[130px]" value={observation} onChange={(e) => setObservation(e.target.value)} />
          </div>
          <div>
            <label className="label">Solución recomendada</label>
            <textarea className="input min-h-[90px]" value={solution} onChange={(e) => setSolution(e.target.value)} />
          </div>
          <div>
            <label className="label">Call to action</label>
            <textarea className="input min-h-[60px]" value={cta} onChange={(e) => setCta(e.target.value)} />
          </div>
          <div>
            <label className="label">Línea de despedida</label>
            <textarea className="input min-h-[60px]" value={signature} onChange={(e) => setSignature(e.target.value)} />
            <p className="text-xs text-taupe mt-1.5">
              La firma de los socios (nombres, roles y teléfonos) es fija y va siempre debajo — sólo editás esta línea.
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(false)}>Cancelar</Button>
            <Button onClick={saveEdit}><Check size={15} /> Guardar</Button>
          </div>
        </Card>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex flex-wrap items-center gap-1 bg-white/70 rounded-full p-1 border border-sandline w-fit">
            {([
              ["desktop", "Desktop", Monitor],
              ["mobile", "Mobile", Smartphone],
              ["html", "HTML", FileText],
              ["plain", "Texto plano", MessageSquare],
            ] as [Tab, string, typeof Monitor][]).map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-4 py-2 text-sm transition",
                  tab === key ? "bg-night text-white" : "text-taupe hover:text-ink"
                )}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          {/* Preview */}
          <div className="bg-white rounded-2xl border border-sandline overflow-hidden shadow-card">
            <div className="border-b border-sandline px-4 py-2 flex items-center gap-2 text-xs text-taupe">
              <Eye size={13} /> Preview · de {proposal.lead_name ?? ""} · versión {proposal.version}
            </div>
            <div className="flex justify-center bg-[#EDE9DE] p-4 md:p-8 max-h-[75vh] overflow-auto">
              {tab === "html" && (
                <pre className="text-[10px] leading-relaxed bg-white p-4 rounded-lg w-full overflow-auto">{proposal.body_html}</pre>
              )}
              {tab === "plain" && (
                <pre className="text-sm leading-relaxed whitespace-pre-wrap bg-white p-6 rounded-lg w-full max-w-xl">{proposal.body_plain}</pre>
              )}
              {(tab === "desktop" || tab === "mobile") && (
                <div className={cn("rounded-lg bg-white", tab === "mobile" && "w-[390px] max-w-full")}>
                  <iframe
                    srcDoc={proposal.body_html ?? ""}
                    className={cn("w-full h-[900px] rounded-lg", tab === "mobile" && "border border-sandline")}
                    sandbox=""
                    title="Email preview"
                  />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* F7/D7.3: trazabilidad ítem a ítem — qué dato salió de dónde */}
      <EvidenceCard proposal={proposal} />

      {/* Send panel */}
      {isApproved && (
        <Card className="border-gold/40">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Send size={17} className="text-gold" /> Enviar a {proposal.lead_name}
          </h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Cuenta emisora</label>
              <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                <option value="">Rotación automática (round robin)</option>
                {(accounts ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.email} · {a.sent_today}/{a.daily_limit} hoy
                  </option>
                ))}
              </select>
              {(accounts ?? []).length === 0 && (
                <p className="text-xs text-taupe mt-1.5">Sin cuentas conectadas — en modo demo se usa la cuenta mock local.</p>
              )}
            </div>
            <div>
              <label className="label">Cuándo</label>
              <div className="flex gap-2">
                <button className={cn("input !py-2 text-center", sendNow && "!border-gold !ring-2 !ring-gold/30")} onClick={() => setSendNow(true)}>
                  Enviar ahora
                </button>
                <button className={cn("input !py-2 text-center", !sendNow && "!border-gold !ring-2 !ring-gold/30")} onClick={() => setSendNow(false)}>
                  Programar
                </button>
              </div>
              {!sendNow && (
                <input type="datetime-local" className="input mt-2" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />
              )}
            </div>
          </div>
          <div className="text-xs text-taupe bg-sand rounded-lg px-3 py-2.5 mt-4 flex gap-2">
            <Clock size={13} className="mt-0.5 shrink-0" />
            El sistema verifica límite diario de la cuenta, horario permitido, suppression list, confianza del email y estado del lead. Nada se envía sin tu aprobación.
          </div>
          <div className="flex justify-end mt-4">
            <Button variant="gold" onClick={send} disabled={!sendNow && !scheduleAt}>
              <Send size={15} /> {sendNow ? "Enviar ahora" : "Poner en cola"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- evidence --
   Card F7: cada afirmación del email atada a su evidencia real. */

type AnchoredStrength = { text?: string; evidence?: string | null; kind?: string };

function normalizeStrengths(list: ProposalSummary["strengths"]): AnchoredStrength[] {
  return (list ?? [])
    .map((s): AnchoredStrength => (typeof s === "string" ? { text: s } : (s ?? {})))
    .filter((s) => (s.text ?? "").trim().length > 0);
}

function KindChip({ kind }: { kind?: string }) {
  const isFact = (kind ?? "FACT") === "FACT";
  return (
    <span
      className={cn(
        "text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0",
        isFact ? "bg-[#E6F4EA] text-[#1E8E3E]" : "bg-gold/15 text-[#7a5c00]"
      )}
      title={isFact ? "Dato verificable" : "Inferencia marcada como tal"}
    >
      {isFact ? "Dato" : "Inferencia"}
    </span>
  );
}

function EvidenceCard({ proposal }: { proposal: ProposalSummary }) {
  const ledger = proposal.ai_reasoning?.evidence_ledger;
  const strengths = normalizeStrengths(proposal.strengths);
  const opportunities: Opportunity[] = proposal.opportunities ?? [];
  if (!ledger && strengths.length === 0 && opportunities.length === 0) return null;

  const places = ledger?.places;
  const audit = ledger?.audit;

  return (
    <Card className="space-y-4 border-[#1E8E3E]/30">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold flex items-center gap-2">
          <ShieldCheck size={17} className="text-[#1E8E3E]" /> Evidencia detrás de esta propuesta
        </h2>
        <p className="text-xs text-taupe max-w-md">
          Nada se afirma sin respaldo: cada dato sale de Google Maps (API oficial) o de nuestra
          auditoría del sitio. Lo que no tiene evidencia real no llega al correo.
        </p>
      </div>

      {/* Procedencia */}
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-sand px-3 py-2.5">
          <div className="text-xs font-semibold text-taupe uppercase tracking-wide mb-1">Ficha comercial</div>
          <p className="text-ink/85">{places?.source ?? "Google Maps Platform — Places API (New)"}</p>
          {(places?.rating != null || places?.reviews != null) && (
            <p className="text-xs text-taupe mt-1">
              Rating {places?.rating ?? "—"} · {places?.reviews ?? "—"} reseñas (dato oficial de la ficha)
            </p>
          )}
        </div>
        <div className="rounded-lg bg-sand px-3 py-2.5">
          <div className="text-xs font-semibold text-taupe uppercase tracking-wide mb-1">
            {audit?.audit_id ? "Auditoría propia del sitio" : "Sin sitio auditado"}
          </div>
          {audit?.audit_id ? (
            <>
              <p className="text-ink/85">
                Puntaje {audit.overall_score ?? "—"}/10 · {audit.findings_count ?? 0} hallazgos
                {audit.screenshots_count ? ` · ${audit.screenshots_count} capturas` : ""}
              </p>
              <p className="text-xs text-taupe mt-1">
                {audit.url ?? ""}
                {audit.audited_at ? ` · ${new Date(audit.audited_at).toLocaleDateString("es-AR")}` : ""}
              </p>
              <Link href={`/leads/${proposal.lead_id}`} className="text-xs text-gold hover:underline">
                Ver auditoría completa →
              </Link>
            </>
          ) : (
            <p className="text-ink/85">La ficha consultada no incluye URL web; la propuesta lo dice así de claro.</p>
          )}
        </div>
      </div>

      {/* Fortalezas ancladas */}
      {strengths.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-taupe uppercase tracking-wide mb-2">
            Fortalezas citadas en el email ({strengths.length})
          </div>
          <ul className="space-y-1.5">
            {strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <KindChip kind={s.kind} />
                <div className="min-w-0">
                  <span className="text-ink/90">{s.text}</span>
                  {s.evidence && <span className="block text-xs text-taupe">↳ {s.evidence}</span>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Oportunidades (todas con evidencia — D7.2) */}
      {opportunities.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-taupe uppercase tracking-wide mb-2">
            Oportunidades propuestas ({opportunities.length}) — todas con evidencia
          </div>
          <ul className="space-y-1.5">
            {opportunities.map((o, i) => (
              <li key={i} className="text-sm">
                <span className="text-ink/90 font-medium">{o.title}</span>
                {o.opportunity && <span className="text-ink/70"> — {o.opportunity}</span>}
                {o.evidence && <span className="block text-xs text-taupe">↳ {o.evidence}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* URLs fuente del audit */}
      {!!audit?.source_urls?.length && (
        <div className="text-xs text-taupe border-t border-sandline pt-3">
          <span className="font-semibold">Páginas analizadas: </span>
          {audit.source_urls.slice(0, 5).map((u) => (
            <a key={u} href={u} target="_blank" rel="noreferrer" className="text-gold hover:underline mr-2 break-all">
              {u.replace(/^https?:\/\//, "")}
            </a>
          ))}
        </div>
      )}
    </Card>
  );
}
