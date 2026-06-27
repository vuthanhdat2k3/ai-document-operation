'use client';

import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ChatMessage, ChatSession, ChatSessionDetail, Citation, QAResponse } from '@/types';

export function useChatSessions() {
  return useQuery({
    queryKey: ['chat-sessions'],
    queryFn: () => api.get<{ items: ChatSession[]; total: number }>('/chat/sessions'),
  });
}

export function useChatSession(id: string | null) {
  return useQuery({
    queryKey: ['chat-session', id],
    queryFn: () => api.get<ChatSessionDetail>(`/chat/sessions/${id}`),
    enabled: !!id,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data?: { title?: string; document_id?: string }) =>
      api.post<ChatSession>('/chat/sessions', data || {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
    },
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/chat/sessions/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
    },
  });
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const sendMessage = useCallback(
    async (content: string, documentId?: string) => {
      const msgId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

      const userMessage: ChatMessage = {
        id: `${msgId}-user`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };

      const assistantMessage: ChatMessage = {
        id: `${msgId}-assistant`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
        citations: [],
      };

      setIsStreaming(true);
      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      try {
        const sid = sessionId;
        const response = await api.post<QAResponse>('/qa/ask', {
          query: content,
          document_id: documentId || undefined,
          session_id: sid || undefined,
        });

        if (response.session_id && response.session_id !== sid) {
          setSessionId(response.session_id);
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? {
                  ...m,
                  content: response.answer,
                  citations: response.citations || [],
                  groundedness_score: response.groundedness_score,
                  isStreaming: false,
                }
              : m
          )
        );

        queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? {
                  ...m,
                  content: 'Đã xảy ra lỗi khi xử lý yêu cầu. Vui lòng thử lại.',
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, queryClient]
  );

  const loadSession = useCallback(async (sessionIdToLoad: string) => {
    try {
      const session = await api.get<ChatSessionDetail>(`/chat/sessions/${sessionIdToLoad}`);
      setSessionId(session.id);
      setMessages(
        session.messages.map((m, idx) => ({
          id: m.id || `loaded-${sessionIdToLoad}-${idx}`,
          role: m.role,
          content: m.content,
          citations: m.citations,
          groundedness_score: m.groundedness_score,
          timestamp: m.created_at || new Date().toISOString(),
        }))
      );
    } catch {
      console.error('Failed to load session');
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  return { messages, sendMessage, clearMessages, loadSession, isStreaming, sessionId };
}
