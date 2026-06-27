'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  useDocument,
  useProcessDocument,
  useParseDocument,
  useIndexDocument,
} from '@/lib/hooks/useDocuments';
import { formatFileSize, formatDate } from '@/lib/utils';
import type { DocumentDetail as DocDetail } from '@/types';

interface DocumentDetailProps {
  id: string;
}

const severityVariant: Record<string, 'default' | 'destructive' | 'warning' | 'secondary'> = {
  low: 'secondary',
  medium: 'warning',
  high: 'destructive',
  critical: 'destructive',
};

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
    } catch (err) {
      setProcessStep('Error');
    }
  };

  const handleParse = async () => {
    setProcessStep('Parsing...');
    try {
      await parseDoc.mutateAsync(id);
      setProcessStep('Parsed!');
    } catch (err) {
      setProcessStep('Error');
    }
  };

  const handleIndex = async () => {
    setProcessStep('Indexing...');
    try {
      await indexDoc.mutateAsync(id);
      setProcessStep('Indexed!');
    } catch (err) {
      setProcessStep('Error');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="p-12 text-center text-destructive">
        Failed to load document details.
      </div>
    );
  }

  const isUploaded = doc.status === 'uploaded';
  const isCompleted = doc.status === 'completed';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">{doc.filename}</h2>
          <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
            <span>{doc.mime_type}</span>
            <span>{formatFileSize(doc.file_size_bytes)}</span>
            <span>Uploaded {formatDate(doc.uploaded_at)}</span>
          </div>
        </div>
        <Badge variant={isCompleted ? 'default' : doc.status === 'failed' ? 'destructive' : 'secondary'}>
          {doc.status}
        </Badge>
      </div>

      {/* Action Buttons */}
      <Card>
        <CardHeader>
          <CardTitle>Xử lý tài liệu</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={handleProcess}
              disabled={isProcessing}
              size="lg"
            >
              {isProcessing ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-background border-t-transparent" />
                  {processStep || 'Đang xử lý...'}
                </>
              ) : (
                'Xử lý toàn bộ (Parse + Index)'
              )}
            </Button>

            <Button
              onClick={handleParse}
              disabled={isProcessing}
              variant="outline"
            >
              {parseDoc.isPending ? 'Đang parse...' : 'Parse only'}
            </Button>

            <Button
              onClick={handleIndex}
              disabled={isProcessing}
              variant="outline"
            >
              {indexDoc.isPending ? 'Đang index...' : 'Index only'}
            </Button>

            {processStep && !isProcessing && (
              <span className="text-sm text-muted-foreground">{processStep}</span>
            )}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            <strong>Parse:</strong> Trích xuất text từ tài liệu PDF/DOCX<br />
            <strong>Index:</strong> Chunk text, tạo embeddings, lưu vào Qdrant để Q&A hoạt động
          </p>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="fields">Extracted Fields</TabsTrigger>
          <TabsTrigger value="risks">Risks</TabsTrigger>
          <TabsTrigger value="checklist">Checklist</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle>Document Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-muted-foreground">Filename</dt>
                  <dd className="text-sm font-medium">{doc.filename}</dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">File Type</dt>
                  <dd className="text-sm font-medium">{doc.mime_type}</dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">File Size</dt>
                  <dd className="text-sm font-medium">{formatFileSize(doc.file_size_bytes)}</dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Status</dt>
                  <dd className="text-sm font-medium">{doc.status}</dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Uploaded</dt>
                  <dd className="text-sm font-medium">{formatDate(doc.uploaded_at)}</dd>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground">Document ID</dt>
                  <dd className="text-xs font-mono text-muted-foreground">{doc.id}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="content">
          <Card>
            <CardHeader>
              <CardTitle>Parsed Content</CardTitle>
            </CardHeader>
            <CardContent>
              {doc.pages && doc.pages.length > 0 ? (
                <div className="space-y-4">
                  {doc.pages.map((page: any, i: number) => (
                    <div key={i} className="rounded-md border p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-medium">Page {page.page_number || i + 1}</span>
                        {page.confidence && (
                          <span className="text-xs text-muted-foreground">
                            OCR: {Math.round(page.confidence * 100)}%
                          </span>
                        )}
                      </div>
                      <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap text-sm text-muted-foreground">
                        {page.text || 'No text content'}
                      </pre>
                    </div>
                  ))}
                </div>
              ) : (doc as any).content ? (
                <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-md bg-muted p-4 text-sm">
                  {(doc as any).content}
                </pre>
              ) : (
                <p className="text-muted-foreground">
                  Chưa có nội dung. Nhấn <strong>Xử lý toàn bộ</strong> để trích xuất text.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="fields">
          <Card>
            <CardHeader>
              <CardTitle>Extracted Fields</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Nhấn <strong>Extract</strong> trên thanh công cụ để trích xuất trường dữ liệu.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risks">
          <Card>
            <CardHeader>
              <CardTitle>Risk Assessment</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Nhấn <strong>Analyze</strong> để phát hiện rủi ro.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="checklist">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Checklist</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Checklist sẽ được tạo sau khi phân tích rủi ro.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
