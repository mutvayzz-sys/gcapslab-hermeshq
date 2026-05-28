import { useState, useEffect } from "react";
import { useM365AppConfig, useUpdateM365AppConfig } from "../../api/m365";

export default function M365Tab() {
  const { data: config, isLoading } = useM365AppConfig();
  const updateConfig = useUpdateM365AppConfig();

  const [clientId, setClientId] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [enabledScopes, setEnabledScopes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) {
      setClientId(config.client_id ?? "");
      setTenantId(config.tenant_id ?? "");
      setEnabledScopes(config.enabled_scopes ?? []);
    }
  }, [config]);

  function toggleScope(scope: string) {
    setEnabledScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  }

  async function handleSave() {
    await updateConfig.mutateAsync({
      client_id: clientId,
      tenant_id: tenantId,
      enabled_scopes: enabledScopes,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  if (isLoading) {
    return <p className="text-sm text-[var(--text-secondary)]">Cargando...</p>;
  }

  const availableScopes = config?.available_scopes ?? {};

  return (
    <div className="grid gap-6">
      <article className="panel-frame p-6">
        <p className="panel-label">Configuración de la app Azure</p>
        <h3 className="mt-2 text-xl text-[var(--text-display)]">App Registration</h3>
        <p className="mt-2 max-w-[48rem] text-sm leading-6 text-[var(--text-secondary)]">
          Configura la app registrada en Azure AD que usará HermesHQ para autenticar usuarios con
          Microsoft 365. Debe ser una <strong>Public client application</strong> con Device Code
          Flow habilitado. No se require client secret.
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="panel-field">
            <span className="panel-label">Application (client) ID</span>
            <input
              type="text"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="font-mono text-sm"
            />
          </label>
          <label className="panel-field">
            <span className="panel-label">Directory (tenant) ID</span>
            <input
              type="text"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="font-mono text-sm"
            />
          </label>
        </div>

        <div className="mt-6">
          <p className="panel-label">Permisos disponibles para usuarios</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Solo los permisos activos aquí estarán disponibles. Los usuarios conectan su propia
            cuenta — estos son los scopes máximos que se pueden solicitar.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {Object.entries(availableScopes).map(([scope, label]) => (
              <label key={scope} className="flex cursor-pointer items-center gap-3 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-3 hover:border-[var(--accent)]">
                <input
                  type="checkbox"
                  checked={enabledScopes.includes(scope)}
                  onChange={() => toggleScope(scope)}
                  className="shrink-0"
                />
                <div className="min-w-0">
                  <p className="text-sm text-[var(--text-primary)]">{label}</p>
                  <p className="font-mono text-xs text-[var(--text-disabled)]">{scope}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="mt-6 flex items-center gap-4">
          <button
            className="panel-button-primary"
            onClick={handleSave}
            disabled={updateConfig.isPending}
          >
            Guardar configuración
          </button>
          {saved && <p className="text-sm text-[var(--success)]">Guardado</p>}
          {updateConfig.isError && (
            <p className="text-sm text-[var(--accent)]">Error al guardar</p>
          )}
        </div>
      </article>

      <article className="panel-frame p-6">
        <p className="panel-label">Estado</p>
        <h3 className="mt-2 text-xl text-[var(--text-display)]">Configuración actual</h3>
        <div className="mt-4 space-y-2 text-sm text-[var(--text-secondary)]">
          <p>
            <span className="text-[var(--text-primary)]">Estado: </span>
            {config?.configured ? (
              <span className="text-[var(--success)]">Configurado</span>
            ) : (
              <span className="text-[var(--text-disabled)]">No configurado</span>
            )}
          </p>
          <p>
            <span className="text-[var(--text-primary)]">Client ID: </span>
            <span className="font-mono">{config?.client_id ?? "—"}</span>
          </p>
          <p>
            <span className="text-[var(--text-primary)]">Tenant ID: </span>
            <span className="font-mono">{config?.tenant_id ?? "—"}</span>
          </p>
          <p>
            <span className="text-[var(--text-primary)]">Scopes activos: </span>
            {(config?.enabled_scopes ?? []).length > 0
              ? config!.enabled_scopes.join(", ")
              : "Ninguno"}
          </p>
        </div>
      </article>
    </div>
  );
}
