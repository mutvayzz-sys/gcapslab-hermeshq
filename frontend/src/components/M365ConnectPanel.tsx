import { useEffect, useRef, useState } from "react";

import {
  useDisconnectM365,
  useMyM365Status,
  usePollM365ConnectStatus,
  useStartM365Connect,
  type M365ConnectFlow,
} from "../api/m365";
import { useQueryClient } from "@tanstack/react-query";

export function M365ConnectPanel() {
  const { data: status, isLoading } = useMyM365Status();
  const startConnect = useStartM365Connect();
  const pollStatus = usePollM365ConnectStatus();
  const disconnect = useDisconnectM365();
  const queryClient = useQueryClient();

  const [flow, setFlow] = useState<M365ConnectFlow | null>(null);
  const [copied, setCopied] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollErrorCountRef = useRef(0);
  const MAX_POLL_ERRORS = 10;

  function stopPolling() {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }

  useEffect(() => {
    return () => stopPolling();
  }, []);

  async function handleStartConnect() {
    setPollError(null);
    try {
      const result = await startConnect.mutateAsync();
      setFlow(result);
      startPolling();
    } catch {
      setPollError("No se pudo iniciar la autenticación. Verifica que M365 esté configurado.");
    }
  }

  function startPolling() {
    stopPolling();
    pollErrorCountRef.current = 0;
    pollIntervalRef.current = setInterval(async () => {
      try {
        const result = await pollStatus.mutateAsync();
        pollErrorCountRef.current = 0;
        if (result.status === "connected") {
          stopPolling();
          setFlow(null);
          await queryClient.invalidateQueries({ queryKey: ["m365-me"] });
        }
      } catch {
        pollErrorCountRef.current += 1;
        if (pollErrorCountRef.current >= MAX_POLL_ERRORS) {
          stopPolling();
          setPollError("No se pudo verificar el estado de la conexión. Intenta de nuevo.");
        }
      }
    }, 3000);
  }

  async function handleCopyCode() {
    if (!flow) return;
    await navigator.clipboard.writeText(flow.user_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleDisconnect() {
    stopPolling();
    setFlow(null);
    try {
      await disconnect.mutateAsync();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Disconnect failed");
    }
  }

  if (isLoading) {
    return (
      <section className="panel-section">
        <h3 className="panel-section-title">Microsoft 365</h3>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Cargando...</p>
      </section>
    );
  }

  return (
    <section className="panel-section">
      <h3 className="panel-section-title">Microsoft 365</h3>

      {status?.connected ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-start gap-3 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <span className="mt-0.5 text-[var(--success)]">●</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {status.account_name ?? status.account_email}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">{status.account_email}</p>
              {status.scopes.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {status.scopes.map((scope) => (
                    <span
                      key={scope}
                      className="rounded-full border border-[var(--border)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]"
                    >
                      {scope}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button
            className="panel-button-danger"
            onClick={handleDisconnect}
            disabled={disconnect.isPending}
          >
            Desconectar cuenta
          </button>
        </div>
      ) : flow ? (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Para conectar tu cuenta Microsoft 365, sigue estos pasos:
          </p>
          <ol className="space-y-3 text-sm text-[var(--text-secondary)]">
            <li className="flex gap-2">
              <span className="font-medium text-[var(--text-primary)]">1.</span>
              <span>
                Abre{" "}
                <a
                  href={flow.verification_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--accent)] underline"
                >
                  {flow.verification_uri}
                </a>{" "}
                en tu navegador
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-medium text-[var(--text-primary)]">2.</span>
              <span>Ingresa este código:</span>
            </li>
          </ol>
          <div className="flex items-center gap-3">
            <span className="rounded border border-[var(--border)] bg-[var(--surface)] px-4 py-2 font-mono text-xl tracking-widest text-[var(--text-primary)]">
              {flow.user_code}
            </span>
            <button className="panel-button" onClick={handleCopyCode}>
              {copied ? "Copiado" : "Copiar"}
            </button>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Esperando autenticación...{" "}
            <button
              className="text-[var(--accent)] underline"
              onClick={() => { stopPolling(); setFlow(null); }}
            >
              Cancelar
            </button>
          </p>
          {pollError && <p className="text-sm text-[var(--accent)]">{pollError}</p>}
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="text-sm text-[var(--text-secondary)]">
            No hay cuenta Microsoft 365 conectada. Conecta tu cuenta para que los agentes puedan
            acceder a tu correo, calendario y SharePoint en tu nombre.
          </p>
          {pollError && <p className="text-sm text-[var(--accent)]">{pollError}</p>}
          <button
            className="panel-button-primary"
            onClick={handleStartConnect}
            disabled={startConnect.isPending}
          >
            Conectar mi cuenta Microsoft 365
          </button>
        </div>
      )}
    </section>
  );
}
