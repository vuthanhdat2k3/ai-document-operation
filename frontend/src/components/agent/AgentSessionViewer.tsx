'use client';

import { Clock, Zap, DollarSign, CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import type { AgentSession, AgentStep } from '@/types';

interface AgentSessionViewerProps {
  session: AgentSession;
}

export function AgentSessionViewer({ session }: AgentSessionViewerProps) {
  const totalDuration = session.steps.reduce((acc, s) => acc + s.duration_ms, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Agent Session</h2>
          <p className="mt-1 text-muted-foreground">{session.task}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Started {formatDate(session.created_at)}
            {session.completed_at && ` • Completed ${formatDate(session.completed_at)}`}
          </p>
        </div>
        <Badge
          variant={
            session.status === 'completed'
              ? 'success'
              : session.status === 'failed'
                ? 'destructive'
                : 'warning'
          }
        >
          {session.status}
        </Badge>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Duration</p>
              <p className="font-medium">{(totalDuration / 1000).toFixed(1)}s</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Zap className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Tokens</p>
              <p className="font-medium">{session.total_tokens?.toLocaleString() ?? '—'}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <DollarSign className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Cost</p>
              <p className="font-medium">
                {session.total_cost != null ? `$${session.total_cost.toFixed(4)}` : '—'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {session.error_message && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {session.error_message}
        </div>
      )}

      <div className="space-y-3">
        <h3 className="font-semibold">Execution Steps</h3>
        {session.steps.map((step) => (
          <StepCard key={step.step_number} step={step} />
        ))}
      </div>
    </div>
  );
}

function StepCard({ step }: { step: AgentStep }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {step.status === 'success' ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-destructive" />
            )}
            <div>
              <span className="text-xs text-muted-foreground">Step {step.step_number}</span>
              <h4 className="font-medium">{step.tool_name}</h4>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{(step.duration_ms / 1000).toFixed(2)}s</span>
            {step.tokens_used && <span>{step.tokens_used.toLocaleString()} tokens</span>}
            {step.cost != null && <span>${step.cost.toFixed(4)}</span>}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Input</p>
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-xs">
              {step.input}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Output</p>
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-xs">
              {step.output}
            </pre>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
