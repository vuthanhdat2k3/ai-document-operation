'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Trash2, FileText, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useChat } from '@/lib/hooks/useChat';
import { ChatSessionSidebar } from './ChatSessionSidebar';
import type { ChatMessage } from '@/types';

export function ChatInterface() {
  const { messages, sendMessage, clearMessages, loadSession, isStreaming, sessionId } = useChat();
  const [input, setInput] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const msg = input.trim();
    setInput('');
    await sendMessage(msg);
  };

  const handleNewChat = () => {
    clearMessages();
  };

  const handleSelectSession = (sid: string) => {
    loadSession(sid);
  };

  return (
    <div className="flex h-[calc(100vh-120px)]">
      {/* Sidebar */}
      {showSidebar && (
        <ChatSessionSidebar
          currentSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-3">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Document Q&A</h2>
            {sessionId && (
              <Badge variant="outline" className="text-xs">
                Session: {sessionId.slice(0, 8)}...
              </Badge>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleNewChat}>
              <FileText className="mr-2 h-4 w-4" />
              New Chat
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={clearMessages}
              disabled={messages.length === 0}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Clear
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <p className="text-lg font-medium">Hỏi đáp về tài liệu</p>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  Hệ thống sẽ tìm kiếm trong tất cả tài liệu đã index và trả lời
                  với citations. Hỗ trợ tiếng Việt và tiếng Anh.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {[
                    'Tóm tắt nội dung chính',
                    'Những rủi ro nào được phát hiện?',
                    'Cho tôi checklist cần làm',
                  ].map((q) => (
                    <Button
                      key={q}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setInput(q);
                      }}
                    >
                      {q}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {isStreaming && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-lg border bg-card px-4 py-3">
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-3/4" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t px-6 py-4">
          <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl gap-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Đặt câu hỏi về tài liệu..."
              disabled={isStreaming}
              className="flex-1"
              aria-label="Chat message input"
            />
            <Button type="submit" disabled={!input.trim() || isStreaming} aria-label="Send message">
              <Send className="mr-2 h-4 w-4" />
              Gửi
            </Button>
          </form>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-groundedness">
            Powered by Xiaomi MiMo v2.5-pro | Hybrid Search + Reranking
          </p>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'border bg-card'
        }`}
      >
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {message.isStreaming && (
              <span className="inline-block h-4 w-2 animate-pulse bg-foreground" />
            )}
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 border-t pt-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Sources ({message.citations.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((cite, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {cite.document_id.slice(0, 8)}...
                  {cite.page ? ` p.${cite.page}` : ''}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {message.groundedness_score !== undefined && message.groundedness_score > 0 && (
          <div className="mt-2">
            <Badge
              variant={message.groundedness_score > 0.7 ? 'default' : 'secondary'}
              className="text-xs"
            >
              Grounded: {Math.round(message.groundedness_score * 100)}%
            </Badge>
          </div>
        )}
      </div>
    </div>
  );
}
