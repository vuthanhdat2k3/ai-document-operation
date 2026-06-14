# Document Processing Pipeline Design

## AI Document Operations Agent

---

## 1. Pipeline Overview

The document processing pipeline is a multi-stage system that ingests raw documents, extracts structured content, generates embeddings, and indexes results for retrieval. The pipeline is designed for high throughput, fault tolerance, and quality assurance.

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Upload   │───▶│ Validate │───▶│  Detect  │───▶│ Extract  │───▶│   OCR    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                       │
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────▼───┐
│  Index   │◀───│  Embed   │◀───│ Enrich   │◀───│  Chunk   │◀───│  Layout  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │
      ▼
┌──────────┐    ┌──────────┐
│  Store   │───▶│  Quality │
└──────────┘    └──────────┘
```

Each stage is independently retryable. Failures at any stage halt the pipeline for that document and report status via webhook/SSE.

**Technology Stack:**

| Component       | Technology              |
|-----------------|-------------------------|
| Object Storage  | MinIO / S3-compatible   |
| Database        | PostgreSQL 16           |
| Vector Store    | Qdrant                  |
| OCR Engine      | PaddleOCR               |
| PDF Parser      | PyMuPDF (fitz)          |
| Docx Parser     | python-docx             |
| XLSX Parser     | openpyxl                |
| Layout Engine   | Docling / MinerU        |
| Embedding Model | bge-m3                  |
| Task Queue      | Celery + Redis          |

---

## 2. Pipeline Stages

### Stage 1: Upload

**Purpose:** Accept document files from clients via multipart upload.

**Endpoint:** `POST /api/v1/documents/upload`

**Specifications:**

- **Multipart Upload:** Support chunked multipart upload for large files. Client splits file into 5MB parts, uploads each, then completes the upload.
- **File Size Limit:** Maximum 50MB per file. Return `413 Payload Too Large` if exceeded.
- **Supported Formats:**
  - PDF (`.pdf`)
  - Microsoft Word (`.docx`)
  - Microsoft Excel (`.xlsx`)
  - PNG (`.png`)
  - JPEG (`.jpg`, `.jpeg`)
  - TIFF (`.tiff`, `.tif`)
- **Upload Validation:**
  - Verify `Content-Type` header matches expected format
  - Generate SHA-256 hash of uploaded content immediately
  - Store original file in MinIO/S3 with hash-based path: `documents/{hash_prefix}/{hash}.{ext}`
  - Create database record with status `UPLOADED`
  - Return document ID and upload confirmation

**Request Schema:**

```json
{
  "file": "<binary>",
  "metadata": {
    "source": "web|api|email",
    "tags": ["string"],
    "folder_id": "uuid"
  }
}
```

**Response Schema:**

```json
{
  "document_id": "uuid",
  "status": "UPLOADED",
  "filename": "string",
  "size_bytes": 12345,
  "content_hash": "sha256:abc123...",
  "upload_time": "ISO8601"
}
```

---

### Stage 2: File Validation

**Purpose:** Verify file integrity, safety, and uniqueness before processing.

**Steps:**

1. **MIME Type Verification (Magic Bytes):**
   - Read first 8192 bytes of file
   - Use `python-magic` or `libmagic` to detect actual MIME type
   - Compare against declared extension/Content-Type
   - Reject mismatches with `422 Unprocessable Entity`
   - Expected signatures:
     - PDF: `%PDF` (hex: `2550 4446`)
     - PNG: `\x89PNG` (hex: `8950 4E47`)
     - JPEG: `\xFF\xD8\xFF`
     - TIFF: `II\x2A\x00` or `MM\x00\x2A`
     - DOCX: PK ZIP signature (since DOCX is a ZIP archive)
     - XLSX: PK ZIP signature

2. **File Integrity Check:**
   - For PDF: Attempt to open with PyMuPDF, verify no corruption
   - For DOCX/XLSX: Attempt to open as ZIP, verify internal structure
   - For images: Attempt to decode with Pillow, verify dimensions > 0
   - Mark as `VALIDATION_FAILED` if any check fails

3. **Virus Scanning (Placeholder):**
   - Interface: `scan_file(file_path: str) -> ScanResult`
   - `ScanResult`: `{clean: bool, threat: str | None, engine: str}`
   - Default implementation: always returns clean
   - Production: integrate ClamAV via `clamd` daemon
   - Quarantine infected files, do not delete

4. **Duplicate Detection:**
   - Query database for existing document with same SHA-256 hash
   - If duplicate found:
     - Option A (default): Return existing document ID with `status: DUPLICATE`
     - Option B (configurable): Create new document record, link to same storage object
   - Store content hash in `documents.content_hash` column with unique index

**Status Transitions:**
- `UPLOADED` → `VALIDATED` or `VALIDATION_FAILED` or `DUPLICATE`

---

### Stage 3: File Type Detection

**Purpose:** Determine precise file type and subtype for parser selection.

**Detection Strategy (priority order):**

1. **Magic Byte Verification:**
   - Primary detection method
   - More reliable than extension-based detection
   - Handles renamed files correctly

2. **Extension-Based Detection:**
   - Secondary fallback
   - Used when magic bytes are ambiguous (e.g., generic ZIP vs DOCX)

3. **PDF Subtype Detection:**
   - Open PDF with PyMuPDF
   - Count pages with extractable text: `page.get_text().strip()`
   - If > 80% of pages have < 50 characters → classified as **scanned PDF**
   - If pages contain images with minimal text → classified as **scanned PDF**
   - Otherwise → classified as **text PDF**
   - Store subtype in `documents.file_subtype` column

**Detection Result:**

```json
{
  "mime_type": "application/pdf",
  "extension": ".pdf",
  "file_subtype": "text_pdf|scanned_pdf",
  "detection_confidence": 0.95,
  "detection_method": "magic_bytes|extension|content_analysis"
}
```

---

### Stage 4: Text Extraction

**Purpose:** Extract raw text content from documents using format-specific parsers.

**Fallback Strategy:**

| File Type       | Primary Parser         | Fallback 1            | Fallback 2          |
|-----------------|------------------------|-----------------------|---------------------|
| Text PDF        | PyMuPDF (fitz)         | Docling               | pdfplumber          |
| Scanned PDF     | PaddleOCR              | MinerU                | Tesseract           |
| Complex Layout  | Docling / MinerU       | PaddleOCR             | Manual region OCR   |
| Image (PNG/JPG) | PaddleOCR              | Tesseract             | —                   |
| TIFF            | PaddleOCR (per frame)  | Tesseract             | —                   |
| DOCX            | python-docx            | mammoth (fallback)    | —                   |
| XLSX            | openpyxl               | pandas read_excel     | —                   |

**Parser Implementations:**

**PDF Text (PyMuPDF):**

```python
import fitz

def extract_pdf_text(file_path: str) -> ExtractionResult:
    doc = fitz.open(file_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages.append(PageContent(
            page_number=page_num + 1,
            text=text,
            char_count=len(text)
        ))
    doc.close()
    return ExtractionResult(pages=pages, method="pymupdf")
```

**PDF Scanned (PaddleOCR):**

```python
from paddleocr import PaddleOCR

def extract_scanned_pdf(file_path: str) -> ExtractionResult:
    ocr = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=True)
    doc = fitz.open(file_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        result = ocr.ocr(img_bytes, cls=True)
        text = "\n".join([line[1][0] for line in result[0]])
        pages.append(PageContent(
            page_number=page_num + 1,
            text=text,
            char_count=len(text),
            ocr_confidence=calculate_avg_confidence(result)
        ))
    doc.close()
    return ExtractionResult(pages=pages, method="paddleocr")
```

**DOCX (python-docx):**

```python
from docx import Document

def extract_docx(file_path: str) -> ExtractionResult:
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    text = "\n".join(full_text)
    return ExtractionResult(
        pages=[PageContent(page_number=1, text=text, char_count=len(text))],
        method="python-docx"
    )
```

**XLSX (openpyxl):**

```python
from openpyxl import load_workbook

def extract_xlsx(file_path: str) -> ExtractionResult:
    wb = load_workbook(file_path, data_only=True)
    pages = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append("\t".join([str(c) if c is not None else "" for c in row]))
        text = "\n".join(rows)
        pages.append(PageContent(
            page_number=1,
            text=text,
            char_count=len(text),
            sheet_name=sheet_name
        ))
    return ExtractionResult(pages=pages, method="openpyxl")
```

---

### Stage 5: OCR Configuration

**Purpose:** Configure optical character recognition for scanned documents and images.

**PaddleOCR Settings:**

```yaml
paddleocr:
  use_angle_cls: true          # Enable text angle classification
  lang: "vi"                   # Primary language: Vietnamese
  use_gpu: true                # GPU acceleration
  det_model_dir: "models/det"  # Detection model path
  rec_model_dir: "models/rec"  # Recognition model path
  cls_model_dir: "models/cls"  # Classification model path
  det_db_thresh: 0.3           # Detection threshold
  det_db_box_thresh: 0.5       # Box threshold
  det_db_unclip_ratio: 1.6     # Unclip ratio
  rec_batch_num: 6             # Recognition batch size
  max_text_length: 250         # Max text length per detection
  use_space: true              # Enable space recognition
  drop_score: 0.5              # Drop low confidence results
```

**Language Models:**

| Language   | Model          | Use Case                    |
|------------|----------------|-----------------------------|
| Vietnamese | `vi`           | Default for Vietnamese docs |
| English    | `en`           | English-only documents      |
| Mixed      | `vi` + `en`    | Bilingual documents         |

**Confidence Thresholds:**

| Threshold       | Value | Description                              |
|-----------------|-------|------------------------------------------|
| Character-level | 0.7   | Minimum per-character confidence         |
| Line-level      | 0.6   | Minimum average line confidence          |
| Block-level     | 0.5   | Minimum block confidence for inclusion   |
| Page-level      | 0.4   | Minimum page average for quality gate    |

**Image Preprocessing Pipeline:**

1. **Deskew:** Detect and correct rotation using Hough transform or PaddleOCR angle classifier
2. **Denoise:** Apply non-local means denoising (`cv2.fastNlMeansDenoising`)
3. **Binarize:** Adaptive thresholding for black/white conversion (`cv2.adaptiveThreshold`)
4. **Contrast Enhancement:** CLAHE (Contrast Limited Adaptive Histogram Equalization)
5. **Resolution Upscale:** If DPI < 200, upscale to 300 DPI using bicubic interpolation

```python
import cv2
import numpy as np

def preprocess_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    return binary
```

---

### Stage 6: Layout Detection

**Purpose:** Identify structural layout elements on each page.

**Detection Components:**

1. **Page Segmentation:**
   - Segment page into text blocks, image regions, and table regions
   - Use Docling or MinerU for complex layouts
   - Output: list of regions with bounding boxes and types

2. **Column Detection:**
   - Detect multi-column layouts
   - Analyze vertical whitespace gaps
   - Determine reading order (left-to-right, top-to-bottom)
   - Output: column count and column boundaries

3. **Header/Footer Detection:**
   - Identify repeated elements across pages
   - Detect page numbers, running headers, footers
   - Mark regions for exclusion from main content
   - Output: list of header/footer regions per page

4. **Reading Order Detection:**
   - Determine correct reading sequence for text blocks
   - Handle multi-column, sidebar, and footnote layouts
   - Use spatial analysis: sort by y-coordinate first, then x-coordinate within rows
   - Output: ordered list of block IDs per page

**Layout Detection Result:**

```json
{
  "page_number": 1,
  "regions": [
    {
      "id": "r1",
      "type": "text|table|image|header|footer|title",
      "bbox": [x1, y1, x2, y2],
      "reading_order": 1,
      "column": 1
    }
  ],
  "columns": 2,
  "has_header": true,
  "has_footer": true,
  "layout_confidence": 0.87
}
```

---

### Stage 7: Table Extraction

**Purpose:** Detect and extract tabular data from documents.

**Extraction Steps:**

1. **Table Detection:**
   - Use Docling table detection model
   - Identify table boundaries via line detection and cell grid analysis
   - Distinguish tables from surrounding text
   - Confidence threshold: 0.6

2. **Cell Extraction:**
   - Parse cell boundaries within detected table regions
   - Extract cell text using OCR or direct text extraction
   - Handle merged cells, spanning rows/columns
   - Preserve cell coordinates for reconstruction

3. **Table-to-Text Conversion:**
   - Convert table to Markdown format for embedding
   - Preserve column headers and row alignment
   - Format: pipe-delimited Markdown tables

   ```markdown
   | Header 1 | Header 2 | Header 3 |
   |----------|----------|----------|
   | Cell 1   | Cell 2   | Cell 3   |
   | Cell 4   | Cell 5   | Cell 6   |
   ```

4. **Structured Table Data:**
   - Store as JSON for programmatic access
   - Preserve data types (numbers, dates, strings)

   ```json
   {
     "headers": ["Name", "Date", "Amount"],
     "rows": [
       ["Item A", "2024-01-15", "1500000"],
       ["Item B", "2024-01-16", "2300000"]
     ],
     "metadata": {
       "page": 3,
       "bbox": [72, 300, 540, 600],
       "confidence": 0.92
     }
   }
   ```

---

### Stage 8: Section Detection

**Purpose:** Identify document structure and hierarchical sections.

**Detection Methods:**

1. **Heading Detection:**
   - Font size analysis: headings typically larger than body text
   - Font weight: bold text more likely to be headings
   - Position analysis: headings typically at start of block, often left-aligned
   - Numbering patterns: regex matching for `1.`, `1.1`, `I.`, `A.`, etc.
   - Vietnamese patterns: `PHẦN`, `CHƯƠNG`, `MỤC`, `ĐIỀU`, `KHOẢN`

2. **Section Boundary Identification:**
   - Detected headings mark section starts
   - Section ends at next heading of same or higher level
   - Page breaks may indicate section boundaries
   - Large whitespace gaps (> 2x line height) may indicate section breaks

3. **Hierarchical Structure:**
   - Build tree structure: Document → Sections → Subsections → Paragraphs
   - Heading levels: H1 (largest) through H6 (smallest)
   - Inferred from font size ranking when explicit levels not available

**Section Tree Example:**

```json
{
  "title": "Document Title",
  "sections": [
    {
      "heading": "1. Introduction",
      "level": 1,
      "start_page": 1,
      "end_page": 2,
      "subsections": [
        {
          "heading": "1.1 Background",
          "level": 2,
          "start_page": 1,
          "end_page": 1
        }
      ]
    }
  ]
}
```

---

### Stage 9: Chunking

**Purpose:** Split extracted text into optimal chunks for embedding and retrieval.

**Chunking Strategy per Document Type:**

| Document Type   | Strategy                  | Chunk Size | Overlap  |
|-----------------|---------------------------|------------|----------|
| Text PDF        | Recursive character split | 512 tokens | 50 tokens |
| Scanned PDF     | Page-based + recursive    | 512 tokens | 50 tokens |
| DOCX            | Paragraph-aware split     | 512 tokens | 50 tokens |
| XLSX            | Sheet-based (per sheet)   | 1024 tokens| 0        |
| Tables          | Table-aware (per table)   | N/A        | N/A      |
| Complex Layout  | Semantic chunking         | 512 tokens | 50 tokens |

**Recursive Character Splitting:**

```python
def recursive_split(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_recursive(text, separators, chunk_size, overlap)

def _split_recursive(text, separators, chunk_size, overlap):
    if len(text) <= chunk_size:
        return [text]
    separator = separators[0]
    splits = text.split(separator)
    chunks = []
    current = ""
    for split in splits:
        if len(current) + len(split) + len(separator) <= chunk_size:
            current += (separator if current else "") + split
        else:
            if current:
                chunks.append(current)
            current = split
    if current:
        chunks.append(current)
    # Apply overlap
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i-1][-overlap:]
            overlapped.append(prev_tail + " " + chunks[i])
        chunks = overlapped
    return chunks
```

**Semantic Chunking (for complex documents):**

- Split on sentence boundaries using spaCy or NLTK
- Group sentences until chunk_size limit
- Prefer splitting at paragraph breaks over sentence breaks
- Preserve sentence integrity (never split mid-sentence)

**Table-Aware Chunking:**

- Tables are kept as single chunks (never split across chunks)
- If table exceeds chunk_size, increase chunk_size for that chunk only
- Surrounding context (1-2 sentences before/after table) included in chunk

**Metadata Preservation per Chunk:**

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "chunk_index": 5,
  "text": "...",
  "token_count": 487,
  "page_numbers": [3, 4],
  "section_title": "1.2 Methodology",
  "has_table": false,
  "start_char": 5120,
  "end_char": 7680
}
```

---

### Stage 10: Metadata Enrichment

**Purpose:** Attach rich metadata to each chunk for filtering and context.

**Metadata Fields:**

| Field              | Type    | Source                    | Description                          |
|--------------------|---------|---------------------------|--------------------------------------|
| `page_numbers`     | int[]   | Extraction                | Pages this chunk spans               |
| `section_title`    | string  | Section detection         | Nearest heading/title                |
| `document_type`    | string  | Classification            | invoice, contract, report, etc.      |
| `language`         | string  | Detection (langdetect)    | ISO 639-1 code (vi, en)             |
| `quality_score`    | float   | Quality check             | Overall quality 0-1                  |
| `ocr_confidence`   | float   | OCR engine                | Average OCR confidence for page      |
| `char_count`       | int     | Calculation               | Character count of chunk text        |
| `token_count`      | int     | tiktoken                  | Token count for embedding model      |
| `has_table`        | bool    | Table detection           | Whether chunk contains table data    |
| `source_filename`  | string  | Upload                    | Original filename                    |
| `upload_date`      | ISO8601 | Upload                    | When document was uploaded           |
| `processing_time`  | float   | Pipeline                  | Seconds spent processing             |
| `parser_used`      | string  | Extraction                | Which parser extracted this chunk    |
| `chunk_strategy`   | string  | Chunking                  | Which chunking method was used       |

---

### Stage 11: Embedding

**Purpose:** Generate dense vector embeddings for semantic search.

**Configuration:**

```yaml
embedding:
  model: "BAAI/bge-m3"
  dimension: 1024
  batch_size: 32
  max_length: 8192
  normalize: true
  device: "cuda"
  fp16: true
```

**Batch Processing:**

```python
from sentence_transformers import SentenceTransformer
import numpy as np

def embed_chunks(chunks: list[str], model_name: str = "BAAI/bge-m3") -> np.ndarray:
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        chunks,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        device="cuda"
    )
    return embeddings  # shape: (n_chunks, 1024)
```

**Embedding Specifications:**

- **Model:** BAAI/bge-m3 (multilingual, supports Vietnamese)
- **Dimension:** 1024
- **Normalization:** L2 normalization applied
- **Batch Size:** 32 chunks per batch (adjustable based on GPU memory)
- **Max Input Length:** 8192 tokens per chunk
- **Precision:** FP16 for inference

---

### Stage 12: Indexing

**Purpose:** Store vectors and payloads in Qdrant for fast retrieval.

**Qdrant Collection Setup:**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, PayloadSchemaType
)

def setup_collection(client: QdrantClient, collection_name: str):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    )
    # Create payload indexes for filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="page_numbers",
        field_schema=PayloadSchemaType.INTEGER
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="section_title",
        field_schema=PayloadSchemaType.TEXT
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="language",
        field_schema=PayloadSchemaType.KEYWORD
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_type",
        field_schema=PayloadSchemaType.KEYWORD
    )
```

**Point Upload:**

```python
def index_chunks(client, collection_name, chunks, embeddings):
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        points.append(PointStruct(
            id=chunk["chunk_id"],
            vector=embedding.tolist(),
            payload={
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "page_numbers": chunk["page_numbers"],
                "section_title": chunk["section_title"],
                "document_type": chunk["document_type"],
                "language": chunk["language"],
                "quality_score": chunk["quality_score"],
                "has_table": chunk["has_table"],
                "source_filename": chunk["source_filename"]
            }
        ))
    client.upsert(collection_name=collection_name, points=points)
```

---

### Stage 13: Quality Check

**Purpose:** Evaluate extraction quality and gate low-quality results.

**Quality Metrics:**

| Metric                | Range  | Calculation                                      |
|-----------------------|--------|--------------------------------------------------|
| `ocr_confidence`      | 0-1    | Average OCR confidence across all pages          |
| `text_density`        | 0-∞    | Characters per page (higher = more content)      |
| `table_detection_score` | 0-1  | Confidence of table detection model              |
| `layout_confidence`   | 0-1    | Layout detection model confidence                |
| `language_detection`  | string | Detected language code (langdetect library)      |
| `page_coverage`       | 0-1    | % of pages successfully parsed                   |

**Quality Gate Thresholds:**

```yaml
quality_gate:
  min_ocr_confidence: 0.4
  min_text_density: 50          # chars per page minimum
  min_page_coverage: 0.5        # at least 50% pages parsed
  min_overall_score: 0.3        # weighted average
```

**Quality Score Calculation:**

```python
def calculate_quality_score(metrics: dict) -> float:
    weights = {
        "ocr_confidence": 0.3,
        "text_density_normalized": 0.2,
        "table_detection_score": 0.15,
        "layout_confidence": 0.15,
        "page_coverage": 0.2
    }
    # Normalize text_density to 0-1 range (500 chars/page = 1.0)
    metrics["text_density_normalized"] = min(metrics["text_density"] / 500.0, 1.0)

    score = sum(
        metrics.get(key, 0) * weight
        for key, weight in weights.items()
    )
    return round(score, 4)
```

**Quality Gate Actions:**

| Score Range | Action                                      |
|-------------|---------------------------------------------|
| >= 0.7      | Full indexing, mark as HIGH quality          |
| 0.3 - 0.7  | Index with warning, mark as MEDIUM quality   |
| < 0.3       | Do not index, mark as LOW quality, flag for review |

---

### Stage 14: Storage

**Purpose:** Persist all artifacts to appropriate storage systems.

**Storage Map:**

| Artifact           | Storage       | Path / Table                         |
|--------------------|---------------|--------------------------------------|
| Original file      | MinIO/S3      | `s3://documents/{hash_prefix}/{hash}.{ext}` |
| Parsed text        | PostgreSQL    | `document_pages` table               |
| Chunks             | PostgreSQL    | `document_chunks` table              |
| Chunk vectors      | Qdrant        | `documents` collection               |
| Metadata           | PostgreSQL    | `documents` table                    |
| Quality report     | PostgreSQL    | `document_quality` table             |
| Extraction log     | PostgreSQL    | `processing_logs` table              |

**PostgreSQL Schema (key tables):**

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    mime_type TEXT NOT NULL,
    file_subtype TEXT,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    quality_score FLOAT,
    language TEXT,
    document_type TEXT,
    page_count INT,
    chunk_count INT,
    processing_time_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT,
    page_numbers INT[],
    section_title TEXT,
    has_table BOOLEAN DEFAULT FALSE,
    quality_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3. Parser Selection Matrix

| Input Format   | Subtype       | Primary Parser     | Fallback 1    | Fallback 2   | Confidence Check           |
|----------------|---------------|--------------------|---------------|--------------|----------------------------|
| PDF            | Text          | PyMuPDF (fitz)     | Docling       | pdfplumber   | char_count > 50/page       |
| PDF            | Scanned       | PaddleOCR          | MinerU        | Tesseract    | ocr_confidence > 0.4       |
| PDF            | Mixed         | Docling            | PaddleOCR     | PyMuPDF      | layout_confidence > 0.5    |
| DOCX           | —             | python-docx        | mammoth       | LibreOffice  | paragraph_count > 0        |
| XLSX           | —             | openpyxl           | pandas        | LibreOffice  | sheet_count > 0            |
| PNG/JPG        | —             | PaddleOCR          | Tesseract     | —            | ocr_confidence > 0.4       |
| TIFF           | Single-frame  | PaddleOCR          | Tesseract     | —            | ocr_confidence > 0.4       |
| TIFF           | Multi-frame   | PaddleOCR (loop)   | Tesseract     | —            | ocr_confidence > 0.4       |

---

## 4. Quality Scoring System

### Scoring Components

| Component              | Weight | Range | Normalization                     |
|------------------------|--------|-------|-----------------------------------|
| OCR Confidence         | 0.30   | 0-1   | Direct from OCR engine            |
| Text Density           | 0.20   | 0-∞   | `min(chars_per_page / 500, 1.0)` |
| Table Detection Score  | 0.15   | 0-1   | Direct from detection model       |
| Layout Confidence      | 0.15   | 0-1   | Direct from layout model          |
| Page Coverage          | 0.20   | 0-1   | `parsed_pages / total_pages`      |

### Quality Levels

| Level  | Score Range | Description                              | Action                  |
|--------|-------------|------------------------------------------|-------------------------|
| HIGH   | 0.7 - 1.0  | Clean extraction, high confidence        | Full indexing           |
| MEDIUM | 0.3 - 0.7  | Acceptable quality, some noise           | Index with flag         |
| LOW    | 0.0 - 0.3  | Poor quality, likely extraction errors   | Skip indexing, alert    |

### Per-Page Quality

Each page receives an individual quality score. Page-level scores are aggregated using harmonic mean (penalizes pages with very low scores more than arithmetic mean).

---

## 5. Error Handling Per Stage

| Stage              | Error Type               | Handling                                          | Retry |
|--------------------|--------------------------|---------------------------------------------------|-------|
| Upload             | File too large           | Return 413, reject immediately                    | No    |
| Upload             | Unsupported format       | Return 415, reject immediately                    | No    |
| Upload             | Network timeout          | Return 408, client retries                        | Yes   |
| Validation         | MIME mismatch            | Return 422, log warning                           | No    |
| Validation         | Corrupted file           | Mark `VALIDATION_FAILED`, notify user             | No    |
| Validation         | Virus detected           | Quarantine file, alert admin                      | No    |
| Validation         | Duplicate found          | Return existing doc ID                            | No    |
| Type Detection     | Ambiguous type           | Try all candidate parsers, use best result        | Yes   |
| Text Extraction    | Parser crash             | Try fallback parser                               | Yes   |
| Text Extraction    | Empty result             | Try next parser in chain                          | Yes   |
| Text Extraction    | Out of memory            | Reduce batch size, retry                          | Yes   |
| OCR                | Model load failure       | Retry with CPU fallback                           | Yes   |
| OCR                | GPU out of memory        | Reduce image resolution, retry                    | Yes   |
| OCR                | Low confidence (< 0.3)   | Log warning, flag page for review                 | No    |
| Layout Detection   | No regions detected      | Treat as single-column full page                  | No    |
| Layout Detection   | Model timeout            | Fall back to simple heuristics                    | Yes   |
| Table Extraction   | No tables found          | Skip table stage, continue                        | No    |
| Table Extraction   | Malformed table          | Extract as text, flag for review                  | No    |
| Chunking           | Empty chunks             | Skip empty chunks, log warning                    | No    |
| Embedding          | Model not loaded         | Retry model load, then fail                       | Yes   |
| Embedding          | OOM                      | Reduce batch size, retry                          | Yes   |
| Indexing           | Qdrant connection error  | Retry with exponential backoff                    | Yes   |
| Indexing           | Payload too large        | Split batch, retry                                | Yes   |
| Storage            | S3 upload failure        | Retry with exponential backoff                    | Yes   |
| Storage            | DB write failure         | Retry, then dead-letter queue                     | Yes   |

---

## 6. Retry Strategy

**General Policy:**

```yaml
retry:
  max_attempts: 3
  base_delay_seconds: 2
  max_delay_seconds: 60
  backoff_multiplier: 2
  jitter: true
```

**Retry Behavior by Stage:**

| Stage              | Max Retries | Backoff     | Notes                              |
|--------------------|-------------|-------------|------------------------------------|
| Upload             | 0           | —           | Client-side retry only             |
| Validation         | 0           | —           | Fail fast                          |
| Type Detection     | 1           | Immediate   | Try content analysis fallback      |
| Text Extraction    | 2           | 2s, 4s      | Try each parser in fallback chain  |
| OCR                | 3           | 2s, 4s, 8s  | GPU→CPU fallback on OOM            |
| Layout Detection   | 2           | 2s, 4s      | Heuristic fallback                 |
| Table Extraction   | 1           | 2s          | Skip tables on persistent failure  |
| Chunking           | 1           | Immediate   | Simplify strategy on retry         |
| Embedding          | 3           | 2s, 4s, 8s  | Reduce batch size on OOM           |
| Indexing           | 3           | 2s, 4s, 8s  | Split batch on payload error       |
| Storage            | 3           | 2s, 4s, 8s  | Dead-letter after max retries      |

**Dead-Letter Queue:**

Documents that fail all retries at storage stage are placed in a dead-letter queue (Redis list) for manual review.

---

## 7. Progress Tracking

**WebSocket/SSE Endpoint:** `GET /api/v1/documents/{id}/progress`

**Event Types:**

```json
{
  "event": "stage_started|stage_completed|stage_failed|pipeline_completed|pipeline_failed",
  "document_id": "uuid",
  "stage": "upload|validation|type_detection|extraction|ocr|layout|tables|sections|chunking|metadata|embedding|indexing|quality|storage",
  "status": "in_progress|completed|failed",
  "progress_percent": 45,
  "message": "Processing OCR on page 3 of 10",
  "timestamp": "ISO8601",
  "details": {
    "current_page": 3,
    "total_pages": 10,
    "elapsed_seconds": 12.5,
    "estimated_remaining_seconds": 28.3
  }
}
```

**Progress Calculation:**

| Stage              | Weight (%) |
|--------------------|------------|
| Upload             | 5          |
| Validation         | 5          |
| Type Detection     | 2          |
| Text Extraction    | 20         |
| OCR                | 25         |
| Layout Detection   | 8          |
| Table Extraction   | 5          |
| Section Detection  | 3          |
| Chunking           | 5          |
| Metadata Enrichment| 2          |
| Embedding          | 10         |
| Indexing           | 5          |
| Quality Check      | 3          |
| Storage            | 2          |

---

## 8. Implementation Checklist

### Phase 1: Core Pipeline (Week 1-2)
- [ ] Upload endpoint with multipart support
- [ ] MinIO/S3 integration for file storage
- [ ] File validation (magic bytes, integrity)
- [ ] SHA-256 duplicate detection
- [ ] PDF text extraction (PyMuPDF)
- [ ] DOCX extraction (python-docx)
- [ ] XLSX extraction (openpyxl)
- [ ] Basic recursive character chunking
- [ ] PostgreSQL schema and migrations
- [ ] Celery task queue setup

### Phase 2: OCR & Layout (Week 3-4)
- [ ] PaddleOCR integration
- [ ] Scanned PDF detection and processing
- [ ] Image preprocessing pipeline
- [ ] Vietnamese + English language support
- [ ] Layout detection (Docling/MinerU)
- [ ] Column detection
- [ ] Header/footer detection
- [ ] Reading order detection

### Phase 3: Advanced Extraction (Week 5)
- [ ] Table detection and extraction
- [ ] Table-to-text conversion
- [ ] Section/heading detection
- [ ] Hierarchical document structure
- [ ] Semantic chunking for complex docs
- [ ] Table-aware chunking

### Phase 4: Embedding & Indexing (Week 6)
- [ ] bge-m3 model integration
- [ ] Batch embedding pipeline
- [ ] Qdrant collection setup
- [ ] Payload indexing
- [ ] Vector upload with metadata

### Phase 5: Quality & Monitoring (Week 7)
- [ ] Quality scoring system
- [ ] Quality gate implementation
- [ ] Progress tracking (SSE/WebSocket)
- [ ] Error handling and retry logic
- [ ] Dead-letter queue
- [ ] Logging and monitoring

### Phase 6: Testing & Hardening (Week 8)
- [ ] Unit tests for all parsers
- [ ] Integration tests for full pipeline
- [ ] Performance benchmarking
- [ ] Load testing
- [ ] Error injection testing
- [ ] Documentation

---

## 9. Acceptance Criteria

### Functional Requirements

1. **Upload:** System accepts PDF, DOCX, XLSX, PNG, JPG, TIFF files up to 50MB
2. **Validation:** All files validated against magic bytes before processing
3. **Duplicate Detection:** Duplicate files (same SHA-256) detected and handled without reprocessing
4. **Text Extraction:** Text extracted from all supported formats with > 90% character accuracy for clean documents
5. **OCR:** Vietnamese and English text recognized with > 80% accuracy on 300 DPI scans
6. **Tables:** Tables detected and extracted with correct cell structure in > 85% of cases
7. **Chunking:** Documents chunked into 512-token segments with 50-token overlap
8. **Embedding:** All chunks embedded using bge-m3 (1024 dimensions)
9. **Indexing:** Chunks searchable via Qdrant within 5 seconds of processing completion
10. **Quality:** Quality score computed for every document; low-quality documents flagged

### Performance Requirements

| Metric                        | Target              |
|-------------------------------|---------------------|
| Upload throughput             | 100 files/minute    |
| Text PDF processing           | < 5 seconds/page    |
| Scanned PDF processing        | < 15 seconds/page   |
| Image OCR processing          | < 10 seconds/image  |
| DOCX processing               | < 3 seconds/doc     |
| Embedding throughput          | 500 chunks/minute   |
| Indexing throughput            | 1000 points/minute  |
| End-to-end (10-page PDF)      | < 120 seconds       |
| Search latency (p95)          | < 200ms             |

### Reliability Requirements

- Pipeline survives individual stage failures without data loss
- All failed documents tracked in database with error details
- Retry mechanism handles transient failures automatically
- Dead-letter queue captures permanently failed documents
- No duplicate processing of same document

---

## 10. Test Requirements

### Unit Tests

| Module              | Test Cases                                                     |
|---------------------|----------------------------------------------------------------|
| Upload              | Valid file upload, oversized file rejection, format validation |
| Validation          | MIME type matching, corruption detection, duplicate handling   |
| Type Detection      | Correct type identification, PDF subtype classification        |
| PDF Parser          | Text extraction, empty page handling, encrypted PDF rejection  |
| DOCX Parser         | Paragraph extraction, table extraction, image skip             |
| XLSX Parser         | Multi-sheet extraction, empty cell handling, formula skip       |
| OCR                 | Vietnamese text, English text, mixed language, low-quality image|
| Layout Detection    | Single column, multi-column, header/footer, reading order      |
| Table Extraction    | Simple table, merged cells, nested tables, borderless tables   |
| Chunking            | Short doc (no split), long doc (multiple chunks), overlap correctness |
| Embedding           | Single text, batch processing, dimension verification          |
| Quality Scoring     | High quality, medium quality, low quality edge cases           |

### Integration Tests

| Test Case                           | Description                                           |
|-------------------------------------|-------------------------------------------------------|
| Full pipeline - text PDF            | Upload → extract → chunk → embed → index              |
| Full pipeline - scanned PDF         | Upload → OCR → chunk → embed → index                  |
| Full pipeline - DOCX                | Upload → extract → chunk → embed → index              |
| Full pipeline - XLSX                | Upload → extract → chunk → embed → index              |
| Full pipeline - image               | Upload → OCR → chunk → embed → index                  |
| Duplicate detection                 | Upload same file twice, verify no reprocessing        |
| Pipeline failure recovery           | Kill process mid-pipeline, verify retry on restart    |
| Concurrent uploads                  | 10 simultaneous uploads, verify no data corruption    |
| Progress tracking                   | Verify SSE events emitted for each stage              |
| Quality gate                        | Low-quality document correctly blocked from indexing  |

### Performance Tests

| Test Case                           | Target                                                |
|-------------------------------------|-------------------------------------------------------|
| Sustained upload rate               | 100 files/minute for 10 minutes                       |
| Large file processing               | 50MB PDF completes within 10 minutes                  |
| Concurrent OCR                      | 5 scanned PDFs processed simultaneously               |
| Embedding throughput                | 10,000 chunks embedded within 20 minutes              |
| Qdrant query latency                | p95 < 200ms with 1M indexed vectors                   |

### Test Data Requirements

- 10 clean text PDFs (various page counts: 1, 5, 10, 50, 100)
- 10 scanned PDFs (Vietnamese and English, various qualities)
- 5 DOCX files (simple text, with tables, with images)
- 5 XLSX files (single sheet, multi-sheet, large datasets)
- 10 images (PNG, JPG, TIFF with Vietnamese text)
- 5 corrupted files (one per format)
- 5 duplicate pairs (same content, different filenames)
- 3 complex layout documents (multi-column, mixed content)

---

*Document version: 1.0*
*Last updated: 2026-06-11*
*Author: AI Document Operations Agent Team*
