export type DatabaseType = 'oracle' | 'oceanbase_oracle';

export interface DatabaseSettings {
  db_type: DatabaseType;
  host: string;
  port: number;
  service_name: string;
  tenant: string;
  cluster: string;
  user: string;
  password: string;
  jdbc_jar_path: string;
}

export interface LlmSettings {
  base_url: string;
  api_key: string;
  model: string;
  temperature: number;
}

export interface QueryResponse {
  query_id: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  elapsed_ms: number;
  warnings: string[];
}

export interface TestConnectionResponse {
  ok: boolean;
  message: string;
}
