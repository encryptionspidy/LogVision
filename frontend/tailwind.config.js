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
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
