import { existsSync, readFileSync, writeFileSync, mkdirSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { parse, stringify } from 'yaml';
import { resolveHermesHome } from './paths.js';

/**
 * Read-modify-write store for the `mcp_servers` key in $HERMES_HOME/config.yaml.
 *
 * Hermes loads MCP servers from this key (tools/mcp_tool.py). The HTTP transport
 * entry shape is: { url: string, headers?: Record<string,string>, enabled?: boolean,
 * transport?: 'sse'|'http'|'streamable_http', timeout?: number }.
 *
 * The desktop IMcpServer contract (ipcBridge.ts → storage.ts:609) expects an array
 * of { id, name, enabled, transport: { type, url, headers? }, ... }. We convert
 * between the YAML dict (keyed by name) and the array shape at the boundary.
 */

export interface HermesMcpServerEntry {
  url: string;
  headers?: Record<string, string>;
  enabled?: boolean;
  transport?: string;
  timeout?: number;
  [key: string]: unknown;
}

export interface DesktopMcpServer {
  id: string;
  name: string;
  description?: string;
  enabled: boolean;
  transport: {
    type: 'http' | 'sse' | 'streamable_http';
    url: string;
    headers?: Record<string, string>;
  };
  builtin?: boolean;
  original_json?: string;
  created_at?: number;
  updated_at?: number;
  [key: string]: unknown;
}

function configPath(): string {
  return join(resolveHermesHome(), 'config.yaml');
}

function readConfigFile(): Record<string, unknown> {
  const path = configPath();
  if (!existsSync(path)) return {};
  try {
    const raw = readFileSync(path, 'utf8');
    const parsed = parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function writeConfigFile(config: Record<string, unknown>): void {
  const path = configPath();
  mkdirSync(resolveHermesHome(), { recursive: true });
  // Atomic write: write to temp then rename. Hermes' own save_config uses
  // atomic_replace too — we mirror that to avoid a half-written file if the
  // worker reads mid-write.
  const tmp = `${path}.tmp.${process.pid}`;
  writeFileSync(tmp, stringify(config), 'utf8');
  renameSync(tmp, path);
}

function getServersDict(config: Record<string, unknown>): Record<string, HermesMcpServerEntry> {
  const servers = config['mcp_servers'];
  if (!servers || typeof servers !== 'object' || Array.isArray(servers)) return {};
  return servers as Record<string, HermesMcpServerEntry>;
}

function entryToDesktop(name: string, entry: HermesMcpServerEntry): DesktopMcpServer {
  const transportType = entry.transport === 'sse'
    ? 'sse'
    : entry.transport === 'streamable_http'
      ? 'streamable_http'
      : 'http';
  return {
    id: name,
    name,
    enabled: entry.enabled !== false,
    transport: {
      type: transportType,
      url: entry.url,
      ...(entry.headers ? { headers: entry.headers } : {}),
    },
    original_json: JSON.stringify(entry),
    builtin: false,
  };
}

export async function listMcpServers(): Promise<DesktopMcpServer[]> {
  const config = readConfigFile();
  const dict = getServersDict(config);
  return Object.entries(dict).map(([name, entry]) => entryToDesktop(name, entry));
}

export async function upsertMcpServer(name: string, entry: HermesMcpServerEntry): Promise<DesktopMcpServer> {
  const config = readConfigFile();
  const dict = getServersDict(config);
  dict[name] = entry;
  config['mcp_servers'] = dict;
  writeConfigFile(config);
  return entryToDesktop(name, entry);
}

export async function removeMcpServer(name: string): Promise<boolean> {
  const config = readConfigFile();
  const dict = getServersDict(config);
  if (!(name in dict)) return false;
  delete dict[name];
  if (Object.keys(dict).length === 0) {
    delete config['mcp_servers'];
  } else {
    config['mcp_servers'] = dict;
  }
  writeConfigFile(config);
  return true;
}

export async function toggleMcpServer(name: string): Promise<DesktopMcpServer | null> {
  const config = readConfigFile();
  const dict = getServersDict(config);
  if (!(name in dict)) return null;
  dict[name].enabled = dict[name].enabled === false; // flip
  config['mcp_servers'] = dict;
  writeConfigFile(config);
  return entryToDesktop(name, dict[name]);
}

export async function getMcpServer(name: string): Promise<DesktopMcpServer | null> {
  const config = readConfigFile();
  const dict = getServersDict(config);
  if (!(name in dict)) return null;
  return entryToDesktop(name, dict[name]);
}