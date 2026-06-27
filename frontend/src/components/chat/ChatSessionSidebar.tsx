'use client';

import { useRef, useEffect } from 'react';
import {
  MessageSquare,
  Plus,
  Trash2,
  ChevronsLeft,
  MessageCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useChatSessions, useDeleteChatSession } from '@/lib/hooks/useChat';

interface ChatSessionSidebarProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onToggle: () => void;
}

function SessionSkeleton() {
  return (
    <div className="space-y-2 p-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg px-3 py-2.5">
          <div className="h-4 w-4 shrink-0 rounded bg-muted shimmer" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="h-3.5 w-3/4 rounded bg-muted shimmer" />
            <div className="h-2.5 w-1/3 rounded bg-muted shimmer" />
          </div>
        </div>
      ))}
    </div>
  );
}

function formatTime(dateStr: string | null) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;
  if (diffHours < 168) return `${Math.floor(diffHours / 24)}d`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function ChatSessionSidebar({
  currentSessionId,
  onSelectSession,
  onNewChat,
  onToggle,
}: ChatSessionSidebarProps) {
  const { data, isLoading } = useChatSessions();
  const deleteSession = useDeleteChatSession();
  const activeRef = useRef<HTMLDivElement>(null);

  const sessions = data?.items || [];

  // Scroll active session into view on mount/change
  useEffect(() => {
    if (currentSessionId && activeRef.current) {
      activeRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [currentSessionId]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (confirm('Delete this chat?')) {
      await deleteSession.mutateAsync(sessionId);
      if (currentSessionId === sessionId) {
        onNewChat();
      }
    }
  };

  return (
    <div className="flex w-[280px] flex-col border-r border-border/50 bg-muted/20">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/50 px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
            <MessageCircle className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-semibold">History</span>
        </div>
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon"
            onClick={onNewChat}
            className="h-7 w-7 rounded-lg text-muted-foreground/60 hover:text-foreground"
            title="New Chat"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="h-7 w-7 rounded-lg text-muted-foreground/40 hover:text-foreground"
            title="Collapse"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Session List */}
      <div className="chat-scrollbar flex-1 overflow-auto py-1.5">
        {isLoading ? (
          <SessionSkeleton />
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center px-6 py-12 text-center">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-muted/50">
              <MessageSquare className="h-5 w-5 text-muted-foreground/40" />
            </div>
            <p className="text-sm font-medium text-muted-foreground/60">No chats yet</p>
            <p className="mt-1 text-xs text-muted-foreground/40">
              Start a new conversation
            </p>
          </div>
        ) : (
          <div className="space-y-0.5 px-1.5">
            {sessions.map((session) => {
              const isActive = currentSessionId === session.id;
              return (
                <div
                  key={session.id}
                  ref={isActive ? activeRef : undefined}
                  onClick={() => onSelectSession(session.id)}
                  className={`group relative flex cursor-pointer items-start gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-all duration-150 ${
                    isActive
                      ? 'bg-primary/[0.08] text-foreground'
                      : 'text-muted-foreground/80 hover:bg-muted/50 hover:text-foreground'
                  }`}
                >
                  {/* Active indicator bar */}
                  {isActive && (
                    <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />
                  )}

                  <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium leading-snug">
                      {session.title}
                    </p>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground/50">
                      <span>{session.message_count} msgs</span>
                      <span>·</span>
                      <span>{formatTime(session.last_message_at)}</span>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-2 top-2 h-6 w-6 rounded-full opacity-0 transition-all duration-150 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
                    onClick={(e) => handleDelete(e, session.id)}
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border/50 px-4 py-2.5">
        <p className="text-[11px] text-muted-foreground/40">
          {sessions.length} conversation{sessions.length !== 1 ? 's' : ''}
        </p>
      </div>
    </div>
  );
}
