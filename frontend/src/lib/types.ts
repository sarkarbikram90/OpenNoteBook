/* ── TypeScript types matching backend Pydantic schemas ─────────────── */

/** Notebook entity */
export interface Notebook {
  id: string;
  name: string;
  description: string | null;
  source_count: number;
  created_at: string;
  updated_at: string;
}

export interface NotebookListResponse {
  notebooks: Notebook[];
  total: number;
}

/** Source document entity */
export interface Source {
  id: string;
  notebook_id: string;
  name: string;
  source_type: 'pdf' | 'docx' | 'txt' | 'md' | 'url' | 'youtube';
  status: SourceStatus;
  error_message: string | null;
  page_count: number | null;
  chunk_count: number | null;
  embedding_model: string | null;
  storage_path: string | null;
  source_url: string | null;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type SourceStatus =
  | 'PENDING'
  | 'EXTRACTING'
  | 'CHUNKING'
  | 'EMBEDDING'
  | 'READY'
  | 'FAILED';

export interface SourceListResponse {
  sources: Source[];
  total: number;
}

export interface SourceUploadResponse {
  source_id: string;
  status: string;
  message: string;
}

/** Chat session */
export interface ChatSession {
  id: string;
  notebook_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatSessionListResponse {
  sessions: ChatSession[];
  total: number;
}

/** Chat message */
export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  retrieval_meta: Record<string, unknown>;
  created_at: string;
}

export interface MessageListResponse {
  messages: Message[];
  total: number;
}

/** Citation detail */
export interface Citation {
  chunk_id: string;
  source_name: string;
  source_id: string;
  page: number | null;
  section: string | null;
  relevance_score: number;
}

/** SSE event types from backend chat endpoint */
export interface SSETokenEvent {
  token: string;
}

export interface SSECitationEvent {
  chunk_id: string;
  source_name: string;
  page: number | null;
}

export interface SSEDoneEvent {
  message_id: string;
  latency_ms: number;
}

export interface SSEErrorEvent {
  code: string;
  message: string;
}

/** Source status SSE event */
export interface SourceStatusEvent {
  source_id: string;
  status: SourceStatus;
  chunk_count?: number;
  error_message?: string;
}

/** Settings / Model registry */
export interface Settings {
  id: string;
  user_id: string;
  llm_model: string;
  embedding_model: string;
  reranker_model: string;
  llm_temperature: number;
  context_window: number;
  max_chunks: number;
  updated_at: string;
}

export interface SettingsUpdate {
  llm_model?: string;
  embedding_model?: string;
  reranker_model?: string;
  llm_temperature?: number;
  context_window?: number;
  max_chunks?: number;
}

/** Auth */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

/** Search */
export interface SearchResult {
  chunk_id: string;
  source_id: string;
  source_name: string;
  text: string;
  page: number | null;
  section: string | null;
  relevance_score: number;
  token_count: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  latency_ms: number;
}

/** Source summary */
export interface SourceSummary {
  id: string;
  source_id: string;
  executive_summary: string;
  key_findings: string[];
  entities: {
    people: string[];
    organisations: string[];
    concepts: string[];
  };
  suggested_questions: string[];
  created_at: string;
}
