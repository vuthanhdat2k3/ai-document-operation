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
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {TASK_TYPES.map((task) => {
        const Icon = task.icon;
        const isSelected = value === task.value;
        return (
          <button
            key={task.value}
            type="button"
            onClick={() => onChange(task.value)}
            className={`
              flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-all
              ${
                isSelected
                  ? 'border-primary bg-primary/5 text-primary ring-2 ring-primary/20'
                  : 'border-muted bg-card hover:border-muted-foreground/30 hover:bg-accent/50'
              }
            `}
          >
            <Icon className={`h-6 w-6 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
            <span className="text-sm font-medium">{task.label}</span>
            <span className="text-xs text-muted-foreground line-clamp-2">{task.description}</span>
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
      className="w-full rounded-lg border bg-card p-4 text-left transition-all hover:border-primary/50 hover:shadow-sm"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {session.status === 'completed' ? (
            <CheckCircle className="h-5 w-5 text-green-500" />
          ) : session.status === 'failed' ? (
            <XCircle className="h-5 w-5 text-destructive" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          )}
          <div>
            <p className="font-medium">
              {(session.agent_type?.charAt(0).toUpperCase() ?? '') + (session.agent_type?.slice(1) ?? '')}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDate(session.started_at ?? session.created_at)}
              {duration !== null && ` · ${duration}s`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant={
              session.status === 'completed'
                ? 'default'
                : session.status === 'failed'
                  ? 'destructive'
                  : 'secondary'
            }
          >
            {session.status}
          </Badge>
          {session.total_tokens != null && (
            <span className="text-xs text-muted-foreground">
              {session.total_tokens.toLocaleString()} tok
            </span>
          )}
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
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
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">AI Agent</h2>
        <p className="mt-1 text-muted-foreground">
          Run autonomous agent tasks on your documents.
        </p>
      </div>

      {/* Run Task Card */}
      <Card className="border-primary/10 shadow-sm">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle>Run Agent Task</CardTitle>
          </div>
          <CardDescription>
            Describe what you want the agent to do. It will retrieve documents, reason, and execute
            tools to complete your request.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Task Type */}
          <div>
            <label className="mb-2 block text-sm font-medium">Task Type</label>
            <TaskTypeSelector value={taskType} onChange={setTaskType} />
          </div>

          {/* Query Input */}
          <div>
            <label htmlFor="agent-query" className="mb-2 block text-sm font-medium">
              Instructions
            </label>
            <textarea
              id="agent-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Analyze all vendor contracts for compliance risks and generate a remediation checklist..."
              className="flex min-h-[120px] w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {/* Document ID (optional) */}
          <div>
            <label htmlFor="agent-doc-id" className="mb-2 block text-sm font-medium">
              Document ID{' '}
              <span className="text-xs text-muted-foreground">(optional — scope to one document)</span>
            </label>
            <input
              id="agent-doc-id"
              type="text"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="doc_a1b2c3d4e5"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              The agent will use up to 10 reasoning iterations.
            </p>
            <Button
              onClick={handleRun}
              disabled={!query.trim() || runTask.isPending}
              size="lg"
              className="gap-2"
            >
              {runTask.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Task
                </>
              )}
            </Button>
          </div>

          {/* Result */}
          {runTask.data && (
            <Card className="border-green-500/20 bg-green-50/50 dark:bg-green-950/10">
              <CardContent className="p-4">
                <div className="mb-2 flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium text-green-700 dark:text-green-400">
                    Task completed in {runTask.data.iterations} iterations
                  </span>
                  <Badge variant="outline" className="ml-auto">
                    {(runTask.data.duration_ms / 1000).toFixed(1)}s
                  </Badge>
                </div>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground line-clamp-6">
                  {runTask.data.answer}
                </p>
                {runTask.data.session_id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 gap-1"
                    onClick={() =>
                      window.open(`/agent/sessions/${runTask.data.session_id}`, '_self')
                    }
                  >
                    <ArrowRight className="h-3 w-3" />
                    View full session details
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {/* Error */}
          {runTask.isError && (
            <Card className="border-destructive/20 bg-destructive/5">
              <CardContent className="flex items-center gap-3 p-4">
                <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" />
                <p className="text-sm text-destructive">
                  {runTask.error instanceof Error
                    ? runTask.error.message
                    : 'Failed to run agent task. Please try again.'}
                </p>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Recent Sessions */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Recent Sessions</CardTitle>
          </div>
          <CardDescription>
            View the results and execution traces of past agent runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bot className="mb-3 h-12 w-12 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No agent sessions yet.</p>
              <p className="text-xs text-muted-foreground">
                Run a task above to see results here.
              </p>
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

