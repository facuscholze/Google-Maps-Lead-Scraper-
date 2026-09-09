"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { FileText, SearchX } from "lucide-react";
import { api } from "@/lib/api";
import type { ProposalSummary } from "@/lib/types";
import { Card, EmptyState, ErrorNote, Spinner, StatusChip } from "@/components/ui";

export default function ProposalsPage() {
  const { data, isLoading, isError, error } = useQuery<ProposalSummary[]>({
    queryKey: ["proposals"],
    queryFn: () => api.get<ProposalSummary[]>("/api/proposals"),
    refetchInterval: 8000,
  });

  if (isLoading) return <Spinner label="Cargando propuestas…" />;
  if (isError) return <ErrorNote message={error instanceof Error ? error.message : "Error"} />;

  const byStatus = (statuses: string[]) => (data ?? []).filter((p) => statuses.includes(p.status));
  const review = byStatus(["READY_FOR_REVIEW", "AI_GENERATED"]);
  const approved = byStatus(["APPROVED"]);
  const sent = byStatus(["SENT", "QUEUED"]);

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="font-display text-3xl font-semibold">Propuestas</h1>
        <p className="text-sm text-taupe mt-1">Revisión humana antes de cualquier envío. La IA nunca envía directamente.</p>
      </div>

      {(!data || data.length === 0) && (
        <EmptyState
          icon={<SearchX size={30} />}
          title="Todavía no hay propuestas"
          subtitle="Entrá a un lead calificado y elegí «Generar propuesta»."
          action={<Link href="/leads?temperature=HOT" className="btn-primary">Ver leads HOT</Link>}
        />
      )}

      {review.length > 0 && (
        <Section title="READY FOR REVIEW" subtitle="Propuestas listas para revisar y aprobar.">
          {review.map((p) => <ProposalRow key={p.id} p={p} action="Revisar" />)}
        </Section>
      )}
      {approved.length > 0 && (
        <Section title="APROBADAS" subtitle="Pendientes de envío (elegí cuenta y horario).">
          {approved.map((p) => <ProposalRow key={p.id} p={p} action="Enviar" />)}
        </Section>
      )}
      {sent.length > 0 && (
        <Section title="ENVIADAS" subtitle="Historial de envíos.">
          {sent.map((p) => <ProposalRow key={p.id} p={p} action="Ver" />)}
        </Section>
      )}
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="font-display text-xl font-semibold tracking-wide">{title}</h2>
        <p className="text-xs text-taupe">{subtitle}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function ProposalRow({ p, action }: { p: ProposalSummary; action: string }) {
  return (
    <Card className="p-5 flex flex-wrap items-center gap-4">
      <div className="min-w-0 flex-1">
        <Link href={`/proposals/${p.id}`} className="font-semibold hover:text-gold transition truncate block">
          {p.lead_name ?? `Lead #${p.lead_id}`}
        </Link>
        <div className="text-xs text-taupe mt-0.5 line-clamp-1">{p.subject}</div>
      </div>
      <div className="flex items-center gap-3 text-xs text-taupe">
        <span>v{p.version}</span>
        <StatusChip status={p.status} />
      </div>
      <Link href={`/proposals/${p.id}`} className="btn-primary !px-4 !py-2 !text-xs">
        <FileText size={14} /> {action}
      </Link>
    </Card>
  );
}
