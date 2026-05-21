import { useState } from "react";
import {
  useResourceStatus,
  useUpdateSemaphore,
  useGenerateOverride,
} from "../../api/settings";
import { useAgents } from "../../api/agents";
import { useI18n } from "../../lib/i18n";

function formatMb(mb: number | null | undefined): string {
  if (mb == null) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${Math.round(mb)} MB`;
}

function formatPct(pct: number | null | undefined): string {
  if (pct == null) return "—";
  return `${pct.toFixed(1)}%`;
}

export default function ResourcesTab() {
  const { t } = useI18n();
  const { data: resourceStatus, isLoading: loadingStatus } = useResourceStatus();
  const { data: agentsData } = useAgents();
  const updateSemaphore = useUpdateSemaphore();
  const generateOverride = useGenerateOverride();

  const [semaphoreInput, setSemaphoreInput] = useState("");
  const [plannedAgents, setPlannedAgents] = useState("");
  const [overrideContent, setOverrideContent] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const registeredAgents = agentsData?.length ?? 0;

  const handleApplySemaphore = () => {
    const value = parseInt(semaphoreInput, 10);
    if (isNaN(value) || value < 1 || value > 200) return;
    setSuccessMessage(null);
    updateSemaphore.mutate(value, {
      onSuccess: (data) => {
        setSuccessMessage(t("settings.semaphoreUpdated", { value: data.semaphore }));
        setSemaphoreInput("");
      },
    });
  };

  const handleEstimate = () => {
    const agents = parseInt(plannedAgents, 10);
    if (isNaN(agents) || agents < 1) return;
    generateOverride.mutate(agents, {
      onSuccess: (data) => {
        setOverrideContent(data.content);
      },
    });
  };

  const handleDownloadOverride = () => {
    if (!overrideContent) return;
    const blob = new Blob([overrideContent], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "docker-compose.override.yml";
    a.click();
    URL.revokeObjectURL(url);
  };

  const sem = resourceStatus?.semaphore;
  const container = resourceStatus?.container;
  const system = resourceStatus?.system;

  const estimatedOverride = generateOverride.data;

  if (loadingStatus) {
    return <div className="panel-frame p-6 text-sm text-[var(--text-secondary)]">Loading resources…</div>;
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Concurrency ────────────────────────────────── */}
      <section className="panel-frame p-6">
        <h3 className="text-lg font-semibold text-[var(--text-display)]">{t("settings.concurrency")}</h3>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("settings.semaphoreDescription")}</p>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              {t("settings.maxConcurrentTasks")}
            </label>
            <input
              type="number"
              min={1}
              max={200}
              value={semaphoreInput}
              onChange={(e) => setSemaphoreInput(e.target.value)}
              placeholder={sem ? String(sem.current) : "8"}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text-display)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={handleApplySemaphore}
            disabled={updateSemaphore.isPending || !semaphoreInput}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {updateSemaphore.isPending ? "…" : t("settings.semaphoreApply")}
          </button>
        </div>

        {sem && (
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-[var(--text-secondary)]">
            <span>
              {t("settings.resourceCurrent")}: <strong className="text-[var(--text-display)]">{sem.current}</strong>
            </span>
            <span>
              {t("settings.activeTasks")}:{" "}
              <strong className="text-[var(--text-display)]">
                {sem.active_tasks}/{sem.max_tasks}
              </strong>{" "}
              ({sem.utilization_pct}%)
            </span>
            {registeredAgents > 0 && (
              <span>
                {t("settings.semaphoreRecommended", {
                  value: Math.max(1, Math.ceil(registeredAgents / 2)),
                  agents: registeredAgents,
                })}
              </span>
            )}
          </div>
        )}

        <p className="mt-2 text-xs text-[var(--text-tertiary)]">{t("settings.restartRequired")}</p>

        {successMessage && (
          <div className="mt-3 rounded-lg bg-[color-mix(in_srgb,green_12%,transparent)] border border-green-800 px-4 py-2 text-sm text-green-300">
            {successMessage}
          </div>
        )}
      </section>

      {/* ── Resource Estimator ─────────────────────────── */}
      <section className="panel-frame p-6">
        <h3 className="text-lg font-semibold text-[var(--text-display)]">{t("settings.resourceEstimator")}</h3>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[160px]">
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              {t("settings.plannedAgents")}
            </label>
            <input
              type="number"
              min={1}
              max={200}
              value={plannedAgents}
              onChange={(e) => {
                setPlannedAgents(e.target.value);
                setOverrideContent(null);
              }}
              placeholder="100"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text-display)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={handleEstimate}
            disabled={generateOverride.isPending || !plannedAgents}
            className="rounded-lg border border-[var(--accent)] bg-transparent px-4 py-2 text-sm font-medium text-[var(--accent)] transition hover:bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] disabled:opacity-50"
          >
            {generateOverride.isPending ? "…" : "Calculate"}
          </button>
        </div>

        {estimatedOverride && (
          <div className="mt-4">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("settings.estimatedResources", {
                agents: estimatedOverride.agents,
                concurrent: estimatedOverride.agents / 2,
              })}
            </p>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-[var(--text-secondary)]">
                    <th className="pb-2 pr-4 font-medium">{t("settings.resourceCurrent")}</th>
                    <th className="pb-2 pr-4 font-medium">{t("settings.resourceNeeded")}</th>
                    <th className="pb-2 font-medium">{t("settings.resourceAvailable")}</th>
                  </tr>
                </thead>
                <tbody className="text-[var(--text-display)]">
                  <tr className="border-b border-[var(--border)]">
                    <td className="py-2 pr-4">{t("settings.resourceBackendRam")}</td>
                    <td className="py-2 pr-4">
                      {formatMb(estimatedOverride.semaphore * 50 + 500)}
                    </td>
                    <td className="py-2">
                      {container?.memory_limit_mb
                        ? formatMb(container.memory_limit_mb)
                        : system
                          ? formatMb(system.available_ram_mb)
                          : "—"}
                    </td>
                  </tr>
                  <tr className="border-b border-[var(--border)]">
                    <td className="py-2 pr-4">{t("settings.resourcePostgresRam")}</td>
                    <td className="py-2 pr-4">
                      {formatMb(estimatedOverride.semaphore * 10 + 200)}
                    </td>
                    <td className="py-2">—</td>
                  </tr>
                  <tr className="border-b border-[var(--border)]">
                    <td className="py-2 pr-4">{t("settings.resourceCpu")}</td>
                    <td className="py-2 pr-4">
                      {Math.max(1, Math.ceil(estimatedOverride.semaphore / 6) + 1)}
                    </td>
                    <td className="py-2">{system?.cpu_cores ?? "—"}</td>
                  </tr>
                  <tr className="border-b border-[var(--border)]">
                    <td className="py-2 pr-4">{t("settings.resourceDisk")}</td>
                    <td className="py-2 pr-4">
                      {formatMb(estimatedOverride.agents * 1500 + 5000)}
                    </td>
                    <td className="py-2">
                      {system ? formatMb(system.disk_available_gb * 1024) : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">{t("settings.resourceSemaphore")}</td>
                    <td className="py-2 pr-4">{estimatedOverride.semaphore}</td>
                    <td className="py-2">{sem?.current ?? "—"}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {container?.memory_limit_mb &&
              estimatedOverride &&
              container.memory_limit_mb < estimatedOverride.semaphore * 50 + 500 && (
                <div className="mt-3 rounded-lg bg-[color-mix(in_srgb,orange_12%,transparent)] border border-orange-700 px-4 py-2 text-sm text-orange-300">
                  {t("settings.containerWarning", {
                    limit: Math.round(container.memory_limit_mb),
                    needed: estimatedOverride.semaphore * 50 + 500,
                    concurrent: estimatedOverride.agents / 2,
                  })}
                </div>
              )}
          </div>
        )}

        <p className="mt-3 text-xs text-[var(--text-tertiary)]">{t("settings.sizingNote")}</p>
      </section>

      {/* ── Generate Override ──────────────────────────── */}
      {overrideContent && (
        <section className="panel-frame p-6">
          <h3 className="text-lg font-semibold text-[var(--text-display)]">
            {t("settings.generateOverride")}
          </h3>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {t("settings.generateOverrideCopy")}
          </p>
          <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-[var(--surface-raised)] p-4 text-xs text-[var(--text-secondary)]">
            {overrideContent}
          </pre>
          <button
            type="button"
            onClick={handleDownloadOverride}
            className="mt-3 rounded-lg border border-[var(--accent)] bg-transparent px-4 py-2 text-sm font-medium text-[var(--accent)] transition hover:bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]"
          >
            {t("settings.generateOverrideDownload")}
          </button>
        </section>
      )}

      {/* ── Current Status ─────────────────────────────── */}
      <section className="panel-frame p-6">
        <h3 className="text-lg font-semibold text-[var(--text-display)]">{t("settings.currentStatus")}</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <p className="text-xs text-[var(--text-secondary)]">{t("settings.activeTasks")}</p>
            <p className="mt-1 text-xl font-semibold text-[var(--text-display)]">
              {sem ? `${sem.active_tasks}/${sem.max_tasks}` : "—"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <p className="text-xs text-[var(--text-secondary)]">{t("settings.memoryUsage")}</p>
            <p className="mt-1 text-xl font-semibold text-[var(--text-display)]">
              {container?.memory_usage_mb != null
                ? `${formatMb(container.memory_usage_mb)} / ${formatMb(container.memory_limit_mb)}`
                : "—"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <p className="text-xs text-[var(--text-secondary)]">{t("settings.cpuUsage")}</p>
            <p className="mt-1 text-xl font-semibold text-[var(--text-display)]">
              {container?.cpu_usage_pct != null
                ? `${formatPct(container.cpu_usage_pct)} / ${container.cpu_limit ?? "—"}`
                : "—"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <p className="text-xs text-[var(--text-secondary)]">{t("settings.resourceSemaphore")}</p>
            <p className="mt-1 text-xl font-semibold text-[var(--text-display)]">
              {sem?.current ?? "—"}
            </p>
          </div>
        </div>

        {system && (
          <div className="mt-4 text-xs text-[var(--text-tertiary)]">
            {t("settings.systemDetected")}: {formatMb(system.total_ram_mb)} RAM / {system.cpu_cores} CPUs / {formatMb(system.disk_available_gb * 1024)} disk
          </div>
        )}
      </section>
    </div>
  );
}
