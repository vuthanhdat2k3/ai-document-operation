'use client';

import { ArrowLeft, Bot, Loader2, AlertTriangle } from 'lucide-react';
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
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/agent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Agent Session</h2>
          <p className="text-muted-foreground">
            View agent execution details, steps, and results.
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-4 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading session details...</p>
          </div>
        </div>
      )}

      {error && (
        <Card className="border-destructive/20">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <div>
              <p className="font-medium text-destructive">Failed to load session</p>
              <p className="text-sm text-muted-foreground">
                {error instanceof Error ? error.message : 'An unexpected error occurred.'}
              </p>
              <Button variant="outline" size="sm" className="mt-2" asChild>
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
