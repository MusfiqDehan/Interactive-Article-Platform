import typography from "@tailwindcss/typography";
import animate from "tailwindcss-animate";
import type { Config } from "tailwindcss";

/** shadcn tokens read `rgb(var(--x) / <alpha>)`, so opacity modifiers work. */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
          // `DEFAULT` is what makes the two systems coexist: shadcn components
          // use `bg-primary`, while the ~30 existing files using
          // `bg-primary-600` keep resolving against the numbered palette above.
          // Overwriting this key with a single colour, as `shadcn init` does,
          // would silently break every one of them.
          DEFAULT: token("primary"),
          foreground: token("primary-foreground"),
        },
        accent: {
          50: "#faf5ff",
          100: "#f3e8ff",
          200: "#e9d5ff",
          300: "#d8b4fe",
          400: "#c084fc",
          500: "#a855f7",
          600: "#9333ea",
          700: "#7e22ce",
          800: "#6b21a8",
          900: "#581c87",
          DEFAULT: token("accent"),
          foreground: token("accent-foreground"),
        },

        // Non-colliding shadcn tokens.
        background: token("background"),
        foreground: token("foreground"),
        card: { DEFAULT: token("card"), foreground: token("card-foreground") },
        popover: { DEFAULT: token("popover"), foreground: token("popover-foreground") },
        secondary: {
          DEFAULT: token("secondary"),
          foreground: token("secondary-foreground"),
        },
        muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
        destructive: {
          DEFAULT: token("destructive"),
          foreground: token("destructive-foreground"),
        },
        border: token("border"),
        input: token("input"),
        ring: token("ring"),
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-hind-siliguri)", "Hind Siliguri", "system-ui", "sans-serif"],
        display: ["var(--font-hind-siliguri)", "Hind Siliguri", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "grid-white":
          "url(\"data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' width='32' height='32' fill='none' stroke='white'%3e%3cpath d='M0 .5H31.5V32'/%3e%3c/svg%3e\")",
        "grid-black":
          "url(\"data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' width='32' height='32' fill='none' stroke='black'%3e%3cpath d='M0 .5H31.5V32'/%3e%3c/svg%3e\")",
      },
    },
  },
  // `animate` was already being *used* by Modal.tsx (`animate-in`, `zoom-in-95`)
  // without ever being installed, so those animations silently did nothing.
  plugins: [typography, animate],
};

export default config;
