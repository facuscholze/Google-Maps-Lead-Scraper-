"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { useTheme } from "next-themes";
import {
  LayoutDashboard,
  Map as MapIcon,
  Users,
  FileText,
  Send,
  Settings,
  Plus,
  Moon,
  Sun,
  Building2,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { paths, components } from "@/lib/api-types";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

type LeadRow = components["schemas"]["LeadSummary"];
type LeadListResponse = components["schemas"]["LeadListResponse"];

const NAV_ITEMS = [
  { href: "/", label: "Inicio · Panel", icon: LayoutDashboard },
  { href: "/searches", label: "Descubrir", icon: MapIcon },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/proposals", label: "Propuestas", icon: FileText },
  { href: "/shipments", label: "Envíos", icon: Send },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

export function useCommandPalette() {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

export function CommandPalette({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [query, setQuery] = React.useState("");

  React.useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const { data: leadResults, isFetching } = useQuery({
    queryKey: ["palette-leads", query],
    queryFn: () =>
      api.get<LeadListResponse>(
        `/api/leads?q=${encodeURIComponent(query)}&page_size=8&include_unlinked=true`
      ),
    enabled: open && query.trim().length >= 2,
    placeholderData: (prev) => prev,
  });

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="top-[12%] translate-y-0 gap-0 overflow-hidden !p-0 sm:max-w-xl"
        aria-describedby={undefined}
      >
        <DialogTitle className="sr-only">Buscar y navegar</DialogTitle>
        <Command label="Buscar y navegar" shouldFilter={query.trim().length < 2}>
          <div className="flex items-center gap-2 border-b border-border px-4">
            {isFetching ? (
              <Loader2 size={16} className="animate-spin text-muted-foreground" />
            ) : (
              <Plus size={16} className="rotate-45 text-muted-foreground" />
            )}
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Buscá leads, secciones o acciones…"
              className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <kbd className="hidden shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
              ESC
            </kbd>
          </div>
          <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
            <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
              Sin resultados para «{query}».
            </Command.Empty>

            {query.trim().length < 2 && (
              <Command.Group
                heading={<GroupHeading>Secciones</GroupHeading>}
                className="[&_[cmdk-group-heading]]:contents"
              >
                {NAV_ITEMS.map((item) => (
                  <PaletteItem key={item.href} onSelect={() => go(item.href)}>
                    <item.icon size={16} className="text-muted-foreground" />
                    {item.label}
                  </PaletteItem>
                ))}
              </Command.Group>
            )}

            {query.trim().length < 2 && (
              <Command.Group heading={<GroupHeading>Acciones</GroupHeading>} className="[&_[cmdk-group-heading]]:contents">
                <PaletteItem onSelect={() => go("/searches/new")}>
                  <Plus size={16} className="text-accent-foreground" />
                  Nueva búsqueda
                </PaletteItem>
                <PaletteItem
                  onSelect={() => {
                    setTheme(resolvedTheme === "dark" ? "light" : "dark");
                    setOpen(false);
                  }}
                >
                  {resolvedTheme === "dark" ? (
                    <Sun size={16} className="text-muted-foreground" />
                  ) : (
                    <Moon size={16} className="text-muted-foreground" />
                  )}
                  Cambiar a tema {resolvedTheme === "dark" ? "claro" : "oscuro"}
                </PaletteItem>
              </Command.Group>
            )}

            {query.trim().length >= 2 && (leadResults?.items?.length ?? 0) > 0 && (
              <Command.Group heading={<GroupHeading>Leads</GroupHeading>} className="[&_[cmdk-group-heading]]:contents">
                {leadResults!.items.map((lead: LeadRow) => (
                  <PaletteItem key={lead.id} onSelect={() => go(`/leads/${lead.id}`)}>
                    <Building2 size={16} className="text-muted-foreground" />
                    <span className="flex-1 truncate">{lead.business_name}</span>
                    {lead.lead_score != null && (
                      <span className="font-mono text-[10px] text-accent-foreground">{lead.lead_score}</span>
                    )}
                  </PaletteItem>
                ))}
                <PaletteItem onSelect={() => go(`/leads?q=${encodeURIComponent(query)}`)}>
                  <Users size={16} className="text-muted-foreground" />
                  Ver todos los resultados en Leads
                </PaletteItem>
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

function GroupHeading({ children }: { children: React.ReactNode }) {
  return (
    <span className="block px-2 pb-1 pt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
      {children}
    </span>
  );
}

function PaletteItem({
  children,
  onSelect,
}: {
  children: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-md px-3 text-sm text-foreground aria-selected:bg-secondary"
    >
      {children}
    </Command.Item>
  );
}

// Referenciado para mantener el tipo `paths` en uso público del módulo de tipos.
export type { paths as ApiPaths };
