/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        sand: {
          50: "#fdf8f0",
        },
      },
    },
  },
  plugins: [],
};
