'use client';

import { use } from 'react';
import { ArrowLeft, FileDown } from 'lucide-react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import type { Report } from '@/types';

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['report', id],
    queryFn: () => api.get<Report>(`/reports/${id}`),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-12 text-center text-destructive">
        Failed to load report.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/reports">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h2 className="text-2xl font-bold tracking-tight">{report.title}</h2>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{report.report_type}</span>
            <span>•</span>
            <span>{formatDate(report.created_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
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
          {report.file_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={report.file_url} download>
                <FileDown className="mr-2 h-4 w-4" />
                Download
              </a>
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Report Content</CardTitle>
        </CardHeader>
        <CardContent>
          {report.status === 'generating' ? (
            <div className="flex items-center gap-3 p-8">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <span className="text-muted-foreground">Generating report...</span>
            </div>
          ) : report.status === 'failed' ? (
            <div className="rounded-md bg-destructive/10 p-4 text-destructive">
              {report.error_message ?? 'Report generation failed.'}
            </div>
          ) : report.content ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown>{report.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-muted-foreground">No content available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
