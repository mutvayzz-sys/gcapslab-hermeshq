import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { forgotPassword } from "../api/auth";
import { usePublicBranding } from "../api/settings";
import { resolveAssetUrl } from "../api/settings";
import { useI18n } from "../lib/i18n";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const { data: branding } = usePublicBranding();
  const logoUrl = resolveAssetUrl(branding?.logo_url);
  const appName = branding?.app_name || "HermesHQ";

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch {
      setError(t("forgotPassword.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page min-h-screen bg-[var(--black)] px-4 py-6 text-[var(--text-primary)] md:px-8 md:py-8">
      <div className="mx-auto grid max-w-[1440px] gap-8 md:grid-cols-[1.2fr_0.8fr]">
        <section className="login-hero flex min-h-[65vh] flex-col justify-between border border-[var(--border)] bg-[var(--surface)] p-8 md:p-12">
          <div>
            <p className="panel-label">{t("forgotPassword.title")}</p>
          </div>
          <div className="space-y-6">
            {logoUrl ? (
              <img src={logoUrl} alt={appName} className="h-20 w-auto max-w-[14rem] object-contain" />
            ) : (
              <h1 className="font-display text-[clamp(3rem,10vw,6rem)] leading-[0.9] text-[var(--text-display)]">
                {appName}
              </h1>
            )}
            <p className="max-w-[24rem] text-lg leading-relaxed text-[var(--text-primary)]">
              {t("forgotPassword.heroCopy")}
            </p>
          </div>
          <div className="border-t border-[var(--border)] pt-6">
            <p className="text-sm text-[var(--text-secondary)]">{t("forgotPassword.footerCopy", { appName })}</p>
          </div>
        </section>

        <section className="login-access-card panel-frame flex items-center p-8 md:p-10">
          <div className="w-full space-y-6">
            <div className="space-y-3">
              <p className="panel-label">{t("forgotPassword.subtitle")}</p>
              <h2 className="text-2xl text-[var(--text-display)]">{t("forgotPassword.heading")}</h2>
            </div>

            {sent ? (
              <div className="space-y-5 border-t border-[var(--border)] pt-6">
                <div className="rounded-2xl border border-[var(--accent)]/30 bg-[var(--accent)]/10 p-5">
                  <p className="text-sm leading-6 text-[var(--text-primary)]">
                    {t("forgotPassword.sentMessage")}
                  </p>
                </div>
                <button
                  type="button"
                  className="panel-button-secondary w-full"
                  onClick={() => navigate("/login")}
                >
                  {t("forgotPassword.backToLogin")}
                </button>
              </div>
            ) : (
              <form className="space-y-5 border-t border-[var(--border)] pt-6" onSubmit={onSubmit}>
                <p className="text-sm leading-6 text-[var(--text-secondary)]">
                  {t("forgotPassword.instructions")}
                </p>
                <label className="panel-field">
                  <span className="panel-label">{t("forgotPassword.email")}</span>
                  <input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="user@example.com"
                    required
                  />
                </label>
                <button type="submit" className="panel-button-primary w-full" disabled={loading || !email}>
                  {loading ? t("common.loading") : t("forgotPassword.sendLink")}
                </button>
                <Link
                  to="/login"
                  className="block text-center text-sm text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                >
                  {t("forgotPassword.backToLogin")}
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
