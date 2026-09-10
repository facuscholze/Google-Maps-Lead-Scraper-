"use client";

import { ExternalLink, FileSpreadsheet } from "lucide-react";
import type { SheetsExportOutcome } from "@/lib/use-export-to-sheets";
import { cn } from "@/components/ui";

/** Inline confirmation shown after a successful "Enviar a Sheets". */
export function SheetsResultNote({
  outcome,
  className,
}: {
  outcome: SheetsExportOutcome | null;
  className?: string;
}) {
  if (!outcome) return null;
  return (
    <div
      className={cn(
        "rounded-xl bg-[#E6F4EA] text-[#1E8E3E] text-sm px-4 py-3 border border-[#B7E1C4] flex flex-wrap items-center gap-2",
        className
      )}
    >
      <FileSpreadsheet size={15} />
      <span>
        {outcome.rows_written === 0
          ? "Ningún lead coincidía con los filtros, no se escribió nada."
          : `${outcome.rows_written} ${outcome.rows_written === 1 ? "lead enviado" : "leads enviados"} a Google Sheets${
              outcome.sheet_name ? ` · pestaña «${outcome.sheet_name}»` : ""
            }.`}
      </span>
      <a
        href={outcome.spreadsheet_url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 underline underline-offset-2 font-medium"
      >
        Abrir la spreadsheet <ExternalLink size={13} />
      </a>
    </div>
  );
}
