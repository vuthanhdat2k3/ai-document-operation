'use client';

import Link from 'next/link';
import { FileText, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { SearchResult } from '@/types';

interface SearchResultsProps {
  results: SearchResult[];
  isLoading?: boolean;
}

export function SearchResults({ results, isLoading }: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        No results found. Try a different search query.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((result, index) => (
        <Card key={`${result.document_id}-${index}`} className="transition-shadow hover:shadow-md">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{result.filename}</span>
                {result.page_number && (
                  <Badge variant="outline">Page {result.page_number}</Badge>
                )}
              </div>
              <Badge variant="secondary">
                {Math.round(result.relevance_score * 100)}% match
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-muted-foreground line-clamp-3">
              {result.chunk_text}
            </p>
            <Button variant="ghost" size="sm" asChild>
              <Link href={`/documents/${result.document_id}`}>
                <ExternalLink className="mr-2 h-3 w-3" />
                View Document
              </Link>
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
