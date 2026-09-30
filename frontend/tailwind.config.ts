import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        pitch: {
          950: "#07120c",
          900: "#0b1a12",
          800: "#11261a",
          700: "#1a3827",
          600: "#245038",
        },
        blood: {
          500: "#e0413a",
          600: "#c22f28",
          700: "#9c231d",
        },
        gold: {
          400: "#f5c451",
          500: "#e0a92c",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 10px 30px -18px rgba(0,0,0,0.9)",
      },
    },
  },
  plugins: [],
};

export default config;
