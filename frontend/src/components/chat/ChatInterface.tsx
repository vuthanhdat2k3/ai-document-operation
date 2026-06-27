'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  FileText,
  Sparkles,
  Bot,
  User,
  ArrowDown,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Trash2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useChat } from '@/lib/hooks/useChat';
import { ChatSessionSidebar } from './ChatSessionSidebar';
import type { ChatMessage } from '@/types';

function TypingDots() {
  return (
    <div className="flex items-center gap-1.5">
      <span className="typing-dot inline-block h-2 w-2 rounded-full bg-foreground/40" />
      <span className="typing-dot inline-block h-2 w-2 rounded-full bg-foreground/40" />
      <span className="typing-dot inline-block h-2 w-2 rounded-full bg-foreground/40" />
    </div>
  );
}

function MessageTimestamp({ timestamp }: { timestamp: string }) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  let label: string;
  if (diffMins < 1) label = 'Vừa xong';
  else if (diffMins < 60) label = `${diffMins} phút trước`;
  else if (diffMins < 1440) label = `${Math.floor(diffMins / 60)} giờ trước`;
  else label = date.toLocaleDateString('vi-VN');

  return (
    <span className="text-[11px] font-medium tracking-wide text-muted-foreground/60 uppercase">
      {label}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground/40 opacity-0 transition-all duration-200 hover:bg-secondary group-hover:opacity-100 hover:text-muted-foreground active:scale-90"
      aria-label="Copy message"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function CitationBadges({ citations }: { citations: NonNullable<ChatMessage['citations']> }) {
  const [expanded, setExpanded] = useState(false);

  if (!citations.length) return null;

  const displayed = expanded ? citations : citations.slice(0, 3);

  return (
    <div className="mt-3 border-t border-border/50 pt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground/70 transition-colors hover:text-muted-foreground"
      >
        <FileText className="h-3.5 w-3.5" />
        Sources ({citations.length})
        {citations.length > 3 && (
          expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
        )}
      </button>
      <div className="flex flex-wrap gap-1.5">
        {displayed.map((cite, i) => (
          <Badge
            key={i}
            variant="outline"
            className="border-border/40 bg-secondary/50 px-2.5 py-0.5 text-[11px] font-normal text-muted-foreground/80 transition-colors hover:bg-secondary"
          >
            <FileText className="mr-1 h-3 w-3" />
            {cite.document_id.slice(0, 8)}
            {cite.page ? ` · p.${cite.page}` : ''}
            <span className="ml-1 text-[10px] text-muted-foreground/50">
              {Math.round(cite.score * 100)}%
            </span>
          </Badge>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isLoading = !isUser && message.isStreaming;

  return (
    <div className={`message-enter flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`group flex max-w-[85%] items-end gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
            isUser
              ? 'bg-primary/10 text-primary'
              : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
          }`}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>

        {/* Bubble */}
        <div className="flex flex-col">
          <div
            className={`rounded-2xl px-5 py-3.5 ${
              isUser
                ? 'bg-chat-user text-chat-user-foreground shadow-sm'
                : isLoading
                  ? 'border bg-secondary/60 shadow-sm'
                  : 'border bg-secondary/80 shadow-sm'
            }`}
          >
            {isUser ? (
              <p className="text-[15px] leading-relaxed">{message.content}</p>
            ) : isLoading ? (
              <div className="flex items-center gap-2.5">
                <span className="text-sm text-muted-foreground/60">Đang trả lời</span>
                <TypingDots />
              </div>
            ) : (
              <>
                <div className="prose prose-sm dark:prose-invert max-w-none text-[15px] leading-relaxed">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.citations && message.citations.length > 0 && (
                  <CitationBadges citations={message.citations} />
                )}

                {message.groundedness_score !== undefined && message.groundedness_score > 0 && (
                  <div className="mt-2.5 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border/50">
                      <div
                        className="h-full rounded-full bg-emerald-500/60 transition-all duration-500"
                        style={{ width: `${Math.round(message.groundedness_score * 100)}%` }}
                      />
                    </div>
                    <span className="text-[11px] font-medium text-muted-foreground/60 whitespace-nowrap">
                      {Math.round(message.groundedness_score * 100)}% grounded
                    </span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer: timestamp + copy */}
          <div className={`mt-1.5 flex items-center gap-2 px-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
            {isLoading ? (
              <span className="text-[11px] font-medium tracking-wide text-muted-foreground/40 uppercase">Đang xử lý...</span>
            ) : (
              <MessageTimestamp timestamp={message.timestamp} />
            )}
            {!isUser && !isLoading && message.content && <CopyButton text={message.content} />}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ChatInterface() {
  const { messages, sendMessage, clearMessages, loadSession, isStreaming, sessionId } = useChat();
  const [input, setInput] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isNearBottom]);

  // Auto-resize textarea
  const adjustTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }
  }, []);

  useEffect(() => {
    adjustTextarea();
  }, [input, adjustTextarea]);

  // Track scroll position
  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const threshold = 100;
    const atBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
    setIsNearBottom(atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setIsNearBottom(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const msg = input.trim();
    setInput('');
    setIsNearBottom(true);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await sendMessage(msg);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleNewChat = () => {
    clearMessages();
  };

  const handleSelectSession = (sid: string) => {
    loadSession(sid);
  };

  const suggestionQuestions = [
    'Tóm tắt nội dung chính',
    'Những rủi ro nào được phát hiện?',
    'Cho tôi checklist cần làm',
  ];

  return (
    <div className="flex h-[calc(100vh-120px)] overflow-hidden rounded-xl border bg-background shadow-sm">
      {/* Sidebar */}
      {showSidebar && (
        <ChatSessionSidebar
          currentSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onToggle={() => setShowSidebar(false)}
        />
      )}

      {/* Main Chat Area */}
      <div className="relative flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/50 px-6 py-3.5">
          <div className="flex items-center gap-3">
            {!showSidebar && (
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowSidebar(true)} aria-label="Show sidebar">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-foreground/70">
                  <rect x="1" y="3" width="14" height="1.5" rx="0.75" fill="currentColor" />
                  <rect x="1" y="7.25" width="14" height="1.5" rx="0.75" fill="currentColor" />
                  <rect x="1" y="11.5" width="14" height="1.5" rx="0.75" fill="currentColor" />
                </svg>
              </Button>
            )}
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Document Q&A</h2>
              {sessionId && (
                <p className="text-[11px] text-muted-foreground/60">
                  Session {sessionId.slice(0, 8)}...
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNewChat}
              className="h-8 gap-1.5 rounded-lg text-xs font-medium text-muted-foreground/80 hover:text-foreground"
            >
              <FileText className="h-3.5 w-3.5" />
              New Chat
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearMessages}
              disabled={messages.length === 0}
              className="h-8 gap-1.5 rounded-lg text-xs font-medium text-muted-foreground/60 hover:text-destructive disabled:opacity-30"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          className="chat-scrollbar flex-1 overflow-auto px-6 py-6"
        >
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="mx-auto max-w-md text-center">
                <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/10 to-primary/5 ring-1 ring-primary/10 ring-inset">
                  <Sparkles className="h-7 w-7 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">Hỏi đáp về tài liệu</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground/80">
                  Hệ thống sẽ tìm kiếm trong tất cả tài liệu đã index và trả lời với citations.
                  Hỗ trợ tiếng Việt và tiếng Anh.
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-2">
                  {suggestionQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => {
                        setInput(q);
                        textareaRef.current?.focus();
                      }}
                      className="inline-flex items-center rounded-full border border-border/60 bg-secondary/50 px-4 py-2 text-sm text-muted-foreground/80 transition-all duration-200 hover:border-primary/30 hover:bg-primary/[0.06] hover:text-foreground active:scale-[0.97]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Jump to bottom button */}
        {!isNearBottom && messages.length > 0 && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-24 left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border bg-background shadow-lg backdrop-blur-sm transition-all duration-200 hover:bg-secondary active:scale-90"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-4 w-4 text-muted-foreground" />
          </button>
        )}

        {/* Input Area */}
        <div className="border-t border-border/50 bg-gradient-to-t from-background via-background to-transparent px-6 pb-4 pt-3">
          <form
            onSubmit={handleSubmit}
            className="mx-auto max-w-3xl"
          >
            <div className="glass group flex items-end gap-2 rounded-2xl border border-border/60 p-2 pl-5 transition-all duration-200 focus-within:border-primary/30 focus-within:shadow-[0_0_0_1px_hsl(var(--primary)/0.15)]">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Đặt câu hỏi về tài liệu..."
                disabled={isStreaming}
                rows={1}
                className="flex-1 resize-none bg-transparent text-[15px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/50 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Chat message input"
              />
              <Button
                type="submit"
                disabled={!input.trim() || isStreaming}
                size="icon"
                className="mb-0.5 h-9 w-9 shrink-0 rounded-full transition-all duration-200 active:scale-90 disabled:opacity-40"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-2 text-center text-[11px] text-muted-foreground/40">
              AI-powered document analysis
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
