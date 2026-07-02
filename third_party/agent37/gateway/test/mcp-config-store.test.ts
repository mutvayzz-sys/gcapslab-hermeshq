import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

let tempHome: string;

before(() => {
  tempHome = mkdtempSync(join(tmpdir(), 'mcp-config-test-'));
  process.env.HERMES_HOME = tempHome;
});

after(() => {
  delete process.env.HERMES_HOME;
});

test('listMcpServers returns empty when no config.yaml exists', async () => {
  const { listMcpServers } = await import('../server/mcpConfigStore.js');
  const servers = await listMcpServers();
  assert.equal(servers.length, 0);
});

test('upsertMcpServer writes to config.yaml mcp_servers key', async () => {
  const { upsertMcpServer, listMcpServers } = await import('../server/mcpConfigStore.js');
  await upsertMcpServer('composio-gmail', {
    url: 'https://backend.composio.dev/v3/mcp/server1?user_id=u1',
    enabled: true,
    headers: { Authorization: 'Bearer test-token' },
  });
  const servers = await listMcpServers();
  assert.equal(servers.length, 1);
  assert.equal(servers[0].name, 'composio-gmail');
  assert.equal(servers[0].transport.type, 'http');
  assert.equal(servers[0].transport.url, 'https://backend.composio.dev/v3/mcp/server1?user_id=u1');
  assert.equal(servers[0].enabled, true);
});

test('upsertMcpServer preserves other config.yaml keys', async () => {
  const configPath = join(tempHome, 'config.yaml');
  writeFileSync(configPath, 'model:\n  default: kimi-k2.7-code\n  provider: kimi-coding\nmcp_servers:\n  existing:\n    url: "https://old.example.com"\n    enabled: false\n');
  const { upsertMcpServer, listMcpServers } = await import('../server/mcpConfigStore.js');
  await upsertMcpServer('new-server', { url: 'https://new.example.com', enabled: true });
  const raw = readFileSync(configPath, 'utf8');
  assert.ok(raw.includes('kimi-k2.7-code'), 'model config preserved');
  assert.ok(raw.includes('old.example.com'), 'existing mcp server preserved');
  assert.ok(raw.includes('new.example.com'), 'new server written');
  const servers = await listMcpServers();
  assert.equal(servers.length, 2);
});

test('removeMcpServer removes only the named server', async () => {
  const { removeMcpServer, listMcpServers } = await import('../server/mcpConfigStore.js');
  await removeMcpServer('new-server');
  const servers = await listMcpServers();
  assert.equal(servers.length, 1);
  assert.equal(servers[0].name, 'existing');
});

test('toggleMcpServer flips enabled', async () => {
  const { toggleMcpServer, listMcpServers } = await import('../server/mcpConfigStore.js');
  await toggleMcpServer('existing');
  const servers = await listMcpServers();
  assert.equal(servers[0].enabled, true);
});