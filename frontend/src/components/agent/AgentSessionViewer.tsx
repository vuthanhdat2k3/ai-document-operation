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
          <h2 className="text-xl font-semibold tracking-tight">{displayType}</h2>
          <p className="mt-1 text-sm text-muted-foreground/60">
            Started {formatDate(session.started_at ?? session.created_at)}
            {completedAt && <span> &middot; Completed {formatDate(completedAt)}</span>}
          </p>
        </div>
        <Badge
          variant={
            session.status === 'completed'
              ? 'success'
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
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/50">
              <Clock className="h-4 w-4 text-muted-foreground/60" />
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Duration</p>
              <p className="text-sm font-medium tabular-nums">{(totalDuration / 1000).toFixed(1)}s</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/50">
              <Zap className="h-4 w-4 text-muted-foreground/60" />
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Tokens</p>
              <p className="text-sm font-medium tabular-nums">{session.total_tokens?.toLocaleString() ?? '\u2014'}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/50">
              <DollarSign className="h-4 w-4 text-muted-foreground/60" />
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Cost</p>
              <p className="text-sm font-medium tabular-nums">
                {displayCost != null ? `$${displayCost.toFixed(4)}` : '\u2014'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {session.error_message && (
        <div className="flex items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
            <XCircle className="h-4 w-4 text-destructive" />
          </div>
          <div>
            <p className="text-sm font-medium text-destructive">Error</p>
            <p className="mt-1 text-sm text-destructive/80">{session.error_message}</p>
          </div>
        </div>
      )}

      {/* Steps */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">Execution Steps ({session.steps.length})</h3>
        {session.steps.length === 0 ? (
          <p className="text-sm text-muted-foreground/60">No steps recorded.</p>
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
    <Card className="transition-all duration-200 hover:shadow-sm">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${
              isSuccess
                ? 'bg-success/10 text-success'
                : 'bg-destructive/10 text-destructive'
            }`}>
              {isSuccess ? (
                <CheckCircle className="h-3.5 w-3.5" />
              ) : (
                <XCircle className="h-3.5 w-3.5" />
              )}
            </div>
            <div>
              <span className="text-[10px] text-muted-foreground/50">
                {step.step_type ?? 'step'} #{stepNumber}
              </span>
              <h4 className="text-sm font-medium">{stepName}</h4>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground/50">
            <span className="tabular-nums">{(stepDuration / 1000).toFixed(2)}s</span>
            {step.tokens_used != null && (
              <span className="tabular-nums">{step.tokens_used.toLocaleString()} tok</span>
            )}
          </div>
        </div>
        {(displayInput || displayOutput) && (
          <div className="mt-3 grid grid-cols-2 gap-4">
            {displayInput && (
              <div>
                <p className="mb-1 text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider">Input</p>
                <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-secondary/30 p-3 text-xs leading-relaxed scrollbar-thin">
                  {typeof displayInput === 'string' ? displayInput : JSON.stringify(displayInput, null, 2)}
                </pre>
              </div>
            )}
            {displayOutput && (
              <div>
                <p className="mb-1 text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider">Output</p>
                <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-secondary/30 p-3 text-xs leading-relaxed scrollbar-thin">
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
