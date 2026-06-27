'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useDocument,
  useProcessDocument,
  useParseDocument,
  useIndexDocument,
} from '@/lib/hooks/useDocuments';
import { formatFileSize, formatDate } from '@/lib/utils';

interface DocumentDetailProps {
  id: string;
}

export function DocumentDetail({ id }: DocumentDetailProps) {
  const { data: doc, isLoading, error } = useDocument(id);
  const processDoc = useProcessDocument();
  const parseDoc = useParseDocument();
  const indexDoc = useIndexDocument();
  const [processStep, setProcessStep] = useState<string>('');

  const isProcessing = processDoc.isPending || parseDoc.isPending || indexDoc.isPending;

  const handleProcess = async () => {
    setProcessStep('Parsing...');
    try {
      await parseDoc.mutateAsync(id);
      setProcessStep('Indexing...');
      await new Promise((r) => setTimeout(r, 2000));
      await indexDoc.mutateAsync(id);
      setProcessStep('Done!');
    } catch {
      setProcessStep('Error');
    }
  };

  const handleParse = async () => {
    setProcessStep('Parsing...');
    try {
      await parseDoc.mutateAsync(id);
      setProcessStep('Parsed!');
    } catch {
      setProcessStep('Error');
    }
  };

  const handleIndex = async () => {
    setProcessStep('Indexing...');
    try {
      await indexDoc.mutateAsync(id);
      setProcessStep('Indexed!');
    } catch {
      setProcessStep('Error');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="flex items-center gap-3 text-muted-foreground/60">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading document...</span>
        </div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/10">
          <AlertTriangle className="h-5 w-5 text-destructive" />
        </div>
        <p className="text-sm font-medium text-destructive">Failed to load document details.</p>
      </div>
    );
  }

  const isCompleted = doc.status === 'completed';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{doc.filename}</h2>
          <div className="mt-1.5 flex items-center gap-4 text-sm text-muted-foreground/70">
            <span>{doc.mime_type}</span>
            <span className="text-muted-foreground/30">&middot;</span>
            <span>{formatFileSize(doc.file_size_bytes)}</span>
            <span className="text-muted-foreground/30">&middot;</span>
            <span>Uploaded {formatDate(doc.uploaded_at)}</span>
          </div>
        </div>
        <Badge variant={isCompleted ? 'success' : doc.status === 'failed' ? 'destructive' : 'secondary'}>
          {doc.status}
        </Badge>
      </div>

      {/* Action Buttons */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Process document</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleProcess} disabled={isProcessing} size="sm">
              {isProcessing ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  {processStep || 'Processing...'}
                </>
              ) : (
                'Process (Parse + Index)'
              )}
            </Button>
            <Button onClick={handleParse} disabled={isProcessing} variant="outline" size="sm">
              {parseDoc.isPending ? 'Parsing...' : 'Parse only'}
            </Button>
            <Button onClick={handleIndex} disabled={isProcessing} variant="outline" size="sm">
              {indexDoc.isPending ? 'Indexing...' : 'Index only'}
            </Button>
            {processStep && !isProcessing && (
              <span className="text-xs text-muted-foreground/60">{processStep}</span>
            )}
          </div>
          <div className="mt-3 text-xs text-muted-foreground/60 space-y-0.5">
            <p><strong>Parse:</strong> Extract text from documents</p>
            <p><strong>Index:</strong> Chunk text and create embeddings for Q&A</p>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="fields">Extracted Fields</TabsTrigger>
          <TabsTrigger value="risks">Risks</TabsTrigger>
          <TabsTrigger value="checklist">Checklist</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Document Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-xs text-muted-foreground/60">Filename</dt>
                  <dd className="text-sm font-medium mt-0.5">{doc.filename}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground/60">File Type</dt>
                  <dd className="text-sm font-medium mt-0.5">{doc.mime_type}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground/60">File Size</dt>
                  <dd className="text-sm font-medium mt-0.5">{formatFileSize(doc.file_size_bytes)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground/60">Status</dt>
                  <dd className="text-sm font-medium mt-0.5">{doc.status}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground/60">Uploaded</dt>
                  <dd className="text-sm font-medium mt-0.5">{formatDate(doc.uploaded_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground/60">Document ID</dt>
                  <dd className="text-xs font-mono text-muted-foreground/60 mt-0.5">{doc.id}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="content">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Parsed Content</CardTitle>
            </CardHeader>
            <CardContent>
              {doc.pages && doc.pages.length > 0 ? (
                <div className="space-y-4">
                  {doc.pages.map((page: any, i: number) => (
                    <div key={i} className="rounded-lg border border-border/30 bg-secondary/20 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-medium">Page {page.page_number || i + 1}</span>
                        {page.confidence && (
                          <span className="text-xs text-muted-foreground/60">
                            OCR: {Math.round(page.confidence * 100)}%
                          </span>
                        )}
                      </div>
                      <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap text-sm text-muted-foreground/80 scrollbar-thin">
                        {page.text || 'No text content'}
                      </pre>
                    </div>
                  ))}
                </div>
              ) : (doc as any).content ? (
                <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg bg-secondary/30 p-4 text-sm text-muted-foreground/80 scrollbar-thin">
                  {(doc as any).content}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground/60">
                  No content yet. Click <strong>Process</strong> to extract text.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="fields">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Extracted Fields</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground/60">
                Run extraction to see structured data fields from this document.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risks">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Risk Assessment</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground/60">
                Run analysis to detect risks and compliance gaps.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="checklist">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Compliance Checklist</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground/60">
                Checklist will be generated after risk analysis.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
