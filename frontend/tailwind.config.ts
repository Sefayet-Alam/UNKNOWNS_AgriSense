import type { Config } from "tailwindcss";

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
        primary: {
          50: "#F2F9EE",
          100: "#E1F0D8",
          200: "#C3E1B4",
          300: "#A0CD8A",
          400: "#7DB868",
          500: "#5B9A48",
          600: "#47823A",
          700: "#386830",
          800: "#2E5228",
          900: "#253F21",
        },
        accent: {
          50: "#FDF8EC",
          100: "#FBF0D3",
          300: "#EFCB6E",
          500: "#D99A1F",
          700: "#7A5610",
        },
        // Light surfaces / text
        background: "#F7FAF5",
        surface: "#FFFFFF",
        "surface-muted": "#F0F5EC",
        border: "#DCE7D6",
        "text-primary": "#1B2A17",
        "text-muted": "#5B6B57",
        // Dark-mode tokens (applied via .dark selectors in globals.css / utilities)
        dark: {
          background: "#10190E",
          surface: "#1C2818",
          "surface-muted": "#22301C",
          border: "#2E3F29",
          text: "#EAF3E4",
          "text-muted": "#9FB39A",
        },
        status: {
          success: "#1F6E40",
          "success-chip": "#DCEFE2",
          error: "#C6423A",
          "error-chip": "#FBE7E5",
          info: "#2563A8",
          "info-chip": "#E6F0FA",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-sora)", "Sora", "system-ui", "sans-serif"],
      },
      keyframes: {
        "pulse-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
        shimmer: "shimmer 1.6s linear infinite",
        "fade-in": "fade-in 0.25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
