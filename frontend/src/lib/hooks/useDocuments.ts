import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Document, DocumentDetail, PaginatedResponse } from '@/types';

export function useDocuments(page = 1, pageSize = 20, search?: string) {
  return useQuery({
    queryKey: ['documents', page, pageSize, search],
    queryFn: () =>
      api.get<PaginatedResponse<Document>>('/documents', {
        page,
        page_size: pageSize,
        search,
      }),
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => api.get<DocumentDetail>(`/documents/${id}`),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      api.upload<Document>('/documents', file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/documents/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useParseDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/documents/${id}/parse`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document'] });
    },
  });
}

export function useIndexDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/documents/${id}/index`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document'] });
    },
  });
}

export function useProcessDocument() {
  const parse = useParseDocument();
  const index = useIndexDocument();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      // Step 1: Parse
      await parse.mutateAsync(id);
      // Step 2: Wait a bit for parsing to complete
      await new Promise((r) => setTimeout(r, 2000));
      // Step 3: Index
      return index.mutateAsync(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document'] });
    },
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.get<import('@/types').DashboardStats>('/dashboard/stats'),
  });
}
