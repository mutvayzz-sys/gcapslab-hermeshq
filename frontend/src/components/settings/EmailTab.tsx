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
