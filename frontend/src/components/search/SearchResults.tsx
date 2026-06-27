'use client';

import Link from 'next/link';
import { FileText, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { SearchResult } from '@/types';

interface SearchResultsProps {
  results: SearchResult[];
}

export function SearchResults({ results }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary/50">
          <FileText className="h-5 w-5 text-muted-foreground/40" />
        </div>
        <p className="text-sm font-medium text-muted-foreground/60">No results found</p>
        <p className="text-xs text-muted-foreground/40">Try a different search query</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((result, index) => (
        <Card key={`${result.document_id}-${index}`} className="transition-all duration-200 hover:bg-accent/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                <span className="text-sm font-medium truncate">{result.filename}</span>
                {result.page_number && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0">p.{result.page_number}</Badge>
                )}
              </div>
              <Badge variant="secondary" className="text-[10px] shrink-0 ml-2">
                {Math.round((result.relevance_score ?? result.score) * 100)}% match
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-1">
            <p className="mb-2 text-sm text-muted-foreground/80 line-clamp-2 leading-relaxed">
              {result.chunk_text}
            </p>
            <Button variant="ghost" size="sm" asChild className="h-7 text-xs">
              <Link href={`/documents/${result.document_id}`}>
                <ExternalLink className="mr-1.5 h-3 w-3" />
                View Document
              </Link>
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
