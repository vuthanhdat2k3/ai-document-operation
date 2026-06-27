'use client';

import { ArrowLeft, Loader2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { AgentSessionViewer } from '@/components/agent/AgentSessionViewer';
import { useAgentSession } from '@/lib/hooks/useAgent';

export default function AgentSessionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { data: session, isLoading, error } = useAgentSession(params.id);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild className="h-8 w-8">
          <Link href="/agent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Agent Session</h2>
          <p className="text-sm text-muted-foreground/70">
            View agent execution details, steps, and results.
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/60" />
            <p className="text-sm text-muted-foreground/60">Loading session details...</p>
          </div>
        </div>
      )}

      {error && (
        <Card className="border-destructive/20">
          <CardContent className="flex items-center gap-4 p-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-destructive/10">
              <AlertTriangle className="h-[18px] w-[18px] text-destructive" />
            </div>
            <div>
              <p className="text-sm font-medium text-destructive">Failed to load session</p>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                {error instanceof Error ? error.message : 'An unexpected error occurred.'}
              </p>
              <Button variant="outline" size="sm" className="mt-2 h-7 text-xs" asChild>
                <Link href="/agent">Back to Agent</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {session && !isLoading && !error && (
        <AgentSessionViewer session={session} />
      )}
    </div>
  );
}
