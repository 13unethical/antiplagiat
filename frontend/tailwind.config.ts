import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-medeo)", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["13px", "20px"],
        base: ["15px", "24px"],
        lg: ["16px", "24px"],
        xl: ["18px", "24px"],
      },
      colors: {
        canvas: "#f4f4f5",
        gray: {
          50: "#f8f8f9",
          100: "#f1f1f3",
          200: "#e6e6e9",
          300: "#d3d4d8",
          400: "#73757d",
          500: "#62646c",
          600: "#4b4d54",
          700: "#36383e",
          800: "#26272c",
          900: "#17181b",
        },
        blue: {
          50: "#f2f3fc",
          100: "#e4e6f9",
          200: "#ced2f3",
          300: "#adb4ea",
          400: "#8089df",
          500: "#6470d6",
          600: "#5460cc",
          700: "#4550b6",
          800: "#384199",
        },
      },
      borderColor: { DEFAULT: "#e6e6e9" },
      borderRadius: { lg: "8px", xl: "10px", "2xl": "12px" },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
