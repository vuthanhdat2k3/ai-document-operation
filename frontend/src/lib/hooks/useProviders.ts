'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { LLMProvider, LLMModel, AgentModelConfig, AgentInfo, PaginatedResponse } from '@/types';

// ─── Providers ───────────────────────────────────────────────────────────────

export function useProviders(page = 1, pageSize = 50) {
  return useQuery({
    queryKey: ['providers', page, pageSize],
    queryFn: () =>
      api.get<PaginatedResponse<LLMProvider>>('/providers', {
        page,
        page_size: pageSize,
      }),
  });
}

export function useProvider(id: string | null) {
  return useQuery({
    queryKey: ['provider', id],
    queryFn: () => api.get<LLMProvider>(`/providers/${id}`),
    enabled: !!id,
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      slug: string;
      description?: string | null;
      api_base_url?: string | null;
      api_key?: string | null;
    }) => api.post<LLMProvider>('/providers', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] });
    },
  });
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (data: { api_base_url: string; api_key?: string | null; provider_slug?: string }) =>
      api.post<{ success: boolean; message: string; latency_ms?: number }>('/providers/test', data),
  });
}

export function useTestModel() {
  return useMutation({
    mutationFn: (data: { provider_id: string; model_slug: string }) =>
      api.post<{ success: boolean; message: string; latency_ms?: number; available_models?: string[] }>('/models/test', data),
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      slug?: string;
      description?: string | null;
      api_base_url?: string | null;
      api_key?: string | null;
      is_active?: boolean;
    }) => api.put<LLMProvider>(`/providers/${id}`, data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['providers'] });
      queryClient.invalidateQueries({ queryKey: ['provider', result.id] });
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/providers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] });
    },
  });
}

// ─── Models ──────────────────────────────────────────────────────────────────

export function useProviderModels(providerId: string | null) {
  return useQuery({
    queryKey: ['provider-models', providerId],
    queryFn: () =>
      api.get<PaginatedResponse<LLMModel>>(`/providers/${providerId}/models`),
    enabled: !!providerId,
  });
}

export function useModels(params?: { provider_id?: string }) {
  return useQuery({
    queryKey: ['models', params],
    queryFn: () => api.get<PaginatedResponse<LLMModel>>('/models', params as Record<string, string | number | boolean | undefined>),
  });
}

export function useCreateModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      providerId,
      ...data
    }: {
      providerId: string;
      name: string;
      slug: string;
      description?: string | null;
      max_tokens: number;
      default_temperature?: number;
      supports_streaming?: boolean;
      supports_thinking?: boolean;
    }) => api.post<LLMModel>(`/providers/${providerId}/models`, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['provider-models', variables.providerId] });
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
  });
}

export function useUpdateModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      slug?: string;
      description?: string | null;
      max_tokens?: number;
      default_temperature?: number;
      supports_streaming?: boolean;
      supports_thinking?: boolean;
      is_active?: boolean;
    }) => api.put<LLMModel>(`/models/${id}`, data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['provider-models'] });
    },
  });
}

export function useDeleteModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/models/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['provider-models'] });
    },
  });
}

// ─── Agent Model Configs ─────────────────────────────────────────────────────

export function useAgentModelConfig(agentName: string | null) {
  return useQuery({
    queryKey: ['agent-model-config', agentName],
    queryFn: () => api.get<AgentModelConfig>(`/agents/${agentName}/model-config`),
    enabled: !!agentName,
    retry: false,
  });
}

export function useSetAgentModelConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      agentName,
      ...data
    }: {
      agentName: string;
      provider_id: string;
      model_id: string;
      temperature?: number | null;
      max_tokens?: number | null;
    }) => api.put<AgentModelConfig>(`/agents/${agentName}/model-config`, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['agent-model-config', variables.agentName] });
    },
  });
}

export function useDeleteAgentModelConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (agentName: string) => api.delete(`/agents/${agentName}/model-config`),
    onSuccess: (_result, agentName) => {
      queryClient.invalidateQueries({ queryKey: ['agent-model-config', agentName] });
    },
  });
}

// ─── Available Agents ────────────────────────────────────────────────────────

export function useAvailableAgents() {
  return useQuery({
    queryKey: ['available-agents'],
    queryFn: () => api.get<AgentInfo[]>('/agent'),
  });
}
