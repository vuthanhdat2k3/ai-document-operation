'use client';

import { FileDown, RefreshCw, FileText, AlertTriangle } from 'lucide-react';
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
        <div key={i} className="rounded-lg border border-border/30 bg-card p-3 shadow-sm">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-4 w-32" />
            </div>
            <Skeleton className="h-5 w-16" />
          </div>
          <Skeleton className="h-3 w-24 mt-1.5" />
        </div>
      ))}
    </div>
  );
}

function ReportContentSkeleton() {
  return (
    <div className="rounded-xl border border-border/30 bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-8 w-28" />
      </div>
      <Skeleton className="h-3 w-32 mb-4" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
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
          <h3 className="text-sm font-semibold text-foreground/80">Reports</h3>
          <div className="flex gap-1.5">
            {onRefresh && (
              <Button variant="ghost" size="icon" onClick={onRefresh} className="h-7 w-7 text-muted-foreground/40 hover:text-foreground" aria-label="Refresh reports">
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            )}
            {onGenerate && (
              <Button size="sm" onClick={onGenerate} className="h-7 rounded-lg text-xs gap-1.5 px-3">
                Generate
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <ReportListSkeleton />
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-secondary/50">
              <FileText className="h-[18px] w-[18px] text-muted-foreground/40" />
            </div>
            <p className="text-sm text-muted-foreground/60">No reports yet</p>
            <p className="mt-1 text-xs text-muted-foreground/40">Generate your first report</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {reports.map((report) => (
              <Card
                key={report.id}
                className={`cursor-pointer transition-all duration-200 ${
                  selectedReport?.id === report.id
                    ? 'border-primary/30 bg-primary/[0.03] shadow-sm'
                    : 'hover:bg-accent/20 shadow-xs'
                }`}
                onClick={() => onSelectReport?.(report)}
                role="button"
                aria-pressed={selectedReport?.id === report.id}
              >
                <CardContent className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/40" />
                      <span className="text-xs font-medium truncate">{report.title}</span>
                    </div>
                    <Badge
                      variant={
                        report.status === 'completed'
                          ? 'success'
                          : report.status === 'failed'
                            ? 'destructive'
                            : 'warning'
                      }
                      className="shrink-0 text-[10px] px-1.5 py-0"
                    >
                      {report.status}
                    </Badge>
                  </div>
                  <p className="mt-1.5 pl-6 text-[10px] text-muted-foreground/40">
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
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-4">
                <CardTitle className="text-base truncate">{selectedReport.title}</CardTitle>
                {selectedReport.file_url && (
                  <Button variant="outline" size="sm" asChild className="shrink-0 h-8 rounded-lg gap-1.5 text-xs">
                    <a href={selectedReport.file_url} download aria-label="Download PDF">
                      <FileDown className="h-3.5 w-3.5" />
                      Download PDF
                    </a>
                  </Button>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground/50">
                <span>{selectedReport.report_type}</span>
                <span>&middot;</span>
                <span>{formatDate(selectedReport.created_at)}</span>
              </div>
            </CardHeader>
            <CardContent>
              {selectedReport.status === 'generating' ? (
                <div className="space-y-3 p-6">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-5/6" />
                  <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground/60">
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary/40 border-t-primary" />
                    Generating report...
                  </div>
                </div>
              ) : selectedReport.status === 'failed' ? (
                <div className="flex items-start gap-3 rounded-lg bg-destructive/8 p-4 text-destructive">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p className="text-sm">{selectedReport.error_message ?? 'Report generation failed.'}</p>
                </div>
              ) : selectedReport.content ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown>{selectedReport.content}</ReactMarkdown>
                </div>
              ) : (
                <div className="flex flex-col items-center py-12 text-center">
                  <FileText className="mb-2 h-7 w-7 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground/60">No content available</p>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-xl border border-border/30 bg-card text-muted-foreground/40">
            <FileText className="h-7 w-7" />
            <p className="text-sm">Select a report to view its content</p>
          </div>
        )}
      </div>
    </div>
  );
}
