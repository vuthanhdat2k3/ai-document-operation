'use client';

import { useState } from 'react';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';
import { useSearch } from '@/lib/hooks/useSearch';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const { data, isLoading } = useSearch(query);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Search</h2>
        <p className="text-muted-foreground">
          Search through your documents using semantic search.
        </p>
      </div>

      <SearchBar onSearch={setQuery} />

      {data && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {data.total} result{data.total !== 1 ? 's' : ''} for &ldquo;{data.query}&rdquo;
          </span>
          <span>{data.took_ms}ms</span>
        </div>
      )}

      <SearchResults results={data?.results ?? []} isLoading={isLoading && query.length > 0} />
    </div>
  );
}
