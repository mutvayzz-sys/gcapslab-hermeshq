import { useEffect, useState } from "react";

import { useAuditLogs } from "../api/audit";
import { useI18n } from "../lib/i18n";
import { useSessionStore } from "../stores/sessionStore";

const ACTION_LABELS: Record<string, string> = {
  "agent.create": "Agent created",
  "agent.update": "Agent updated",
  "agent.archive": "Agent archived",
  "agent.permanent_delete": "Agent permanently deleted",
  "settings.update": "Settings updated",
  "user.create": "User created",
  "user.update": "User updated",
  "user.delete": "User deleted",
  "mfa.toggle": "MFA toggled",
};

const TARGET_ICONS: Record<string, string> = {
  agent: "🤖",
  settings: "⚙️",
  user: "👤",
  mfa: "🔐",
};

function formatTimeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

function formatChanges(oldVal: Record<string, unknown> | null, newVal: Record<string, unknown> | null): string {
  if (!newVal) return "";
  const changes: string[] = [];
  for (const key of Object.keys(newVal)) {
    const old = oldVal?.[key];
    const nw = newVal[key];
    if (old !== nw) {
      changes.push(key);
    }
  }
  return changes.join(", ");
}

export function AuditPage() {
  const currentUser = useSessionStore((state) => state.user);
  const isAdmin = currentUser?.role === "admin";
  const { t } = useI18n();

  const [search, setSearch] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterTarget, setFilterTarget] = useState("");
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [history, setHistory] = useState<string[]>([]);

  const { data, isLoading } = useAuditLogs({
    action: filterAction || undefined,
    target_type: filterTarget || undefined,
    search: search || undefined,
    cursor,
    limit: 50,
  });

  useEffect(() => {
    setCursor(undefined);
    setHistory([]);
  }, [search, filterAction, filterTarget]);

  if (!isAdmin) {
    return (
      <section className="panel-frame p-6">
        <p className="text-sm text-[var(--text-secondary)]">{t("audit.adminOnly")}</p>
      </section>
    );
  }

  const entries = data?.items ?? [];

  return (
    <div className="grid gap-6">
      {/* Header */}
      <section className="panel-frame p-6">
        <p className="panel-label">{t("audit.label")}</p>
        <h2 className="mt-2 text-3xl text-[var(--text-display)]">{t("audit.title")}</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
          {t("audit.description")}
        </p>
      </section>

      {/* Filters */}
      <section className="panel-frame p-6">
        <div className="grid gap-4 md:grid-cols-[1fr_auto_auto_auto]">
          <label className="panel-field">
            <span className="panel-label">{t("audit.search")}</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("audit.searchPlaceholder")}
            />
          </label>
          <label className="panel-field">
            <span className="panel-label">{t("audit.action")}</span>
            <select value={filterAction} onChange={(e) => setFilterAction(e.target.value)}>
              <option value="">{t("audit.allActions")}</option>
              {Object.entries(ACTION_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </label>
          <label className="panel-field">
            <span className="panel-label">{t("audit.targetType")}</span>
            <select value={filterTarget} onChange={(e) => setFilterTarget(e.target.value)}>
              <option value="">{t("audit.allTargets")}</option>
              <option value="agent">Agent</option>
              <option value="settings">Settings</option>
              <option value="user">User</option>
            </select>
          </label>
          <div className="flex items-end">
            <span className="panel-label">
              {data ? t("audit.totalEntries", { count: data.total }) : "..."}
            </span>
          </div>
        </div>
      </section>

      {/* Log entries */}
      <section className="panel-frame p-6">
        {isLoading ? (
          <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">{t("audit.noEntries")}</p>
        ) : (
          <div className="space-y-0">
            {entries.map((entry) => (
              <article
                key={entry.id}
                className="grid gap-3 border-b border-[var(--border)] py-4 last:border-b-0 md:grid-cols-[auto_1fr_auto]"
              >
                <div className="flex items-center gap-3">
                  <span className="text-lg">{TARGET_ICONS[entry.target_type] ?? "📋"}</span>
                  <div>
                    <p className="text-sm font-medium text-[var(--text-display)]">
                      {ACTION_LABELS[entry.action] ?? entry.action}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {entry.target_type}
                      {entry.target_name ? `: ${entry.target_name}` : ""}
                      {entry.target_id ? (
                        <span className="ml-2 font-mono text-[var(--text-disabled)]">
                          {entry.target_id.slice(0, 8)}…
                        </span>
                      ) : null}
                    </p>
                  </div>
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-[var(--text-secondary)]">
                    {entry.actor_username ?? t("audit.system")}
                    {entry.actor_role ? (
                      <span className="ml-2 text-xs uppercase tracking-[0.1em] text-[var(--text-disabled)]">
                        {entry.actor_role}
                      </span>
                    ) : null}
                  </p>
                  {(entry.old_value || entry.new_value) && (
                    <p className="mt-1 text-xs font-mono text-[var(--text-disabled)] truncate">
                      {formatChanges(entry.old_value, entry.new_value)}
                    </p>
                  )}
                  {entry.ip_address && (
                    <p className="mt-1 text-xs font-mono text-[var(--text-disabled)]">
                      IP: {entry.ip_address}
                    </p>
                  )}
                </div>
                <div className="flex items-start">
                  <span className="text-xs text-[var(--text-disabled)] whitespace-nowrap">
                    {formatTimeAgo(entry.created_at)}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}

        {/* Pagination */}
        {data?.has_more && (
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              className="panel-button-secondary"
              onClick={() => {
                if (entries.length > 0) {
                  setHistory((prev) => [...prev, cursor ?? ""]);
                  setCursor(entries[entries.length - 1].id);
                }
              }}
            >
              {t("audit.loadMore")}
            </button>
          </div>
        )}
        {history.length > 0 && (
          <div className="mt-3 flex justify-center">
            <button
              type="button"
              className="panel-button-secondary text-xs"
              onClick={() => {
                const prev = history[history.length - 1];
                setHistory((h) => h.slice(0, -1));
                setCursor(prev || undefined);
              }}
            >
              {t("audit.goBack")}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
