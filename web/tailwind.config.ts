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
        'xs': ['0.6875rem', { lineHeight: '0.9375rem', letterSpacing: '0' }],    // 11px/15px - labels, badges
        'sm': ['0.75rem', { lineHeight: '1rem', letterSpacing: '0' }],           // 12px/16px - secondary text
        'base': ['0.8125rem', { lineHeight: '1.125rem', letterSpacing: '0' }],   // 13px/18px - primary UI
        'md': ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '0' }],       // 14px/20px - emphasized
        'lg': ['1rem', { lineHeight: '1.5rem', letterSpacing: '-0.01em' }],      // 16px/24px - headings
        'xl': ['1.125rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }], // 18px/28px
        '2xl': ['1.25rem', { lineHeight: '1.875rem', letterSpacing: '-0.02em' }], // 20px/30px
        '3xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.02em' }],     // 24px/32px
        '4xl': ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.03em' }],     // 32px/40px
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
          vibrant: "hsl(var(--accent-vibrant))",
          "vibrant-foreground": "hsl(var(--accent-vibrant-foreground))",
          cyan: "hsl(var(--accent-cyan))",
          amber: "hsl(var(--accent-amber))",
          rose: "hsl(var(--accent-rose))",
          blue: "hsl(var(--accent-blue))",
          purple: "hsl(var(--accent-purple))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
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
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "var(--font-jetbrains-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "SF Mono",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      boxShadow: {
        glow: "0 0 20px -5px hsl(var(--accent-cyan) / 0.4)",
        "glow-sm": "0 0 10px -3px hsl(var(--accent-cyan) / 0.3)",
        "glow-lg": "0 0 30px -5px hsl(var(--accent-cyan) / 0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
