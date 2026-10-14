"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Map as MapIcon,
  Users,
  FileText,
  Send,
  Settings,
  LogOut,
  Plus,
  Search as SearchIcon,
  Moon,
  Sun,
  PanelLeftClose,
  PanelLeftOpen,
  MoreHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearSession } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { CommandPalette, useCommandPalette } from "@/components/command-palette";

const NAV = [
  { href: "/", label: "Inicio", icon: LayoutDashboard, exact: true },
  { href: "/searches", label: "Descubrir", icon: MapIcon },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/proposals", label: "Propuestas", icon: FileText },
  { href: "/shipments", label: "Envíos", icon: Send },
  { href: "/settings", label: "Ajustes", icon: Settings },
] as const;

const MOBILE_TABS = NAV.filter((n) => ["/", "/searches", "/leads", "/proposals"].includes(n.href));

function isActive(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(href + "/");
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const palette = useCommandPalette();
  const isLogin = pathname.startsWith("/login");

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar pathname={pathname} />
      <MobileTopBar onOpenPalette={() => palette.setOpen(true)} />
      <div className="flex min-h-screen flex-col transition-[padding] duration-200 md:pl-[var(--sidebar-w,240px)]">
        <DesktopTopBar onOpenPalette={() => palette.setOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 pb-28 pt-6 sm:px-6 md:pb-10 md:pt-8 lg:px-10">
          {children}
        </main>
      </div>
      <MobileTabBar pathname={pathname} />
      <CommandPalette open={palette.open} setOpen={palette.setOpen} />
    </div>
  );
}

/* ------------------------------------------------------------ sidebar --- */
function Sidebar({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [collapsed, setCollapsed] = React.useState(false);

  React.useEffect(() => {
    const stored = window.localStorage.getItem("avascho_sidebar_collapsed");
    if (stored === "1") setCollapsed(true);
  }, []);

  React.useEffect(() => {
    document.documentElement.style.setProperty("--sidebar-w", collapsed ? "72px" : "240px");
  }, [collapsed]);

  const toggle = () => {
    setCollapsed((v) => {
      window.localStorage.setItem("avascho_sidebar_collapsed", v ? "0" : "1");
      return !v;
    });
  };

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ type: "tween", duration: 0.18, ease: "easeOut" }}
      className="fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border bg-[#070707] text-white md:flex"
    >
      {/* --- marca --- */}
      <Link
        href="/"
        className={cn(
          "flex items-center gap-3 border-b border-white/10 px-5 py-5",
          collapsed && "justify-center px-0"
        )}
      >
        <span
          aria-hidden
          className="h-[18px] w-[18px] shrink-0 border-[3px] border-white bg-white shadow-[0_0_0_2px_#D90000]"
        />
        {!collapsed && (
          <span className="min-w-0">
            <span className="block font-display text-[15px] font-extrabold leading-none tracking-[0.22em]">
              AVASCHO
            </span>
            <span className="mt-1 block font-mono text-[8.5px] uppercase tracking-[0.3em] text-white/50">
              Lead Intelligence
            </span>
          </span>
        )}
        <span className="sr-only">AvaScho Lead Intelligence — Inicio</span>
      </Link>

      {/* --- CTA --- */}
      <div className={cn("p-3", collapsed && "px-2")}>
        <Button
          asChild
          size={collapsed ? "icon" : "default"}
          className={cn("w-full", collapsed && "mx-auto")}
        >
          <Link href="/searches/new" aria-label="Nueva búsqueda">
            <Plus size={16} />
            {!collapsed && "Nueva búsqueda"}
          </Link>
        </Button>
      </div>

      {/* --- navegación --- */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2" aria-label="Secciones">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href, "exact" in item ? item.exact : false);
          const link = (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex min-h-[44px] items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors",
                active
                  ? "bg-white/10 text-white before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-brand-red"
                  : "text-white/55 hover:bg-white/5 hover:text-white",
                collapsed && "justify-center px-0"
              )}
            >
              <item.icon size={18} className={cn(active && "text-brand-bright")} />
              {!collapsed && item.label}
            </Link>
          );
          if (!collapsed) return link;
          return (
            <Tooltip key={item.href}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{item.label}</TooltipContent>
            </Tooltip>
          );
        })}
      </nav>

      {/* --- footer --- */}
      <div className={cn("space-y-1 border-t border-white/10 p-3", collapsed && "px-2")}>
        <ThemeToggle collapsed={collapsed} />
        <SidebarButton
          icon={<LogOut size={18} />}
          label="Salir"
          collapsed={collapsed}
          onClick={() => {
            clearSession();
            router.push("/login");
          }}
        />
        <SidebarButton
          icon={collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          label={collapsed ? "Expandir menú" : "Colapsar menú"}
          collapsed={collapsed}
          onClick={toggle}
        />
      </div>
    </motion.aside>
  );
}

function SidebarButton({
  icon,
  label,
  collapsed,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  collapsed: boolean;
  onClick: () => void;
}) {
  const btn = (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex min-h-[44px] w-full items-center gap-3 rounded-md px-3 text-sm text-white/55 transition-colors hover:bg-white/5 hover:text-white",
        collapsed && "justify-center px-0"
      )}
    >
      {icon}
      {!collapsed && label}
    </button>
  );
  if (!collapsed) return btn;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{btn}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

function ThemeToggle({ collapsed }: { collapsed?: boolean }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const isDark = !mounted || resolvedTheme === "dark";
  return (
    <SidebarButton
      icon={isDark ? <Sun size={18} /> : <Moon size={18} />}
      label={isDark ? "Tema claro" : "Tema oscuro"}
      collapsed={!!collapsed}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    />
  );
}

/* ---------------------------------------------------------- top bars --- */
function DesktopTopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <header className="sticky top-0 z-20 hidden items-center justify-between gap-4 border-b border-border bg-background/85 px-6 py-3 backdrop-blur md:flex lg:px-10">
      <button
        type="button"
        onClick={onOpenPalette}
        className="flex min-h-[40px] w-full max-w-sm items-center gap-3 rounded-md border border-input bg-card px-4 text-sm text-muted-foreground transition hover:border-ring/60 hover:text-foreground"
      >
        <SearchIcon size={15} />
        <span className="flex-1 text-left">Buscar leads, secciones…</span>
        <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
          ⌘K
        </kbd>
      </button>
      <div className="flex items-center gap-2">
        <ThemeToggleIcon />
      </div>
    </header>
  );
}

function MobileTopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-border bg-background/85 px-4 py-3 backdrop-blur md:hidden">
      <Link href="/" className="flex items-center gap-2.5" aria-label="Inicio">
        <span
          aria-hidden
          className="h-4 w-4 border-[3px] border-foreground bg-foreground shadow-[0_0_0_2px_#D90000]"
        />
        <span className="font-display text-sm font-extrabold tracking-[0.22em]">AVASCHO</span>
      </Link>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" onClick={onOpenPalette} aria-label="Buscar (⌘K)">
          <SearchIcon size={18} />
        </Button>
        <ThemeToggleIcon />
      </div>
    </header>
  );
}

function ThemeToggleIcon() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const isDark = !mounted || resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </Button>
  );
}

/* ------------------------------------------------------- mobile tabs --- */
function MobileTabBar({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [moreOpen, setMoreOpen] = React.useState(false);
  const moreActive = ["/shipments", "/settings"].some((h) => isActive(pathname, h));

  return (
    <>
      <nav
        aria-label="Navegación principal"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-[#070707]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {MOBILE_TABS.map((item) => {
          const active = isActive(pathname, item.href, "exact" in item ? item.exact : false);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex min-h-[56px] flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
                active ? "text-white" : "text-white/50"
              )}
            >
              {active && (
                <span className="absolute inset-x-6 top-0 h-[3px] rounded-b-full bg-brand-red" />
              )}
              <item.icon size={20} className={cn(active && "text-brand-bright")} />
              {item.label}
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          aria-label="Más opciones"
          className={cn(
            "relative flex min-h-[56px] flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
            moreActive ? "text-white" : "text-white/50"
          )}
        >
          {moreActive && (
            <span className="absolute inset-x-6 top-0 h-[3px] rounded-b-full bg-brand-red" />
          )}
          <MoreHorizontal size={20} className={cn(moreActive && "text-brand-bright")} />
          Más
        </button>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="px-0 pb-8">
          <SheetHeader className="px-5">
            <SheetTitle>Más</SheetTitle>
            <SheetDescription>Secciones y acciones de la cuenta</SheetDescription>
          </SheetHeader>
          <div className="mt-2 px-3">
            {NAV.filter((n) => !MOBILE_TABS.includes(n)).map((item) => (
              <button
                key={item.href}
                type="button"
                onClick={() => {
                  setMoreOpen(false);
                  router.push(item.href);
                }}
                className="flex min-h-[48px] w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-foreground hover:bg-secondary"
              >
                <item.icon size={18} className="text-muted-foreground" />
                {item.label}
              </button>
            ))}
            <div className="my-2 h-px bg-border" />
            <button
              type="button"
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
              className="flex min-h-[48px] w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-destructive hover:bg-secondary"
            >
              <LogOut size={18} />
              Salir de la cuenta
            </button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
