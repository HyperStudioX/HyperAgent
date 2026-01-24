# Frontend Style Guide

A warm, minimal design system inspired by natural materials - terracotta accents, warm neutrals, flat design, and clarity over decoration.

## Design Philosophy

- **Radically Minimal** - No shadows, borders only where structure is needed
- **Warm Neutrals** - Warm stone light theme, warm charcoal dark theme with subtle brown undertones
- **Terracotta Primary** - Rich, earthy terracotta as the primary accent color for emphasis
- **Semantic Tokens** - Use CSS variables for consistency across themes
- **Ultra-Flat Design** - Borders for structure, no glows or effects
- **Subtle Interactions** - Minimal hover states, focus on clarity over decoration
- **Generous Whitespace** - Let content breathe with consistent spacing
- **No Micro-Interactions** - Avoid scale/transform effects, keep it simple
- **Reduced Motion** - Respects prefers-reduced-motion for accessibility

## Semantic Color Tokens

**Always use semantic tokens instead of hardcoded colors.** This ensures consistency and makes theming easier.

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `bg-background` | Warm off-white (30 15% 98%) | Warm charcoal (25 8% 7%) | Page backgrounds |
| `bg-card` | Warm white (30 10% 100%) | Deep warm black (25 10% 4%) | Editor areas (chat input, message list), cards, elevated surfaces |
| `bg-secondary` | Warm beige (30 12% 96%) | Warm dark gray (25 6% 12%) | Sidebars, subtle backgrounds |
| `bg-muted` | Warm taupe (28 10% 94%) | Warm dark brown (25 6% 14%) | Disabled states, read items |
| `text-foreground` | Warm dark brown (25 8% 12%) | Warm off-white (30 10% 92%) | Primary text |
| `text-muted-foreground` | Warm gray (25 5% 45%) | Warm gray (28 5% 50%) | Secondary text |
| `border-border` | Warm light beige (28 8% 93%) | Warm dark brown (25 6% 16%) | Standard borders |
| `border-border/50` | 50% opacity | 50% opacity | Card borders, containers |
| `border-border/30` | 30% opacity | 30% opacity | Dividers, separators |
| `bg-primary` | Rich terracotta (18 65% 42%) | Bright terracotta (18 70% 58%) | Primary buttons, interactive accents |
| `text-primary-foreground` | Warm white (30 10% 100%) | Deep warm black (25 10% 4%) | Text on primary |
| `bg-destructive` | Red (0 72% 51%) | Red (0 72% 55%) | Error states, delete buttons |
| `text-destructive` | Red | Red | Error text, warning icons |

### Interactive States

Interactive elements use terracotta primary for emphasis, warm neutrals for subtle states:

| State | Color Treatment |
|-------|-----------------|
| Default | `bg-card text-foreground` |
| Hover | `bg-secondary text-foreground` or `bg-muted` |
| Active/Selected Primary | `bg-primary text-primary-foreground` (terracotta accent) |
| Active/Selected Subtle | `bg-secondary text-foreground` (warm neutral) |
| Focus | `ring-2 ring-primary` (terracotta ring) |
| Disabled | `opacity-50` |

**Warm Accent Philosophy:**
- Terracotta primary (`bg-primary`) for high-emphasis interactive elements (primary buttons, active states)
- Warm neutrals for subtle states and secondary actions
- No glows or decorative effects - flat design maintained
- Focus on hierarchy through typography weight, spacing, and strategic use of terracotta
- Links can use terracotta for emphasis or subtle underline for minimal style

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

### CSS Variables (Light Mode - Warm Stone)

```css
--background: 30 15% 98%;     /* Warm off-white with peachy undertone - site background */
--foreground: 25 8% 12%;      /* Warm dark brown - primary text */
--primary: 18 65% 42%;        /* Rich terracotta - primary accent */
--primary-foreground: 30 10% 100%;  /* Warm white - text on terracotta */
--secondary: 30 12% 96%;      /* Warm beige */
--muted: 28 10% 94%;          /* Warm taupe */
--muted-foreground: 25 5% 45%;
--border: 28 8% 93%;          /* Warm light beige */
--card: 30 10% 100%;          /* Warm white - editor areas (chat input, message list) */
--ring: 18 55% 42%;           /* Terracotta focus ring */
```

### CSS Variables (Dark Mode - Warm Charcoal)

```css
--background: 25 8% 7%;       /* Warm charcoal - site background */
--foreground: 30 10% 92%;     /* Warm off-white - primary text */
--primary: 18 70% 58%;        /* Bright terracotta - primary accent */
--primary-foreground: 25 10% 4%;  /* Deep warm black - text on terracotta */
--secondary: 25 6% 12%;       /* Warm dark gray */
--muted: 25 6% 14%;           /* Warm dark brown */
--muted-foreground: 28 5% 50%;
--border: 25 6% 16%;          /* Warm dark brown */
--card: 25 10% 4%;            /* Deep warm black - editor areas (chat input, message list) */
--ring: 18 60% 65%;           /* Lighter terracotta focus ring */
```

### Status Colors (Both Themes)

Use terracotta for primary actions, red for destructive states:

```css
/* Primary - terracotta accent */
--primary: 18 65% 42%;        /* Light mode - rich terracotta */
--primary: 18 70% 58%;        /* Dark mode - bright terracotta */

/* Destructive/Error - red */
--destructive: 0 72% 51%;     /* Light mode - red */
--destructive: 0 72% 55%;     /* Dark mode - red */

/* Success/Info use warm neutral foreground */
/* Terracotta used for emphasis and primary actions */
```

## Brand Title

Brand titles use simple, clean typography with no gradients or effects:

```tsx
<h1 className="brand-title brand-title-lg">HyperAgent</h1>
```

```css
.brand-title {
  font-family: var(--font-plus-jakarta-sans), system-ui, sans-serif;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: hsl(var(--foreground));
  /* No gradients or effects */
}
```

### Brand Title Sizes

| Class | Size | Responsive |
|-------|------|------------|
| `.brand-title-sm` | 17px | Fixed |
| `.brand-title-md` | 32px | Fixed |
| `.brand-title-lg` | 40px | 48px on md+ |

## Buttons

All buttons use the Button component with variant props. Standard button includes:
- No transform effects (no scale, translate, or rotate)
- Subtle color transitions only: `transition-colors duration-150`
- Minimum 32px touch target (44px for mobile-critical actions)

### Button Component Usage

```tsx
import { Button } from "@/components/ui/button";

// Default button (subtle, secondary style)
<Button variant="default">Save</Button>

// Primary button (inverted colors for emphasis)
<Button variant="primary">Continue</Button>

// Secondary button (even more subtle)
<Button variant="secondary">Cancel</Button>

// Ghost button (minimal, transparent)
<Button variant="ghost">View More</Button>

// Destructive button (only colored button)
<Button variant="destructive">Delete</Button>

// Outline button
<Button variant="outline">Settings</Button>
```

### Button Variants

#### Default
```tsx
className="bg-secondary text-foreground hover:bg-muted border border-border/50 transition-colors"
```
**Usage:** Non-critical actions, form buttons, secondary CTAs

#### Primary (Terracotta Accent)
```tsx
className="bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
```
**Usage:** Important actions requiring high visibility (Continue, Submit, primary CTAs)

#### Secondary
```tsx
className="bg-muted text-foreground hover:bg-muted/80 border border-border/30 transition-colors"
```
**Usage:** Cancel actions, alternative options

#### Ghost
```tsx
className="hover:bg-secondary hover:text-foreground transition-colors"
```
**Usage:** Icon buttons, menu items, minimal actions

#### Outline
```tsx
className="border border-border bg-transparent hover:bg-secondary hover:text-foreground transition-colors"
```
**Usage:** Secondary actions, alternative choices

#### Destructive (Only Colored Button)
```tsx
className="bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
```
**Usage:** Delete, remove, destructive actions

### Button Sizes

```tsx
size="default"  // h-9 px-4 py-2
size="sm"       // h-8 px-3 text-xs
size="lg"       // h-10 px-8
size="icon"     // h-9 w-9 (square)
```

### Button Best Practices

**DO:**
- Use `variant="primary"` for primary CTAs (terracotta background)
- Keep transitions to `transition-colors` only
- Use clear typography hierarchy instead of effects
- Maintain 32px minimum touch targets

**DON'T:**
- Don't use transform effects (scale, translate, rotate)
- Don't use shadows except on destructive in rare cases
- Don't use colors beyond terracotta primary and warm neutrals
- Don't add glow effects or decorative elements

## Focus States

Use terracotta rings for focus states, no glow effects:

```tsx
// Focus ring (for all interactive elements)
className="focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:outline-none"
```

**Focus Ring Philosophy:**
- Use warm terracotta `ring-primary` for accessibility and brand consistency
- Never use box-shadow or glow effects
- Ring offset of 2px for clear separation
- Remove default outline with `outline-none`

**Examples:**

```tsx
// Button focus
<button className="... focus-visible:ring-2 focus-visible:ring-primary">
  Click me
</button>

// Input focus
<input className="... focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2" />

// Link focus
<a className="... focus-visible:ring-2 focus-visible:ring-primary focus-visible:rounded">
  Read more
</a>
```

## Selection States

### Pill/Chip Selection

Use foreground/background inversion for selected states with thin borders:

```tsx
// Unselected
className="flex items-center gap-2 px-3 py-2 rounded-sm text-sm font-medium bg-card text-muted-foreground border border-border hover:bg-secondary hover:text-foreground transition-colors"

// Selected (with thin border for contrast)
className="flex items-center gap-2 px-3 py-2 rounded-sm text-sm font-medium bg-secondary text-foreground border border-foreground/15 transition-colors"
```

**Selection Border Guidelines:**
- Use `border` (1px) - always thin borders, never `border-2` or thicker
- Use low opacity for subtle contrast: `border-foreground/15` (15% opacity)
- Border radius: `rounded-sm` (8px) for selection items

### Selection with Checkmark Indicator

```tsx
{isSelected ? (
  <span className="flex items-center justify-center w-4 h-4 rounded-full bg-background text-foreground">
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
className="w-full rounded-lg border border-border bg-card px-4 py-3 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 transition-colors"
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

**Ultra-minimal design - borders only, no shadows:**

```tsx
// Standard card
className="rounded-xl bg-card border border-border"

// Interactive card
className="bg-card rounded-xl p-6 border border-border transition-colors hover:bg-secondary/50"

// Container with dividers
className="divide-y divide-border"
```

**Never use:** Shadows, glows, gradients, or transform effects.

## Shadows

**Do not use shadows.** Use borders for all structure and hierarchy.

If absolutely necessary for critical overlays (modals), use minimal shadow:

```tsx
// Only for critical overlays
className="shadow-sm"  // box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)
```

**Never use:** `shadow`, `shadow-md`, `shadow-lg`, `shadow-xl`, or any decorative shadows.

## Border Thickness

**Always use thin borders (1px) - never use thicker borders:**

```tsx
// DO: Use thin border (1px)
className="border border-border"
className="border border-foreground/15"  // For selection states with low opacity

// DON'T: Use thicker borders
className="border-2 border-border"  // ❌ Never use border-2 or thicker
```

**Border Opacity Guidelines:**
- Standard borders: `border-border` (full opacity)
- Card/container borders: `border-border/50` (50% opacity)
- Dividers/separators: `border-border/30` (30% opacity)
- Selection states: `border-foreground/15` (15% opacity for subtle contrast)

**Philosophy:**
- All borders are 1px (`border`) - thin and minimal
- Use opacity to create visual hierarchy, not thickness
- Borders provide structure without visual weight

## Border Radius

Systematic border radius hierarchy for visual consistency:

| Class | Size | Usage |
|-------|------|-------|
| `rounded-sm` | 8px | Selection items (sidebar items, list selections), small badges, minimal elements |
| `rounded-md` | 10px | Badges, tags, tool indicators |
| `rounded-lg` | 12px | Buttons, inputs, icon buttons, pills, chips, agent selection buttons |
| `rounded-xl` | 16px | Cards, containers, modals, input areas |
| `rounded-2xl` | 20px | Large containers, hero sections |
| `rounded-full` | 9999px | Avatars, status dots, circular pills |

**Hierarchy Philosophy:**
- Large containers (hero sections) = `rounded-2xl` (20px)
- Standard containers (cards, modals) = `rounded-xl` (16px)
- Interactive elements (buttons, inputs) = `rounded-lg` (12px)
- Selection items (sidebar items, list selections) = `rounded-sm` (8px)
- Smaller elements (pills, chips) = `rounded-lg` (12px)
- Micro elements (badges, tags) = `rounded-md` (10px)

**Note:** Border radius values are calculated from `--radius: 0.75rem` (12px) base:
- `rounded-sm` = `calc(var(--radius) - 4px)` = 8px
- `rounded-md` = `calc(var(--radius) - 2px)` = 10px
- `rounded-lg` = `var(--radius)` = 12px
- `rounded-xl` = `calc(var(--radius) + 0.25rem)` = 16px
- `rounded-2xl` = `calc(var(--radius) + 0.5rem)` = 20px

```tsx
// Example: Chat input container
<div className="bg-card rounded-xl border border-border">
  <textarea className="..." />
  <button className="rounded-lg ...">Send</button>
</div>
```

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

Only use color transitions, no transform effects:

```tsx
// Default transition (applied globally)
className="transition-colors"

// Explicit when needed
className="transition-colors duration-150"
```

**Global transitions applied automatically:**
```css
* {
  transition-property: background-color, border-color, color, opacity;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
}
```

**Never use:**
- `transition-all` (use `transition-colors` only)
- Transform effects (`scale`, `translate`, `rotate`)
- Shadow transitions
- Complex multi-property animations

**Minimal interaction philosophy:**
- Hover: Background color change only (warm neutrals)
- Active: Terracotta primary for high-emphasis states
- Focus: Terracotta ring (via `ring-primary`)
- Loading: Simple opacity fade

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

## Type Hierarchy

Use typography weight and size for all hierarchy, not color:

```tsx
// Primary heading
className="text-lg font-semibold text-foreground"

// Secondary heading
className="text-sm font-medium text-foreground"

// Body text
className="text-sm text-foreground"

// Secondary text
className="text-sm text-muted-foreground"

// Emphasized inline
className="font-medium text-foreground"
```

**No color coding:** All file types, agent types, and categories use the same neutral colors with typography for distinction.

## Key Principles

1. **Warm neutrals throughout** - Subtle brown undertones (18-30° hue) create organic, inviting feel
2. **Terracotta primary accent** - Rich, earthy terracotta (18 65% 42%) for emphasis and primary actions
3. **No decorative effects** - No shadows, glows, gradients, or transforms - maintain flat design
4. **Borders for structure** - Never use shadows, always use subtle warm-toned borders
5. **Semantic tokens only** - Never hardcode hex/rgb values in components
6. **Consistent spacing** - Use Tailwind's spacing scale (p-4, p-6, gap-3, etc.)
7. **Accessible** - 32px minimum touch targets, 12px minimum font size, WCAG AAA contrast
8. **Color transitions only** - `transition-colors` for all interactions, no transforms
9. **Terracotta focus rings** - Use `ring-2 ring-primary` for accessibility and brand consistency
10. **Typography for hierarchy** - Use weight/size for distinction, strategic terracotta for emphasis
11. **Border radius hierarchy** - xl (containers) > lg (buttons) > md (pills)
12. **Minimal is better** - When in doubt, remove decoration
13. **Warm aesthetic** - All neutrals have brown undertones for cohesive warmth
14. **Flat design** - Strictly 2D, no depth effects
15. **Clarity over decoration** - Functionality and usability trump visual flourish
