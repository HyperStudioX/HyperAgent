# Frontend Style Guide

A clean, minimal, and modern design system using warm stone (light) and refined ink (dark) themes with semantic color tokens.

## Design Philosophy

- **Clean & Minimal** - No unnecessary shadows, borders only where needed
- **Warm Neutrals** - Warm stone light theme, refined ink dark theme
- **Semantic Tokens** - Use CSS variables for consistency across themes
- **Flat Design** - No gradients, simple solid colors
- **Subtle Interactions** - Simple background color changes, no translate/scale effects
- **Generous Whitespace** - Let content breathe
- **Reduced Motion** - Simple fade/opacity transitions only

## Semantic Color Tokens

**Always use semantic tokens instead of hardcoded colors.** This ensures consistency and makes theming easier.

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `bg-background` | Warm cream | Deep blue-gray | Page backgrounds |
| `bg-card` | Off-white | Dark blue-gray | Cards, elevated surfaces |
| `bg-secondary` | Light stone | Muted ink | Sidebars, subtle backgrounds |
| `bg-muted` | Light stone | Muted ink | Disabled states, read items |
| `text-foreground` | Near black | Off-white | Primary text |
| `text-muted-foreground` | Warm gray | Cool gray | Secondary text |
| `border-border` | Light border | Dark border | Standard borders |
| `border-subtle` | 50% opacity | 50% opacity | Card borders, containers |
| `border-muted` | 30% opacity | 30% opacity | Dividers, separators |
| `bg-primary` | Near black | Off-white | Primary buttons, accents |
| `text-primary-foreground` | White | Near black | Text on primary |
| `bg-destructive` | Red | Red | Error states, delete buttons |
| `text-destructive` | Red | Red | Error text, warning icons |

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

**Benefits:**
- No external font loading (faster page loads)
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

## Color Palette

### CSS Variables (Light Mode - Warm Stone)

```css
--background: 40 25% 96%;      /* Warm cream */
--foreground: 30 10% 15%;      /* Near black */
--primary: 30 15% 15%;         /* Dark warm */
--primary-foreground: 40 20% 97%;
--secondary: 35 15% 93%;       /* Light stone */
--muted: 35 12% 91%;
--muted-foreground: 30 8% 45%;
--border: 35 12% 88%;
--card: 40 25% 99%;
```

### CSS Variables (Dark Mode - Refined Ink)

```css
--background: 220 18% 12%;     /* Deep blue-gray */
--foreground: 40 15% 92%;      /* Off-white */
--primary: 40 15% 92%;
--primary-foreground: 220 15% 13%;
--secondary: 220 12% 22%;      /* Muted ink */
--muted: 220 10% 20%;
--muted-foreground: 220 8% 58%;
--border: 220 10% 25%;
--card: 220 14% 16%;
```

## Logo

### Theme-Adaptive Logo

Use a single SVG logo with `currentColor` that adapts to themes:

```tsx
// Logo in inverted container (recommended)
<div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
  <Image
    src="/images/logo.svg"
    alt="Logo"
    width={20}
    height={20}
    className="invert dark:invert-0"
  />
</div>

// Larger variant for welcome screens
<div className="w-11 h-11 rounded-xl bg-foreground flex items-center justify-center">
  <Image
    src="/images/logo.svg"
    alt="Logo"
    width={26}
    height={26}
    className="invert dark:invert-0"
  />
</div>
```

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

**Avoid:** Gradients, shadows, scale effects, rotate animations on buttons.

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

## Transitions

Standard transition for all interactive elements:

```tsx
className="transition-colors"
```

**Avoid:** `hover:-translate-y`, `hover:scale-*`, `transition-all`, complex animations.

## Touch Targets

Minimum 44px for mobile accessibility:

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
```

**Stagger pattern:** 0.1s, 0.2s, 0.3s, 0.4s for sequential elements.

## Key Principles

1. **Flat design** - No gradients, use solid colors
2. **No scale/translate on hover** - Use background color changes instead
3. **Minimal shadows** - Borders provide structure, shadows are optional
4. **Semantic colors only** - Never hardcode hex/rgb values in components
5. **Consistent spacing** - Use Tailwind's spacing scale (p-4, p-6, gap-3, etc.)
6. **Accessible** - 44px touch targets, 12px minimum font size
7. **Simple transitions** - `transition-colors` for most interactions
8. **Ring for selection** - Use `ring-1 ring-foreground/50` for selected states
9. **Checkmark indicators** - Show selection with circular checkmark badges
