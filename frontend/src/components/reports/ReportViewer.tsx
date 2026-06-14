'use client';

import { FileDown, RefreshCw, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate } from '@/lib/utils';
import type { Report } from '@/types';

interface ReportViewerProps {
  reports: Report[];
  isLoading?: boolean;
  onGenerate?: () => void;
  onRefresh?: () => void;
  selectedReport?: Report | null;
  onSelectReport?: (report: Report) => void;
}

function ReportListSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border p-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-4 w-32" />
            </div>
            <Skeleton className="h-5 w-16" />
          </div>
          <Skeleton className="h-3 w-24 mt-1" />
        </div>
      ))}
    </div>
  );
}

function ReportContentSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-9 w-32" />
      </div>
      <Skeleton className="h-4 w-32 mb-4" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  );
}

export function ReportViewer({
  reports,
  isLoading,
  onGenerate,
  onRefresh,
  selectedReport,
  onSelectReport,
}: ReportViewerProps) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-1 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Reports</h3>
          <div className="flex gap-2">
            {onRefresh && (
              <Button variant="ghost" size="icon" onClick={onRefresh} aria-label="Refresh reports">
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
            {onGenerate && (
              <Button size="sm" onClick={onGenerate}>
                Generate
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <ReportListSkeleton />
        ) : reports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reports yet.</p>
        ) : (
          <div className="space-y-2">
            {reports.map((report) => (
              <Card
                key={report.id}
                className={`cursor-pointer transition-colors ${
                  selectedReport?.id === report.id ? 'border-primary' : ''
                }`}
                onClick={() => onSelectReport?.(report)}
                role="button"
                aria-pressed={selectedReport?.id === report.id}
              >
                <CardContent className="p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{report.title}</span>
                    </div>
                    <Badge
                      variant={
                        report.status === 'completed'
                          ? 'success'
                          : report.status === 'failed'
                            ? 'destructive'
                            : 'warning'
                      }
                    >
                      {report.status}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatDate(report.created_at)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="lg:col-span-2">
        {isLoading && !selectedReport ? (
          <ReportContentSkeleton />
        ) : selectedReport ? (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{selectedReport.title}</CardTitle>
                {selectedReport.file_url && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={selectedReport.file_url} download aria-label="Download PDF">
                      <FileDown className="mr-2 h-4 w-4" />
                      Download PDF
                    </a>
                  </Button>
                )}
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>{selectedReport.report_type}</span>
                <span>•</span>
                <span>{formatDate(selectedReport.created_at)}</span>
              </div>
            </CardHeader>
            <CardContent>
              {selectedReport.status === 'generating' ? (
                <div className="space-y-3 p-8">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-5/6" />
                  <p className="text-muted-foreground text-sm mt-4">Generating report...</p>
                </div>
              ) : selectedReport.status === 'failed' ? (
                <div className="rounded-md bg-destructive/10 p-4 text-destructive">
                  {selectedReport.error_message ?? 'Report generation failed.'}
                </div>
              ) : selectedReport.content ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown>{selectedReport.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-muted-foreground">No content available.</p>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="flex h-64 items-center justify-center text-muted-foreground">
              Select a report to view its content.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
