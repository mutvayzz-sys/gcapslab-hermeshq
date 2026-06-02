import { useEffect, useState } from "react";
import { useAgentM365Scopes, useMyM365Status, useUpdateAgentM365Scopes } from "../api/m365";

const SHAREPOINT_SCOPE = "Files.Read.All";

export function AgentM365ScopesPanel({ agentId }: { agentId: string }) {
  const { data: status } = useMyM365Status();
  const { data: scopeData, isLoading } = useAgentM365Scopes(status?.connected ? agentId : null);
  const update = useUpdateAgentM365Scopes(agentId);

  const [selected, setSelected] = useState<string[] | null>(null);
  const [sharepointSiteUrl, setSharepointSiteUrl] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (scopeData) {
      setSelected(scopeData.allowed_scopes ?? scopeData.user_scopes);
      setSharepointSiteUrl(scopeData.sharepoint_site_url ?? "");
    }
  }, [scopeData]);

  if (!status?.connected || (!isLoading && !scopeData && status?.connected)) {
    return (
      <p className="text-sm text-[var(--text-secondary)]">
        Conecta tu cuenta Microsoft 365 en{" "}
        <a href="/account" className="text-[var(--accent)] underline">Mi cuenta</a>{" "}
        para configurar los permisos de este agente.
      </p>
    );
  }

  if (isLoading || selected === null) {
    return <p className="text-sm text-[var(--text-secondary)]">Cargando...</p>;
  }

  if (!scopeData || scopeData.user_scopes.length === 0) {
    return (
      <p className="text-sm text-[var(--text-secondary)]">
        No tienes permisos M365 disponibles. Reconecta tu cuenta con los permisos necesarios.
      </p>
    );
  }

  function toggle(scope: string) {
    setSelected((prev) => {
      const current = prev ?? [];
      return current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope];
    });
    setSaved(false);
  }

  async function handleSave() {
    await update.mutateAsync({
      allowed_scopes: selected,
      sharepoint_site_url: sharepointSiteUrl.trim() || null,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const allAllowed = scopeData.user_scopes.every((s) => selected?.includes(s));
  const sharepointEnabled = selected?.includes(SHAREPOINT_SCOPE) ?? false;

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text-secondary)]">
        Elige qué permisos Microsoft 365 puede usar este agente en tu nombre. Solo se muestran los permisos que autorizaste al conectar tu cuenta.
      </p>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="m365-all"
          checked={allAllowed}
          onChange={() => setSelected(allAllowed ? [] : scopeData.user_scopes)}
          className="h-4 w-4 shrink-0 rounded border-[var(--border)] text-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] focus:ring-offset-0 accent-[var(--accent)]"
        />
        <label htmlFor="m365-all" className="cursor-pointer text-sm text-[var(--text-primary)]">
          Permitir todos
        </label>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {scopeData.user_scopes.map((scope) => {
          const label = scopeData.available_scopes[scope] ?? scope;
          const checked = selected?.includes(scope) ?? false;
          return (
            <label
              key={scope}
              className="flex cursor-pointer items-center gap-3 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-3 hover:border-[var(--accent)]"
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(scope)}
                className="h-4 w-4 shrink-0 rounded border-[var(--border)] text-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] focus:ring-offset-0 accent-[var(--accent)]"
              />
              <div className="min-w-0">
                <p className="font-medium text-[var(--text-primary)]">{label}</p>
                <p className="font-mono text-xs text-[var(--text-disabled)]">{scope}</p>
              </div>
            </label>
          );
        })}
      </div>

      {sharepointEnabled && (
        <div className="rounded border border-[var(--border)] bg-[var(--surface-raised)] p-4 space-y-2">
          <p className="text-sm font-medium text-[var(--text-primary)]">📁 Sitio SharePoint del agente</p>
          <p className="text-xs text-[var(--text-secondary)]">
            Indica la URL del sitio SharePoint donde este agente trabajará. Déjalo vacío para que el agente pueda acceder a cualquier sitio dentro de tu cuenta.
          </p>
          <input
            type="url"
            value={sharepointSiteUrl}
            onChange={(e) => { setSharepointSiteUrl(e.target.value); setSaved(false); }}
            placeholder="https://empresa.sharepoint.com/sites/MiSitio  (opcional)"
            className="w-full rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
        </div>
      )}

      <div className="flex items-center gap-4">
        <button
          className="panel-button-primary"
          onClick={handleSave}
          disabled={update.isPending}
        >
          Guardar permisos
        </button>
        {saved && <p className="text-sm text-[var(--success)]">Guardado</p>}
        {update.isError && <p className="text-sm text-[var(--accent)]">Error al guardar</p>}
      </div>
    </div>
  );
}
