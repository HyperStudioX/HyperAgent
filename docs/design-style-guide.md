# Frontend Style Guide

A clean, minimal, and modern design system using pure neutral grays with semantic color tokens.

## Design Philosophy

- **Clean & Minimal** - No unnecessary shadows, borders only where needed
- **Pure Neutrals** - Black, white, and gray palette (no warm tones)
- **Semantic Tokens** - Use CSS variables for consistency across themes
- **Subtle Interactions** - Simple background color changes, no translate/scale effects
- **Generous Whitespace** - Let content breathe
- **Reduced Motion** - Simple fade/opacity transitions only

## Semantic Color Tokens

**Always use semantic tokens instead of hardcoded colors.** This ensures consistency and makes theming easier.

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `bg-background` | White | #0a0a0a | Page backgrounds |
| `bg-card` | White | #1a1a1a | Cards, elevated surfaces |
| `bg-secondary` | #f5f5f5 | #262626 | Sidebars, subtle backgrounds |
| `bg-muted` | #f5f5f5 | #262626 | Disabled states, read items |
| `text-foreground` | #171717 | #fafafa | Primary text |
| `text-muted-foreground` | #737373 | #a3a3a3 | Secondary text |
| `border-border` | #e5e5e5 | #2d2d2d | Standard borders |
| `border-subtle` | 50% opacity | 50% opacity | Card borders, containers |
| `border-muted` | 30% opacity | 30% opacity | Dividers, separators |
| `bg-primary` | #171717 | #fafafa | Primary buttons, accents |
| `text-primary-foreground` | White | #171717 | Text on primary |
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

**Note:** Minimum font size is 12px (`text-xs`) for WCAG accessibility.

### Font Weights

| Class | Weight | Usage |
|-------|--------|-------|
| (default) | 400 | Body text, descriptions |
| `font-medium` | 500 | Labels, buttons, primary status |
| `font-semibold` | 600 | Headings, important CTAs |
| `font-bold` | 700 | Page titles, strong emphasis |

## Color Palette

### CSS Variables (Light Mode)

```css
--background: 0 0% 100%;      /* Pure white */
--foreground: 0 0% 9%;        /* Near black #171717 */
--primary: 0 0% 9%;           /* Same as foreground */
--primary-foreground: 0 0% 100%;
--secondary: 0 0% 96%;        /* Light gray #f5f5f5 */
--muted: 0 0% 96%;
--muted-foreground: 0 0% 45%;
--border: 0 0% 90%;           /* #e5e5e5 */
--card: 0 0% 100%;
```

### CSS Variables (Dark Mode)

```css
--background: 0 0% 4%;        /* Deep black #0a0a0a */
--foreground: 0 0% 98%;       /* Off-white #fafafa */
--primary: 0 0% 98%;
--primary-foreground: 0 0% 9%;
--secondary: 0 0% 15%;        /* #262626 */
--muted: 0 0% 15%;
--muted-foreground: 0 0% 64%;
--border: 0 0% 18%;           /* #2d2d2d */
--card: 0 0% 7%;              /* #1a1a1a */
```

### Gray Palette

| Shade | Hex | Usage |
|-------|-----|-------|
| gray-50 | #fafafa | Lightest backgrounds |
| gray-100 | #f5f5f5 | Secondary backgrounds |
| gray-200 | #e5e5e5 | Borders |
| gray-400 | #a3a3a3 | Muted text (dark mode) |
| gray-500 | #737373 | Muted text (light mode) |
| gray-600 | #525252 | Body text |
| gray-900 | #171717 | Headings, primary text |
| gray-950 | #0a0a0a | Dark mode backgrounds |

## Buttons

### Primary Button

```tsx
className="bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
```

### Secondary Button

```tsx
className="bg-secondary text-foreground hover:bg-secondary transition-colors"
```

### Outline Button

```tsx
className="border border-subtle bg-card text-foreground hover:bg-secondary/50 transition-colors"
```

### Ghost Button

```tsx
className="hover:bg-secondary hover:text-foreground transition-colors"
```

### Destructive Button

```tsx
// Solid
className="bg-destructive text-white hover:bg-destructive/90 transition-colors"

// Icon
className="p-2 text-destructive hover:text-destructive/80 hover:bg-destructive/10 rounded-lg transition-colors"
```

## Cards & Containers

**Clean, minimal design - borders only, no shadows by default:**

```tsx
// Standard card
className="rounded-xl bg-card border border-subtle"

// Interactive card
className="bg-card rounded-xl p-6 border border-subtle transition-colors hover:bg-secondary/50"

// Container with dividers
className="divide-y divide-muted"
```

**Avoid:** Shadow effects on cards, translate/scale hover transforms.

## Shadows

Simplified to 4 essential variants:

| Class | Usage |
|-------|-------|
| `shadow-sm` | Subtle elevation (rare use) |
| `shadow` | Default elevation |
| `shadow-md` | Dropdowns, floating elements |
| `shadow-lg` | Modals, important overlays |

**Note:** Prefer borderless/border designs over shadows for cards.

## Border Radius

| Class | Size | Usage |
|-------|------|-------|
| `rounded-md` | 6px | Badges, tags, small pills |
| `rounded-lg` | 8px | Buttons, inputs, icon containers |
| `rounded-xl` | 12px | Cards, containers, modals |
| `rounded-full` | 9999px | Avatars, status dots, pills |

## Icons

Use `lucide-react` for all icons:

| Size | Class | Usage |
|------|-------|-------|
| Small | `w-4 h-4` | Default, most buttons |
| Medium | `w-5 h-5` | Section headers, nav items |
| Large | `w-6 h-6` | Feature cards, empty states |

### Icon Container

```tsx
// Neutral
<div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
  <Icon className="w-5 h-5 text-muted-foreground" />
</div>

// Primary
<div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
  <Icon className="w-5 h-5 text-primary" />
</div>
```

## Navigation

### Sidebar Nav Items

```tsx
// Active
className="bg-card text-foreground font-medium shadow-sm"

// Inactive
className="text-muted-foreground hover:bg-card hover:text-foreground transition-colors"
```

## Badges

### Content Type Badge (on images)

```tsx
className="px-2.5 py-1 rounded-md text-xs font-medium bg-black/60 text-white backdrop-blur-sm"
```

### Feature Tag

```tsx
className="px-2.5 py-1 text-xs bg-secondary text-muted-foreground rounded-md"
```

## Form Inputs

```tsx
className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground
  focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
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
// or for multiple properties:
className="transition-all duration-200"
```

**Avoid:** `hover:-translate-y`, `hover:scale-*`, complex animations.

## Touch Targets

Minimum 44px for mobile accessibility:

```tsx
className="min-h-[44px] min-w-[44px]"
```

## Quick Reference Patterns

### Card with Hover

```tsx
<div className="bg-card rounded-xl p-6 border border-subtle transition-colors hover:bg-secondary/50">
  {/* content */}
</div>
```

### Primary Button

```tsx
<button className="px-5 py-2 bg-primary text-primary-foreground font-medium rounded-lg
  transition-colors hover:bg-primary/90">
  Action
</button>
```

### Error Alert

```tsx
<div className="p-4 bg-destructive/10 border border-destructive/30 rounded-xl">
  <p className="text-sm text-destructive">{error}</p>
</div>
```

### Avatar Fallback

```tsx
<div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center">
  <span className="text-sm font-medium text-muted-foreground">{initials}</span>
</div>
```

## Key Principles

1. **No scale/translate on hover** - Use background color changes instead
2. **Minimal shadows** - Borders provide structure, shadows are optional
3. **Semantic colors only** - Never hardcode hex/rgb values in components
4. **Consistent spacing** - Use Tailwind's spacing scale (p-4, p-6, gap-3, etc.)
5. **Accessible** - 44px touch targets, 12px minimum font size
6. **Simple transitions** - `transition-colors` for most interactions