# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Development
npm run dev              # Start Next.js dev server on http://localhost:3000

# Build & Production
npm run build            # Build for production
npm start                # Start production server
npm run clean            # Remove .next build directory

# Code Quality
npm run lint             # Run ESLint
npx tsc --noEmit        # Type-check without emitting files
```

## Architecture Overview

### Frontend Framework
- **Next.js 16** (App Router with React 18)
- **Internationalization**: `next-intl` with locale prefix set to "never" (locales: en, zh-CN)
- **API Proxy**: `/api/v1/*` routes proxy to backend at `NEXT_PUBLIC_API_URL` (default: http://localhost:8080)

### State Management
Two Zustand stores with persistence to localStorage:

1. **Chat Store** (`lib/stores/chat-store.ts`)
   - Manages conversations (chat & research types)
   - Messages with streaming support
   - Active conversation tracking
   - Hydration state to prevent SSR mismatches

2. **Task Store** (`lib/stores/task-store.ts`)
   - Research tasks with 4 scenarios: academic, market, technical, news
   - Task lifecycle: pending → running → completed/failed
   - Steps tracking (search, analyze, synthesize, write)
   - Sources and results management

**Important**: Both stores use `hasHydrated` flag. Always check hydration before rendering items to prevent SSR/client mismatches.

### Design System
- **Theme**: Warm stone (light) / Refined ink (dark) with auto mode following system preference
- **Typography**: IBM Plex Sans (body) & IBM Plex Mono (code)
- **Color System**: HSL-based CSS variables in `app/globals.css`
- **Theme Hook**: `lib/hooks/use-theme.ts` returns `theme` (preference: auto/light/dark), `resolvedTheme` (actual: light/dark), and `setTheme`
- **Icons**: Lucide React
- **UI Components**: Radix UI primitives + custom components in `components/ui/`

### Component Structure

```
components/
├── layout/
│   ├── main-layout.tsx      # Root layout with sidebar
│   └── sidebar.tsx           # Navigation, recent tasks, user menu, preferences
├── ui/
│   ├── recent-tasks.tsx      # Unified timeline for conversations & tasks
│   ├── preferences-panel.tsx # Theme (auto/light/dark) & language selector
│   └── ...                   # Reusable UI primitives
├── query/
│   └── unified-interface.tsx # Main chat/research interface
├── chat/                     # Chat-specific components
├── task/                     # Research task components
└── auth/
    └── user-menu.tsx         # Authentication UI
```

### Key Patterns

**Sidebar Recent Items**:
- Combines conversations and tasks into unified timeline
- Groups by time: Today, Yesterday, This Week, Earlier
- Type indicator badges: Chat vs Research
- Status indicators for tasks: running (spinner), completed (check), failed (alert)

**Translations**:
- Messages in `messages/en.json` and `messages/zh-CN.json`
- Access via `useTranslations("namespace")` hook
- Common namespaces: sidebar, home, research, task, chat

**Authentication**:
- NextAuth with Google OAuth
- Config in `lib/auth/config.ts`
- Environment variables: `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

**Images**:
- Remote patterns allow `lh3.googleusercontent.com`
- Use `unoptimized` prop for user avatars to bypass private IP blocking

## Important Implementation Notes

### State Hydration
Always check `hasHydrated` before rendering store-dependent UI:
```tsx
const { hasHydrated } = useChatStore();
if (!hasHydrated) return null; // or loading state
```

### Theme System
- Theme preference stored as `theme-preference` in localStorage
- Auto mode listens to `prefers-color-scheme` media query
- Always use `theme` for UI display (shows user preference)
- Use `resolvedTheme` if you need actual light/dark value

### API Integration
- Backend assumed at `http://localhost:8080` (configurable via env)
- API routes proxied through Next.js rewrites
- No direct fetch to external API URLs from client

### Type Imports
- Main types in `lib/types/index.ts`
- Store types co-located with stores: `ResearchTask` in task-store, `Conversation` in chat-store
- Use `type` imports for type-only imports

### UI Component Guidelines
- Follow minimal, clean design philosophy
- Use existing color variables instead of hardcoding colors
- Prefer grid layouts for option groups (theme selector uses 3-col grid)
- Active states: inverted colors (foreground bg, background text)
- Icons should be 3.5-4px (w-3.5 h-3.5 or w-4 h-4)

## Backend API Contract

The frontend expects these endpoints:
- `POST /api/v1/chat` - Chat completions
- `POST /api/v1/research` - Research task creation
- `GET /api/v1/research/:id` - Research task status
- SSE streams for real-time updates

Ensure backend is running on port 8080 or configure `NEXT_PUBLIC_API_URL`.
