'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';
import { useSearch } from '@/lib/hooks/useSearch';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const { data, isLoading } = useSearch(query);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Search</h2>
        <p className="mt-1 text-sm text-muted-foreground/70">
          Search through your documents using semantic search.
        </p>
      </div>

      <SearchBar onSearch={setQuery} />

      {data && (
        <div className="flex items-center justify-between rounded-lg bg-secondary/40 px-4 py-2.5 text-sm text-muted-foreground/70">
          <span>
            {data.total} result{data.total !== 1 ? 's' : ''} for &ldquo;{data.query}&rdquo;
          </span>
          <span className="text-xs text-muted-foreground/50">{data.took_ms}ms</span>
        </div>
      )}

      {isLoading && query.length > 0 ? (
        <div className="flex items-center justify-center p-8">
          <div className="flex items-center gap-2.5 text-muted-foreground/60">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary/40 border-t-primary" />
            <span className="text-sm">Searching...</span>
          </div>
        </div>
      ) : !query ? (
        <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary/50">
            <Search className="h-6 w-6 text-muted-foreground/40" />
          </div>
          <p className="text-sm font-medium text-muted-foreground/60">Search your documents</p>
          <p className="text-xs text-muted-foreground/40">Enter a query to search across all uploaded documents.</p>
        </div>
      ) : null}

      {data && data.results.length > 0 && <SearchResults results={data.results} />}
    </div>
  );
}
