'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Trash2, Eye, FileText, File, FileSpreadsheet, ArrowUpDown, ArrowUp, ArrowDown, AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { TableSkeleton } from '@/components/ui/skeleton';
import { useDocuments, useDeleteDocument } from '@/lib/hooks/useDocuments';
import { formatFileSize, formatDate } from '@/lib/utils';
import type { DocumentStatus } from '@/types';

interface DocumentListProps {
  page?: number;
  pageSize?: number;
  search?: string;
  onPageChange?: (page: number) => void;
}

type SortField = 'filename' | 'file_size_bytes' | 'status' | 'uploaded_at';
type SortDirection = 'asc' | 'desc';

const statusVariant: Record<DocumentStatus, 'default' | 'secondary' | 'destructive' | 'success' | 'warning'> = {
  uploaded: 'secondary',
  queued: 'secondary',
  processing: 'warning',
  completed: 'success',
  failed: 'destructive',
  deleted: 'destructive',
};

const fileIcon = (mimeType: string) => {
  if (mimeType.includes('pdf')) return <FileText className="h-4 w-4" />;
  if (mimeType.includes('spreadsheet') || mimeType.includes('csv') || mimeType.includes('excel'))
    return <FileSpreadsheet className="h-4 w-4" />;
  return <File className="h-4 w-4" />;
};

function SortButton({
  field,
  label,
  currentSort,
  onSort,
}: {
  field: SortField;
  label: string;
  currentSort: { field: SortField; direction: SortDirection };
  onSort: (field: SortField) => void;
}) {
  const isActive = currentSort.field === field;
  return (
    <button
      className="flex items-center gap-1 hover:text-foreground transition-colors"
      onClick={() => onSort(field)}
      aria-label={`Sort by ${label}`}
    >
      {label}
      {isActive ? (
        currentSort.direction === 'asc' ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      ) : (
        <ArrowUpDown className="h-3 w-3 opacity-40" />
      )}
    </button>
  );
}

export function DocumentList({ page = 1, pageSize = 20, search, onPageChange }: DocumentListProps) {
  const { data, isLoading, error } = useDocuments(page, pageSize, search);
  const deleteMutation = useDeleteDocument();
  const [sortConfig, setSortConfig] = useState<{ field: SortField; direction: SortDirection }>({
    field: 'uploaded_at',
    direction: 'desc',
  });

  const handleSort = (field: SortField) => {
    setSortConfig((prev) => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const documents = useMemo(() => {
    const items = data?.items ?? [];
    return [...items].sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      switch (sortConfig.field) {
        case 'filename':
          aVal = a.filename.toLowerCase();
          bVal = b.filename.toLowerCase();
          break;
        case 'file_size_bytes':
          aVal = a.file_size_bytes;
          bVal = b.file_size_bytes;
          break;
        case 'status':
          aVal = a.status;
          bVal = b.status;
          break;
        case 'uploaded_at':
        default:
          aVal = new Date(a.uploaded_at).getTime();
          bVal = new Date(b.uploaded_at).getTime();
          break;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data?.items, sortConfig]);

  const totalPages = data?.pages ?? 1;

  if (isLoading) {
    return <TableSkeleton rows={5} cols={6} />;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-8 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/10">
          <AlertTriangle className="h-5 w-5 text-destructive" />
        </div>
        <p className="font-medium text-destructive">Failed to load documents</p>
        <p className="mt-1 text-sm text-muted-foreground">Please try again later.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border/30 bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortButton field="filename" label="Name" currentSort={sortConfig} onSort={handleSort} />
              </TableHead>
              <TableHead>Type</TableHead>
              <TableHead>
                <SortButton field="file_size_bytes" label="Size" currentSort={sortConfig} onSort={handleSort} />
              </TableHead>
              <TableHead>
                <SortButton field="status" label="Status" currentSort={sortConfig} onSort={handleSort} />
              </TableHead>
              <TableHead>
                <SortButton field="uploaded_at" label="Uploaded" currentSort={sortConfig} onSort={handleSort} />
              </TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-12 text-center">
                  <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-secondary/50">
                    <FileText className="h-5 w-5 text-muted-foreground/50" />
                  </div>
                  <p className="text-sm text-muted-foreground/60">No documents found</p>
                </TableCell>
              </TableRow>
            ) : (
              documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/[0.06]">
                        {fileIcon(doc.mime_type)}
                      </div>
                      <span className="text-sm font-medium">{doc.filename}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground/70 uppercase font-mono">{doc.mime_type.split('/').pop()}</TableCell>
                  <TableCell className="text-sm font-mono text-muted-foreground/80">{formatFileSize(doc.file_size_bytes)}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant[doc.status]} className="text-[10px] px-2 py-0.5">
                      {doc.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground/70">{formatDate(doc.uploaded_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-0.5">
                      <Button variant="ghost" size="icon" asChild className="h-7 w-7" aria-label={`View ${doc.filename}`}>
                        <Link href={`/documents/${doc.id}`}>
                          <Eye className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteMutation.mutate(doc.id)}
                        disabled={deleteMutation.isPending}
                        className="h-7 w-7 text-muted-foreground/40 hover:text-destructive"
                        aria-label={`Delete ${doc.filename}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg bg-secondary/30 px-4 py-2.5">
          <span className="text-xs text-muted-foreground/70">
            Page {page} of {totalPages}
            <span className="mx-1.5 text-muted-foreground/30">&middot;</span>
            {data?.total ?? 0} documents
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange?.(page - 1)}
              className="h-7 text-xs"
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange?.(page + 1)}
              className="h-7 text-xs"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
