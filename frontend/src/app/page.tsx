'use client';

import { useMemo } from 'react';
import { FileText, Search, MessageSquare, FileBarChart, HardDrive, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useDashboardStats } from '@/lib/hooks/useDocuments';
import { formatFileSize, formatDate } from '@/lib/utils';

function StatCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: string;
  value: number;
  icon: React.ElementType;
  description: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value.toLocaleString()}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
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
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">Loading...</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-8 w-16 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-destructive">
        Failed to load dashboard data.
      </div>
    );
  }

  const statCards = [
    {
      title: 'Documents',
      value: stats?.total_documents ?? 0,
      icon: FileText,
      description: 'Tài liệu đã upload',
    },
    {
      title: 'Pages Parsed',
      value: stats?.total_pages ?? 0,
      icon: HardDrive,
      description: 'Trang đã parse',
    },
    {
      title: 'Chat Sessions',
      value: stats?.total_sessions ?? 0,
      icon: MessageSquare,
      description: 'Phiên chat Q&A',
    },
    {
      title: 'Risks Found',
      value: stats?.total_risks ?? 0,
      icon: AlertTriangle,
      description: 'Rủi ro đã phát hiện',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Tổng quan hệ thống AI Document Operations.
        </p>
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
          <CardHeader>
            <CardTitle>Documents by Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {Object.entries(stats.documents_by_status).map(([status, count]) => (
                <Badge
                  key={status}
                  variant={
                    status === 'completed'
                      ? 'default'
                      : status === 'failed'
                        ? 'destructive'
                        : 'secondary'
                  }
                  className="text-sm"
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
          <CardHeader>
            <CardTitle>Recent Uploads</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recent_documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{doc.filename}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(doc.file_size_bytes)} | {formatDate(doc.created_at)}
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      doc.status === 'completed'
                        ? 'default'
                        : doc.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                    }
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
