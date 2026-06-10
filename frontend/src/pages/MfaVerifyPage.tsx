import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { resendMfa, verifyMfa } from "../api/auth";
import { useI18n } from "../lib/i18n";
import { useSessionStore } from "../stores/sessionStore";

export function MfaVerifyPage() {
  const navigate = useNavigate();
  const setSession = useSessionStore((state) => state.setSession);
  const { t } = useI18n();

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Retrieve MFA token from sessionStorage (set by LoginPage)
  const mfaToken = sessionStorage.getItem("hermeshq.mfa_token") || "";
  const emailMask = sessionStorage.getItem("hermeshq.mfa_email_mask") || null;

  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus the input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Cooldown timer for resend
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  // If no MFA token, redirect to login
  useEffect(() => {
    if (!mfaToken) {
      navigate("/login", { replace: true });
    }
  }, [mfaToken, navigate]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    if (code.length !== 6) {
      setError(t("mfa.sixDigitCode"));
      setLoading(false);
      return;
    }

    try {
      const data = await verifyMfa(mfaToken, code);
      // Clear MFA state
      sessionStorage.removeItem("hermeshq.mfa_token");
      sessionStorage.removeItem("hermeshq.mfa_email_mask");
      // Set session and redirect
      setSession(data.access_token, null);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const msg = extractErrorMessage(err);
      setError(msg || t("mfa.invalidCode"));
    } finally {
      setLoading(false);
    }
  }

  async function onResend() {
    if (resendCooldown > 0 || resending) return;
    setResending(true);
    setResendMessage(null);
    setError(null);

    try {
      const data = await resendMfa(mfaToken);
      // Update stored token and email mask
      sessionStorage.setItem("hermeshq.mfa_token", data.mfa_token);
      if (data.email_mask) {
        sessionStorage.setItem("hermeshq.mfa_email_mask", data.email_mask);
      }
      setResendMessage(t("mfa.codeResent"));
      setResendCooldown(30);
      setCode("");
    } catch (err: unknown) {
      const msg = extractErrorMessage(err);
      setError(msg || t("mfa.resendError"));
    } finally {
      setResending(false);
    }
  }

  function handleCodeChange(value: string) {
    // Only allow digits, max 6
    const digits = value.replace(/\D/g, "").slice(0, 6);
    setCode(digits);
    setError(null);
  }

  return (
    <div className="login-page min-h-screen bg-[var(--black)] px-4 py-6 text-[var(--text-primary)] md:px-8 md:py-8">
      <div className="mx-auto grid max-w-[1440px] gap-8 md:grid-cols-[1.2fr_0.8fr]">
        {/* Hero section - reuse same layout as LoginPage */}
        <section className="login-hero flex min-h-[65vh] flex-col justify-between border border-[var(--border)] bg-[var(--surface)] p-8 md:p-12">
          <div>
            <p className="panel-label">{t("mfa.verification")}</p>
            <p className="mt-3 text-sm text-[var(--text-secondary)]">
              {t("mfa.heroCopy")}
            </p>
          </div>
          <div className="space-y-6">
            <h1 className="font-display text-[clamp(3rem,10vw,6rem)] leading-[0.9] text-[var(--text-display)]">
              {t("mfa.title")}
            </h1>
            <p className="max-w-[30rem] text-lg leading-relaxed text-[var(--text-primary)]">
              {t("mfa.description")}
            </p>
          </div>
          <div className="grid gap-6 border-t border-[var(--border)] pt-6 md:grid-cols-3">
            <div>
              <p className="panel-label">{t("mfa.step1")}</p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{t("mfa.step1Copy")}</p>
            </div>
            <div>
              <p className="panel-label">{t("mfa.step2")}</p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{t("mfa.step2Copy")}</p>
            </div>
            <div>
              <p className="panel-label">{t("mfa.step3")}</p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{t("mfa.step3Copy")}</p>
            </div>
          </div>
        </section>

        {/* Code input card */}
        <section className="login-access-card panel-frame flex items-end p-8 md:p-10">
          <div className="w-full space-y-6">
            <div className="space-y-3">
              <p className="panel-label">{t("mfa.enterCode")}</p>
              <h2 className="text-3xl text-[var(--text-display)]">{t("mfa.verifyIdentity")}</h2>
            </div>

            {emailMask && (
              <p className="text-sm text-[var(--text-secondary)]">
                {t("mfa.sentTo")} <strong className="text-[var(--text-primary)]">{emailMask}</strong>
              </p>
            )}

            <form className="space-y-5 border-t border-[var(--border)] pt-6" onSubmit={onSubmit}>
              <label className="panel-field">
                <span className="panel-label">{t("mfa.verificationCode")}</span>
                <input
                  ref={inputRef}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => handleCodeChange(e.target.value)}
                  placeholder="000000"
                  maxLength={6}
                  className="text-center tracking-[0.5em] text-2xl font-mono"
                  disabled={loading}
                />
              </label>

              <button type="submit" className="panel-button-primary w-full" disabled={loading || code.length !== 6}>
                {loading ? t("common.loading") : t("mfa.verify")}
              </button>

              <div className="flex items-center justify-between gap-4">
                <button
                  type="button"
                  className="text-sm text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:opacity-50"
                  onClick={onResend}
                  disabled={resending || resendCooldown > 0}
                >
                  {resendCooldown > 0
                    ? t("mfa.resendIn", { seconds: resendCooldown })
                    : resending
                      ? t("common.loading")
                      : t("mfa.resendCode")}
                </button>

                <button
                  type="button"
                  className="text-sm text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                  onClick={() => {
                    sessionStorage.removeItem("hermeshq.mfa_token");
                    sessionStorage.removeItem("hermeshq.mfa_email_mask");
                    navigate("/login");
                  }}
                >
                  {t("mfa.backToLogin")}
                </button>
              </div>

              {resendMessage && (
                <p className="text-sm text-[var(--success)]">{resendMessage}</p>
              )}

              {error && (
                <p className="panel-inline-status text-[var(--accent)]">[ERROR] {error}</p>
              )}
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}

function extractErrorMessage(error: unknown): string | null {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: unknown } }).response;
    const data = response?.data;
    if (typeof data === "object" && data && "detail" in data) {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
    }
  }
  return error instanceof Error ? error.message : null;
}
