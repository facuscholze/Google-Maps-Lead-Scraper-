"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Ban, Check, Mail, Plus, Trash2, Link2, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { EmailAccount, SuppressionEntry } from "@/lib/types";
import { Button, Card, EmptyState, ErrorNote, Spinner, StatusChip } from "@/components/ui";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | undefined>();
  const [success, setSuccess] = useState<string | undefined>();
  const [busyConnect, setBusyConnect] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [searchSupp, setSearchSupp] = useState("");

  const { data: accounts, isLoading: loadingAccounts } = useQuery<EmailAccount[]>({
    queryKey: ["email-accounts"],
    queryFn: () => api.get<EmailAccount[]>("/api/email-accounts"),
  });
  const { data: suppression, isLoading: loadingSupp } = useQuery<SuppressionEntry[]>({
    queryKey: ["suppression"],
    queryFn: () => api.get<SuppressionEntry[]>(`/api/suppression${searchSupp ? `?q=${encodeURIComponent(searchSupp)}` : ""}`),
  });

  const withNotice = <A extends unknown[]>(fn: (...args: A) => Promise<unknown>, ok?: string) => async (...args: A) => {
    setError(undefined);
    setSuccess(undefined);
    try {
      await fn(...args);
      await queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["suppression"] });
      if (ok) setSuccess(ok);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    }
  };

  const connectGmail = withNotice(async () => {
    setBusyConnect(true);
    try {
      const res = await api.post<{ url: string }>("/api/email-accounts/gmail/connect");
      window.open(res.url, "_blank");
    } finally {
      setBusyConnect(false);
    }
  });

  const deleteAccount = withNotice(async (id: number) => {
    await api.del(`/api/email-accounts/${id}`);
  }, "Cuenta eliminada.");

  const addSuppression = withNotice(async () => {
    await api.post("/api/suppression", { email: newEmail, reason: "MANUAL" });
    setNewEmail("");
  }, "Email agregado a la suppression list.");

  const removeSuppression = withNotice(async (id: number) => {
    await api.del(`/api/suppression/${id}`);
  }, "Entrada removida.");

  const [limitValue, setLimitValue] = useState<Record<number, number>>({});
  const setLimit = withNotice(async (id: number, limit: number) => {
    await api.patch(`/api/email-accounts/${id}?daily_limit=${limit}`);
    setLimitValue((prev) => ({ ...prev, [id]: limit }));
  }, "Límite actualizado.");

  if (loadingAccounts) return <Spinner label="Cargando configuración…" />;

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="font-display text-3xl font-semibold">Cuentas & envíos</h1>
        <p className="text-sm text-taupe mt-1">Conectá cuentas Gmail autorizadas y gestioná la lista de no-contacto.</p>
      </div>

      {error && <ErrorNote message={error} />}
      {success && <div className="rounded-xl bg-[#E6F4EA] text-[#1E8E3E] text-sm px-4 py-3">{success}</div>}

      {/* Email accounts */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="font-display text-xl font-semibold">Cuentas Gmail</h2>
            <p className="text-xs text-taupe">OAuth 2.0 — nunca pedimos contraseñas. Tokens cifrados en backend.</p>
          </div>
          <Button variant="outline" onClick={connectGmail} disabled={busyConnect}>
            <Link2 size={15} /> {busyConnect ? "Abriendo…" : "Conectar cuenta"}
          </Button>
        </div>
        {!accounts || accounts.length === 0 ? (
          <EmptyState
            icon={<Mail size={30} />}
            title="Sin cuentas conectadas"
            subtitle="Para enviar de verdad conectá una cuenta Gmail. En modo demo el sistema usa una cuenta mock local."
          />
        ) : (
          <div className="space-y-3">
            {accounts.map((a) => (
              <Card key={a.id} className="p-5 flex flex-wrap items-center gap-4">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold flex items-center gap-2">
                    {a.email}
                    {a.provider === "mock" ? (
                      <span className="chip bg-[#FFF3E0] text-[#B26A00]">demo</span>
                    ) : (
                      <StatusChip status={a.status} />
                    )}
                  </div>
                  <div className="text-xs text-taupe mt-0.5">
                    Límite diario: <b>{a.daily_limit}</b> · enviados hoy: {a.sent_today}
                    {a.last_sent_at ? ` · último envío ${new Date(a.last_sent_at).toLocaleString("es-UY")}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    className="input !w-24 !py-1.5 text-xs"
                    value={limitValue[a.id] ?? a.daily_limit}
                    onChange={(e) => setLimit(a.id, Number(e.target.value))}
                  >
                    {[3, 5, 10, 20, 50].map((v) => (
                      <option key={v} value={v}>{v}/día</option>
                    ))}
                  </select>
                  {a.provider !== "mock" && (
                    <Button variant="ghost" onClick={() => deleteAccount(a.id)} title="Desconectar">
                      <Trash2 size={15} />
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Sending policy summary */}
      <Card>
        <h2 className="font-display text-lg font-semibold mb-3">Política de envío responsable</h2>
        <ul className="text-sm text-ink/75 space-y-1.5">
          <li>✓ Los envíos requieren aprobación humana (estado APPROVED).</li>
          <li>✓ Emails con confianza LOW nunca se envían automáticamente.</li>
          <li>✓ Se respeta suppression list y DO_NOT_CONTACT.</li>
          <li>✓ Pausas variables entre envíos y límite diario por cuenta.</li>
          <li>✓ Horario permitido y días hábiles configurables (backend).</li>
          <li>✓ Sin mecanismos para evadir límites o políticas de Gmail.</li>
        </ul>
      </Card>

      {/* Suppression list */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="font-display text-xl font-semibold flex items-center gap-2">
              <Ban size={18} className="text-[#C5221F]" /> Suppression List
            </h2>
            <p className="text-xs text-taupe">DO_NOT_CONTACT — nunca volvemos a escribirles.</p>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 mb-3">
          <input
            className="input flex-1"
            placeholder="nuevo@email.com"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
          />
          <Button onClick={addSuppression} variant="outline">
            <Plus size={15} /> Agregar
          </Button>
        </div>
        <input className="input mb-3" placeholder="Buscar en la lista…" value={searchSupp} onChange={(e) => setSearchSupp(e.target.value)} />
        {loadingSupp ? (
          <Spinner label="Cargando…" />
        ) : !suppression || suppression.length === 0 ? (
          <EmptyState icon={<Ban size={26} />} title="Lista vacía" subtitle="Si alguien pide no recibir más mensajes, aparece acá y bloquea futuros envíos." />
        ) : (
          <Card className="!p-0 overflow-hidden">
            {suppression.map((entry) => (
              <div key={entry.id} className="flex items-center gap-3 px-5 py-3 border-b border-sandline last:border-0">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{entry.email}</div>
                  <div className="text-xs text-taupe">{entry.reason} · {new Date(entry.created_at).toLocaleDateString("es-UY")}</div>
                </div>
                <Button variant="ghost" onClick={() => removeSuppression(entry.id)} title="Quitar de la lista">
                  <Trash2 size={15} />
                </Button>
              </div>
            ))}
          </Card>
        )}
      </section>
    </div>
  );
}
