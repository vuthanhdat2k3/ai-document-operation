# AI Document Operations — Design System

## 1. Atmosphere & Identity

A calm command center for document intelligence. The interface feels like a precision instrument — quiet, capable, never theatrical. Surfaces separate by tonal shift rather than hard borders, creating a sense of layered depth you feel more than see.

The signature is **soft luminescence**: interactive elements catch light with subtle glass effects (`backdrop-blur` + translucent fills), while content areas recede into matte, velvety backgrounds. The chat feels like a conversation with an attentive expert — intimate, responsive, trustworthy.

## 2. Color

### Palette — Extended from existing HSL variables

| Role | Token | Light | Dark | Usage |
|------|-------|-------|------|-------|
| Surface/primary | `--surface-primary` | `0 0% 100%` | `222.2 84% 4.9%` | Main page background |
| Surface/secondary | `--surface-secondary` | `210 40% 96.1%` | `217.2 32.6% 17.5%` | Cards, chat bubbles (AI) |
| Surface/elevated | `--surface-elevated` | `0 0% 100%` | `217.2 32.6% 14%` | Modals, dropdowns, tooltips |
| Surface/glass | `--surface-glass` | `0 0% 100% / 0.7` | `0 0% 100% / 0.05` | Floating elements, sticky headers |
| Text/primary | `--foreground` | `222.2 84% 4.9%` | `210 40% 98%` | Headlines, body |
| Text/secondary | `--muted-foreground` | `215.4 16.3% 46.9%` | `215 20.2% 65.1%` | Captions, hints |
| Text/tertiary | — | `215.4 16.3% 60%` | `215 20.2% 50%` | Disabled, metadata |
| Border/default | `--border` | `214.3 31.8% 91.4%` | `217.2 32.6% 17.5%` | Dividers, outlines |
| Border/subtle | `--border-subtle` | `214.3 31.8% 95%` | `217.2 32.6% 22%` | Soft separations |
| Accent/primary | `--primary` | `221.2 83.2% 53.3%` | `217.2 91.2% 59.8%` | CTAs, links, focus ring |
| Accent/hover | — | `221.2 83.2% 45%` | `217.2 91.2% 65%` | Hover state |
| Accent/glow | `--accent-glow` | `221.2 83.2% 53.3% / 0.15` | `217.2 91.2% 59.8% / 0.2` | Glow effect on active elements |
| Chat/user | `--chat-user` | `221.2 83.2% 53.3%` | `217.2 91.2% 59.8%` | User message bubble |
| Chat/user-text | `--chat-user-foreground` | `210 40% 98%` | `222.2 47.4% 11.2%` | Text in user bubble |
| Status/success | — | `142.1 76.2% 36.3%` | `142.1 70.6% 45.3%` | Confirmations |
| Status/warning | — | `32.1 94.6% 43.7%` | `32.1 94.6% 53.7%` | Cautions |
| Status/error | `--destructive` | `0 84.2% 60.2%` | `0 62.8% 50.6%` | Errors, destructive |

### Rules
- Surface hierarchy creates depth via tonal shift. No harsh borders between layers.
- Accent (primary) used ONLY for interactive elements. Never decorative.
- Glass effect (`backdrop-blur-xl`) applied only to fixed/sticky elements — never to scrolling content.
- Chat bubbles use dedicated tokens to maintain distinct identity from UI chrome.

## 3. Typography

### Font Stack
- **Primary**: `"Geist", "Inter", system-ui, -apple-system, sans-serif` — clean geometric sans for UI and body text.
- **Mono**: `"JetBrains Mono", "Fira Code", monospace` — for code blocks in messages.
- **Serif**: Not used. Clean sans-only identity.

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| Display | 48px / 3rem | 700 | 1.1 | -0.02em | Page title (not in chat) |
| H1 | 36px / 2.25rem | 600 | 1.2 | -0.015em | Section headers |
| H2 | 28px / 1.75rem | 600 | 1.3 | -0.01em | Subsection headers |
| H3 | 22px / 1.375rem | 600 | 1.4 | 0 | Card titles |
| Body/lg | 18px / 1.125rem | 400 | 1.6 | 0 | Lead paragraphs |
| **Body** | **15px / 0.9375rem** | **400** | **1.65** | **0** | **Chat message body** |
| Body/sm | 13px / 0.8125rem | 400 | 1.5 | 0 | Secondary info, input |
| Caption | 12px / 0.75rem | 500 | 1.4 | 0.02em | Labels, metadata |
| Overline | 11px / 0.6875rem | 600 | 1.3 | 0.08em | Section labels, uppercase |

### Rules
- Chat message body uses 15px — slightly smaller than default 16px for a more refined reading experience.
- Code blocks in AI responses render in mono font with a tinted background.
- Headings in markdown messages follow the scale above, up to H3.
- Max 2 font families. Mono is only for code — never for UI text.

## 4. Spacing & Layout

### Base Unit
All spacing derives from a base of **4px**.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight: icon-to-label, inline gaps |
| `--space-2` | 8px | Compact: message bubble padding (AI) |
| `--space-3` | 12px | Comfortable: message bubble padding (user) |
| `--space-4` | 16px | Standard: card padding, input area gutters |
| `--space-5` | 20px | Section inner spacing |
| `--space-6` | 24px | Generous: between message groups |
| `--space-8` | 32px | Separated: sidebar items |
| `--space-10` | 40px | Sections within a page |
| `--space-12` | 48px | Major section breaks |
| `--space-16` | 64px | Page-level vertical rhythm |
| `--space-20` | 80px | Hero-level spacing |
| `--space-24` | 96px | Maximum separation |

### Chat-Specific Layout
- **Chat container**: `max-w-3xl` (768px) centered — comfortable reading width.
- **Message gap**: `gap-6` (24px) between messages — room to breathe.
- **Bubble padding**: User: `px-5 py-3`, AI: `px-5 py-4` — generous but not wasteful.
- **Input area**: Fixed at bottom, `py-4` vertical padding, glass effect backdrop.
- **Sidebar**: 280px (`w-70`) wide — enough for readable session titles.

### Rules
- No magic numbers. Every spacing value maps to a token.
- Chat messages never exceed 85% of container width.
- The input area is always visible — never scrolls away.

## 5. Components

### ChatMessage (bubble)
- **Structure**: `div.flex` (justify-end for user, justify-start for AI) > `div.bubble`
- **User bubble**: Solid primary color fill, rounded-2xl, text white.
- **AI bubble**: Glass-effect surface (secondary background), rounded-2xl, subtle border.
- **Entry animation**: Fade-up + scale from 0.95 → 1 over 300ms, staggered per message.
- **Citations**: Collapsible badge row below AI message text.
- **Timestamp**: Hidden by default, shown on hover (micro interaction).

### ChatInput
- **Structure**: Form with textarea + send button in a glass container.
- **Textarea**: Auto-resizing, no scrollbar until 6+ lines.
- **Send button**: Circular pill with arrow icon, disabled state when empty.
- **Focus state**: Outer glow ring using accent-glow.
- **Variants**: Default / disabled (when streaming).

### ChatSidebar
- **Structure**: Vertical list of session items.
- **Session item**: Icon + title + metadata row (message count, time).
- **Active state**: Tonal highlight with left accent bar.
- **Hover**: Subtle background shift.
- **Collapsed state**: Icon-only mode with tooltips.

### TypingIndicator
- **Structure**: Three animated dots in an AI-style bubble.
- **Animation**: Bouncing dots with staggered delays (CSS keyframes).
- **Duration**: 1.2s loop, each dot delayed by 0.15s.

### EmptyState
- **Structure**: Centered vertical layout with icon, heading, description, suggestion chips.
- **Suggestion chips**: Outlined pill buttons with hover fill effect.

## 6. Motion & Interaction

### Timing

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Micro | 150ms | `cubic-bezier(0.25, 0.1, 0.25, 1)` | Button press, toggle, hover lift |
| Standard | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Panel open, tab switch, message entry |
| Emphasis | 500ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Page transition, typing indicator |
| Streaming | 800ms loop | `cubic-bezier(0.4, 0, 0.6, 1)` | Typing dots animation |

### Chat-Specific Motion
- **Message entry**: AI messages slide up (`translate-y-4` → `translate-y-0`) + fade (`opacity-0` → `opacity-1`) with 300ms duration. User messages appear without entry animation (instant — feels more responsive).
- **Typing dots**: Infinite bounce animation, staggered per dot.
- **Scroll behavior**: Auto-scroll to bottom on new message, but only if user is near bottom (< 100px). If user scrolled up, show a "Jump to bottom" floating button.
- **Sidebar collapse/expand**: Smooth width transition 300ms.

### Interactive States
- **Button hover**: Scale down 0.98 (physical press simulation).
- **Button active**: Scale down 0.95.
- **Message hover**: Show timestamp + copy button via opacity transition.
- **Input focus**: 2px primary glow ring + subtle background shift.

### Rules
- Only animate `transform` and `opacity`. Never `height`, `width`, `top`, `left`.
- Reduced motion: `prefers-reduced-motion` disables all entry animations, keeps micro-interactions only.
- All custom `cubic-bezier` curves — no `linear` or `ease-in-out`.

## 7. Depth & Surface

### Strategy: **Tonal-shift + accent glass**

Surfaces are differentiated by subtle tonal shifts (lighter/darker shades of the same hue) rather than borders or shadows. Interactive surfaces (input area, active sidebar item) use a glass effect with `backdrop-blur-xl` and a translucent fill.

| Level | Technique | Usage |
|-------|-----------|-------|
| Page background | Base surface color | `/chat` page main area |
| Content surface | Secondary surface color | AI message bubbles, sidebar |
| Elevated surface | Glass effect `backdrop-blur-xl bg-surface-glass` | Input area, sticky header |
| Interactive | Glass + accent glow on focus | Input, buttons, active items |
| Overlay | Heavy glass `backdrop-blur-2xl` + dark/light overlay | Mobile sidebar overlay |

### Rules
- No box shadows for surface separation. Shadows used only for drag handles and modals.
- Glass effect is the premium signature — use sparingly, only on 1-2 elements per view.
- Every glass element has a `pointer-events-none` guard on decorative uses.
