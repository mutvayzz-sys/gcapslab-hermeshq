import { useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { useEmailConfig } from "../../api/auth";
import { useSettings } from "../../api/settings";
import { useI18n } from "../../lib/i18n";

export function EmailTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: settings } = useSettings();
  const { data: emailConfig } = useEmailConfig();

  const [resendApiKey, setResendApiKey] = useState(settings?.resend_api_key || "");
  const [fromEmail, setFromEmail] = useState(settings?.from_email || "");
  const [fromName, setFromName] = useState(settings?.from_name || "");
  const [publicBaseUrl, setPublicBaseUrl] = useState(settings?.public_base_url || "");
  const [mfaEnabled, setMfaEnabled] = useState(settings?.mfa_email_enabled ?? false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const configured = emailConfig?.configured ?? false;

  async function onSave() {
    setSaving(true);
    setMessage(null);
    try {
      const { apiClient } = await import("../../api/client");
      await apiClient.put("/settings", {
        resend_api_key: resendApiKey || null,
        from_email: fromEmail || null,
        from_name: fromName || null,
        public_base_url: publicBaseUrl || null,
        mfa_email_enabled: mfaEnabled,
      });
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["email-config"] });
      setMessage({ kind: "ok", text: t("emailTab.saved") });
    } catch {
      setMessage({ kind: "err", text: t("emailTab.saveError") });
    } finally {
      setSaving(false);
    }
  }

  async function onTestEmail() {
    setMessage(null);
    try {
      const { apiClient } = await import("../../api/client");
      const me = await queryClient.getQueryData<any>(["me"]);
      if (!me?.email) {
        setMessage({ kind: "err", text: t("emailTab.noEmailConfigured") });
        return;
      }
      await apiClient.post("/auth/forgot-password", { email: me.email });
      setMessage({ kind: "ok", text: t("emailTab.testSent") });
    } catch {
      setMessage({ kind: "err", text: t("emailTab.testError") });
    }
  }

  async function onToggleMfa() {
    if (!configured) {
      setMessage({ kind: "err", text: t("mfa.emailRequired") });
      return;
    }
    const newValue = !mfaEnabled;
    setMfaEnabled(newValue);
    // Auto-save the MFA toggle
    try {
      const { apiClient } = await import("../../api/client");
      await apiClient.put("/settings", {
        mfa_email_enabled: newValue,
      });
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      setMessage({
        kind: "ok",
        text: newValue ? t("mfa.enabled") : t("mfa.disabled"),
      });
    } catch {
      setMfaEnabled(!newValue);
      setMessage({ kind: "err", text: t("emailTab.saveError") });
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-raised)] p-5">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${configured ? "bg-green-500" : "bg-[var(--accent)]"}`}
          />
          <p className="panel-label">
            {configured ? t("emailTab.configured") : t("emailTab.notConfigured")}
          </p>
        </div>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {t("emailTab.description")}
        </p>
      </div>

      {/* MFA Toggle */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-raised)] p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="panel-label">{t("mfa.mfaSection")}</p>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
              {t("mfa.adminToggleCopy")}
            </p>
          </div>
          <button
            type="button"
            onClick={onToggleMfa}
            disabled={!configured}
            className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border transition-colors ${
              mfaEnabled
                ? "border-blue-600 bg-blue-600"
                : "border-[var(--border)] bg-[var(--surface)]"
            } ${!configured ? "opacity-50 cursor-not-allowed" : ""}`}
            role="switch"
            aria-checked={mfaEnabled}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                mfaEnabled ? "translate-x-6" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${mfaEnabled ? "bg-green-500" : "bg-[var(--text-disabled)]"}`}
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {mfaEnabled ? t("mfa.enabled") : t("mfa.disabled")}
          </p>
        </div>
        {!configured && (
          <p className="mt-2 text-xs text-[var(--accent)]">{t("mfa.emailRequired")}</p>
        )}
      </div>

      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-raised)] p-5 space-y-5">
        <p className="panel-label">{t("emailTab.resendConfig")}</p>

        <label className="panel-field">
          <span className="panel-label">Resend API Key</span>
          <input
            type="password"
            value={resendApiKey}
            onChange={(e) => setResendApiKey(e.target.value)}
            placeholder="re_xxxxxxxxxxxx"
          />
          <p className="mt-1 text-xs text-[var(--text-secondary)]">{t("emailTab.resendKeyHint")}</p>
        </label>

        <label className="panel-field">
          <span className="panel-label">{t("emailTab.fromEmail")}</span>
          <input
            type="email"
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
            placeholder="HermesHQ &lt;noreply@yourdomain.com&gt;"
          />
          <p className="mt-1 text-xs text-[var(--text-secondary)]">{t("emailTab.fromEmailHint")}</p>
        </label>

        <label className="panel-field">
          <span className="panel-label">{t("emailTab.fromName")}</span>
          <input
            value={fromName}
            onChange={(e) => setFromName(e.target.value)}
            placeholder="HermesHQ"
          />
        </label>
      </div>

      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-raised)] p-5 space-y-5">
        <p className="panel-label">{t("emailTab.publicUrl")}</p>

        <label className="panel-field">
          <span className="panel-label">Public Base URL</span>
          <input
            type="url"
            value={publicBaseUrl}
            onChange={(e) => setPublicBaseUrl(e.target.value)}
            placeholder="https://hermeshq.example.com"
          />
          <p className="mt-1 text-xs text-[var(--text-secondary)]">{t("emailTab.publicUrlHint")}</p>
        </label>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          className="panel-button-primary"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? t("common.loading") : t("emailTab.save")}
        </button>

        {configured && (
          <button
            type="button"
            className="panel-button-secondary"
            onClick={onTestEmail}
            disabled={saving}
          >
            {t("emailTab.sendTest")}
          </button>
        )}
      </div>

      {message && (
        <p className={`text-sm ${message.kind === "ok" ? "text-green-400" : "text-[var(--accent)]"}`}>
          {message.text}
        </p>
      )}
    </div>
  );
}
