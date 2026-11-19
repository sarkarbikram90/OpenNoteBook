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
  source_type: 'pdf' | 'image' | 'docx' | 'txt' | 'md' | 'url' | 'youtube';
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
  | 'UPLOADED'
  | 'QUEUED'
  | 'PENDING'
  | 'EXTRACTING'
  | 'CHUNKING'
  | 'EMBEDDING'
  | 'READY'
  | 'FAILED';

export interface SignedUploadRequest {
  filename: string;
  content_type?: string;
  size_bytes?: number;
  sha256?: string;
}

export interface SignedUploadResponse {
  source_id: string;
  object_name: string;
  upload_url: string;
  method: string;
  content_type: string;
  expires_in_seconds: number;
  status: SourceStatus;
  duplicate: boolean;
}

export interface SignedDownloadResponse {
  source_id: string;
  object_name: string;
  download_url: string;
  expires_in_seconds: number;
}

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
  snippet?: string;
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
export interface SourceSummary {  id: string;
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

/** Feedback */
export type FeedbackRating = 'up' | 'down';

export interface FeedbackResponse {
  id: string;
  message_id: string;
  rating: FeedbackRating;
  created_at: string;
}

/** Workspaces & RBAC */
export type WorkspaceRole = 'owner' | 'admin' | 'member' | 'viewer';
export type SensitivityLevel = 'public' | 'internal' | 'confidential' | 'restricted';

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  role: WorkspaceRole;
  enable_pii_redaction: boolean;
  default_sensitivity: SensitivityLevel;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceCreateRequest {
  name: string;
  enable_pii_redaction?: boolean;
  default_sensitivity?: SensitivityLevel;
}

export interface WorkspaceUpdateRequest {
  name?: string;
  enable_pii_redaction?: boolean;
  default_sensitivity?: SensitivityLevel;
}

export interface WorkspaceMember {
  user_id: string;
  email: string;
  role: WorkspaceRole;
  created_at: string;
}

/** Enterprise Connectors */
export type ConnectorType =
  | 'confluence'
  | 'sharepoint'
  | 'salesforce'
  | 's3'
  | 'sql'
  | 'web'
  | 'fileshare'
  | 'rest';

export interface Connector {
  id: string;
  workspace_id: string;
  notebook_id: string | null;
  name: string;
  connector_type: ConnectorType;
  schedule_cron: string | null;
  status: string;
  last_sync_at: string | null;
  error_message: string | null;
}

export interface ConnectorCreateRequest {
  workspace_id: string;
  notebook_id?: string | null;
  name: string;
  connector_type: ConnectorType;
  config_json: Record<string, unknown>;
  schedule_cron?: string | null;
}

export interface ConnectorTestResponse {
  success: boolean;
  message: string;
}

export interface ConnectorSyncResponse {
  connector_id: string;
  documents_synced: number;
  status: string;
}

/** Ingestion Jobs / DLQ */
export interface FailedJob {
  id: string;
  source_id: string;
  task_name: string;
  error_message: string;
  traceback: string | null;
  retry_count: number;
  retried: boolean;
  created_at: string;
}

export interface FailedJobListResponse {
  jobs: FailedJob[];
  total: number;
}

export interface RetryJobResponse {
  job_id: string;
  source_id: string;
  status: string;
}
