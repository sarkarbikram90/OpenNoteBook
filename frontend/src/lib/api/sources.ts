/** OpenNotebook — Sources API functions. */

import { apiFetch } from '@/lib/api';
import type {
  SignedDownloadResponse,
  SignedUploadRequest,
  SignedUploadResponse,
  Source,
  SourceListResponse,
  SourceUploadResponse,
} from '@/lib/types';
import { getTokens } from '@/stores/auth';

const API_BASE = '/api/v1';

export async function getSources(notebookId: string): Promise<SourceListResponse> {
  return apiFetch<SourceListResponse>(`/notebooks/${notebookId}/sources`);
}

export async function getSource(notebookId: string, sourceId: string): Promise<Source> {
  return apiFetch<Source>(`/notebooks/${notebookId}/sources/${sourceId}`);
}

export async function uploadFileSource(
  notebookId: string,
  file: File,
): Promise<SourceUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const tokens = getTokens();
  const headers: Record<string, string> = {};
  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }

  const response = await fetch(`${API_BASE}/notebooks/${notebookId}/sources/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }

  return response.json() as Promise<SourceUploadResponse>;
}

export async function uploadUrlSource(
  notebookId: string,
  data: { url: string; source_type: 'url' | 'youtube'; name?: string },
): Promise<SourceUploadResponse> {
  return apiFetch<SourceUploadResponse>(`/notebooks/${notebookId}/sources/url`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteSource(notebookId: string, sourceId: string): Promise<void> {
  return apiFetch<void>(`/notebooks/${notebookId}/sources/${sourceId}`, {
    method: 'DELETE',
  });
}

export async function reindexSource(
  notebookId: string,
  sourceId: string,
): Promise<SourceUploadResponse> {
  return apiFetch<SourceUploadResponse>(
    `/notebooks/${notebookId}/sources/${sourceId}/reindex`,
    { method: 'POST' },
  );
}

export async function triggerSummary(
  notebookId: string,
  sourceId: string,
): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(
    `/notebooks/${notebookId}/sources/${sourceId}/summary`,
    { method: 'POST' },
  );
}

export async function createSignedUploadUrl(
  notebookId: string,
  data: SignedUploadRequest,
): Promise<SignedUploadResponse> {
  return apiFetch<SignedUploadResponse>(
    `/notebooks/${notebookId}/sources/upload-url`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
  );
}

export async function confirmSignedUpload(
  notebookId: string,
  sourceId: string,
): Promise<SourceUploadResponse> {
  return apiFetch<SourceUploadResponse>(
    `/notebooks/${notebookId}/sources/${sourceId}/confirm-upload`,
    { method: 'POST' },
  );
}

export async function getSignedDownloadUrl(
  notebookId: string,
  sourceId: string,
): Promise<SignedDownloadResponse> {
  return apiFetch<SignedDownloadResponse>(
    `/notebooks/${notebookId}/sources/${sourceId}/download-url`,
  );
}

export async function uploadFileViaSignedUrl(
  notebookId: string,
  file: File,
): Promise<SourceUploadResponse> {
  const signed = await createSignedUploadUrl(notebookId, {
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size_bytes: file.size,
  });

  if (signed.duplicate) {
    return {
      source_id: signed.source_id,
      status: signed.status,
      message: 'Duplicate document detected; using existing source',
    };
  }

  if (signed.upload_url.startsWith('http://') || signed.upload_url.startsWith('https://')) {
    const putResp = await fetch(signed.upload_url, {
      method: signed.method || 'PUT',
      headers: {
        'Content-Type': signed.content_type || file.type || 'application/octet-stream',
      },
      body: file,
    });
    if (!putResp.ok) {
      throw new Error(`Signed URL upload failed with HTTP ${putResp.status}`);
    }
    return confirmSignedUpload(notebookId, signed.source_id);
  }

  // Fallback for local storage mode where no external presigned host is configured
  return uploadFileSource(notebookId, file);
}

