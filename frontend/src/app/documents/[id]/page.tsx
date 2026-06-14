'use client';

import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { DocumentDetail } from '@/components/documents/DocumentDetail';

export default function DocumentDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/documents">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Document Details</h2>
          <p className="text-muted-foreground">View and analyze document content.</p>
        </div>
      </div>

      <DocumentDetail id={params.id} />
    </div>
  );
}
