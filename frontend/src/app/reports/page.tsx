'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ReportViewer } from '@/components/reports/ReportViewer';
import type { Report, PaginatedResponse } from '@/types';

export default function ReportsPage() {
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.get<PaginatedResponse<Report>>('/reports'),
  });

  const generateMutation = useMutation({
    mutationFn: () => api.post<Report>('/reports/generate'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
  });

  const reports = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Reports</h2>
        <p className="mt-1 text-sm text-muted-foreground/70">
          Generate and view document analysis reports.
        </p>
      </div>

      <ReportViewer
        reports={reports}
        isLoading={isLoading}
        onGenerate={() => generateMutation.mutate()}
        onRefresh={() => refetch()}
        selectedReport={selectedReport}
        onSelectReport={setSelectedReport}
      />
    </div>
  );
}
