/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular"],
      },
      colors: {
        "accent-primary": "#ff8a5b",
        "accent-secondary": "#ffb38a",
        "accent-glow": "rgba(255,138,91,0.35)",
        "bg-primary": "#0b0b0c",
        "surface": "#121214",
        "text-primary": "#f5f5f5",
        "text-secondary": "#b8b8c0",
        "border": "rgba(255, 255, 255, 0.08)",
        "danger": "#ff4d6d",
        "warning": "#f59e0b",
        "success": "#22c55e",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: 0, transform: "translateY(5px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        slideDown: {
          "0%": { opacity: 0, height: 0, transform: "translateY(-10px)" },
          "100%": { opacity: 1, height: "auto", transform: "translateY(0)" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.3s ease-out forwards",
        slideDown: "slideDown 0.2s ease-out forwards",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
