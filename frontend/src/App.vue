<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">DA</div>
        <div>
          <h1>Dataset Agent</h1>
          <p>Oracle / OceanBase 查询工作台</p>
        </div>
      </div>

      <section class="panel">
        <div class="panel-title">
          <Database class="icon" />
          <h2>数据库连接</h2>
        </div>
        <label>
          数据库类型
          <select v-model="database.db_type">
            <option value="oracle">Oracle</option>
            <option value="oceanbase_oracle">OceanBase Oracle 模式</option>
          </select>
        </label>
        <div class="field-grid">
          <label>
            主机
            <input v-model="database.host" placeholder="127.0.0.1" />
          </label>
          <label>
            端口
            <input v-model.number="database.port" type="number" />
          </label>
        </div>
        <label>
          Service Name
          <input v-model="database.service_name" placeholder="ORCLPDB1" />
        </label>
        <template v-if="database.db_type === 'oceanbase_oracle'">
          <div class="field-grid">
            <label>
              租户
              <input v-model="database.tenant" placeholder="oracle_tenant" />
            </label>
            <label>
              集群
              <input v-model="database.cluster" placeholder="可选" />
            </label>
          </div>
          <label>
            JDBC Jar 路径
            <input v-model="database.jdbc_jar_path" placeholder="/path/oceanbase-client.jar" />
          </label>
        </template>
        <div class="field-grid">
          <label>
            用户
            <input v-model="database.user" />
          </label>
          <label>
            密码
            <input v-model="database.password" type="password" autocomplete="new-password" />
          </label>
        </div>
        <div class="button-row">
          <button class="secondary" @click="testDatabase" :disabled="busy.database">
            <PlugZap class="icon" />
            测试
          </button>
          <button @click="saveDatabase" :disabled="busy.database">
            <Save class="icon" />
            保存
          </button>
        </div>
        <p v-if="messages.database" :class="['message', messages.databaseOk ? 'ok' : 'error']">{{ messages.database }}</p>
      </section>

      <section class="panel">
        <div class="panel-title">
          <Bot class="icon" />
          <h2>大模型 API</h2>
        </div>
        <label>
          Base URL
          <input v-model="llm.base_url" placeholder="https://api.openai.com/v1" />
        </label>
        <label>
          API Key
          <input v-model="llm.api_key" type="password" autocomplete="new-password" />
        </label>
        <div class="field-grid">
          <label>
            模型
            <input v-model="llm.model" placeholder="gpt-4.1-mini" />
          </label>
          <label>
            温度
            <input v-model.number="llm.temperature" type="number" min="0" max="2" step="0.1" />
          </label>
        </div>
        <div class="button-row">
          <button class="secondary" @click="testLlm" :disabled="busy.llm">
            <Sparkles class="icon" />
            检查
          </button>
          <button @click="saveLlm" :disabled="busy.llm">
            <Save class="icon" />
            保存
          </button>
        </div>
        <p v-if="messages.llm" :class="['message', messages.llmOk ? 'ok' : 'error']">{{ messages.llm }}</p>
      </section>

      <section class="panel history">
        <div class="panel-title">
          <History class="icon" />
          <h2>最近查询</h2>
        </div>
        <button v-for="item in history" :key="item" class="history-item" @click="question = item">{{ item }}</button>
        <p v-if="history.length === 0" class="muted">暂无查询记录</p>
      </section>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <p class="eyeline">Natural Language SQL Agent</p>
          <h2>用自然语言查询企业数据库</h2>
        </div>
        <div class="status">
          <span :class="['dot', result ? 'ready' : '']"></span>
          {{ result ? '结果已就绪' : '等待查询' }}
        </div>
      </header>

      <section class="query-panel">
        <label class="query-label" for="question">输入查询问题</label>
        <textarea
          id="question"
          v-model="question"
          placeholder="例如：查询最近 10 条订单，显示订单号、客户名称和创建时间"
          @keydown.meta.enter.prevent="runQuery"
          @keydown.ctrl.enter.prevent="runQuery"
        ></textarea>
        <div class="query-actions">
          <label class="max-rows">
            最大行数
            <input v-model.number="maxRows" type="number" min="1" max="500" />
          </label>
          <button class="run-button" @click="runQuery" :disabled="busy.query || !question.trim()">
            <Send class="icon" />
            {{ busy.query ? '查询中' : '执行查询' }}
          </button>
        </div>
      </section>

      <section v-if="error" class="notice error">{{ error }}</section>

      <section class="result-layout">
        <div class="sql-panel">
          <div class="section-head">
            <h3>生成 SQL</h3>
            <button class="icon-button" @click="copySql" :disabled="!result?.sql" title="复制 SQL">
              <Copy class="icon" />
            </button>
          </div>
          <pre>{{ result?.sql || '执行查询后将在这里显示 Agent 生成的 SQL。' }}</pre>
          <div v-if="result?.warnings.length" class="warnings">
            <AlertTriangle class="icon" />
            {{ result.warnings.join('，') }}
          </div>
        </div>

        <div class="table-panel">
          <div class="section-head">
            <div>
              <h3>查询结果</h3>
              <p v-if="result">{{ result.row_count }} 行 · {{ result.elapsed_ms }} ms</p>
            </div>
            <div class="export-actions">
              <button class="secondary" :disabled="!result" @click="download('csv')">
                <FileText class="icon" />
                CSV
              </button>
              <button class="secondary" :disabled="!result" @click="download('xlsx')">
                <Sheet class="icon" />
                Excel
              </button>
              <button class="secondary" :disabled="!result" @click="openSqlExport">
                <FileCode2 class="icon" />
                INSERT SQL
              </button>
            </div>
          </div>

          <div v-if="busy.query" class="empty-state">正在生成 SQL 并查询数据库...</div>
          <div v-else-if="!result" class="empty-state">配置连接后输入问题，结果会以表格展示。</div>
          <div v-else-if="result.rows.length === 0" class="empty-state">查询成功，但没有返回数据。</div>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="column in result.columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in result.rows" :key="rowIndex">
                  <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ formatCell(cell) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>

    <div v-if="sqlDialogOpen" class="modal-backdrop" @click.self="sqlDialogOpen = false">
      <form class="modal" @submit.prevent="download('sql')">
        <h3>导出 INSERT SQL</h3>
        <label>
          目标表名
          <input v-model="exportTableName" placeholder="QUERY_RESULT_EXPORT" />
        </label>
        <p v-if="exportNameError" class="message error">{{ exportNameError }}</p>
        <div class="button-row">
          <button type="button" class="secondary" @click="sqlDialogOpen = false">取消</button>
          <button type="submit">
            <Download class="icon" />
            下载
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  AlertTriangle,
  Bot,
  Copy,
  Database,
  Download,
  FileCode2,
  FileText,
  History,
  PlugZap,
  Save,
  Send,
  Sheet,
  Sparkles,
} from 'lucide-vue-next';
import { onMounted, reactive, ref } from 'vue';
import { api, exportUrl } from './api';
import type { DatabaseSettings, LlmSettings, QueryResponse } from './types';

const database = reactive<DatabaseSettings>({
  db_type: 'oracle',
  host: '',
  port: 1521,
  service_name: '',
  tenant: '',
  cluster: '',
  user: '',
  password: '',
  jdbc_jar_path: '',
});

const llm = reactive<LlmSettings>({
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model: '',
  temperature: 0,
});

const question = ref('');
const maxRows = ref(100);
const result = ref<QueryResponse | null>(null);
const error = ref('');
const history = ref<string[]>([]);
const sqlDialogOpen = ref(false);
const exportTableName = ref('QUERY_RESULT_EXPORT');
const exportNameError = ref('');

const busy = reactive({ database: false, llm: false, query: false });
const messages = reactive({ database: '', databaseOk: false, llm: '', llmOk: false });

onMounted(async () => {
  await Promise.all([loadDatabase(), loadLlm()]);
});

async function loadDatabase() {
  try {
    Object.assign(database, await api.getDatabaseSettings());
  } catch (err) {
    messages.database = errorMessage(err);
  }
}

async function loadLlm() {
  try {
    Object.assign(llm, await api.getLlmSettings());
  } catch (err) {
    messages.llm = errorMessage(err);
  }
}

async function saveDatabase() {
  await withBusy('database', async () => {
    Object.assign(database, await api.saveDatabaseSettings(database));
    messages.database = '数据库配置已保存';
    messages.databaseOk = true;
  });
}

async function testDatabase() {
  await withBusy('database', async () => {
    const response = await api.testDatabaseSettings(database);
    messages.database = response.message;
    messages.databaseOk = response.ok;
  });
}

async function saveLlm() {
  await withBusy('llm', async () => {
    Object.assign(llm, await api.saveLlmSettings(llm));
    messages.llm = '大模型配置已保存';
    messages.llmOk = true;
  });
}

async function testLlm() {
  await withBusy('llm', async () => {
    const response = await api.testLlmSettings(llm);
    messages.llm = response.message;
    messages.llmOk = response.ok;
  });
}

async function runQuery() {
  error.value = '';
  result.value = null;
  await withBusy('query', async () => {
    result.value = await api.query(question.value, maxRows.value);
    history.value = [question.value, ...history.value.filter((item) => item !== question.value)].slice(0, 6);
  });
}

function openSqlExport() {
  exportNameError.value = '';
  exportTableName.value = 'QUERY_RESULT_EXPORT';
  sqlDialogOpen.value = true;
}

function download(format: 'csv' | 'xlsx' | 'sql') {
  if (!result.value) return;
  if (format === 'sql' && !/^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$/.test(exportTableName.value.trim())) {
    exportNameError.value = '表名只允许普通标识符或 schema.table';
    return;
  }
  window.location.href = exportUrl(result.value.query_id, format, exportTableName.value);
  sqlDialogOpen.value = false;
}

async function copySql() {
  if (result.value?.sql) {
    await navigator.clipboard.writeText(result.value.sql);
  }
}

async function withBusy(key: keyof typeof busy, action: () => Promise<void>) {
  busy[key] = true;
  try {
    await action();
  } catch (err) {
    if (key === 'query') {
      error.value = errorMessage(err);
    } else if (key === 'database') {
      messages.database = errorMessage(err);
      messages.databaseOk = false;
    } else {
      messages.llm = errorMessage(err);
      messages.llmOk = false;
    }
  } finally {
    busy[key] = false;
  }
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return 'NULL';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function errorMessage(err: unknown) {
  return err instanceof Error ? err.message : String(err);
}
</script>
