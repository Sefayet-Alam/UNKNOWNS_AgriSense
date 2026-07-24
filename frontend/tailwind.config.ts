import type { Config } from "tailwindcss";

// AgriSense — Delta Field Atlas. A light, editorial palette drawn from rice
// paper, paddy fields, jute fibre, river water, and fired clay.
const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          50: "#FFFDF6",
          100: "#F7F1DF",
          200: "#E9DDBD",
        },
        field: {
          50: "#F2F7EE",
          100: "#DFECD7",
          200: "#C2D8B6",
          300: "#96BB84",
          400: "#689454",
          500: "#3F6F35",
          600: "#315C2B",
          700: "#254A24",
          800: "#1E3E20",
          900: "#17351B",
        },
        jute: {
          100: "#F2E9D2",
          300: "#D9C28F",
          500: "#AB8B50",
        },
        clay: {
          50: "#FBF1EB",
          200: "#EDC2A8",
          400: "#C96F42",
          500: "#AD5835",
          700: "#7D3C27",
        },
        river: {
          50: "#EDF7F8",
          300: "#7FB6BF",
          500: "#43838D",
          700: "#2E646D",
        },
        ink: {
          DEFAULT: "#17261C",
          500: "#58675D",
          700: "#344338",
          900: "#17261C",
        },
        // Existing semantic names remain aliases so behavior-first components
        // can be restyled progressively without changing their contracts.
        canvas: "#FFFDF6",
        panel: "#FFFEF9",
        "panel-2": "#F7F1DF",
        hairline: "#DED8C8",
        "ink-dim": "#58675D",
        signal: {
          DEFAULT: "#315C2B",
          dim: "#689454",
          glow: "#3F6F35",
          deep: "#17351B",
        },
        amber: { DEFAULT: "#AB8B50", dim: "#7D663B" },
        danger: { DEFAULT: "#B74836", dim: "#913628" },

        // Legacy semantic names (auth pages) — light
        background: "#FFFDF6",
        surface: "#FFFEF9",
        "surface-muted": "#F7F1DF",
        border: "#DED8C8",
        "text-primary": "#17261C",
        "text-muted": "#58675D",
        primary: {
          50: "#F0FAF3",
          100: "#DCF3E3",
          200: "#BBE7C9",
          300: "#8AD5A4",
          400: "#52BC7A",
          500: "#3F6F35",
          600: "#315C2B",
          700: "#254A24",
          800: "#1E3E20",
          900: "#17351B",
        },
        accent: {
          50: "#FDF6EC",
          100: "#FAEBD3",
          300: "#E3B45C",
          500: "#AD5835",
          700: "#7D3C27",
        },
        status: {
          success: "#315C2B",
          "success-chip": "#E8F1E2",
          error: "#B74836",
          "error-chip": "#FBEDEA",
          info: "#2E646D",
          "info-chip": "#E8F3F4",
        },
      },
      fontFamily: {
        sans: ["Arial", "Helvetica Neue", "system-ui", "sans-serif"],
        display: ["Georgia", "Cambria", "Times New Roman", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(23,53,27,.05), 0 16px 35px -26px rgba(23,53,27,.35)",
        lift: "0 2px 0 rgba(23,53,27,.05), 0 28px 60px -30px rgba(23,53,27,.42)",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "stream-in": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        reveal: {
          "0%": { opacity: "0", transform: "translateY(8px)", filter: "blur(6px)" },
          "60%": { filter: "blur(0)" },
          "100%": { opacity: "1", transform: "translateY(0)", filter: "blur(0)" },
        },
        "glow-pulse": {
          "0%": { boxShadow: "0 0 0 0 rgba(21,128,61,0.0)" },
          "35%": { boxShadow: "0 0 0 3px rgba(21,128,61,0.18)" },
          "100%": { boxShadow: "0 0 0 0 rgba(21,128,61,0.0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        sway: {
          "0%, 100%": { transform: "rotate(-2.5deg)" },
          "50%": { transform: "rotate(2.5deg)" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
        "fade-in": "fade-in 0.25s ease-out",
        "stream-in": "stream-in 0.22s ease-out both",
        reveal: "reveal 0.5s ease-out both",
        "glow-pulse": "glow-pulse 1.4s ease-out 1",
        float: "float 6s ease-in-out infinite",
        sway: "sway 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
