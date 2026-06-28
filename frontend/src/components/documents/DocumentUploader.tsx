'use client';

import { useState, useCallback, useRef } from 'react';
import { Upload, X, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUploadDocument } from '@/lib/hooks/useDocuments';
import { ApiError } from '@/lib/api';
import { Progress } from '@/components/ui/progress';

interface DocumentUploaderProps {
  onUploadComplete?: (doc: import('@/types').Document) => void;
}

export function DocumentUploader({ onUploadComplete }: DocumentUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadDocument();

  const ACCEPTED_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'image/png',
    'image/jpeg',
    'image/tiff',
  ];

  const handleFile = useCallback(
    async (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError('Unsupported file type. Please upload PDF, DOC, DOCX, XLSX, TXT, CSV, PNG, JPEG, or TIFF.');
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setError('File too large. Maximum size is 50MB.');
        return;
      }

      setError(null);
      setSuccess(false);
      setUploadProgress(0);

      try {
        const result = await uploadMutation.mutateAsync(file);
        setUploadProgress(100);
        setSuccess(true);
        onUploadComplete?.(result);
        setTimeout(() => {
          setSuccess(false);
          setUploadProgress(0);
        }, 3000);
      } catch (err) {
        const msg =
          err instanceof ApiError && typeof err.body === 'object' && err.body !== null
            ? (err.body as Record<string, unknown>).message as string
            : 'Upload failed. Please try again.';
        setError(msg);
      }
    },
    [uploadMutation, onUploadComplete],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all duration-200',
          isDragging
            ? 'border-primary/40 bg-primary/[0.03]'
            : 'border-border/40 hover:border-primary/30 hover:bg-primary/[0.02]',
        )}
      >
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/[0.06] ring-1 ring-primary/[0.08]">
          <Upload className="h-5 w-5 text-primary/60" />
        </div>
        <p className="mb-1 text-sm font-medium text-foreground/70">
          Drop files here, or click to browse
        </p>
        <p className="text-xs text-muted-foreground/50">
          PDF, DOC, DOCX, XLSX, TXT, CSV, PNG, JPEG, TIFF &mdash; up to 50MB
        </p>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.doc,.docx,.xlsx,.txt,.csv,.png,.jpg,.jpeg,.tiff,.tif"
          onChange={handleInputChange}
        />
      </div>

      {uploadMutation.isPending && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground/70">
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary/40 border-t-primary" />
            <span>Uploading...</span>
          </div>
          <Progress value={uploadProgress} />
        </div>
      )}

      {success && (
        <div className="flex items-center gap-2.5 rounded-lg bg-success/8 p-3 text-sm text-success">
          <CheckCircle className="h-4 w-4" />
          <span className="font-medium">Document uploaded successfully!</span>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between rounded-lg bg-destructive/8 p-3">
          <div className="flex items-center gap-2.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="flex h-6 w-6 items-center justify-center rounded-lg text-destructive/50 transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
