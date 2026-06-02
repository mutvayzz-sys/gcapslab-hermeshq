import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { resetPassword } from "../api/auth";
import { usePublicBranding, resolveAssetUrl } from "../api/settings";
import { useI18n } from "../lib/i18n";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const { t } = useI18n();
  const { data: branding } = usePublicBranding();
  const logoUrl = resolveAssetUrl(branding?.logo_url);
  const appName = branding?.app_name || "HermesHQ";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordsMatch = newPassword === confirmPassword;
  const passwordValid = newPassword.length >= 8 && /[A-Z]/.test(newPassword) && /[0-9]/.test(newPassword) && /[^A-Za-z0-9]/.test(newPassword);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!passwordsMatch) {
      setError(t("resetPassword.passwordsDontMatch"));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await resetPassword(token, newPassword);
      setSuccess(true);
    } catch (err: unknown) {
      const detail = (err instanceof Error ? err.message : null) || (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("resetPassword.error");
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="login-page min-h-screen bg-[var(--black)] px-4 py-6 text-[var(--text-primary)] md:px-8">
        <div className="mx-auto max-w-md pt-32 text-center">
          <h2 className="text-2xl text-[var(--text-display)]">{t("resetPassword.invalidToken")}</h2>
          <p className="mt-4 text-sm text-[var(--text-secondary)]">{t("resetPassword.invalidTokenCopy")}</p>
          <Link to="/login" className="mt-6 inline-block text-sm text-[var(--accent)] transition hover:underline">
            {t("resetPassword.backToLogin")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page min-h-screen bg-[var(--black)] px-4 py-6 text-[var(--text-primary)] md:px-8 md:py-8">
      <div className="mx-auto grid max-w-[1440px] gap-8 md:grid-cols-[1.2fr_0.8fr]">
        <section className="login-hero flex min-h-[65vh] flex-col justify-between border border-[var(--border)] bg-[var(--surface)] p-8 md:p-12">
          <div>
            <p className="panel-label">{t("resetPassword.title")}</p>
          </div>
          <div className="space-y-6">
            {logoUrl ? (
              <img src={logoUrl} alt={appName} className="h-20 w-auto max-w-[14rem] object-contain" />
            ) : (
              <h1 className="font-display text-[clamp(3rem,10vw,6rem)] leading-[0.9] text-[var(--text-display)]">
                {appName}
              </h1>
            )}
          </div>
          <div className="border-t border-[var(--border)] pt-6">
            <p className="text-sm text-[var(--text-secondary)]">{t("resetPassword.footerCopy", { appName })}</p>
          </div>
        </section>

        <section className="login-access-card panel-frame flex items-center p-8 md:p-10">
          <div className="w-full space-y-6">
            <div className="space-y-3">
              <p className="panel-label">{t("resetPassword.subtitle")}</p>
              <h2 className="text-2xl text-[var(--text-display)]">{t("resetPassword.heading")}</h2>
            </div>

            {success ? (
              <div className="space-y-5 border-t border-[var(--border)] pt-6">
                <div className="rounded-2xl border border-green-500/30 bg-green-500/10 p-5">
                  <p className="text-sm leading-6 text-[var(--text-primary)]">
                    {t("resetPassword.successMessage")}
                  </p>
                </div>
                <button
                  type="button"
                  className="panel-button-primary w-full"
                  onClick={() => navigate("/login")}
                >
                  {t("resetPassword.backToLogin")}
                </button>
              </div>
            ) : (
              <form className="space-y-5 border-t border-[var(--border)] pt-6" onSubmit={onSubmit}>
                <label className="panel-field">
                  <span className="panel-label">{t("resetPassword.newPassword")}</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </label>
                {newPassword && !passwordValid && (
                  <p className="text-xs text-[var(--text-secondary)]">{t("resetPassword.passwordHint")}</p>
                )}
                <label className="panel-field">
                  <span className="panel-label">{t("resetPassword.confirmPassword")}</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </label>
                {confirmPassword && !passwordsMatch && (
                  <p className="text-xs text-[var(--accent)]">{t("resetPassword.passwordsDontMatch")}</p>
                )}
                <button
                  type="submit"
                  className="panel-button-primary w-full"
                  disabled={loading || !passwordValid || !passwordsMatch}
                >
                  {loading ? t("common.loading") : t("resetPassword.resetButton")}
                </button>
                <Link
                  to="/login"
                  className="block text-center text-sm text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                >
                  {t("resetPassword.backToLogin")}
                </Link>
              </form>
            )}

            {error ? <p className="panel-inline-status text-[var(--accent)]">[ERROR] {error}</p> : null}
          </div>
        </section>
      </div>
    </div>
  );
}
