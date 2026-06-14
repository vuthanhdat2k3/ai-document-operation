import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { SearchResponse } from '@/types';

export function useSearch(query: string, limit = 20) {
  return useQuery({
    queryKey: ['search', query, limit],
    queryFn: () =>
      api.get<SearchResponse>('/search', { q: query, limit }),
    enabled: query.length > 0,
  });
}
