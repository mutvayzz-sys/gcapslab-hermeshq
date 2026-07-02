import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { Router } from 'express';
import type { Request } from 'express';
import type { AgentModelGroup, AgentType, HermesMessage } from '../../shared/types.js';
import { agentFromQuery, getAdapter } from '../agent.js';
import { gatewayErrorFromWorker, validationError } from '../errors.js';
import { resolveGatewayHome, resolveHermesHome, expandHomePrefix } from '../paths.js';
import { listMcpServers, upsertMcpServer, removeMcpServer, toggleMcpServer, getMcpServer, type HermesMcpServerEntry } from '../mcpConfigStore.js';

type JsonObject = Record<string, unknown>;

type StoreShape = {
  cronJobs: JsonObject[];
  mcpServers: JsonObject[];
  conversationModes: Record<string, { mode: string; initialized: boolean }>;
};

const apiRouter = Router();
export const compatibilityApiRouter = apiRouter;

const STORE_PATH = join(resolveGatewayHome(), 'api-compat.json');
const DEFAULT_STORE: StoreShape = {
  cronJobs: [],
  mcpServers: [],
  conversationModes: {},
};

function readStore(): StoreShape {
  try {
    const parsed = JSON.parse(readFileSync(STORE_PATH, 'utf8')) as Partial<StoreShape>;
    return {
      cronJobs: Array.isArray(parsed.cronJobs) ? parsed.cronJobs : [],
      mcpServers: Array.isArray(parsed.mcpServers) ? parsed.mcpServers : [],
      conversationModes:
        parsed.conversationModes &&
        typeof parsed.conversationModes === 'object' &&
        !Array.isArray(parsed.conversationModes)
          ? parsed.conversationModes
          : {},
    };
  } catch {
    return { ...DEFAULT_STORE };
  }
}

function writeStore(store: StoreShape): void {
  mkdirSync(dirname(STORE_PATH), { recursive: true });
  writeFileSync(STORE_PATH, `${JSON.stringify(store, null, 2)}\n`);
}

function selectedAgent(req: Request): AgentType {
  return agentFromQuery(req.query.agent);
}

function numberQuery(value: unknown, fallback: number): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number.parseInt(String(raw ?? ''), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function modelGroupsToProviders(groups: AgentModelGroup[]): JsonObject[] {
  return groups.map((group) => ({
    name: group.provider,
    slug:
      group.provider
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '') || 'provider',
    authenticated: group.models.length > 0,
    auth_type: 'runtime',
    source: 'gateway',
    models: group.models.map((model) => model.id),
    is_user_defined: false,
  }));
}

async function modelOptions(req: Request): Promise<JsonObject> {
  const agent = selectedAgent(req);
  const adapter = getAdapter(agent);
  const models = await adapter.getModels();
  const providers = modelGroupsToProviders(models.groups);
  const options = models.groups.flatMap((group) =>
    group.models.map((model) => ({
      id: model.id,
      label: model.label || model.id,
      provider: model.provider ?? group.provider,
      source: model.source,
      is_current_default: Boolean(model.isCurrentDefault),
    }))
  );
  return {
    default_model: models.defaultModel,
    active_provider: models.activeProvider,
    providers,
    options,
  };
}

async function profiles(req: Request): Promise<JsonObject[]> {
  const agent = selectedAgent(req);
  const adapter = getAdapter(agent);
  const defaults = await adapter.getDefaults();
  const skillCount = listSkillsFromDisk().length;
  return [
    {
      name: 'default',
      path: resolveHermesHome(),
      is_default: true,
      has_env: true,
      provider: defaults.provider,
      model: defaults.model,
      skill_count: skillCount,
      description: defaults.model ? `${skillCount} skills · ${defaults.model}` : `${skillCount} skills`,
    },
  ];
}

function profileToAssistant(profile: JsonObject): JsonObject {
  const name = String(profile.name || 'default');
  const model = typeof profile.model === 'string' ? profile.model : null;
  const description = typeof profile.description === 'string' ? profile.description : '';
  return {
    id: name,
    source: 'builtin',
    name,
    name_i18n: {},
    description,
    description_i18n: {},
    enabled: true,
    sort_order: profile.is_default ? 0 : 100,
    preset_agent_type: 'aionrs',
    enabled_skills: [],
    custom_skill_names: [],
    disabled_builtin_skills: [],
    context_i18n: {},
    prompts: [],
    prompts_i18n: {},
    models: model ? [model] : [],
  };
}

function profileToAssistantDetail(profile: JsonObject): JsonObject {
  const assistant = profileToAssistant(profile);
  return {
    id: assistant.id,
    source: 'builtin',
    profile: {
      name: assistant.name,
      name_i18n: {},
      description: assistant.description,
      description_i18n: {},
    },
    state: { enabled: true, sort_order: assistant.sort_order },
    engine: { agent_backend: 'aionrs' },
    rules: { content: '', storage_mode: 'profile' },
    prompts: { recommended: [], recommended_i18n: {} },
    defaults: {
      model:
        Array.isArray(assistant.models) && assistant.models[0]
          ? { mode: 'fixed', value: assistant.models[0] }
          : { mode: 'auto' },
      permission: { mode: 'auto' },
      skills: { mode: 'auto', value: [] },
      mcps: { mode: 'auto', value: [] },
    },
    capabilities: {
      default_skill_ids: [],
      custom_skill_names: [],
      default_disabled_builtin_skill_ids: [],
    },
    preferences: {
      last_model_id: Array.isArray(assistant.models) ? assistant.models[0] : undefined,
      last_skill_ids: [],
      last_disabled_builtin_skill_ids: [],
      last_mcp_ids: [],
    },
  };
}

function parseSkillFile(path: string, source: 'builtin' | 'custom'): JsonObject | null {
  try {
    const content = readFileSync(path, 'utf8');
    const name =
      /^name:\s*(.+)$/m.exec(content)?.[1]?.trim() ||
      /^#\s+(.+)$/m.exec(content)?.[1]?.trim() ||
      basename(dirname(path));
    const description = /^description:\s*\|?\s*(.+)$/m.exec(content)?.[1]?.trim() || '';
    return {
      name,
      description,
      location: path,
      relative_location: path,
      is_custom: source === 'custom',
      source,
      category: basename(dirname(dirname(path))) || 'general',
      enabled: true,
    };
  } catch {
    return null;
  }
}

function walkSkillFiles(root: string, source: 'builtin' | 'custom', limit = 200): JsonObject[] {
  if (!existsSync(root)) return [];
  const found: JsonObject[] = [];
  const stack = [root];
  while (stack.length && found.length < limit) {
    const current = stack.pop() as string;
    let entries: string[];
    try {
      entries = readdirSync(current);
    } catch {
      continue;
    }
    for (const entry of entries) {
      const path = join(current, entry);
      let stats;
      try {
        stats = statSync(path);
      } catch {
        continue;
      }
      if (stats.isDirectory()) {
        stack.push(path);
      } else if (entry === 'SKILL.md') {
        const skill = parseSkillFile(path, source);
        if (skill) found.push(skill);
      }
    }
  }
  return found;
}

function listSkillsFromDisk(): JsonObject[] {
  const roots = [
    { path: join(resolveHermesHome(), 'skills'), source: 'custom' as const },
    { path: join(expandHomePrefix(process.env.HERMES_AGENT_DIR || ''), 'skills'), source: 'builtin' as const },
    {
      path: join(expandHomePrefix(process.env.HERMES_AGENT_DIR || ''), '.agents', 'skills'),
      source: 'builtin' as const,
    },
  ].filter((root) => root.path && root.path !== 'skills');
  const byName = new Map<string, JsonObject>();
  for (const root of roots) {
    for (const skill of walkSkillFiles(root.path, root.source)) {
      byName.set(String(skill.name), skill);
    }
  }
  return [...byName.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
}

function createHermesAgent(options: JsonObject): JsonObject {
  return {
    id: 'hermes',
    name: 'Headmaster Runtime',
    description: 'Container runtime agent',
    backend: 'hermes',
    agent_type: 'aionrs',
    agent_source: 'builtin',
    enabled: true,
    available: true,
    team_capable: false,
    handshake: {
      agent_capabilities: {
        load_session: true,
        mcp_capabilities: { stdio: true, http: true, sse: true },
      },
      available_models: options.options ?? [],
      available_modes: {
        current_mode_id: 'default',
        modes: [{ id: 'default', name: 'Default' }],
      },
      available_commands: [{ name: '/help', description: 'Show runtime help' }],
    },
  };
}

function convertMessage(message: HermesMessage, sessionId: string): JsonObject {
  return {
    id: message.id,
    session_id: sessionId,
    role: message.role,
    content: message.content,
    text: message.content,
    reasoning: message.thinking,
    timestamp: message.created_at,
  };
}

apiRouter.get('/status', async (req, res, next) => {
  try {
    const agent = selectedAgent(req);
    const healthy = await getAdapter(agent).healthCheck();
    res.json({ ok: true, status: healthy ? 'ready' : 'unhealthy', agent, healthy });
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/sessions', async (req, res, next) => {
  let agent: AgentType | undefined;
  try {
    agent = selectedAgent(req);
    const limit = numberQuery(req.query.limit, 100);
    const offset = numberQuery(req.query.offset, 0);
    const all = await getAdapter(agent).listSessions();
    const sessions = all.slice(offset, offset + limit);
    res.json({ limit, offset, total: all.length, sessions });
  } catch (error) {
    next(gatewayErrorFromWorker(error, 'Could not list sessions', agent));
  }
});

apiRouter.get('/sessions/:id/messages', async (req, res, next) => {
  let agent: AgentType | undefined;
  try {
    agent = selectedAgent(req);
    const messages = await getAdapter(agent).getMessages(req.params.id);
    res.json({
      session_id: req.params.id,
      messages: messages.map((message) => convertMessage(message, req.params.id)),
    });
  } catch (error) {
    next(gatewayErrorFromWorker(error, 'Could not load session messages', agent));
  }
});

apiRouter.get('/sessions/:id', async (req, res, next) => {
  let agent: AgentType | undefined;
  try {
    agent = selectedAgent(req);
    const adapter = getAdapter(agent);
    const metadata = await adapter.getSessionMetadata(req.params.id);
    if (metadata) {
      res.json({
        ...metadata,
        ended_at: null,
        is_active: false,
        last_active: Date.now(),
        message_count: 0,
        preview: null,
        source: 'headmaster',
        started_at: Date.now(),
        title: null,
        tool_call_count: 0,
      });
      return;
    }
    res.status(404).json({ error: { code: 'not_found', message: 'Session not found.' } });
  } catch (error) {
    next(gatewayErrorFromWorker(error, 'Could not load session', agent));
  }
});

apiRouter.patch('/sessions/:id', async (req, res, next) => {
  let agent: AgentType | undefined;
  try {
    agent = selectedAgent(req);
    const title = (req.body as { title?: unknown } | undefined)?.title;
    if (typeof title !== 'string' || !title.trim()) throw validationError('title is required.', 'title');
    const renamed = await getAdapter(agent).renameSession?.(req.params.id, title);
    res.json({ ok: Boolean(renamed), renamed: Boolean(renamed) });
  } catch (error) {
    next(gatewayErrorFromWorker(error, 'Could not rename session', agent));
  }
});

apiRouter.delete('/sessions/:id', async (req, res, next) => {
  let agent: AgentType | undefined;
  try {
    agent = selectedAgent(req);
    const deleted = await getAdapter(agent).deleteSession(req.params.id);
    res.json({ ok: deleted, deleted });
  } catch (error) {
    next(gatewayErrorFromWorker(error, 'Could not delete session', agent));
  }
});

apiRouter.get('/model/options', async (req, res, next) => {
  try {
    res.json(await modelOptions(req));
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/providers', async (req, res, next) => {
  try {
    res.json((await modelOptions(req)).providers ?? []);
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/providers/oauth', async (req, res, next) => {
  try {
    res.json({ providers: (await modelOptions(req)).providers ?? [] });
  } catch (error) {
    next(error);
  }
});

apiRouter.post('/providers/validate', async (req, res, next) => {
  try {
    const options = await modelOptions(req);
    const requested = String((req.body as JsonObject | undefined)?.id || '').trim();
    const provider = ((options.providers as JsonObject[] | undefined) ?? []).find(
      (item) => !requested || item.slug === requested || item.name === requested
    );
    res.json({
      ok: true,
      valid: true,
      models: Array.isArray(provider?.models)
        ? provider.models
        : (options.options as JsonObject[]).map((item) => item.id),
    });
  } catch (error) {
    next(error);
  }
});

apiRouter.post(
  '/providers/:id/models',
  async (req, res, next) => {
    req.body = { ...(req.body as JsonObject | undefined), id: req.params.id };
    next();
  },
  async (req, res, next) => {
    try {
      const options = await modelOptions(req);
      const provider = ((options.providers as JsonObject[] | undefined) ?? []).find(
        (item) => item.slug === req.params.id || item.name === req.params.id
      );
      res.json({
        models: Array.isArray(provider?.models) ? provider.models : [],
      });
    } catch (error) {
      next(error);
    }
  }
);

apiRouter.post('/providers/detect-protocol', (_req, res) => {
  res.json({ protocol: 'openai-compatible', confidence: 1 });
});

apiRouter.get('/profiles', async (req, res, next) => {
  try {
    res.json({ profiles: await profiles(req) });
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/profiles/:name', async (req, res, next) => {
  try {
    const profile = (await profiles(req)).find((item) => item.name === req.params.name);
    if (!profile) {
      res.status(404).json({ error: { code: 'not_found', message: 'Profile not found.' } });
      return;
    }
    res.json(profile);
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/assistants', async (req, res, next) => {
  try {
    res.json((await profiles(req)).map(profileToAssistant));
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/assistants/:id', async (req, res, next) => {
  try {
    const profile = (await profiles(req)).find((item) => item.name === req.params.id);
    if (!profile) {
      res.status(404).json({ error: { code: 'not_found', message: 'Assistant not found.' } });
      return;
    }
    res.json(profileToAssistantDetail(profile));
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/agents', async (req, res, next) => {
  try {
    res.json([createHermesAgent(await modelOptions(req))]);
  } catch (error) {
    next(error);
  }
});

apiRouter.post('/agents/refresh', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.get('/skills', (_req, res) => {
  res.json({ skills: listSkillsFromDisk() });
});

apiRouter.get('/skills/builtin-auto', (_req, res) => {
  res.json({
    name: 'builtin-auto',
    description: 'Built-in automatic runtime skills',
    location: 'builtin-auto',
    relative_location: 'builtin-auto',
    is_custom: false,
    source: 'builtin',
    category: 'general',
    enabled: true,
  });
});

apiRouter.put('/skills/toggle', (req, res) => {
  res.json({
    ok: true,
    name: (req.body as { name?: unknown } | undefined)?.name,
    enabled: (req.body as { enabled?: unknown } | undefined)?.enabled !== false,
  });
});

apiRouter.get('/mcp/servers', async (_req, res, next) => {
  try {
    res.json({ servers: await listMcpServers() });
  } catch (err) { next(err); }
});

apiRouter.post('/mcp/servers', async (req, res, next) => {
  try {
    const body = (req.body ?? {}) as JsonObject;
    const name = String(body.name || body.id || '').trim();
    if (!name) throw validationError('name is required.', 'name');
    // The desktop sends a transport: { type, url, headers? } shape. Extract the
    // Hermes config.yaml entry fields from it.
    const transport = body.transport as { url?: string; headers?: Record<string, string>; type?: string } | undefined;
    const url = String(body.url || transport?.url || '').trim();
    if (!url) throw validationError('url is required (body.url or body.transport.url).', 'url');
    const entry: HermesMcpServerEntry = {
      url,
      enabled: body.enabled !== false,
      ...(transport?.headers || body.headers ? { headers: (transport?.headers || body.headers) as Record<string, string> } : {}),
      ...(transport?.type && transport.type !== 'http' ? { transport: transport.type } : {}),
    };
    const server = await upsertMcpServer(name, entry);
    res.json(server);
  } catch (err) { next(err); }
});

// TODO: /mcp/servers/import still uses the old api-compat.json store. Migrate
// to mcpConfigStore if the desktop's import flow is ever exercised.
apiRouter.post('/mcp/servers/import', (req, res) => {
  const incoming = Array.isArray((req.body as { servers?: unknown } | undefined)?.servers)
    ? (req.body as { servers: JsonObject[] }).servers
    : [];
  const store = readStore();
  const imported = incoming.map((item) => ({
    id: String(item.name || item.id),
    enabled: true,
    builtin: false,
    ...item,
  }));
  store.mcpServers = [...store.mcpServers, ...imported];
  writeStore(store);
  res.json(imported);
});

apiRouter.put('/mcp/servers/:id', async (req, res, next) => {
  try {
    const existing = await getMcpServer(req.params.id);
    if (!existing) {
      res.status(404).json({ error: { code: 'not_found', message: 'MCP server not found.' } });
      return;
    }
    const body = (req.body ?? {}) as JsonObject;
    const transport = body.transport as { url?: string; headers?: Record<string, string>; type?: string } | undefined;
    const url = String(body.url || transport?.url || existing.transport.url).trim();
    const entry: HermesMcpServerEntry = {
      url,
      enabled: body.enabled !== undefined ? Boolean(body.enabled) : existing.enabled,
      ...(transport?.headers || body.headers || existing.transport.headers ? { headers: ((transport?.headers || body.headers || existing.transport.headers) as Record<string, string>) } : {}),
      ...(transport?.type && transport.type !== 'http' ? { transport: transport.type } : {}),
    };
    const server = await upsertMcpServer(req.params.id, entry);
    res.json(server);
  } catch (err) { next(err); }
});

apiRouter.post('/mcp/servers/:id/toggle', async (req, res, next) => {
  try {
    const server = await toggleMcpServer(req.params.id);
    if (!server) {
      res.status(404).json({ error: { code: 'not_found', message: 'MCP server not found.' } });
      return;
    }
    res.json(server);
  } catch (err) { next(err); }
});

apiRouter.delete('/mcp/servers/:id', async (req, res, next) => {
  try {
    await removeMcpServer(req.params.id);
    res.status(204).end();
  } catch (err) { next(err); }
});

apiRouter.post('/mcp/test-connection', (_req, res) => {
  res.json({ ok: true, success: true });
});

apiRouter.get('/mcp/catalog', (_req, res) => {
  res.json({ items: [], servers: [] });
});

apiRouter.post('/mcp/catalog/install', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.get('/messaging/platforms', (_req, res) => {
  res.json({ platforms: [] });
});

apiRouter.put('/messaging/platforms/:id', (req, res) => {
  res.json({ id: req.params.id, enabled: (req.body as { enabled?: unknown } | undefined)?.enabled === true });
});

apiRouter.get('/webhooks', (_req, res) => {
  res.json({ webhooks: [] });
});

apiRouter.get('/memory', (_req, res) => {
  res.json({ enabled: false, provider: null, providers: [] });
});

apiRouter.put('/memory/provider', (req, res) => {
  res.json({ ok: true, provider: (req.body as { provider?: unknown } | undefined)?.provider ?? null });
});

apiRouter.post('/memory/reset', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.get('/tools/toolsets', (_req, res) => {
  res.json([]);
});

apiRouter.get('/tools/toolsets/:name/config', (req, res) => {
  res.json({ name: req.params.name, config: {} });
});

apiRouter.put('/tools/toolsets/:name', (req, res) => {
  res.json({
    ok: true,
    name: req.params.name,
    enabled: (req.body as { enabled?: unknown } | undefined)?.enabled === true,
  });
});

apiRouter.put('/tools/toolsets/:name/provider', (req, res) => {
  res.json({ ok: true, name: req.params.name, provider: (req.body as JsonObject | undefined)?.provider ?? null });
});

apiRouter.get('/cron/jobs', (req, res) => {
  const conversationId = typeof req.query.conversation_id === 'string' ? req.query.conversation_id : null;
  const jobs = conversationId
    ? readStore().cronJobs.filter((job) => job.conversation_id === conversationId)
    : readStore().cronJobs;
  // ipcBridge.ts's cronManage.listJobs/listJobsByConversation expect a raw
  // ICronJob[] from GET /api/cron/jobs, not an { jobs } envelope — wrapping it
  // broke `.map()` on the desktop client (see cronManage.listJobs in
  // headmasterUI's ipcBridge.ts).
  res.json(jobs);
});

apiRouter.post('/cron/jobs', (req, res) => {
  const store = readStore();
  const id = `job_${Date.now().toString(36)}`;
  const job = { id, job_id: id, enabled: true, created_at: Date.now(), ...(req.body as JsonObject) };
  store.cronJobs.push(job);
  writeStore(store);
  res.json(job);
});

apiRouter.get('/cron/jobs/:id', (req, res) => {
  res.json(readStore().cronJobs.find((job) => job.id === req.params.id || job.job_id === req.params.id) ?? null);
});

apiRouter.put('/cron/jobs/:id', (req, res) => {
  const store = readStore();
  const index = store.cronJobs.findIndex((job) => job.id === req.params.id || job.job_id === req.params.id);
  if (index < 0) {
    res.status(404).json({ error: { code: 'not_found', message: 'Cron job not found.' } });
    return;
  }
  store.cronJobs[index] = { ...store.cronJobs[index], ...(req.body as JsonObject) };
  writeStore(store);
  res.json(store.cronJobs[index]);
});

apiRouter.delete('/cron/jobs/:id', (req, res) => {
  const store = readStore();
  store.cronJobs = store.cronJobs.filter((job) => job.id !== req.params.id && job.job_id !== req.params.id);
  writeStore(store);
  res.status(204).end();
});

apiRouter.post('/cron/jobs/:id/run', (req, res) => {
  res.json({ conversation_id: String((req.body as JsonObject | undefined)?.conversation_id || req.params.id) });
});

apiRouter.get('/cron/jobs/:id/skill', (_req, res) => {
  res.json({ has_skill: false });
});

apiRouter.put('/cron/jobs/:id/skill', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.delete('/cron/jobs/:id/skill', (_req, res) => {
  res.status(204).end();
});

apiRouter.get('/config', async (req, res, next) => {
  try {
    res.json(await getAdapter(selectedAgent(req)).getDefaults());
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/config/defaults', async (req, res, next) => {
  try {
    res.json(await getAdapter(selectedAgent(req)).getDefaults());
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/config/schema', (_req, res) => {
  res.json({
    category_order: ['model', 'runtime'],
    fields: {
      'model.provider': { type: 'string', category: 'model', description: 'Model provider' },
      'model.default': { type: 'string', category: 'model', description: 'Default model' },
      'runtime.show_reasoning': { type: 'boolean', category: 'runtime', description: 'Show reasoning' },
    },
  });
});

apiRouter.put('/config', async (req, res, next) => {
  try {
    const body = (req.body ?? {}) as JsonObject;
    const adapter = getAdapter(selectedAgent(req));
    const defaults = await adapter.getDefaults();
    res.json({ ...defaults, ...body });
  } catch (error) {
    next(error);
  }
});

apiRouter.put('/config/env', (req, res) => {
  res.json({ ok: true, key: (req.body as { key?: unknown } | undefined)?.key ?? null });
});

apiRouter.get('/conversations/:id/artifacts', async (req, res, next) => {
  try {
    const messages = await getAdapter(selectedAgent(req)).getMessages(req.params.id);
    const artifacts = messages
      .filter((message) => /\b(file|artifact|saved|created|wrote)\b/i.test(message.content))
      .map((message) => ({
        id: message.id,
        conversation_id: req.params.id,
        content: message.content,
        created_at: message.created_at,
      }));
    // ipcBridge.ts's chatApi.listArtifacts expects a raw IConversationArtifact[],
    // not an { artifacts } envelope.
    res.json(artifacts);
  } catch (error) {
    next(error);
  }
});

apiRouter.get('/conversations/:id/confirmations', (_req, res) => {
  // ipcBridge.ts's getConfirmations expects a raw IConfirmation<unknown>[],
  // not a { confirmations } envelope.
  res.json([]);
});

apiRouter.get('/conversations/:id/mode', (req, res) => {
  res.json(readStore().conversationModes[req.params.id] ?? { mode: 'default', initialized: false });
});

apiRouter.put('/conversations/:id/mode', (req, res) => {
  const mode = String((req.body as { mode?: unknown } | undefined)?.mode || 'default');
  const store = readStore();
  const value = { mode, initialized: true };
  store.conversationModes[req.params.id] = value;
  writeStore(store);
  res.json(value);
});

apiRouter.get('/conversations/:id/slash-commands', (_req, res) => {
  // ipcBridge.ts's chatApi.getSlashCommands expects a raw AcpSlashCommandApiItem[]
  // (each item keyed by `command`, not `name`) — not a { commands } envelope.
  // Getting this wrong throws inside acpMapping's spread/`.map` and takes down
  // the whole renderer via AppErrorBoundary.
  res.json([
    { command: '/help', description: 'Show available runtime commands' },
    { command: '/clear', description: 'Start a fresh context' },
  ]);
});

apiRouter.get('/extensions', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/themes', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/assistants', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/agents', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/acp-adapters', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/mcp-servers', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/skills', (_req, res) => {
  res.json(listSkillsFromDisk());
});

apiRouter.get('/extensions/settings-tabs', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/webui', (_req, res) => {
  res.json([]);
});

apiRouter.get('/extensions/agent-activity', (_req, res) => {
  res.json({
    generatedAt: Date.now(),
    totalConversations: 0,
    runningConversations: 0,
    agents: [],
  });
});

apiRouter.post('/extensions/i18n', (_req, res) => {
  res.json({});
});

apiRouter.post('/extensions/enable', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.post('/extensions/disable', (_req, res) => {
  res.json({ ok: true });
});

apiRouter.post('/extensions/permissions', (_req, res) => {
  res.json([]);
});

apiRouter.post('/extensions/risk-level', (_req, res) => {
  res.json('safe');
});

apiRouter.get('/google/subscription-status', (_req, res) => {
  res.json({ isSubscriber: false, lastChecked: Date.now() });
});

apiRouter.get('/google/auth-status', (_req, res) => {
  res.json({ success: false, msg: 'Google auth is not configured on this runtime.' });
});
