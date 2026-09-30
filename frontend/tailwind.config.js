/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#120d0b",
        card: "#261912",
        card2: "#342318",
        bone: "#f6ead8",
        muted: "#e4d3bf",
        gold: "#f0c14d",
        blood: "#d6453d",
        pitch: "#1f7a4d",
        line: "#5a3d30",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
      },
      boxShadow: {
        card: "0 12px 30px rgba(0,0,0,0.28)",
      },
    },
  },
  plugins: [],
};
