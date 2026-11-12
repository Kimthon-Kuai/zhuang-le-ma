/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 底色：磁带机身的深靛蓝，不是纯黑
        ink: {
          950: "#0b0e1a",
          900: "#11152a",
          800: "#1a1f3a",
          700: "#252b4d",
          600: "#343b66",
        },
        // 主色：录音键红
        tape: {
          DEFAULT: "#ff4d5e",
          deep: "#d92f43",
          soft: "#ff8a95",
        },
        // 副色：磁带标签的奶油黄
        label: {
          DEFAULT: "#f7e6b5",
          deep: "#e8cf87",
        },
        // 强调：荧光绿（终端光标）
        phosphor: "#7dffa8",
        // 强调：电光蓝（链接 / 信息）
        electric: "#6c8dff",
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Noto Sans SC"', "system-ui", "sans-serif"],
        body: ['"Noto Sans SC"', '"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', "Consolas", "monospace"],
      },
      boxShadow: {
        tape: "0 2px 0 var(--tape-shadow, #05070f), 0 10px 30px -10px rgba(0,0,0,0.7)",
        inset: "inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      keyframes: {
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        "bob": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        "blink": { "0%, 49%": { opacity: "1" }, "50%, 100%": { opacity: "0" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "spin-slow": "spin-slow 8s linear infinite",
        bob: "bob 2.4s ease-in-out infinite",
        blink: "blink 1s steps(1) infinite",
        "slide-up": "slide-up .35s cubic-bezier(.2,.8,.2,1) both",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [],
};
