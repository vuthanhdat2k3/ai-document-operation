export interface Document {
  id: string;
  user_id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  storage_backend: string;
  storage_path: string;
  page_count: number | null;
  status: DocumentStatus;
  document_type: string | null;
  classification: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  checksum_sha256: string;
  uploaded_at: string;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type DocumentStatus =
  | "uploaded"
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "deleted";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  text: string;
  chunk_text?: string;
  score: number;
  relevance_score?: number;
  page: number;
  page_number?: number;
  filename?: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
  took_ms?: number;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  page: number;
  text: string;
  score: number;
}

export interface DebugStep {
  step_type: string;
  iteration: number;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  groundedness_score: number;
  session_id: string;
  debug_steps?: DebugStep[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  groundedness_score?: number;
  debug_steps?: DebugStep[];
  timestamp: string;
  created_at?: string;
  isStreaming?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  document_id: string | null;
  message_count: number;
  total_tokens: number;
  last_message_at: string | null;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface Report {
  id: string;
  document_id: string;
  user_id: string;
  report_type: string;
  title: string;
  content: string;
  format: string;
  status: string;
  file_url?: string;
  error_message?: string | null;
  created_at: string;
}

export interface AgentSession {
  id: string;
  user_id: string;
  agent_type: string;
  task_type?: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown> | null;
  error_message?: string | null;
  total_cost: number;
  total_cost_usd?: number | null;
  total_tokens: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  steps: AgentStep[];
  model?: string | null;
}

export interface AgentStep {
  id?: string;
  session_id?: string;
  step_index?: number;
  step_order?: number;
  step_type: string;
  action?: string;
  tool_name?: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  reasoning?: string;
  tokens_used?: number;
  duration_ms: number;
  latency_ms?: number;
  status?: string;
  input?: string;
  output?: string;
  cost?: number;
  created_at?: string;
  timestamp?: string;
}

export interface RiskItem {
  id: string;
  document_id: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string | null;
  page_number: number | null;
  status: string;
}

export interface ChecklistItem {
  id: string;
  description: string;
  severity: string;
  category: string;
  suggested_action: string;
  due_days: number;
}

export interface ExtractedField {
  id: string;
  document_id: string;
  field_name: string;
  field_value: unknown;
  raw_text: string | null;
  confidence: number | null;
  page_number: number | null;
  is_verified: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
}

export interface EvalResult {
  run_id: string;
  dataset_name: string;
  metrics: Record<string, number>;
  per_sample_count: number;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface DocumentDetail extends Document {
  pages?: Array<{
    page_number: number;
    text: string;
    confidence?: number;
  }>;
  chunks?: Array<{
    chunk_index: number;
    chunk_text: string;
    page_number: number;
  }>;
  extracted_fields?: ExtractedField[];
  risk_items?: RiskItem[];
  checklist_items?: ChecklistItem[];
  content?: string;
}

export interface DashboardStats {
  total_documents: number;
  total_pages: number;
  total_sessions: number;
  total_risks: number;
  documents_by_status: Record<string, number>;
  recent_documents: Array<{
    id: string;
    filename: string;
    mime_type: string;
    file_size_bytes: number;
    status: string;
    created_at: string;
  }>;
}

export interface LLMProvider {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  api_base_url: string | null;
  api_key?: string | null;
  config_schema: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LLMModel {
  id: string;
  provider_id: string;
  name: string;
  slug: string;
  description: string | null;
  max_tokens: number;
  default_temperature: number;
  supports_streaming: boolean;
  supports_thinking: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentModelConfig {
  id: string;
  agent_name: string;
  provider_id: string;
  model_id: string;
  temperature: number | null;
  max_tokens: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  provider_name?: string;
  model_name?: string;
  model_slug?: string;
}

export interface AgentInfo {
  name: string;
  description?: string;
  agent_type?: string;
  is_active?: boolean;
}

export { };
