'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AgentSession, AgentStep } from '@/types';

export interface AgentRunRequest {
  task_type: 'qa' | 'summarize' | 'extract' | 'risk' | 'checklist' | 'report';
  query: string;
  document_id?: string;
  max_iterations?: number;
}

export interface AgentRunResponse {
  session_id: string;
  status: string;
  answer: string;
  iterations: number;
  cost: {
    total_tokens: number;
    total_cost_usd: number;
    max_cost_usd?: number;
    budget_exceeded?: boolean;
  };
  steps: AgentStep[];
  duration_ms: number;
}

export function useAgentSessions() {
  return useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () =>
      api.get<{ items: AgentSession[]; total: number }>('/agent/sessions', {
        limit: 50,
      }),
    refetchInterval: 10_000,
  });
}

export function useAgentSession(id: string | null) {
  return useQuery({
    queryKey: ['agent-session', id],
    queryFn: () => api.get<AgentSession>(`/agent/sessions/${id}`),
    enabled: !!id,
  });
}

export function useRunAgentTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AgentRunRequest) =>
      api.post<AgentRunResponse>('/agent/run', {
        task_type: data.task_type,
        query: data.query,
        ...(data.document_id && { document_id: data.document_id }),
        ...(data.max_iterations && { max_iterations: data.max_iterations }),
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
      queryClient.invalidateQueries({
        queryKey: ['agent-session', result.session_id],
      });
    },
  });
}
