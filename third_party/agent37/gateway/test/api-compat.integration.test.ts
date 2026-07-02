import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import type { AgentAdapter } from '../server/adapters/types.js';
import { setAdapter } from '../server/agent.js';
import { startTestServer, type TestServer } from './test-helpers.js';

const fakeAdapter: AgentAdapter = {
  async *chatStream() {},
  async interruptChat() {
    return false;
  },
  async healthCheck() {
    return true;
  },
  async listSessions() {
    return [
      {
        id: 'session-1',
        title: 'Session One',
        message_count: 2,
        started_at: 1000,
        last_active: 2000,
        model: 'nous/test-model',
      },
    ];
  },
  async getMessages(sessionId: string) {
    return [
      {
        id: 'msg-1',
        task_id: sessionId,
        role: 'user',
        content: 'make a report',
        created_at: 1000,
      },
      {
        id: 'msg-2',
        task_id: sessionId,
        role: 'assistant',
        content: 'created artifact report.md',
        thinking: 'checked workspace',
        created_at: 2000,
      },
    ];
  },
  async getSessionMetadata(sessionId: string) {
    return {
      id: sessionId,
      input_tokens: 1,
      output_tokens: 2,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      reasoning_tokens: 0,
      estimated_cost_usd: null,
      cost_status: 'unknown',
      model: 'nous/test-model',
    };
  },
  async deleteSession() {
    return true;
  },
  async renameSession() {
    return true;
  },
  async getModels() {
    return {
      defaultModel: 'nous/test-model',
      activeProvider: 'nous',
      groups: [
        {
          provider: 'nous',
          models: [{ id: 'nous/test-model', label: 'Test Model', source: 'current', isCurrentDefault: true }],
        },
      ],
    };
  },
  async getDefaults() {
    return {
      provider: 'nous',
      model: 'nous/test-model',
      baseUrl: 'https://inference-api.nousresearch.com/v1',
      apiMode: null,
      reasoningEffort: 'low',
      showReasoning: true,
    };
  },
  async reloadMcp() {
    return {
      added: ['composio'],
      removed: [],
      reconnected: [],
      tool_count: 3,
      server_count: 1,
    };
  },
};

let server: TestServer | undefined;
let base = '';

before(async () => {
  setAdapter(fakeAdapter);
  server = await startTestServer();
  base = server.base;
});

after(async () => {
  await server?.close();
});

async function jsonOk<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init);
  const body = await response.json();
  assert.equal(response.status, 200, `${path}: ${JSON.stringify(body)}`);
  return body as T;
}

test('container compatibility API exposes Headmaster desktop smoke routes', async () => {
  const agents = await jsonOk<Array<{ id: string; available: boolean }>>('/api/agents');
  assert.deepEqual(
    agents.map((agent) => [agent.id, agent.available]),
    [['hermes', true]]
  );

  const assistants = await jsonOk<Array<{ id: string; models: string[] }>>('/api/assistants');
  assert.deepEqual(assistants, [
    {
      id: 'default',
      source: 'builtin',
      name: 'default',
      name_i18n: {},
      description: '0 skills · nous/test-model',
      description_i18n: {},
      enabled: true,
      sort_order: 0,
      preset_agent_type: 'aionrs',
      enabled_skills: [],
      custom_skill_names: [],
      disabled_builtin_skills: [],
      context_i18n: {},
      prompts: [],
      prompts_i18n: {},
      models: ['nous/test-model'],
    },
  ]);

  assert.deepEqual(await jsonOk('/api/cron/jobs'), []);
  assert.deepEqual(await jsonOk('/api/mcp/servers'), { servers: [] });

  const skills = await jsonOk<{ skills: unknown[] }>('/api/skills');
  assert.ok(Array.isArray(skills.skills));
  assert.equal((await jsonOk<{ name: string }>('/api/skills/builtin-auto')).name, 'builtin-auto');

  const profiles = await jsonOk<{ profiles: Array<{ name: string; model: string }> }>('/api/profiles');
  assert.deepEqual(
    profiles.profiles.map((profile) => [profile.name, profile.model]),
    [['default', 'nous/test-model']]
  );

  const providers = await jsonOk<Array<{ slug: string; models: string[] }>>('/api/providers');
  assert.deepEqual(providers, [
    {
      name: 'nous',
      slug: 'nous',
      authenticated: true,
      auth_type: 'runtime',
      source: 'gateway',
      models: ['nous/test-model'],
      is_user_defined: false,
    },
  ]);

  const modelOptions = await jsonOk<{ default_model: string; providers: unknown[]; options: unknown[] }>(
    '/api/model/options'
  );
  assert.equal(modelOptions.default_model, 'nous/test-model');
  assert.equal(modelOptions.providers.length, 1);
  assert.equal(modelOptions.options.length, 1);

  const sessions = await jsonOk<{ total: number; sessions: Array<{ id: string }> }>('/api/sessions');
  assert.equal(sessions.total, 1);
  assert.equal(sessions.sessions[0]?.id, 'session-1');

  const messages = await jsonOk<{ session_id: string; messages: Array<{ role: string; text: string }> }>(
    '/api/sessions/session-1/messages'
  );
  assert.equal(messages.session_id, 'session-1');
  assert.deepEqual(
    messages.messages.map((message) => [message.role, message.text]),
    [
      ['user', 'make a report'],
      ['assistant', 'created artifact report.md'],
    ]
  );

  const artifacts = await jsonOk<Array<{ id: string }>>('/api/conversations/session-1/artifacts');
  assert.deepEqual(
    artifacts.map((artifact) => artifact.id),
    ['msg-2']
  );
  assert.deepEqual(await jsonOk('/api/conversations/session-1/confirmations'), []);
  assert.deepEqual(await jsonOk('/api/conversations/session-1/mode'), { mode: 'default', initialized: false });
  assert.deepEqual(await jsonOk('/api/conversations/session-1/slash-commands'), [
    { command: '/help', description: 'Show available runtime commands' },
    { command: '/clear', description: 'Start a fresh context' },
  ]);
});

test('/api/mcp/servers POST writes to config.yaml and DELETE removes it', async () => {
  const created = await jsonOk<{ id: string; name: string; enabled: boolean }>('/api/mcp/servers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'test-mcp',
      enabled: true,
      transport: { type: 'http', url: 'https://mcp.example.com/endpoint' },
    }),
  });
  assert.equal(created.name, 'test-mcp');
  assert.equal(created.enabled, true);

  const { servers } = await jsonOk<{ servers: Array<{ name: string }> }>('/api/mcp/servers');
  assert.ok(servers.some((s) => s.name === 'test-mcp'));

  await fetch(`${base}/api/mcp/servers/test-mcp`, { method: 'DELETE' });
  const { servers: after } = await jsonOk<{ servers: Array<{ name: string }> }>('/api/mcp/servers');
  assert.ok(!after.some((s) => s.name === 'test-mcp'));
});


test('/api/mcp/servers/import persists imported servers to config.yaml', async () => {
  const imported = await jsonOk<Array<{ id: string; enabled: boolean }>>('/api/mcp/servers/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      servers: [
        {
          name: 'imported-composio',
          enabled: true,
          transport: {
            type: 'http',
            url: 'https://backend.composio.dev/v3/mcp/server?user_id=user-1',
            headers: { 'x-api-key': 'test-key' },
          },
        },
      ],
    }),
  });

  assert.ok(imported.some((server) => server.id === 'imported-composio' && server.enabled));

  const { listMcpServers } = await import('../server/mcpConfigStore.js');
  const servers = await listMcpServers();
  assert.ok(
    servers.some(
      (server) =>
        server.id === 'imported-composio' &&
        server.transport.url === 'https://backend.composio.dev/v3/mcp/server?user_id=user-1' &&
        server.transport.headers?.['x-api-key'] === 'test-key'
    )
  );

  await fetch(`${base}/api/mcp/servers/imported-composio`, { method: 'DELETE' });
});

test('/api/mcp/reload returns worker reload summary', async () => {
  const summary = await jsonOk<{ added: string[]; tool_count: number; server_count: number }>('/api/mcp/reload', {
    method: 'POST',
  });
  assert.deepEqual(summary.added, ['composio']);
  assert.equal(summary.tool_count, 3);
  assert.equal(summary.server_count, 1);
});

test('/v1 primitives still answer after mounting /api', async () => {
  const health = await jsonOk<{ ok: boolean; agent: string; healthy: boolean }>('/v1/health');
  assert.deepEqual(health, { ok: true, agent: 'hermes', healthy: true, hermes: true });

  const models = await jsonOk<{ object: string; data: Array<{ id: string }> }>('/v1/models');
  assert.equal(models.object, 'list');
  assert.deepEqual(
    models.data.map((model) => model.id),
    ['nous/test-model']
  );
});
