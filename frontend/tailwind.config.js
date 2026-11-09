/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070708",
          900: "#0b0b0d",
          850: "#101013",
          800: "#151519",
          750: "#1b1b20",
          700: "#232329",
        },
        duck: {
          50: "#fffbe6",
          100: "#fff3b8",
          200: "#ffe97a",
          300: "#ffdc3d",
          400: "#ffcb05",
          500: "#f2b705",
          600: "#c98f02",
          700: "#9a6b05",
        },
        amber: {
          glow: "#ffb43c",
        },
        danger: "#ff6b57",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        display: [
          "Robtronika",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        glass: "0 24px 80px -32px rgba(0,0,0,0.9), inset 0 1px 0 rgba(255,255,255,0.04)",
        glow: "0 0 60px -10px rgba(255,203,5,0.35)",
        "glow-sm": "0 0 28px -8px rgba(255,203,5,0.4)",
      },
      backgroundImage: {
        "duck-gradient": "linear-gradient(135deg, #ffe97a 0%, #ffcb05 45%, #f2b705 100%)",
        "panel-gradient": "linear-gradient(180deg, rgba(255,255,255,0.035) 0%, rgba(255,255,255,0.008) 100%)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "0.55", transform: "scale(0.98)" },
          "50%": { opacity: "1", transform: "scale(1.02)" },
        },
      },
      animation: {
        "fade-up": "fade-up 340ms cubic-bezier(0.22,1,0.36,1) both",
        shimmer: "shimmer 1.8s linear infinite",
        "pulse-soft": "pulse-soft 2.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
