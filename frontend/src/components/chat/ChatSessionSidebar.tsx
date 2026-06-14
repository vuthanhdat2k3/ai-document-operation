'use client';

import { useState } from 'react';
import { MessageSquare, Plus, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useChatSessions, useCreateChatSession, useDeleteChatSession } from '@/lib/hooks/useChat';
import type { ChatSession } from '@/types';

interface ChatSessionSidebarProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
}

export function ChatSessionSidebar({
  currentSessionId,
  onSelectSession,
  onNewChat,
}: ChatSessionSidebarProps) {
  const { data, isLoading } = useChatSessions();
  const createSession = useCreateChatSession();
  const deleteSession = useDeleteChatSession();
  const [collapsed, setCollapsed] = useState(false);

  const sessions = data?.items || [];

  const handleNewChat = async () => {
    onNewChat();
  };

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (confirm('Delete this chat?')) {
      await deleteSession.mutateAsync(sessionId);
      if (currentSessionId === sessionId) {
        onNewChat();
      }
    }
  };

  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  if (collapsed) {
    return (
      <div className="flex h-full w-12 flex-col items-center border-r bg-muted/30 py-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(false)}
          className="mb-4"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={handleNewChat}>
          <Plus className="h-4 w-4" />
        </Button>
        <div className="mt-4 flex flex-col items-center gap-2">
          {sessions.slice(0, 10).map((s) => (
            <Button
              key={s.id}
              variant={currentSessionId === s.id ? 'secondary' : 'ghost'}
              size="icon"
              onClick={() => onSelectSession(s.id)}
              title={s.title}
            >
              <MessageSquare className="h-4 w-4" />
            </Button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-72 flex-col border-r bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Chat History</h3>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={handleNewChat} title="New Chat">
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} title="Collapse">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="p-4 text-center text-sm text-muted-foreground">Loading...</div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            No chats yet. Start a new conversation!
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`group flex cursor-pointer items-start gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent ${
                  currentSessionId === session.id ? 'bg-accent' : ''
                }`}
              >
                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{session.title}</p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{session.message_count} msgs</span>
                    <span>{formatTime(session.last_message_at)}</span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                  onClick={(e) => handleDelete(e, session.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t px-4 py-2 text-xs text-muted-foreground">
        {sessions.length} conversation{sessions.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
