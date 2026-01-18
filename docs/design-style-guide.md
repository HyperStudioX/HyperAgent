# Frontend Style Guide

A clean, minimal, and modern design system using the Cursor aesthetic - pure neutrals with vibrant accent colors.

## Design Philosophy

- **Clean & Minimal** - No unnecessary shadows, borders only where needed
- **Pure Neutrals** - Clean white light theme, deep black dark theme
- **Vibrant Accents** - Cyan, amber, rose, and blue for interactive elements
- **Semantic Tokens** - Use CSS variables for consistency across themes
- **Flat Design** - No gradients (except brand elements), simple solid colors
- **Subtle Glow Effects** - Use glow for focus and hover states on key elements
- **Generous Whitespace** - Let content breathe
- **Reduced Motion** - Simple fade/opacity transitions only

## Semantic Color Tokens

**Always use semantic tokens instead of hardcoded colors.** This ensures consistency and makes theming easier.

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `bg-background` | Pure white | Deep black | Page backgrounds |
| `bg-card` | Off-white (98%) | Dark gray (7%) | Cards, elevated surfaces |
| `bg-secondary` | Light gray (96%) | Dark gray (12%) | Sidebars, subtle backgrounds |
| `bg-muted` | Light gray (94%) | Dark gray (14%) | Disabled states, read items |
| `text-foreground` | Near black (9%) | Light gray (89%) | Primary text |
| `text-muted-foreground` | Gray (45%) | Gray (50%) | Secondary text |
| `border-border` | Light gray (90%) | Dark gray (18%) | Standard borders |
| `border-subtle` | 50% opacity | 50% opacity | Card borders, containers |
| `border-muted` | 30% opacity | 30% opacity | Dividers, separators |
| `bg-primary` | Near black | Light gray | Primary buttons, accents |
| `text-primary-foreground` | Off-white | Near black | Text on primary |
| `bg-destructive` | Red | Red | Error states, delete buttons |
| `text-destructive` | Red | Red | Error text, warning icons |

### Accent Colors

| Token | HSL Value | Usage |
|-------|-----------|-------|
| `--accent-cyan` | 168 60% 68% | Primary accent, glow effects, brand |
| `--accent-amber` | 30 75% 72% | Warnings, highlights |
| `--accent-rose` | 310 60% 74% | Special features, notifications |
| `--accent-blue` | 210 100% 76% | Links, informational |

### Do's and Don'ts

```tsx
// DO: Use semantic tokens
className="bg-card border-subtle text-foreground"
className="bg-secondary text-muted-foreground"
className="hover:bg-secondary/50"
className="text-muted-foreground hover:text-foreground"

// DON'T: Hardcode colors
className="bg-white dark:bg-gray-800"
className="text-gray-600 dark:text-gray-400"
className="hover:bg-gray-100 dark:hover:bg-gray-700"
```

## Typography

### Font Family

Uses native system fonts for optimal performance and a native feel on each platform:

| Type | Stack | Renders As |
|------|-------|------------|
| `font-sans` | system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif | SF Pro (Mac), Segoe UI (Win), Roboto (Android) |
| `font-mono` | ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace | SF Mono (Mac), Consolas (Win) |

**Brand Title Font:** Plus Jakarta Sans (loaded via next/font) - used for `.brand-title` class.

**Benefits:**
- No external font loading for body text (faster page loads)
- Native look and feel on every platform
- Excellent CJK support built into system fonts

### Font Size Scale

| Class | Size | Usage |
|-------|------|-------|
| `text-xs` | 12px | Minimum readable - captions, timestamps, badges |
| `text-sm` | 14px | Secondary text, form labels |
| `text-base` | 16px | Primary body text |
| `text-lg` | 18px | Card titles, subsections |
| `text-xl` | 20px | Section headers |
| `text-2xl` | 24px | Page titles |
| `text-3xl` | 30px | Hero titles |
| `text-4xl` | 36px | Large hero titles |

**Note:** Minimum font size is 12px (`text-xs`) for WCAG accessibility.

### Font Weights

| Class | Weight | Usage |
|-------|--------|-------|
| (default) | 400 | Body text, descriptions |
| `font-medium` | 500 | Labels, buttons, primary status |
| `font-semibold` | 600 | Headings, important CTAs |
| `font-bold` | 700 | Page titles, strong emphasis |
| `font-extrabold` | 800 | Brand titles (`.brand-title`) |

## Color Palette

### CSS Variables (Light Mode - Clean White)

```css
--background: 0 0% 100%;      /* Pure white */
--foreground: 0 0% 9%;        /* Near black */
--primary: 0 0% 9%;           /* Near black */
--primary-foreground: 0 0% 98%;
--secondary: 0 0% 96%;        /* Light gray */
--muted: 0 0% 94%;
--muted-foreground: 0 0% 45%;
--border: 0 0% 90%;
--card: 0 0% 98%;
--ring: 0 0% 20%;
```

### CSS Variables (Dark Mode - Deep Black)

```css
--background: 0 0% 4%;        /* Deep black */
--foreground: 0 0% 89%;       /* Light gray */
--primary: 0 0% 89%;
--primary-foreground: 0 0% 4%;
--secondary: 0 0% 12%;        /* Dark gray */
--muted: 0 0% 14%;
--muted-foreground: 0 0% 50%;
--border: 0 0% 18%;
--card: 0 0% 7%;
--ring: 0 0% 80%;
```

### Accent Colors (Both Themes)

```css
--accent-cyan: 168 60% 68%;
--accent-amber: 30 75% 72%;
--accent-rose: 310 60% 74%;
--accent-blue: 210 100% 76%;
--accent-vibrant: 168 60% 68%;  /* Alias for primary accent */
```

## Brand Title

### Gradient Brand Title (Dark Mode)

In dark mode, brand titles use a gradient effect:

```tsx
<h1 className="brand-title brand-title-lg">HyperAgent</h1>
```

```css
/* Applied automatically in dark mode */
.dark .brand-title {
  background: linear-gradient(135deg,
    hsl(var(--foreground)) 0%,
    hsl(var(--accent-cyan)) 100%
  );
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### Brand Title Sizes

| Class | Size | Responsive |
|-------|------|------------|
| `.brand-title-sm` | 17px | Fixed |
| `.brand-title-md` | 32px | Fixed |
| `.brand-title-lg` | 40px | 48px on md+ |

## Buttons

### Primary Button (Flat)

```tsx
className="bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
```

**Full example:**
```tsx
<button className="w-full flex items-center justify-center gap-2 h-10 px-4 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
  <Plus className="w-4 h-4" />
  <span>Create</span>
</button>
```

### Accent Button (With Glow)

```tsx
className="btn-accent"
```

```css
.btn-accent {
  background-color: hsl(var(--accent-cyan));
  color: hsl(0 0% 9%);
}

.btn-accent:hover {
  background-color: hsl(var(--accent-cyan) / 0.9);
  box-shadow: 0 0 20px -5px hsl(var(--accent-cyan) / 0.5);
}
```

### Secondary Button

```tsx
className="bg-secondary text-foreground hover:bg-secondary/80 transition-colors"
```

### Outline Button

```tsx
className="border border-border bg-card text-foreground hover:bg-secondary/50 transition-colors"
```

### Ghost Button

```tsx
className="text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
```

### Destructive Button

```tsx
className="bg-destructive text-white hover:bg-destructive/90 transition-colors"
```

**Avoid:** Gradients (except brand), heavy shadows, scale effects, rotate animations on buttons.

## Glow Effects

Use glow effects sparingly for focus states and key interactive elements:

### Glow Utilities

```tsx
// Small glow
className="glow-sm"  // box-shadow: 0 0 10px -3px hsl(var(--accent-cyan) / 0.3)

// Medium glow
className="glow-md"  // box-shadow: 0 0 20px -5px hsl(var(--accent-cyan) / 0.4)

// Hover glow
className="hover-glow"

// Focus glow (for inputs)
className="focus-glow"

// Interactive element glow
className="interactive-glow"
```

### Focus Glow for Inputs

```css
.focus-glow:focus-visible {
  box-shadow: 0 0 0 2px hsl(var(--background)),
              0 0 0 4px hsl(var(--accent-cyan) / 0.5);
  outline: none;
}
```

## Selection States

### Pill/Chip Selection

```tsx
// Unselected
className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-card text-muted-foreground border border-border hover:bg-secondary/50 hover:text-foreground transition-colors"

// Selected (with ring and checkmark)
className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-secondary text-foreground ring-1 ring-foreground/50"
```

### Selection with Checkmark Indicator

```tsx
{isSelected ? (
  <span className="flex items-center justify-center w-4 h-4 rounded-full bg-foreground text-background">
    <Check className="w-3 h-3" strokeWidth={3} />
  </span>
) : (
  <span className="text-muted-foreground">
    <Icon className="w-5 h-5" />
  </span>
)}
```

## Input Areas

### Standard Input

```tsx
className="w-full rounded-lg border border-border bg-card px-4 py-3 text-base text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-foreground/30 transition-colors"
```

### Input with Focus Glow

```tsx
className="w-full rounded-lg border border-border bg-card px-4 py-3 text-base text-foreground placeholder:text-muted-foreground focus-glow"
```

### Large Textarea (Welcome Screen)

```tsx
<div className="relative flex flex-col bg-card rounded-xl border border-border focus-within:border-foreground/30 transition-colors">
  <textarea
    className="flex-1 w-full min-h-[100px] max-h-[200px] px-5 py-4 bg-transparent text-base text-foreground placeholder:text-muted-foreground focus:outline-none resize-none leading-relaxed"
    rows={3}
  />
  {/* Bottom bar */}
  <div className="flex items-center justify-between px-4 py-3 border-t border-border/50">
    <p className="text-xs text-muted-foreground">Keyboard hint</p>
    <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground">
      Send
    </button>
  </div>
</div>
```

## Cards & Containers

**Clean, minimal design - borders only, no shadows by default:**

```tsx
// Standard card
className="rounded-xl bg-card border border-border"

// Interactive card
className="bg-card rounded-xl p-6 border border-border transition-colors hover:bg-secondary/50"

// Interactive card with glow
className="bg-card rounded-xl p-6 border border-border interactive-glow"

// Container with dividers
className="divide-y divide-border"
```

**Avoid:** Shadow effects on cards, translate/scale hover transforms.

## Shadows

Use sparingly - prefer borders for structure:

| Class | Usage |
|-------|-------|
| `shadow-sm` | Subtle elevation (rare use) |
| `shadow` | Default elevation |
| `shadow-md` | Dropdowns, floating elements |
| `shadow-lg` | Modals, important overlays |

## Border Radius

| Class | Size | Usage |
|-------|------|-------|
| `rounded-md` | 6px | Badges, tags, small pills |
| `rounded-lg` | 8px | Buttons, inputs, icon containers |
| `rounded-xl` | 12px | Cards, containers, modals |
| `rounded-full` | 9999px | Avatars, status dots, circular pills |

## Icons

Use `lucide-react` for all icons:

| Size | Class | Usage |
|------|-------|-------|
| Small | `w-4 h-4` | Default, most buttons |
| Medium | `w-5 h-5` | Section headers, nav items, feature pills |
| Large | `w-6 h-6` | Feature cards, empty states |

### Icon Container

```tsx
// Neutral
<div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
  <Icon className="w-5 h-5 text-muted-foreground" />
</div>

// Inverted (for logos)
<div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
  <Icon className="w-4 h-4 text-background" />
</div>

// Accent glow
<div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center glow-sm">
  <Icon className="w-5 h-5 text-foreground" />
</div>
```

## Navigation

### Sidebar Nav Items

```tsx
// Active
className="bg-secondary text-foreground font-medium"

// Inactive
className="text-muted-foreground hover:bg-secondary/50 hover:text-foreground transition-colors"
```

## Badges

### Feature Tag

```tsx
className="px-2.5 py-1 text-xs bg-secondary text-muted-foreground rounded-md"
```

### Status Badge

```tsx
className="px-2 py-0.5 text-xs font-medium rounded-full bg-secondary text-muted-foreground"
```

## Modals & Dialogs

### Overlay

```tsx
className="fixed inset-0 z-50 bg-black/40"
```

### Modal Container

```tsx
className="w-full max-w-md bg-card rounded-xl border border-border"
```

## Dropdown Menus

```tsx
<div className="bg-card border border-border rounded-xl overflow-hidden min-w-[220px]">
  <button className="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-secondary/50">
    <Icon className="w-5 h-5 text-muted-foreground" />
    <div className="flex-1">
      <div className="text-sm font-medium">Title</div>
      <div className="text-xs text-muted-foreground">Description</div>
    </div>
  </button>
</div>
```

## Error States

```tsx
<div className="p-4 bg-destructive/10 border border-destructive/30 rounded-xl">
  <p className="text-sm text-destructive">{error}</p>
</div>
```

## Loading States

### Shimmer Effect

```tsx
<div className="shimmer h-4 w-32 rounded" />
```

### Typing Indicator

```tsx
<div className="flex gap-1">
  <span className="w-2 h-2 rounded-full bg-muted-foreground typing-dot" style={{ animationDelay: '0ms' }} />
  <span className="w-2 h-2 rounded-full bg-muted-foreground typing-dot" style={{ animationDelay: '150ms' }} />
  <span className="w-2 h-2 rounded-full bg-muted-foreground typing-dot" style={{ animationDelay: '300ms' }} />
</div>
```

### Streaming Cursor

```tsx
<span className="streaming-cursor">|</span>
```

## Transitions

Standard transition for all interactive elements:

```tsx
className="transition-colors"
```

**Global transitions are applied automatically:**
```css
* {
  transition-property: background-color, border-color, color, opacity;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
}
```

**Avoid:** `hover:-translate-y`, `hover:scale-*`, `transition-all`, complex animations.

## Touch Targets

Minimum 32px for interactive elements:

```tsx
className="min-h-[32px] min-w-[32px]"
```

For mobile-critical elements, use 44px:
```tsx
className="min-h-[44px] min-w-[44px]"
```

## Animations

Use simple, subtle animations with staggered delays:

```tsx
// Fade in
className="animate-fade-in"
style={{ animationDelay: '0.1s', animationFillMode: 'backwards' }}

// Slide up
className="animate-slide-up"
style={{ animationDelay: '0.2s', animationFillMode: 'backwards' }}

// Scale in
className="animate-scale-in"

// Slide in from left
className="animate-slide-in-left"

// Bounce in (for emphasis)
className="animate-bounce-in"
```

**Stagger pattern:** 0.1s, 0.2s, 0.3s, 0.4s for sequential elements.

## Scrollbars

Custom scrollbar styling (6px width, subtle appearance):

```css
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: hsl(var(--border));
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: hsl(var(--muted-foreground) / 0.3);
}
```

## Key Principles

1. **Pure neutrals** - No warm/cool tints, use pure black/white/grays
2. **Vibrant accents** - Use cyan accent for interactive elements and glow effects
3. **No scale/translate on hover** - Use background color changes and subtle glow instead
4. **Minimal shadows** - Borders provide structure, glow for emphasis
5. **Semantic colors only** - Never hardcode hex/rgb values in components
6. **Consistent spacing** - Use Tailwind's spacing scale (p-4, p-6, gap-3, etc.)
7. **Accessible** - 32px minimum touch targets, 12px minimum font size
8. **Simple transitions** - `transition-colors` for most interactions (global auto-applied)
9. **Ring for selection** - Use `ring-1 ring-foreground/50` for selected states
10. **Glow for focus** - Use `focus-glow` class for input focus states
11. **Brand gradient** - Dark mode brand titles use foreground-to-cyan gradient
