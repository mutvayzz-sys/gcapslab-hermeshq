import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { buildOidcLoginUrl, register, useAuthProviders } from '../api/auth';
import { resolveAssetUrl, usePublicBranding } from '../api/settings';

function AuthProviderIcon({ provider }: { provider: string }) {
  const normalized = provider.toLowerCase();
  if (normalized === 'google') {
    return (
      <svg viewBox='0 0 24 24' aria-hidden='true' className='h-5 w-5'>
        <path
          fill='#EA4335'
          d='M12 10.2v3.9h5.4c-.2 1.2-.9 2.2-1.9 2.9l3 2.3c1.8-1.6 2.8-4 2.8-6.8 0-.7-.1-1.4-.2-2.1H12Z'
        />
        <path
          fill='#34A853'
          d='M12 21c2.7 0 4.9-.9 6.6-2.4l-3-2.3c-.8.5-1.9.9-3.6.9-2.7 0-4.9-1.8-5.7-4.2l-3.1 2.4C4.9 18.7 8.1 21 12 21Z'
        />
        <path
          fill='#4A90E2'
          d='M6.3 13c-.2-.5-.3-1-.3-1.6s.1-1.1.3-1.6L3.2 7.4C2.4 8.9 2 10.4 2 12s.4 3.1 1.2 4.6L6.3 13Z'
        />
        <path
          fill='#FBBC05'
          d='M12 6.8c1.5 0 2.8.5 3.8 1.5l2.8-2.8C16.9 3.9 14.7 3 12 3 8.1 3 4.9 5.3 3.2 8.6L6.3 11c.8-2.4 3-4.2 5.7-4.2Z'
        />
      </svg>
    );
  }
  if (normalized === 'microsoft') {
    return (
      <svg viewBox='0 0 24 24' aria-hidden='true' className='h-5 w-5'>
        <path fill='#F25022' d='M3 3h8.5v8.5H3z' />
        <path fill='#7FBA00' d='M12.5 3H21v8.5h-8.5z' />
        <path fill='#00A4EF' d='M3 12.5h8.5V21H3z' />
        <path fill='#FFB900' d='M12.5 12.5H21V21h-8.5z' />
      </svg>
    );
  }
  return (
    <svg viewBox='0 0 24 24' aria-hidden='true' className='h-5 w-5'>
      <circle cx='12' cy='12' r='10' fill='currentColor' opacity='0.16' />
      <path
        fill='currentColor'
        d='M12 6.5 6.5 9v6L12 18l5.5-3V9L12 6.5Zm0 1.9 3.6 1.6L12 11.7 8.4 10 12 8.4Zm-4 2.9 3.2 1.5v3.6L8 14.9v-3.6Zm8 0v3.6l-3.2 1.5v-3.6l3.2-1.5Z'
      />
    </svg>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { data: branding } = usePublicBranding();
  const { data: authProviders } = useAuthProviders();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const logoUrl = branding?.logo_url ? resolveAssetUrl(branding.logo_url) : null;
  const appName = branding?.app_name ?? 'Headmaster';

  const oauthProviders = authProviders?.providers?.filter((p) => p.enabled && p.kind === 'oidc') ?? [];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const result = await register({ username, password, email: email || undefined });
      setSuccess(result.message);
      setTimeout(() => void navigate('/login'), 3000);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Registration failed. Please try again.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = (provider?: string) => {
    window.location.href = buildOidcLoginUrl(provider);
  };

  return (
    <div className='flex min-h-screen items-center justify-center bg-[var(--bg-primary)] px-4 py-8'>
      <div className='w-full max-w-md'>
        <div className='panel-frame space-y-6 p-8'>
          {/* Header */}
          <div className='flex flex-col items-center gap-3'>
            {logoUrl ? (
              <img src={logoUrl} alt={appName} className='h-10 w-auto' />
            ) : (
              <div className='flex h-10 w-10 items-center justify-center rounded-lg bg-black'>
                <svg className='h-6 w-6' viewBox='0 0 80 80' fill='none'>
                  <path
                    d='M40 20 Q38 22 25 40 Q23 42 26 42 L30 42 Q32 40 40 30 Q48 40 50 42 L54 42 Q57 42 55 40 Q42 22 40 20'
                    fill='white'
                  />
                  <circle cx='40' cy='46' r='3' fill='white' />
                  <path d='M18 50 Q40 70 62 50' stroke='white' strokeWidth='3.5' fill='none' strokeLinecap='round' />
                </svg>
              </div>
            )}
            <div className='text-center'>
              <h1 className='text-xl font-semibold text-[var(--text-primary)]'>{appName}</h1>
              <p className='text-sm text-[var(--text-secondary)]'>Create your account</p>
            </div>
          </div>

          {success ? (
            <div className='rounded-md bg-green-50 p-4 text-center text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400'>
              <p className='font-medium'>Account created!</p>
              <p className='mt-1'>{success}</p>
              <p className='mt-2 text-xs text-[var(--text-secondary)]'>Redirecting to login…</p>
            </div>
          ) : (
            <>
              {/* OAuth providers */}
              {oauthProviders.length > 0 && (
                <div className='space-y-2'>
                  {oauthProviders.map((provider) => (
                    <button
                      key={provider.slug}
                      type='button'
                      className='panel-button-secondary flex w-full items-center justify-center gap-3'
                      onClick={() => handleOAuth(provider.slug)}
                    >
                      <AuthProviderIcon provider={provider.slug} />
                      <span>Sign up with {provider.name}</span>
                    </button>
                  ))}
                  <div className='relative py-2'>
                    <div className='absolute inset-0 flex items-center'>
                      <div className='w-full border-t border-[var(--border)]' />
                    </div>
                    <div className='relative flex justify-center text-xs'>
                      <span className='bg-[var(--bg-primary)] px-2 text-[var(--text-secondary)]'>or</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Registration form */}
              <form className='space-y-4' onSubmit={(e) => void handleSubmit(e)}>
                <label className='panel-field'>
                  <span className='panel-label'>Username</span>
                  <input
                    type='text'
                    autoComplete='username'
                    required
                    minLength={3}
                    maxLength={64}
                    pattern='[a-zA-Z0-9_\-\.]+'
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder='your_username'
                  />
                </label>
                <label className='panel-field'>
                  <span className='panel-label'>Email (optional)</span>
                  <input
                    type='email'
                    autoComplete='email'
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder='you@example.com'
                  />
                </label>
                <label className='panel-field'>
                  <span className='panel-label'>Password</span>
                  <input
                    type='password'
                    autoComplete='new-password'
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder='Min. 8 characters'
                  />
                </label>
                <label className='panel-field'>
                  <span className='panel-label'>Confirm password</span>
                  <input
                    type='password'
                    autoComplete='new-password'
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder='Repeat your password'
                  />
                </label>

                {error && <p className='text-sm text-[var(--accent)]'>{error}</p>}

                <button type='submit' className='panel-button-primary w-full' disabled={loading}>
                  {loading ? 'Creating account…' : 'Create account'}
                </button>
              </form>
            </>
          )}

          <p className='text-center text-sm text-[var(--text-secondary)]'>
            Already have an account?{' '}
            <Link to='/login' className='font-medium text-[var(--text-primary)] hover:underline'>
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
