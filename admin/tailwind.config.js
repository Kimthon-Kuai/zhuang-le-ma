/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#0b0e1a", 900: "#11152a", 800: "#1a1f3a", 700: "#252b4d", 600: "#343b66" },
        tape: { DEFAULT: "#ff4d5e", deep: "#d92f43", soft: "#ff8a95" },
        label: { DEFAULT: "#f7e6b5", deep: "#e8cf87" },
        phosphor: "#7dffa8",
        electric: "#6c8dff",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        body: ['"Noto Sans SC"', '"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
