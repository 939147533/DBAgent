<template>
  <Teleport to="body">
    <Transition name="toast">
      <div v-if="toast.show" :class="['toast', toast.ok ? 'toast-ok' : 'toast-error']">
        <component :is="toast.ok ? CheckCircle : XCircle" class="icon" />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </Teleport>

  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">DA</div>
        <div>
          <h1>Dataset Agent</h1>
          <p>Oracle / OceanBase 自然语言查询</p>
        </div>
      </div>

      <section class="panel">
        <div class="panel-title">
          <Database class="icon" />
          <h2>连接与模型</h2>
        </div>
        <div class="config-summary">
          <div>
            <span>数据库连接</span>
            <strong>{{ activeDatabase?.name || '未配置' }}</strong>
            <small>{{ databaseSummary }}</small>
          </div>
          <button class="secondary" @click="openDatabaseDialog">
            <Settings class="icon" />
            数据库连接配置
          </button>
        </div>
        <div class="config-summary">
          <div>
            <span>大模型 API</span>
            <strong>{{ activeLlm?.name || '未配置' }}</strong>
            <small>{{ llmSummary }}</small>
          </div>
          <button class="secondary" @click="openLlmDialog">
            <SlidersHorizontal class="icon" />
            大模型配置
          </button>
        </div>
        <p v-if="messages.database" :class="['message', messages.databaseOk ? 'ok' : 'error']">{{ messages.database }}</p>
        <p v-if="messages.llm" :class="['message', messages.llmOk ? 'ok' : 'error']">{{ messages.llm }}</p>
      </section>

      <section class="panel history">
        <div class="panel-title">
          <History class="icon" />
          <h2>查询历史</h2>
        </div>
        <button v-for="item in history" :key="item" class="history-item" @click="question = item">{{ item }}</button>
        <p v-if="history.length === 0" class="muted">暂无查询记录</p>
      </section>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <h2>用自然语言查询数据库</h2>
        </div>
        <div class="status">
          <span :class="['dot', result ? 'ready' : '']"></span>
          {{ result ? '结果已生成' : '等待查询' }}
        </div>
      </header>

      <section class="query-panel">
        <label class="query-label" for="question">输入查询问题</label>
        <textarea
          id="question"
          v-model="question"
          placeholder="例如：查询最近 10 条订单，并按创建时间倒序排列"
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
          <pre>{{ result?.sql || '执行查询后，这里会显示 Agent 生成的 SQL。' }}</pre>
          <div v-if="result?.warnings.length" class="warnings">
            <AlertTriangle class="icon" />
            {{ result.warnings.join('；') }}
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
          <div v-else-if="!result" class="empty-state">配置数据库和大模型后，输入问题开始查询。</div>
          <div v-else-if="result.rows.length === 0" class="empty-state">查询完成，没有返回数据。</div>
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

    <div v-if="databaseDialogOpen" class="modal-backdrop" @click.self="databaseDialogOpen = false">
      <section class="modal wide-modal">
        <div class="modal-head">
          <h3>数据库连接配置</h3>
          <button class="icon-button" @click="databaseDialogOpen = false" title="关闭">
            <X class="icon" />
          </button>
        </div>
        <div class="profile-layout">
          <aside class="profile-list">
            <button
              v-for="profile in databaseProfiles"
              :key="profile.id"
              :class="['profile-item', profile.id === activeDatabaseId ? 'active' : '']"
              @click="selectDatabaseProfile(profile.id)"
            >
              <strong>{{ profile.name }}</strong>
              <span>{{ profile.host || '未填写主机' }}</span>
            </button>
            <button class="secondary add-profile" @click="addDatabaseProfile">
              <Plus class="icon" />
              新增连接
            </button>
          </aside>

          <div v-if="databaseDraft" class="profile-form">
            <label>
              配置名称
              <input v-model="databaseDraft.name" placeholder="生产库 / 测试库" />
            </label>
            <label>
              数据库类型
              <select v-model="databaseDraft.db_type">
                <option value="oracle">Oracle</option>
                <option value="oceanbase_oracle">OceanBase Oracle 模式</option>
              </select>
            </label>
            <div class="field-grid">
              <label>
                主机
                <input v-model="databaseDraft.host" placeholder="127.0.0.1" />
              </label>
              <label>
                端口
                <input v-model.number="databaseDraft.port" type="number" />
              </label>
            </div>
            <label>
              Service Name
              <input v-model="databaseDraft.service_name" placeholder="ORCLPDB1" />
            </label>
            <template v-if="databaseDraft.db_type === 'oceanbase_oracle'">
              <div class="field-grid">
                <label>
                  租户
                  <input v-model="databaseDraft.tenant" placeholder="oracle_tenant" />
                </label>
                <label>
                  集群
                  <input v-model="databaseDraft.cluster" placeholder="可选" />
                </label>
              </div>
              <label>
                JDBC Jar 路径
                <input v-model="databaseDraft.jdbc_jar_path" placeholder="/path/oceanbase-client.jar" />
              </label>
            </template>
            <div class="field-grid">
              <label>
                用户名
                <input v-model="databaseDraft.user" />
              </label>
              <label>
                密码
                <input v-model="databaseDraft.password" type="password" autocomplete="new-password" />
              </label>
            </div>
            <div class="button-row split-actions">
              <button
                type="button"
                class="secondary danger"
                @click="deleteDatabaseProfile"
                :disabled="databaseProfiles.length <= 1 || busy.database"
              >
                <Trash2 class="icon" />
                删除
              </button>
              <div class="button-row">
                <button type="button" class="secondary" @click="testDatabase" :disabled="busy.database">
                  <PlugZap class="icon" />
                  测试连接
                </button>
                <button type="button" @click="saveDatabaseProfiles" :disabled="busy.database">
                  <Save class="icon" />
                  保存并使用
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="llmDialogOpen" class="modal-backdrop" @click.self="llmDialogOpen = false">
      <section class="modal wide-modal">
        <div class="modal-head">
          <h3>大模型 API 配置</h3>
          <button class="icon-button" @click="llmDialogOpen = false" title="关闭">
            <X class="icon" />
          </button>
        </div>
        <div class="profile-layout">
          <aside class="profile-list">
            <button
              v-for="profile in llmProfiles"
              :key="profile.id"
              :class="['profile-item', profile.id === activeLlmId ? 'active' : '']"
              @click="selectLlmProfile(profile.id)"
            >
              <strong>{{ profile.name }}</strong>
              <span>{{ profile.model || '未填写模型' }}</span>
            </button>
            <button class="secondary add-profile" @click="addLlmProfile">
              <Plus class="icon" />
              新增模型
            </button>
          </aside>

          <div v-if="llmDraft" class="profile-form">
            <label>
              配置名称
              <input v-model="llmDraft.name" placeholder="OpenAI / 本地模型" />
            </label>
            <label>
              Base URL
              <input v-model="llmDraft.base_url" placeholder="https://api.openai.com/v1" />
            </label>
            <label>
              API Key
              <input v-model="llmDraft.api_key" type="password" autocomplete="new-password" />
            </label>
            <div class="field-grid">
              <label>
                模型
                <input v-model="llmDraft.model" placeholder="gpt-4.1-mini" />
              </label>
              <label>
                Temperature
                <input v-model.number="llmDraft.temperature" type="number" min="0" max="2" step="0.1" />
              </label>
            </div>
            <div class="button-row split-actions">
              <button type="button" class="secondary danger" @click="deleteLlmProfile" :disabled="llmProfiles.length <= 1 || busy.llm">
                <Trash2 class="icon" />
                删除
              </button>
              <div class="button-row">
                <button type="button" class="secondary" @click="testLlm" :disabled="busy.llm">
                  <Sparkles class="icon" />
                  测试配置
                </button>
                <button type="button" @click="saveLlmProfiles" :disabled="busy.llm">
                  <Save class="icon" />
                  保存并使用
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

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
  CheckCircle,
  Copy,
  Database,
  Download,
  FileCode2,
  FileText,
  History,
  PlugZap,
  Plus,
  Save,
  Send,
  Settings,
  Sheet,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
  XCircle,
} from 'lucide-vue-next';
import { computed, onMounted, ref } from 'vue';
import { api, exportUrl } from './api';
import type { DatabaseProfile, LlmProfile, QueryResponse } from './types';

const databaseProfiles = ref<DatabaseProfile[]>([]);
const activeDatabaseId = ref('');
const databaseDraft = ref<DatabaseProfile | null>(null);
const databaseDialogOpen = ref(false);

const llmProfiles = ref<LlmProfile[]>([]);
const activeLlmId = ref('');
const llmDraft = ref<LlmProfile | null>(null);
const llmDialogOpen = ref(false);

const question = ref('');
const maxRows = ref(100);
const result = ref<QueryResponse | null>(null);
const error = ref('');
const history = ref<string[]>([]);
const sqlDialogOpen = ref(false);
const exportTableName = ref('QUERY_RESULT_EXPORT');
const exportNameError = ref('');

const busy = ref({ database: false, llm: false, query: false });
const messages = ref({ database: '', databaseOk: false, llm: '', llmOk: false });

const toast = ref({ show: false, ok: false, message: '', timer: 0 });

function showToast(ok: boolean, message: string) {
  clearTimeout(toast.value.timer);
  toast.value = { show: true, ok, message, timer: 0 };
  toast.value.timer = window.setTimeout(() => { toast.value.show = false; }, 3000);
}

const activeDatabase = computed(() => databaseProfiles.value.find((profile) => profile.id === activeDatabaseId.value));
const activeLlm = computed(() => llmProfiles.value.find((profile) => profile.id === activeLlmId.value));
const databaseSummary = computed(() => {
  const profile = activeDatabase.value;
  if (!profile) return '未选择连接';
  return [profile.db_type, profile.host, profile.service_name].filter(Boolean).join(' · ') || '未填写连接信息';
});
const llmSummary = computed(() => {
  const profile = activeLlm.value;
  if (!profile) return '未选择模型';
  return [profile.model, profile.base_url].filter(Boolean).join(' · ') || '未填写模型信息';
});

onMounted(async () => {
  await Promise.all([loadDatabaseProfiles(), loadLlmProfiles()]);
});

async function loadDatabaseProfiles() {
  try {
    const payload = await api.getDatabaseProfiles();
    databaseProfiles.value = payload.profiles;
    activeDatabaseId.value = payload.active_id;
    databaseDraft.value = cloneProfile(activeDatabase.value);
  } catch (err) {
    messages.value.database = errorMessage(err);
    messages.value.databaseOk = false;
  }
}

async function loadLlmProfiles() {
  try {
    const payload = await api.getLlmProfiles();
    llmProfiles.value = payload.profiles;
    activeLlmId.value = payload.active_id;
    llmDraft.value = cloneProfile(activeLlm.value);
  } catch (err) {
    messages.value.llm = errorMessage(err);
    messages.value.llmOk = false;
  }
}

function openDatabaseDialog() {
  databaseDraft.value = cloneProfile(activeDatabase.value) || newDatabaseProfile();
  if (!activeDatabaseId.value) activeDatabaseId.value = databaseDraft.value.id;
  databaseDialogOpen.value = true;
}

function openLlmDialog() {
  llmDraft.value = cloneProfile(activeLlm.value) || newLlmProfile();
  if (!activeLlmId.value) activeLlmId.value = llmDraft.value.id;
  llmDialogOpen.value = true;
}

function selectDatabaseProfile(id: string) {
  persistDatabaseDraft();
  activeDatabaseId.value = id;
  databaseDraft.value = cloneProfile(databaseProfiles.value.find((profile) => profile.id === id));
}

function selectLlmProfile(id: string) {
  persistLlmDraft();
  activeLlmId.value = id;
  llmDraft.value = cloneProfile(llmProfiles.value.find((profile) => profile.id === id));
}

function addDatabaseProfile() {
  persistDatabaseDraft();
  const profile = newDatabaseProfile(databaseProfiles.value.length + 1);
  databaseProfiles.value.push(profile);
  activeDatabaseId.value = profile.id;
  databaseDraft.value = cloneProfile(profile);
}

function addLlmProfile() {
  persistLlmDraft();
  const profile = newLlmProfile(llmProfiles.value.length + 1);
  llmProfiles.value.push(profile);
  activeLlmId.value = profile.id;
  llmDraft.value = cloneProfile(profile);
}

function deleteDatabaseProfile() {
  if (!databaseDraft.value || databaseProfiles.value.length <= 1) return;
  databaseProfiles.value = databaseProfiles.value.filter((profile) => profile.id !== databaseDraft.value?.id);
  activeDatabaseId.value = databaseProfiles.value[0].id;
  databaseDraft.value = cloneProfile(databaseProfiles.value[0]);
}

function deleteLlmProfile() {
  if (!llmDraft.value || llmProfiles.value.length <= 1) return;
  llmProfiles.value = llmProfiles.value.filter((profile) => profile.id !== llmDraft.value?.id);
  activeLlmId.value = llmProfiles.value[0].id;
  llmDraft.value = cloneProfile(llmProfiles.value[0]);
}

async function saveDatabaseProfiles() {
  await withBusy('database', async () => {
    persistDatabaseDraft();
    const payload = await api.saveDatabaseProfiles({ active_id: activeDatabaseId.value, profiles: databaseProfiles.value });
    databaseProfiles.value = payload.profiles;
    activeDatabaseId.value = payload.active_id;
    databaseDraft.value = cloneProfile(activeDatabase.value);
    messages.value.database = '数据库配置已保存并切换';
    messages.value.databaseOk = true;
    databaseDialogOpen.value = false;
  });
}

async function saveLlmProfiles() {
  await withBusy('llm', async () => {
    persistLlmDraft();
    const payload = await api.saveLlmProfiles({ active_id: activeLlmId.value, profiles: llmProfiles.value });
    llmProfiles.value = payload.profiles;
    activeLlmId.value = payload.active_id;
    llmDraft.value = cloneProfile(activeLlm.value);
    messages.value.llm = '大模型配置已保存并切换';
    messages.value.llmOk = true;
    llmDialogOpen.value = false;
  });
}

async function testDatabase() {
  if (!databaseDraft.value) return;
  await withBusy('database', async () => {
    const response = await api.testDatabaseSettings(databaseDraft.value!);
    messages.value.database = response.message;
    messages.value.databaseOk = response.ok;
    showToast(response.ok, response.message);
  });
}

async function testLlm() {
  if (!llmDraft.value) return;
  await withBusy('llm', async () => {
    const response = await api.testLlmSettings(llmDraft.value!);
    messages.value.llm = response.message;
    messages.value.llmOk = response.ok;
    showToast(response.ok, response.message);
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

function persistDatabaseDraft() {
  if (!databaseDraft.value) return;
  const index = databaseProfiles.value.findIndex((profile) => profile.id === databaseDraft.value?.id);
  if (index >= 0) databaseProfiles.value[index] = cloneProfile(databaseDraft.value)!;
  else databaseProfiles.value.push(cloneProfile(databaseDraft.value)!);
}

function persistLlmDraft() {
  if (!llmDraft.value) return;
  const index = llmProfiles.value.findIndex((profile) => profile.id === llmDraft.value?.id);
  if (index >= 0) llmProfiles.value[index] = cloneProfile(llmDraft.value)!;
  else llmProfiles.value.push(cloneProfile(llmDraft.value)!);
}

function newDatabaseProfile(index = 1): DatabaseProfile {
  return {
    id: createId(),
    name: `数据库连接 ${index}`,
    db_type: 'oracle',
    host: '',
    port: 1521,
    service_name: '',
    tenant: '',
    cluster: '',
    user: '',
    password: '',
    jdbc_jar_path: '',
  };
}

function newLlmProfile(index = 1): LlmProfile {
  return {
    id: createId(),
    name: `大模型配置 ${index}`,
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    model: '',
    temperature: 0,
  };
}

function cloneProfile<T>(profile: T | undefined | null): T | null {
  return profile ? JSON.parse(JSON.stringify(profile)) : null;
}

function createId() {
  return globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
}

function openSqlExport() {
  exportNameError.value = '';
  exportTableName.value = 'QUERY_RESULT_EXPORT';
  sqlDialogOpen.value = true;
}

function download(format: 'csv' | 'xlsx' | 'sql') {
  if (!result.value) return;
  if (format === 'sql' && !/^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$/.test(exportTableName.value.trim())) {
    exportNameError.value = '表名只能使用普通标识符或 schema.table';
    return;
  }
  window.location.href = exportUrl(result.value.query_id, format, exportTableName.value);
  sqlDialogOpen.value = false;
}

async function copySql() {
  if (result.value?.sql) await navigator.clipboard.writeText(result.value.sql);
}

async function withBusy(key: 'database' | 'llm' | 'query', action: () => Promise<void>) {
  busy.value[key] = true;
  try {
    await action();
  } catch (err) {
    if (key === 'query') {
      error.value = errorMessage(err);
    } else if (key === 'database') {
      messages.value.database = errorMessage(err);
      messages.value.databaseOk = false;
    } else {
      messages.value.llm = errorMessage(err);
      messages.value.llmOk = false;
    }
  } finally {
    busy.value[key] = false;
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
