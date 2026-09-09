"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import { ErrorNote } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@avascho.com");
  const [password, setPassword] = useState("demo-avascho-2026");
  const [error, setError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      const res = await api.post<{ access_token: string }>("/api/auth/login", { email, password });
      setToken(res.access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-sand flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="font-display font-bold tracking-[0.34em] text-3xl text-ink">AVASCHO</div>
          <div className="text-[10px] tracking-[0.4em] text-gold uppercase mt-2">Lead Intelligence</div>
          <p className="text-sm text-taupe mt-5">Buscá negocios. Investigá su presencia digital. Convertí oportunidades en conversaciones.</p>
        </div>
        <form onSubmit={submit} className="card p-8 space-y-4">
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div>
            <label className="label">Contraseña</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          <ErrorNote message={error} />
          <button className="btn-primary w-full !py-3" disabled={busy}>
            {busy ? "Ingresando…" : "Ingresar"}
          </button>
          <p className="text-center text-xs text-taupe pt-1">Demo: demo@avascho.com · demo-avascho-2026</p>
        </form>
      </div>
    </div>
  );
}
