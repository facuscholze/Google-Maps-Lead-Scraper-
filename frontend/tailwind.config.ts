import type { Config } from "tailwindcss";

/**
 * innblock design system — tokens live in app/globals.css as CSS variables.
 * Brand source of truth: "nuevo html mail.html" (red #d90000 · black #070707).
 *
 * Legacy color names (ink/sand/gold/taupe/…) are kept as aliases pointing at
 * the new tokens so pages from earlier iterations stay coherent until their
 * redesign phase rewrites them on top of components/ui.
 */
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT: "hsl(var(--popover) / <alpha-value>)",
          foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
        },
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary) / <alpha-value>)",
          foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
        },
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        well: "hsl(var(--well) / <alpha-value>)",
        // Brand literals (from the mail template — do not tune)
        brand: {
          red: "#D90000",
          bright: "#FF3B30",
          black: "#070707",
        },
        // --- legacy aliases (Fase 0 UI) ------------------------------
        ink: "hsl(var(--foreground) / <alpha-value>)",
        coal: "hsl(var(--card) / <alpha-value>)",
        paper: "hsl(var(--card) / <alpha-value>)",
        sand: "hsl(var(--well) / <alpha-value>)",
        sandline: "hsl(var(--border) / <alpha-value>)",
        gold: "hsl(var(--primary) / <alpha-value>)",
        goldsoft: "#FF3B30",
        taupe: "hsl(var(--muted-foreground) / <alpha-value>)",
        night: "#070707",
      },
      fontFamily: {
        sans: ["Archivo", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Archivo", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        serif: ["\"Instrument Serif\"", "Georgia", "\"Times New Roman\"", "serif"],
        mono: ["\"Martian Mono\"", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl2: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.20), 0 8px 24px rgba(0,0,0,0.18)",
        lift: "0 12px 32px rgba(0,0,0,0.35)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "fade-up": "fade-up 220ms cubic-bezier(0.2,0.8,0.2,1)",
        "scale-in": "scale-in 160ms cubic-bezier(0.2,0.8,0.2,1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
