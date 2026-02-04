import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontSize: {
        // UI Scale - optimized for clarity
        'xs': ['0.75rem', { lineHeight: '1rem', letterSpacing: '0' }],             // 12px - labels, badges
        'sm': ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '0' }],         // 14px - primary UI, body text
        'base': ['0.9375rem', { lineHeight: '1.5rem', letterSpacing: '0' }],       // 15px - emphasized UI
        // Reading Scale - comfortable for prose
        'lg': ['1rem', { lineHeight: '1.625rem', letterSpacing: '-0.01em' }],      // 16px - prose body
        'xl': ['1.125rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],   // 18px - lead text
        // Heading Scale - clean hierarchy
        '2xl': ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.015em' }],  // 20px - h4
        '3xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.02em' }],       // 24px - h3
        '4xl': ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.025em' }],      // 32px - h2
        '5xl': ['2.5rem', { lineHeight: '3rem', letterSpacing: '-0.03em' }],       // 40px - h1 hero
        '6xl': ['3rem', { lineHeight: '3.5rem', letterSpacing: '-0.03em' }],       // 48px - display
      },
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        info: "hsl(var(--info))",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "calc(var(--radius) + 0.25rem)",
        "2xl": "calc(var(--radius) + 0.5rem)",
      },
      fontFamily: {
        sans: [
          "var(--font-plus-jakarta-sans)",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        display: [
          "var(--font-plus-jakarta-sans)",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "var(--font-jetbrains-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        // Minimal shadows only for elevation when absolutely needed
        "subtle": "0 1px 2px 0 rgb(0 0 0 / 0.03)",
      },
    },
  },
  plugins: [],
};

export default config;
