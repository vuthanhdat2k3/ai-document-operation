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
  Bug,
  Cpu,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useChat } from '@/lib/hooks/useChat';
import { useProviders, useProviderModels, useAgentModelConfig, useSetAgentModelConfig } from '@/lib/hooks/useProviders';
import { ChatSessionSidebar } from './ChatSessionSidebar';
import type { ChatMessage, DebugStep, LLMModel } from '@/types';

function TypingDots() {
  return (
    <div className="flex items-center gap-1">
      <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-foreground/40" />
      <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-foreground/40" />
      <span className="typing-dot inline-block h-1.5 w-1.5 rounded-full bg-foreground/40" />
    </div>
  );
}

function MessageTimestamp({ timestamp }: { timestamp: string }) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  let label: string;
  if (diffMins < 1) label = 'Just now';
  else if (diffMins < 60) label = `${diffMins}m ago`;
  else if (diffMins < 1440) label = `${Math.floor(diffMins / 60)}h ago`;
  else label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <span className="text-[10px] text-muted-foreground/40">
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
      className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/30 opacity-0 transition-all duration-200 hover:bg-secondary/70 group-hover:opacity-100 hover:text-muted-foreground/60 active:scale-90"
      aria-label="Copy message"
    >
      {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

function CitationBadges({ citations }: { citations: NonNullable<ChatMessage['citations']> }) {
  const [expanded, setExpanded] = useState(false);

  if (!citations.length) return null;

  const displayed = expanded ? citations : citations.slice(0, 3);

  return (
    <div className="mt-3 border-t border-border/30 pt-2.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground/60 transition-colors hover:text-muted-foreground"
      >
        <FileText className="h-3 w-3" />
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
            className="border-border/30 bg-secondary/40 px-2 py-0.5 text-[10px] font-normal text-muted-foreground/70 transition-colors hover:bg-secondary/70"
          >
            <FileText className="mr-1 h-2.5 w-2.5" />
            {cite.document_id.slice(0, 8)}
            {cite.page ? ` \u00b7 p.${cite.page}` : ''}
            <span className="ml-1 text-[9px] text-muted-foreground/40">
              {Math.round(cite.score * 100)}%
            </span>
          </Badge>
        ))}
      </div>
    </div>
  );
}

function DebugStepsPanel({ steps }: { steps: DebugStep[] }) {
  const [open, setOpen] = useState(false);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border/30 pt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground/40 transition-colors hover:text-muted-foreground/60"
      >
        <Bug className="h-3 w-3" />
        Agent Steps ({steps.length})
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="mt-2 space-y-1">
          {steps.map((step, i) => (
            <div
              key={i}
              className="rounded-lg border border-border/25 bg-background/40 px-2.5 py-1.5 text-[10px] leading-relaxed"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-foreground/70 uppercase tracking-wider">
                  {step.step_type}
                </span>
                <span className="text-muted-foreground/30 shrink-0 tabular-nums">
                  #{step.iteration} \u00b7 {step.duration_ms}ms
                </span>
              </div>
              {step.input_summary && (
                <div className="mt-0.5 text-muted-foreground/50">
                  <span className="font-medium text-muted-foreground/40">\u2192</span> {step.input_summary}
                </div>
              )}
              {step.output_summary && (
                <div className="text-muted-foreground/50 truncate" title={step.output_summary}>
                  <span className="font-medium text-muted-foreground/40">\u2190</span> {step.output_summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isLoading = !isUser && message.isStreaming;

  return (
    <div className={`message-enter flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`group flex max-w-[80%] items-end gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 ring-border/20 ${
            isUser
              ? 'bg-primary/10 text-primary'
              : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
          }`}
        >
          {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
        </div>

        {/* Bubble */}
        <div className="flex flex-col">
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? 'bg-chat-user text-chat-user-foreground shadow-sm'
                : isLoading
                  ? 'border border-border/25 bg-card shadow-sm'
                  : 'border border-border/25 bg-card shadow-sm'
            }`}
          >
            {isUser ? (
              <p className="text-sm leading-relaxed">{message.content}</p>
            ) : isLoading ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground/50">Responding</span>
                <TypingDots />
              </div>
            ) : (
              <>
                <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.citations && message.citations.length > 0 && (
                  <CitationBadges citations={message.citations} />
                )}

                {message.groundedness_score !== undefined && message.groundedness_score > 0 && (
                  <div className="mt-2.5 flex items-center gap-2">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-border/40">
                      <div
                        className="h-full rounded-full bg-success/50 transition-all duration-500"
                        style={{ width: `${Math.round(message.groundedness_score * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground/50 whitespace-nowrap tabular-nums">
                      {Math.round(message.groundedness_score * 100)}% grounded
                    </span>
                  </div>
                )}

                {message.debug_steps && message.debug_steps.length > 0 && (
                  <DebugStepsPanel steps={message.debug_steps} />
                )}
              </>
            )}
          </div>

          {/* Footer: timestamp + copy */}
          <div className={`mt-1 flex items-center gap-1.5 px-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
            {isLoading ? (
              <span className="text-[10px] text-muted-foreground/30">Processing...</span>
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

// ─── Model Selector ──────────────────────────────────────────────────────────

function ModelSelector() {
  const [open, setOpen] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const configQuery = useAgentModelConfig('doc-qa');
  const providersQuery = useProviders();
  const modelsQuery = useProviderModels(selectedProviderId);
  const setConfigMutation = useSetAgentModelConfig();

  const currentConfig = configQuery.data;
  const providers = providersQuery.data?.items ?? [];
  const models = modelsQuery.data?.items ?? [];

  const currentProvider = providers.find((p) => p.id === currentConfig?.provider_id);

  const handleSelect = async (model: LLMModel) => {
    try {
      await setConfigMutation.mutateAsync({
        agentName: 'doc-qa',
        provider_id: model.provider_id,
        model_id: model.id,
        temperature: 0.1,
        max_tokens: model.max_tokens,
      });
      setOpen(false);
    } catch {
    }
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedProviderId(null);
  };

  const currentLabel = configQuery.isLoading
    ? '...'
    : currentConfig
      ? (currentConfig.model_name ?? currentConfig.model_slug ?? 'Configured')
      : 'Default';

  const providersLoading = providersQuery.isLoading;
  const providersEmpty = !providersLoading && providers.length === 0;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={providersLoading && !currentConfig}
        className="flex items-center gap-1 rounded-lg border border-border/20 px-2 py-1 text-[11px] font-medium text-muted-foreground/60 transition-all hover:border-border/40 hover:text-foreground active:scale-[0.97] disabled:opacity-40"
      >
        <Cpu className="h-3 w-3" />
        <span>{currentLabel}</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={handleClose} />
          <div className="absolute right-0 top-full z-20 mt-1.5 w-64 origin-top-right animate-fade-up rounded-xl border border-border/30 bg-card p-1.5 shadow-lg">
            {selectedProviderId ? (
              /* ── Models view ── */
              <>
                <button
                  onClick={() => setSelectedProviderId(null)}
                  className="flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-muted-foreground/50 hover:text-foreground transition-colors w-full rounded-lg"
                >
                  <ChevronDown className="h-3 w-3 rotate-90" />
                  Back to providers
                </button>
                <div className="mt-1 border-t border-border/20" />
                <div className="max-h-64 overflow-y-auto pt-1">
                  {modelsQuery.isLoading ? (
                    <div className="space-y-2 px-2 py-3">
                      <div className="h-3 w-24 shimmer rounded" />
                      <div className="h-3 w-32 shimmer rounded" />
                      <div className="h-3 w-20 shimmer rounded" />
                    </div>
                  ) : models.length === 0 ? (
                    <p className="px-2 py-3 text-xs text-muted-foreground/50 text-center">No models for this provider</p>
                  ) : (
                    models.map((model) => {
                      const isSelected = currentConfig?.model_id === model.id;
                      return (
                        <button
                          key={model.id}
                          onClick={() => handleSelect(model)}
                          disabled={setConfigMutation.isPending}
                          className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-all ${
                            isSelected
                              ? 'bg-primary/10 text-primary'
                              : 'text-muted-foreground/70 hover:bg-accent hover:text-foreground'
                          } disabled:opacity-50`}
                        >
                          <span className="flex-1">{model.name}</span>
                          {model.slug && (
                            <span className="text-[10px] text-muted-foreground/30 font-mono">{model.slug}</span>
                          )}
                          {isSelected && <Check className="h-3 w-3 shrink-0" />}
                        </button>
                      );
                    })
                  )}
                </div>
              </>
            ) : (
              /* ── Providers view ── */
              <>
                <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/40">
                  Providers
                </div>
                {providersLoading ? (
                  <div className="space-y-2 px-2 py-3">
                    <div className="h-3 w-24 shimmer rounded" />
                    <div className="h-3 w-32 shimmer rounded" />
                    <div className="h-3 w-20 shimmer rounded" />
                  </div>
                ) : providersEmpty ? (
                  <div className="px-2 py-3 text-center">
                    <p className="text-xs text-muted-foreground/50">No providers yet</p>
                    <a href="/providers" className="mt-1 inline-block text-[11px] text-primary hover:underline">
                      Add providers &rarr;
                    </a>
                  </div>
                ) : (
                  <div className="max-h-64 overflow-y-auto pt-1">
                    {providers.map((provider) => {
                      const isActiveProvider = currentConfig?.provider_id === provider.id;
                      return (
                        <button
                          key={provider.id}
                          onClick={() => setSelectedProviderId(provider.id)}
                          className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-all ${
                            isActiveProvider
                              ? 'bg-primary/10 text-primary'
                              : 'text-muted-foreground/70 hover:bg-accent hover:text-foreground'
                          }`}
                        >
                          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-primary/[0.06]">
                            <Cpu className="h-3 w-3" />
                          </div>
                          <div className="flex-1">
                            <span>{provider.name}</span>
                            {isActiveProvider && (
                              <span className="ml-2 text-[10px] text-primary/60">
                                ({currentConfig?.model_name ?? currentConfig?.model_slug})
                              </span>
                            )}
                          </div>
                          <ChevronDown className="h-3 w-3 -rotate-90 text-muted-foreground/30 shrink-0" />
                        </button>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
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
    'Summarize the key findings',
    'What risks were detected?',
    'Generate a checklist',
  ];

  return (
    <div className="flex h-[calc(100vh-120px)] overflow-hidden rounded-xl border border-border/30 bg-card shadow-sm">
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
        <div className="flex items-center justify-between border-b border-border/30 px-5 py-2.5">
          <div className="flex items-center gap-3">
            {!showSidebar && (
              <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground/40" onClick={() => setShowSidebar(true)} aria-label="Show sidebar">
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                  <rect x="1" y="3" width="14" height="1.5" rx="0.75" fill="currentColor" />
                  <rect x="1" y="7.25" width="14" height="1.5" rx="0.75" fill="currentColor" />
                  <rect x="1" y="11.5" width="14" height="1.5" rx="0.75" fill="currentColor" />
                </svg>
              </Button>
            )}
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/[0.06]">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Document Q&A</h2>
              {sessionId && (
                <p className="text-[10px] text-muted-foreground/40">
                  Session {sessionId.slice(0, 8)}...
                </p>
              )}
            </div>
            <ModelSelector />
          </div>
          <div className="flex items-center gap-0.5">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNewChat}
              className="h-7 gap-1.5 rounded-lg text-xs text-muted-foreground/60 hover:text-foreground"
            >
              <FileText className="h-3.5 w-3.5" />
              New Chat
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearMessages}
              disabled={messages.length === 0}
              className="h-7 gap-1.5 rounded-lg text-xs text-muted-foreground/40 hover:text-destructive disabled:opacity-20"
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
          className="chat-scrollbar flex-1 overflow-auto px-5 py-5"
        >
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="mx-auto max-w-sm text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/[0.06] to-primary/[0.02] ring-1 ring-primary/[0.06]">
                  <Sparkles className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-base font-semibold">Ask about your documents</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground/70">
                  Search across all indexed documents and get answers with citations.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {suggestionQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => {
                        setInput(q);
                        textareaRef.current?.focus();
                      }}
                      className="inline-flex items-center rounded-full border border-border/40 bg-secondary/40 px-3.5 py-1.5 text-xs text-muted-foreground/70 transition-all duration-200 hover:border-primary/25 hover:bg-primary/[0.04] hover:text-foreground active:scale-[0.97]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-5">
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
            className="absolute bottom-24 left-1/2 z-10 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-border/30 bg-background/80 backdrop-blur-sm shadow-sm transition-all duration-200 hover:bg-secondary active:scale-90 animate-fade-up"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-3.5 w-3.5 text-muted-foreground/60" />
          </button>
        )}

        {/* Input Area */}
        <div className="border-t border-border/30 bg-gradient-to-t from-background/60 via-background/40 to-transparent px-5 pb-3 pt-2.5">
          <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-2xl border border-border/40 bg-background/80 backdrop-blur-sm p-1.5 pl-4 transition-all duration-200 focus-within:border-primary/25 focus-within:ring-1 focus-within:ring-primary/[0.12]">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your documents..."
                disabled={isStreaming}
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/40 disabled:cursor-not-allowed disabled:opacity-50 py-1.5"
                aria-label="Chat message input"
              />
              <Button
                type="submit"
                disabled={!input.trim() || isStreaming}
                size="icon"
                className="mb-0.5 h-8 w-8 shrink-0 rounded-full transition-all duration-200 active:scale-90 disabled:opacity-30"
                aria-label="Send message"
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
            <p className="mt-1.5 text-center text-[10px] text-muted-foreground/30">
              AI-powered document analysis
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
