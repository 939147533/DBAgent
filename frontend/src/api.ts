import type {
  DatabaseProfilesPayload,
  DatabaseSettings,
  LlmProfilesPayload,
  LlmSettings,
  QueryResponse,
  TestConnectionResponse,
} from './types';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getDatabaseSettings: () => request<DatabaseSettings>('/api/settings/database'),
  saveDatabaseSettings: (settings: DatabaseSettings) =>
    request<DatabaseSettings>('/api/settings/database', { method: 'PUT', body: JSON.stringify(settings) }),
  getDatabaseProfiles: () => request<DatabaseProfilesPayload>('/api/settings/database/profiles'),
  saveDatabaseProfiles: (payload: DatabaseProfilesPayload) =>
    request<DatabaseProfilesPayload>('/api/settings/database/profiles', { method: 'PUT', body: JSON.stringify(payload) }),
  testDatabaseSettings: (settings: DatabaseSettings) =>
    request<TestConnectionResponse>('/api/settings/database/test', { method: 'POST', body: JSON.stringify(settings) }),
  getLlmSettings: () => request<LlmSettings>('/api/settings/llm'),
  saveLlmSettings: (settings: LlmSettings) =>
    request<LlmSettings>('/api/settings/llm', { method: 'PUT', body: JSON.stringify(settings) }),
  getLlmProfiles: () => request<LlmProfilesPayload>('/api/settings/llm/profiles'),
  saveLlmProfiles: (payload: LlmProfilesPayload) =>
    request<LlmProfilesPayload>('/api/settings/llm/profiles', { method: 'PUT', body: JSON.stringify(payload) }),
  testLlmSettings: (settings: LlmSettings) =>
    request<TestConnectionResponse>('/api/settings/llm/test', { method: 'POST', body: JSON.stringify(settings) }),
  query: (question: string, maxRows: number) =>
    request<QueryResponse>('/api/query', { method: 'POST', body: JSON.stringify({ question, max_rows: maxRows }) }),
};

export function exportUrl(queryId: string, format: 'csv' | 'xlsx' | 'sql', tableName = 'QUERY_RESULT_EXPORT') {
  const params = new URLSearchParams({ format });
  if (format === 'sql') {
    params.set('table_name', tableName);
  }
  return `/api/query/${queryId}/export?${params.toString()}`;
}
