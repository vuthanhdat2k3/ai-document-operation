# Phase 11: Frontend Dashboard — Implementation Plan

## Task
Build Next.js 14 frontend with all pages and components.

## Tech Stack
- Next.js 14 (App Router)
- TypeScript (strict)
- TailwindCSS 3.4+
- shadcn/ui components
- React Query (TanStack Query)
- Zustand (state management)

## Files to Create

### Project Setup

#### `frontend/package.json`
- Dependencies: next, react, react-dom, @tanstack/react-query, zustand, tailwindcss, @radix-ui/*, lucide-react, react-markdown, recharts

#### `frontend/next.config.js`
- API proxy to backend

#### `frontend/tailwind.config.ts`
- shadcn/ui compatible config

#### `frontend/tsconfig.json`
- strict mode, path aliases

#### `frontend/postcss.config.js`

### App Layout

#### `frontend/src/app/layout.tsx`
- Root layout with sidebar, header, providers

#### `frontend/src/app/page.tsx`
- Dashboard home — stats overview

#### `frontend/src/app/globals.css`
- Tailwind imports, CSS variables for theming

### Components

#### `frontend/src/components/ui/` (shadcn/ui)
- button.tsx, card.tsx, input.tsx, dialog.tsx, table.tsx, badge.tsx, tabs.tsx, select.tsx, toast.tsx, dropdown-menu.tsx

#### `frontend/src/components/layout/Sidebar.tsx`
- Navigation: Dashboard, Documents, Search, Chat, Reports, Settings

#### `frontend/src/components/layout/Header.tsx`
- User info, notifications, theme toggle

#### `frontend/src/components/documents/DocumentUploader.tsx`
- Drag-and-drop upload zone
- File type validation
- Upload progress bar
- Error handling

#### `frontend/src/components/documents/DocumentList.tsx`
- Table with columns: name, type, status, date, actions
- Pagination, search, filters
- Status badges (uploaded, parsing, parsed, failed)

#### `frontend/src/components/documents/DocumentDetail.tsx`
- Tabs: Overview, Content, Fields, Risks, Checklist
- Metadata display
- Parsed content viewer
- Extracted fields table

#### `frontend/src/components/search/SearchBar.tsx`
- Search input with filters
- Autocomplete suggestions

#### `frontend/src/components/search/SearchResults.tsx`
- Result cards with relevance score
- Source highlighting
- Click to view document

#### `frontend/src/components/chat/ChatInterface.tsx`
- Message list (user + assistant)
- Input box with send button
- Citation cards
- Streaming response display

#### `frontend/src/components/reports/ReportViewer.tsx`
- Markdown rendering
- PDF download button
- Report history list

#### `frontend/src/components/agent/AgentSessionViewer.tsx`
- Step-by-step execution trace
- Tool calls display
- Timing information
- Cost breakdown

### Pages

#### `frontend/src/app/documents/page.tsx`
- Document list + upload button

#### `frontend/src/app/documents/[id]/page.tsx`
- Document detail view

#### `frontend/src/app/search/page.tsx`
- Search interface with results

#### `frontend/src/app/chat/page.tsx`
- Chat/Q&A interface

#### `frontend/src/app/reports/page.tsx`
- Report list + generate button

#### `frontend/src/app/reports/[id]/page.tsx`
- Report detail + download

#### `frontend/src/app/agent/page.tsx`
- Agent task runner

#### `frontend/src/app/agent/sessions/[id]/page.tsx`
- Session detail viewer

### Lib

#### `frontend/src/lib/api.ts`
- API client with base URL, auth headers
- Typed fetch wrappers

#### `frontend/src/lib/hooks/useDocuments.ts`
- React Query hooks for document CRUD

#### `frontend/src/lib/hooks/useSearch.ts`
- React Query hook for search

#### `frontend/src/lib/hooks/useChat.ts`
- Chat state management with streaming

#### `frontend/src/lib/store.ts`
- Zustand store for global state

### Types

#### `frontend/src/types/index.ts`
- Document, SearchResponse, ChatMessage, Report, AgentSession types

### Docker

#### `frontend/Dockerfile`
- Multi-stage: build + production (nginx)

## Acceptance Criteria
- [ ] All pages render correctly
- [ ] Document upload works with progress
- [ ] Search returns results
- [ ] Chat streams responses
- [ ] Reports viewable and downloadable
- [ ] Responsive layout
- [ ] TypeScript strict mode passes

## Test Requirements
- Component tests with React Testing Library
- API hook tests
- E2E tests (Playwright) for critical flows
