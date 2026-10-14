import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: "AvaScho Lead Intelligence",
  description:
    "Plataforma de prospección comercial de innblock: buscá negocios, auditá su presencia digital, calificá oportunidades y aprobá propuestas con revisión humana.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0A0A0B" },
    { media: "(prefers-color-scheme: light)", color: "#F2F2F2" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-AR" suppressHydrationWarning>
      <head>
        {/* Fuentes de marca del mail (Archivo / Instrument Serif / Martian Mono).
            Cargadas por <link> (runtime browser) — el build no depende de red. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&family=Instrument+Serif:ital@0;1&family=Martian+Mono:wght@400;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased">
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
