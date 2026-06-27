'use client';

import { useState } from 'react';
import { Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DocumentList } from '@/components/documents/DocumentList';
import { DocumentUploader } from '@/components/documents/DocumentUploader';
import { SearchBar } from '@/components/search/SearchBar';

export default function DocumentsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState<string | undefined>();
  const [showUploader, setShowUploader] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Documents</h2>
          <p className="mt-1 text-sm text-muted-foreground/70">Manage and browse your documents.</p>
        </div>
        <Button onClick={() => setShowUploader(!showUploader)} className="gap-2">
          <Upload className="h-4 w-4" />
          Upload
        </Button>
      </div>

      {showUploader && <DocumentUploader onUploadComplete={() => setShowUploader(false)} />}

      <SearchBar
        onSearch={(q) => {
          setSearch(q);
          setPage(1);
        }}
        placeholder="Search documents by name..."
      />

      <DocumentList page={page} search={search} onPageChange={setPage} />
    </div>
  );
}
