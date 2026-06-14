'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Trash2, Eye, FileText, File, FileSpreadsheet, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
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
import type { Document, DocumentStatus } from '@/types';

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
      className="flex items-center gap-1 hover:text-foreground"
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
        <ArrowUpDown className="h-3 w-3 opacity-50" />
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
    return (
      <div className="space-y-4">
        <TableSkeleton rows={5} cols={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-8 text-center">
        <p className="text-destructive font-medium">Failed to load documents</p>
        <p className="text-sm text-muted-foreground mt-1">Please try again later.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                No documents found.
              </TableCell>
            </TableRow>
          ) : (
            documents.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {fileIcon(doc.mime_type)}
                    <span className="font-medium">{doc.filename}</span>
                  </div>
                </TableCell>
                <TableCell className="uppercase text-xs">{doc.mime_type.split('/').pop()}</TableCell>
                <TableCell className="font-mono text-sm">{formatFileSize(doc.file_size_bytes)}</TableCell>
                <TableCell>
                  <Badge variant={statusVariant[doc.status]}>{doc.status}</Badge>
                </TableCell>
                <TableCell>{formatDate(doc.uploaded_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="icon" asChild aria-label={`View ${doc.filename}`}>
                      <Link href={`/documents/${doc.id}`}>
                        <Eye className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteMutation.mutate(doc.id)}
                      disabled={deleteMutation.isPending}
                      aria-label={`Delete ${doc.filename}`}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages} — {data?.total ?? 0} documents
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange?.(page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange?.(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
