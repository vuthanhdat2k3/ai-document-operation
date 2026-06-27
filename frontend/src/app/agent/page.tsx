'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bot,
  Play,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  ChevronRight,
  ArrowRight,
  FileText,
  Sparkles,
  AlertTriangle,
  ListChecks,
  FileBarChart,
  Search,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAgentSessions, useRunAgentTask } from '@/lib/hooks/useAgent';
import { formatDate } from '@/lib/utils';
import type { AgentSession } from '@/types';

const TASK_TYPES = [
  { value: 'qa', label: 'Q&A', icon: Search, description: 'Answer questions about documents' },
  { value: 'summarize', label: 'Summarize', icon: FileText, description: 'Generate document summaries' },
  { value: 'extract', label: 'Extract', icon: Sparkles, description: 'Extract structured fields' },
  { value: 'risk', label: 'Risk Analysis', icon: AlertTriangle, description: 'Detect risks and anomalies' },
  { value: 'checklist', label: 'Checklist', icon: ListChecks, description: 'Generate action checklists' },
  { value: 'report', label: 'Report', icon: FileBarChart, description: 'Generate analysis reports' },
] as const;

function TaskTypeSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {TASK_TYPES.map((task) => {
        const Icon = task.icon;
        const active = value === task.value;
        return (
          <button
            key={task.value}
            type="button"
            onClick={() => onChange(task.value)}
            className={`flex flex-col items-center gap-1.5 rounded-xl border p-3.5 text-center transition-all duration-200 active:scale-[0.98] ${
              active
                ? 'border-primary/30 bg-primary/[0.04] ring-1 ring-primary/[0.15]'
                : 'border-border/40 bg-card hover:border-border/60 hover:bg-accent/30'
            }`}
          >
            <Icon className={`h-4.5 w-4.5 ${active ? 'text-primary' : 'text-muted-foreground/50'}`} />
            <span className="text-xs font-medium">{task.label}</span>
            <span className="text-[10px] text-muted-foreground/50 leading-tight line-clamp-2">{task.description}</span>
          </button>
        );
      })}
    </div>
  );
}

function SessionCard({ session }: { session: AgentSession }) {
  const router = useRouter();
  const duration = session.completed_at
    ? Math.round(
        (new Date(session.completed_at).getTime() - new Date(session.started_at ?? session.created_at).getTime()) / 1000
      )
    : null;

  return (
    <button
      type="button"
      onClick={() => router.push(`/agent/sessions/${session.id}`)}
      className="group w-full rounded-lg border border-border/30 bg-card p-3.5 text-left transition-all duration-200 hover:bg-accent/20 active:scale-[0.99]"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
            session.status === 'completed'
              ? 'bg-success/10 text-success'
              : session.status === 'failed'
                ? 'bg-destructive/10 text-destructive'
                : 'bg-secondary/50 text-muted-foreground/60'
          }`}>
            {session.status === 'completed' ? (
              <CheckCircle className="h-4 w-4" />
            ) : session.status === 'failed' ? (
              <XCircle className="h-4 w-4" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium">
              {(session.agent_type?.charAt(0).toUpperCase() ?? '') + (session.agent_type?.slice(1) ?? '')}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground/50">
              {formatDate(session.started_at ?? session.created_at)}
              {duration !== null && ` \u00b7 ${duration}s`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Badge
            variant={
              session.status === 'completed'
                ? 'success'
                : session.status === 'failed'
                  ? 'destructive'
                  : 'secondary'
            }
            className="text-[10px] px-2 py-0.5"
          >
            {session.status}
          </Badge>
          {session.total_tokens != null && (
            <span className="text-[10px] text-muted-foreground/40 tabular-nums">
              {session.total_tokens.toLocaleString()} tok
            </span>
          )}
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/20 transition-all duration-200 group-hover:text-muted-foreground/50 group-hover:translate-x-0.5" />
        </div>
      </div>
    </button>
  );
}

export default function AgentPage() {
  const [query, setQuery] = useState('');
  const [taskType, setTaskType] = useState('qa');
  const [documentId, setDocumentId] = useState('');

  const { data: sessionsData, isLoading: sessionsLoading } = useAgentSessions();
  const runTask = useRunAgentTask();

  const handleRun = async () => {
    if (!query.trim()) return;
    try {
      await runTask.mutateAsync({
        task_type: taskType as 'qa' | 'summarize' | 'extract' | 'risk' | 'checklist' | 'report',
        query: query.trim(),
        ...(documentId.trim() && { document_id: documentId.trim() }),
      });
      setQuery('');
      setDocumentId('');
    } catch {
      // Error handled by mutation
    }
  };

  const sessions = sessionsData?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-semibold tracking-tight">AI Agent</h2>
        <p className="mt-1 text-sm text-muted-foreground/70">
          Run autonomous agent tasks on your documents.
        </p>
      </div>

      {/* Run Task Card */}
      <Card className="border-primary/10">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-primary/[0.08]">
              <Bot className="h-3.5 w-3.5 text-primary" />
            </div>
            <CardTitle className="text-sm">Run Agent Task</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Describe what you want the agent to do. It will retrieve documents, reason, and execute
            tools to complete your request.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Task Type */}
          <div>
            <label className="mb-2 block text-xs font-medium text-foreground/80">Task Type</label>
            <TaskTypeSelector value={taskType} onChange={setTaskType} />
          </div>

          {/* Query Input */}
          <div>
            <label htmlFor="agent-query" className="mb-1.5 block text-xs font-medium text-foreground/80">
              Instructions
            </label>
            <textarea
              id="agent-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Analyze all vendor contracts for compliance risks and generate a remediation checklist..."
              className="flex min-h-[100px] w-full rounded-lg border border-input/60 bg-background/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground/40 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-y"
            />
          </div>

          {/* Document ID (optional) */}
          <div>
            <label htmlFor="agent-doc-id" className="mb-1.5 block text-xs font-medium text-foreground/80">
              Document ID{' '}
              <span className="text-[10px] text-muted-foreground/50">(optional &mdash; scope to one document)</span>
            </label>
            <input
              id="agent-doc-id"
              type="text"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="doc_a1b2c3d4e5"
              className="flex h-9 w-full rounded-lg border border-input/60 bg-background/50 px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground/40 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground/50">
              The agent will use up to 10 reasoning iterations.
            </p>
            <Button
              onClick={handleRun}
              disabled={!query.trim() || runTask.isPending}
              size="sm"
              className="gap-1.5 rounded-lg"
            >
              {runTask.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" />
                  Run Task
                </>
              )}
            </Button>
          </div>

          {/* Result */}
          {runTask.data && (
            <div className="rounded-lg border border-success/20 bg-success/[0.03] p-4">
              <div className="mb-2 flex items-center gap-2">
                <div className="flex h-5 w-5 items-center justify-center rounded-lg bg-success/10">
                  <CheckCircle className="h-3 w-3 text-success" />
                </div>
                <span className="text-sm font-medium text-success">
                  Task completed in {runTask.data.iterations} iterations
                </span>
                <Badge variant="outline" className="ml-auto text-[10px] px-1.5 py-0 h-5">
                  {(runTask.data.duration_ms / 1000).toFixed(1)}s
                </Badge>
              </div>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground/80 line-clamp-6 leading-relaxed">
                {runTask.data.answer}
              </p>
              {runTask.data.session_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 h-7 gap-1 rounded-lg text-xs"
                  onClick={() =>
                    window.open(`/agent/sessions/${runTask.data.session_id}`, '_self')
                  }
                >
                  <ArrowRight className="h-3 w-3" />
                  View full session details
                </Button>
              )}
            </div>
          )}

          {/* Error */}
          {runTask.isError && (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
                <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
              </div>
              <p className="text-sm text-destructive">
                {runTask.error instanceof Error
                  ? runTask.error.message
                  : 'Failed to run agent task. Please try again.'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Sessions */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-secondary/50">
              <Clock className="h-3.5 w-3.5 text-muted-foreground/50" />
            </div>
            <CardTitle className="text-sm">Recent Sessions</CardTitle>
          </div>
          <CardDescription className="text-xs">
            View the results and execution traces of past agent runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground/60">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Loading sessions...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-2xl bg-secondary/50">
                <Bot className="h-5 w-5 text-muted-foreground/30" />
              </div>
              <p className="text-sm text-muted-foreground/60">No agent sessions yet</p>
              <p className="mt-1 text-xs text-muted-foreground/40">Run a task above to see results here</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <SessionCard key={session.id} session={session} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
