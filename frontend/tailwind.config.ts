import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        coal: "#1C1B18",
        paper: "#FFFFFF",
        sand: "#F4F1EA",
        sandline: "#E8E0CF",
        gold: "#B08D3E",
        goldsoft: "#C9B27A",
        taupe: "#9A927F",
        night: "#0B0B0B",
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', "Georgia", '"Times New Roman"', "serif"],
        sans: ['"Inter"', "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      borderRadius: {
        xl2: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(17,17,17,0.04), 0 8px 24px rgba(17,17,17,0.05)",
        lift: "0 12px 32px rgba(17,17,17,0.12)",
      },
    },
  },
  plugins: [],
};
export default config;
