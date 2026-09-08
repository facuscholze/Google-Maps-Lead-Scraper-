"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Users,
  FileText,
  Mail,
  Settings,
  LogOut,
  Plus,
  SearchCheck,
} from "lucide-react";
import { cn } from "@/components/ui";
import { clearSession } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/proposals", label: "Propuestas", icon: FileText },
  { href: "/searches", label: "Búsquedas", icon: SearchCheck },
  { href: "/settings", label: "Cuentas & envíos", icon: Mail },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname?.startsWith("/login");

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar */}
      <aside className="md:w-60 shrink-0 bg-night text-white md:min-h-screen flex md:flex-col md:fixed md:inset-y-0">
        <div className="flex-1 flex flex-col w-full">
          <Link href="/" className="px-6 py-6 block">
            <div className="font-display font-bold tracking-[0.28em] text-lg">AVASCHO</div>
            <div className="text-[9px] tracking-[0.3em] text-goldsoft uppercase mt-1">Lead Intelligence</div>
          </Link>
          <nav className="flex md:flex-col gap-1 overflow-x-auto px-3 flex-1">
            {NAV.map((item) => {
              const active = pathname === item.href || pathname?.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm whitespace-nowrap transition",
                    active ? "bg-white/10 text-white" : "text-white/55 hover:text-white hover:bg-white/5"
                  )}
                >
                  <item.icon size={17} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="p-3 border-t border-white/10 hidden md:block">
            <button
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
              className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm text-white/55 hover:text-white hover:bg-white/5"
            >
              <LogOut size={17} /> Salir
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 md:ml-60 flex flex-col">
        <header className="sticky top-0 z-20 bg-sand/90 backdrop-blur border-b border-sandline px-5 md:px-10 py-4 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="font-display text-xl md:text-2xl font-semibold truncate text-ink">
              AvaScho Lead Intelligence
            </div>
            <div className="text-xs text-taupe hidden sm:block">Convertí búsquedas en oportunidades comerciales.</div>
          </div>
          <Link href="/searches/new" className="btn-primary shrink-0 !px-4 !py-2">
            <Plus size={16} /> <span className="hidden sm:inline">Nueva búsqueda</span>
            <span className="sm:hidden">Buscar</span>
          </Link>
        </header>
        <main className="px-5 md:px-10 py-8 max-w-[1400px] w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
