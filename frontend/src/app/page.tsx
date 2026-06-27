'use client';

import { FileText, MessageSquare, HardDrive, TrendingUp, AlertTriangle, Clock, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useDashboardStats } from '@/lib/hooks/useDocuments';
import { formatFileSize, formatDate } from '@/lib/utils';

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  trend,
}: {
  title: string;
  value: number;
  icon: React.ElementType;
  description: string;
  trend?: { value: number; positive: boolean };
}) {
  return (
    <Card className="group relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-medium text-muted-foreground/70 uppercase tracking-wider">
            {title}
          </CardTitle>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/[0.06] ring-1 ring-primary/[0.08]">
            <Icon className="h-4 w-4 text-primary" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-1">
        <div className="text-2xl font-bold tabular-nums tracking-tight">
          {value.toLocaleString()}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <p className="text-xs text-muted-foreground/60">{description}</p>
          {trend && (
            <span className={`inline-flex items-center gap-0.5 text-[11px] font-medium ${trend.positive ? 'text-success' : 'text-destructive'}`}>
              <TrendingUp className={`h-3 w-3 ${!trend.positive && 'rotate-180'}`} />
              {trend.value}%
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useDashboardStats();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground/70">Overview of your document operations.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-5">
                <div className="h-3 w-16 animate-pulse rounded bg-muted/60 mb-3" />
                <div className="h-7 w-20 animate-pulse rounded bg-muted/40 mb-2" />
                <div className="h-3 w-24 animate-pulse rounded bg-muted/30" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[300px] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10">
            <AlertTriangle className="h-6 w-6 text-destructive" />
          </div>
          <p className="font-medium text-destructive">Failed to load dashboard</p>
          <p className="text-sm text-muted-foreground/70">Please try refreshing the page.</p>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Documents',
      value: stats?.total_documents ?? 0,
      icon: FileText,
      description: 'Total uploaded',
    },
    {
      title: 'Pages Parsed',
      value: stats?.total_pages ?? 0,
      icon: HardDrive,
      description: 'Pages processed',
    },
    {
      title: 'Chat Sessions',
      value: stats?.total_sessions ?? 0,
      icon: MessageSquare,
      description: 'Q&A conversations',
    },
    {
      title: 'Risks Found',
      value: stats?.total_risks ?? 0,
      icon: AlertTriangle,
      description: 'Detected across docs',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground/70">
            Overview of your document operations.
          </p>
        </div>
        <Button variant="outline" size="sm" className="gap-1.5 text-xs">
          <Clock className="h-3.5 w-3.5" />
          Last 30 days
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Documents by Status */}
      {stats?.documents_by_status && Object.keys(stats.documents_by_status).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Documents by Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.documents_by_status).map(([status, count]) => (
                <Badge
                  key={status}
                  variant={
                    status === 'completed'
                      ? 'success'
                      : status === 'failed'
                        ? 'destructive'
                        : status === 'processing'
                          ? 'warning'
                          : 'secondary'
                  }
                  className="px-3 py-1 text-xs"
                >
                  {status}: {count}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Documents */}
      {stats?.recent_documents && stats.recent_documents.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Recent Uploads</CardTitle>
              <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground/60 hover:text-foreground">
                View all
                <ArrowRight className="h-3 w-3" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="divide-y divide-border/40">
              {stats.recent_documents.slice(0, 5).map((doc) => (
                <div key={doc.id} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/[0.06] ring-1 ring-primary/[0.08]">
                      <FileText className="h-4 w-4 text-primary/70" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{doc.filename}</p>
                      <p className="text-xs text-muted-foreground/50 mt-0.5">
                        {formatFileSize(doc.file_size_bytes)} &middot; {formatDate(doc.created_at)}
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      doc.status === 'completed'
                        ? 'success'
                        : doc.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                    }
                    className="shrink-0 ml-3"
                  >
                    {doc.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
