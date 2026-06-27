'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[400px] items-center justify-center p-6">
      <div className="animate-fade-up w-full max-w-sm">
        <Card>
          <CardHeader className="text-center pb-3">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10">
              <AlertTriangle className="h-6 w-6 text-destructive" />
            </div>
            <CardTitle className="text-base">Something went wrong</CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className="mb-4 text-sm text-muted-foreground/70">
              An unexpected error occurred. Please try again.
            </p>
            {error.digest && (
              <p className="mb-4 font-mono text-xs text-muted-foreground/50">
                Error ID: {error.digest}
              </p>
            )}
            <Button onClick={reset} size="sm">
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
