import type { Config } from "tailwindcss";

// AgriSense — light / professional theme (see frontend/DESIGN.md).
// Clean white surfaces, agronomy green as the signal accent, amber for attention.
// Semantic tokens: instrument names (canvas/panel/ink/signal…) used by the new
// workspace components; the legacy set (background/surface/primary…) kept for the
// auth pages. All tuned for a white background.
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
        // Instrument tokens (new components) — light values
        canvas: "#FFFFFF",
        panel: "#F8FAF8",
        "panel-2": "#EEF3EE",
        hairline: "#E4EAE4",
        ink: "#16211B",
        "ink-dim": "#5E6E63",
        signal: {
          DEFAULT: "#15803D",
          dim: "#4F7D63",
          glow: "#157F3C",
          deep: "#0E5C2C",
        },
        amber: { DEFAULT: "#C2740B", dim: "#9A5E0A" },
        danger: { DEFAULT: "#DC2626", dim: "#B91C1C" },

        // Legacy semantic names (auth pages) — light
        background: "#FFFFFF",
        surface: "#FFFFFF",
        "surface-muted": "#F4F7F4",
        border: "#E4EAE4",
        "text-primary": "#16211B",
        "text-muted": "#5E6E63",
        primary: {
          50: "#F0FAF3",
          100: "#DCF3E3",
          200: "#BBE7C9",
          300: "#8AD5A4",
          400: "#52BC7A",
          500: "#22A55B",
          600: "#15803D",
          700: "#136B34",
          800: "#12572C",
          900: "#0E4023",
        },
        accent: {
          50: "#FDF6EC",
          100: "#FAEBD3",
          300: "#E3B45C",
          500: "#C2740B",
          700: "#8A530A",
        },
        status: {
          success: "#15803D",
          "success-chip": "#E7F5EC",
          error: "#DC2626",
          "error-chip": "#FBEAEA",
          info: "#0E7490",
          "info-chip": "#E4F3F6",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-space-grotesk)", "Space Grotesk", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 33, 27, 0.04), 0 4px 16px rgba(16, 33, 27, 0.05)",
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
