import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: {
          50: "#EAF3EC", 100: "#CFE3D5", 200: "#A6CBB1", 300: "#74AC86",
          400: "#4A8C61", 500: "#357A4B", 600: "#2E6F40", 700: "#235732",
          800: "#1B4332", 900: "#13301F",
        },
        campfire: {
          50: "#FBEDE7", 100: "#F6D6C8", 200: "#EBAD93", 300: "#E0855F",
          400: "#D66A40", 500: "#C7522A", 600: "#A84323", 700: "#84341B",
          800: "#5F2613", 900: "#3D180C",
        },
        sand: { 50: "#FAF9F6", 100: "#F0EFED", 200: "#DFDCD9" },
      },
    },
  },
  plugins: [],
} satisfies Config;
