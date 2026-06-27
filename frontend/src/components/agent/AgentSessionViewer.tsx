'use client';

import { Clock, Zap, DollarSign, CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import type { AgentSession, AgentStep } from '@/types';

interface AgentSessionViewerProps {
  session: AgentSession;
}

export function AgentSessionViewer({ session }: AgentSessionViewerProps) {
  const displayType = session.agent_type
    ? session.agent_type.charAt(0).toUpperCase() + session.agent_type.slice(1)
    : session.task_type
      ? session.task_type.charAt(0).toUpperCase() + session.task_type.slice(1)
      : 'Agent Task';

  const totalDuration = session.steps.reduce(
    (acc, s) => acc + (s.duration_ms ?? s.latency_ms ?? 0),
    0,
  );

  const displayCost =
    session.total_cost_usd != null
      ? session.total_cost_usd
      : session.total_cost != null
        ? session.total_cost
        : null;

  const completedAt = session.completed_at ?? null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">{displayType}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Started {formatDate(session.started_at ?? session.created_at)}
            {completedAt && ` \u2022 Completed ${formatDate(completedAt)}`}
          </p>
        </div>
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
      </div>

      {/* Summary Cards */}
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
                {displayCost != null ? `$${displayCost.toFixed(4)}` : '—'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {session.error_message && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          <p className="text-sm font-medium">Error</p>
          <p className="mt-1 text-sm">{session.error_message}</p>
        </div>
      )}

      {/* Steps */}
      <div className="space-y-3">
        <h3 className="font-semibold">Execution Steps ({session.steps.length})</h3>
        {session.steps.length === 0 ? (
          <p className="text-sm text-muted-foreground">No steps recorded.</p>
        ) : (
          session.steps.map((step, index) => (
            <StepCard key={step.step_index ?? step.step_order ?? index} step={step} index={index} />
          ))
        )}
      </div>
    </div>
  );
}

function StepCard({ step, index }: { step: AgentStep; index: number }) {
  const stepNumber = (step.step_index ?? step.step_order ?? index) + 1;
  const stepName = step.tool_name ?? step.action ?? step.step_type ?? `Step ${stepNumber}`;
  const stepDuration = step.duration_ms ?? step.latency_ms ?? 0;
  const displayInput = step.input ?? (step.input_data ? JSON.stringify(step.input_data, null, 2) : '');
  const displayOutput = step.output ?? (step.output_data ? JSON.stringify(step.output_data, null, 2) : '');

  const stepStatus = step.status ?? 'completed';
  const isSuccess = stepStatus === 'completed' || stepStatus === 'success';

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isSuccess ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-destructive" />
            )}
            <div>
              <span className="text-xs text-muted-foreground">
                {step.step_type ?? 'step'} #{stepNumber}
              </span>
              <h4 className="font-medium">{stepName}</h4>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{(stepDuration / 1000).toFixed(2)}s</span>
            {step.tokens_used != null && (
              <span>{step.tokens_used.toLocaleString()} tok</span>
            )}
          </div>
        </div>
        {(displayInput || displayOutput) && (
          <div className="mt-3 grid grid-cols-2 gap-4">
            {displayInput && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Input</p>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-xs">
                  {typeof displayInput === 'string' ? displayInput : JSON.stringify(displayInput, null, 2)}
                </pre>
              </div>
            )}
            {displayOutput && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Output</p>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-xs">
                  {typeof displayOutput === 'string' ? displayOutput : JSON.stringify(displayOutput, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
