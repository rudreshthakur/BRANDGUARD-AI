/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#16213A", soft: "#2B3754", line: "#3A4766" },
        paper: { DEFAULT: "#F6F7F9", card: "#FFFFFF", edge: "#E3E6EC", rule: "#D3D8E1" },
        graphite: { DEFAULT: "#3D4556", mute: "#6B7385", faint: "#9AA1B0" },
        proof: { DEFAULT: "#2949C6", dark: "#1F389C", tint: "#EAEEFB" },
        sev: { critical: "#A1161B", high: "#C2410C", medium: "#A15C07", low: "#55607A" },
        ev: { conflict: "#C2410C", gap: "#7A4BC2", ok: "#18794E", outdated: "#B4540A", rule: "#A1161B", ctx: "#2949C6" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ['"Source Serif 4"', "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
