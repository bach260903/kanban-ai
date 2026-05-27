import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'IBM Plex Sans'", "var(--font-sans)", "system-ui", "sans-serif"],
        display: ["'JetBrains Mono'", "ui-monospace", "Consolas", "monospace"],
        mono: ["'JetBrains Mono'", "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        brand: {
          50: "#F0FDFA",
          100: "#CCFBF1",
          200: "#99F6E4",
          300: "#5EEAD4",
          400: "#2DD4BF",
          500: "#14B8A6",
          600: "#0D9488",
          700: "#0F766E",
          800: "#115E59",
          900: "#134E4A",
        },
        cta: {
          DEFAULT: "#F97316",
          hover: "#EA580C",
          subtle: "#FFF7ED",
        },
        status: {
          todo: "#64748B",
          progress: "#0D9488",
          review: "#8B5CF6",
          done: "#10B981",
          rejected: "#EF4444",
          conflict: "#F59E0B",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive)",
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        chart: {
          1: "var(--chart-1)",
          2: "var(--chart-2)",
          3: "var(--chart-3)",
          4: "var(--chart-4)",
          5: "var(--chart-5)",
        },
        sidebar: {
          DEFAULT: "var(--sidebar)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        "elev-1": "0 1px 2px rgba(15, 23, 42, 0.06)",
        "elev-2": "0 4px 8px -2px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04)",
        "elev-3": "0 12px 20px -8px rgba(15, 23, 42, 0.12), 0 4px 8px -4px rgba(15, 23, 42, 0.06)",
        "ring-brand": "0 0 0 3px rgba(13, 148, 136, 0.18)",
        "ring-cta": "0 0 0 3px rgba(249, 115, 22, 0.22)",
      },
      keyframes: {
        "pulse-brand": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(13, 148, 136, 0.45)" },
          "70%": { boxShadow: "0 0 0 6px rgba(13, 148, 136, 0)" },
        },
        "slide-down": {
          "0%": { opacity: "0", transform: "translateY(-8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "pulse-brand": "pulse-brand 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-down": "slide-down 200ms ease-out",
        shimmer: "shimmer 2.4s linear infinite",
        "fade-in": "fade-in 150ms ease-out",
      },
    },
  },
  plugins: [],
};
export default config;
