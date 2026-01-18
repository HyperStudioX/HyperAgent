# Frontend Style Guide

A radically minimal design system using the Cursor aesthetic - pure neutrals, flat design, and clarity over decoration.

## Design Philosophy

- **Radically Minimal** - No shadows, borders only where structure is needed
- **Pure Neutrals Only** - Clean white light theme, deep black dark theme (0° saturation)
- **No Accent Colors** - Use foreground/background inversion for emphasis
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
| `bg-background` | Pure white (100%) | Deep black (4%) | Page backgrounds |
| `bg-card` | Off-white (98%) | Dark gray (7%) | Cards, elevated surfaces |
| `bg-secondary` | Light gray (96%) | Dark gray (12%) | Sidebars, subtle backgrounds |
| `bg-muted` | Light gray (94%) | Dark gray (14%) | Disabled states, read items |
| `text-foreground` | Near black (9%) | Light gray (92%) | Primary text |
| `text-muted-foreground` | Gray (45%) | Gray (50%) | Secondary text |
| `border-border` | Light gray (93%) | Dark gray (16%) | Standard borders |
| `border-border/50` | 50% opacity | 50% opacity | Card borders, containers |
| `border-border/30` | 30% opacity | 30% opacity | Dividers, separators |
| `bg-primary` | Near black (9%) | Light gray (92%) | Primary buttons, inverted states |
| `text-primary-foreground` | Off-white (98%) | Near black (4%) | Text on primary |
| `bg-destructive` | Red (0 72% 51%) | Red (0 72% 55%) | Error states, delete buttons |
| `text-destructive` | Red | Red | Error text, warning icons |

### Interactive States

All interactive elements use foreground/background inversion rather than accent colors:

| State | Color Treatment |
|-------|-----------------|
| Default | `bg-card text-foreground` |
| Hover | `bg-secondary text-foreground` or `bg-muted` |
| Active/Selected | `bg-foreground text-background` (inverted) |
| Focus | `ring-2 ring-foreground/20` (subtle ring only) |
| Disabled | `opacity-50` |

**No Accent Colors Philosophy:**
- Use pure grays and foreground/background inversion for all states
- No colored highlights, glows, or decorative effects
- Focus on hierarchy through typography weight and spacing
- Links use subtle underline rather than color

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
--border: 0 0% 93%;           /* Refined from 90% */
--card: 0 0% 98%;
--ring: 0 0% 20%;
```

### CSS Variables (Dark Mode - Deep Black)

```css
--background: 0 0% 4%;        /* Deep black */
--foreground: 0 0% 92%;       /* Light gray (refined from 89%) */
--primary: 0 0% 92%;
--primary-foreground: 0 0% 4%;
--secondary: 0 0% 12%;        /* Dark gray */
--muted: 0 0% 14%;
--muted-foreground: 0 0% 50%;
--border: 0 0% 16%;           /* Refined from 18% */
--card: 0 0% 7%;
--ring: 0 0% 80%;
```

### Status Colors (Both Themes)

Only use color for critical status indicators (errors):

```css
/* Destructive/Error - only colored element */
--destructive: 0 72% 51%;     /* Light mode - red */
--destructive: 0 72% 55%;     /* Dark mode - red */

/* Success/Info use neutral foreground */
/* No accent colors - use foreground/background inversion instead */
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

#### Primary (Inverted for Emphasis)
```tsx
className="bg-foreground text-background hover:bg-foreground/90 transition-colors"
```
**Usage:** Important actions requiring high visibility (Continue, Submit)

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
- Use `variant="primary"` for primary CTAs (inverted colors)
- Keep transitions to `transition-colors` only
- Use clear typography hierarchy instead of effects
- Maintain 32px minimum touch targets

**DON'T:**
- Don't use transform effects (scale, translate, rotate)
- Don't use shadows except on destructive in rare cases
- Don't use accent colors - use foreground/background inversion
- Don't add glow effects or decorative elements

## Focus States

Use subtle rings for focus states, no glow effects:

```tsx
// Focus ring (for all interactive elements)
className="focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:outline-none"
```

**Focus Ring Philosophy:**
- Use subtle `ring-foreground/20` (20% opacity) for accessibility
- Never use box-shadow or glow effects
- Ring offset of 2px for clear separation
- Remove default outline with `outline-none`

**Examples:**

```tsx
// Button focus
<button className="... focus-visible:ring-2 focus-visible:ring-foreground/20">
  Click me
</button>

// Input focus
<input className="... focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2" />

// Link focus
<a className="... focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:rounded">
  Read more
</a>
```

## Selection States

### Pill/Chip Selection

Use foreground/background inversion for selected states:

```tsx
// Unselected
className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-card text-muted-foreground border border-border hover:bg-secondary hover:text-foreground transition-colors"

// Selected (inverted colors)
className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-foreground text-background"
```

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

## Border Radius

Systematic border radius hierarchy for visual consistency:

| Class | Size | Usage |
|-------|------|-------|
| `rounded-sm` | 8px | Small badges, minimal elements |
| `rounded-md` | 10px | Badges, tags, tool indicators |
| `rounded-lg` | 12px | Buttons, inputs, icon buttons, pills, chips, agent selection buttons |
| `rounded-xl` | 16px | Cards, containers, modals, input areas |
| `rounded-2xl` | 20px | Large containers, hero sections |
| `rounded-full` | 9999px | Avatars, status dots, circular pills |

**Hierarchy Philosophy:**
- Large containers (hero sections) = `rounded-2xl` (20px)
- Standard containers (cards, modals) = `rounded-xl` (16px)
- Interactive elements (buttons, inputs) = `rounded-lg` (12px)
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
- Hover: Background color change only
- Active: No visual feedback needed
- Focus: Subtle ring (via `ring-foreground/20`)
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

1. **Pure neutrals only** - No warm/cool tints, 0° saturation grays, no accent colors
2. **No decorative effects** - No shadows, glows, gradients, or transforms
3. **Foreground/background inversion** - Use inverted colors for emphasis, not color
4. **Borders for structure** - Never use shadows, always use subtle borders
5. **Semantic tokens only** - Never hardcode hex/rgb values in components
6. **Consistent spacing** - Use Tailwind's spacing scale (p-4, p-6, gap-3, etc.)
7. **Accessible** - 32px minimum touch targets, 12px minimum font size, WCAG AAA contrast
8. **Color transitions only** - `transition-colors` for all interactions, no transforms
9. **Ring for focus** - Use `ring-2 ring-foreground/20` for accessibility
10. **Typography for hierarchy** - Use weight/size for distinction, not color
11. **Border radius hierarchy** - xl (containers) > lg (buttons) > md (pills)
12. **Minimal is better** - When in doubt, remove decoration
13. **No color coding** - All categories use neutral colors
14. **Flat design** - Strictly 2D, no depth effects
15. **Clarity over decoration** - Functionality and usability trump visual flourish
