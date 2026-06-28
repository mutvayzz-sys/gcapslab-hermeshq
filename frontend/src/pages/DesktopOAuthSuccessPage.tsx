import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useSessionStore } from '../stores/sessionStore';

export function DesktopOAuthSuccessPage() {
  const [searchParams] = useSearchParams();
  const setSession = useSessionStore((state) => state.setSession);

  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      setSession(token, null);
    }
  }, [searchParams, setSession]);

  return (
    <div className='flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--bg-primary)] px-4 text-center'>
      <svg className='h-12 w-12 text-green-500' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2'>
        <path strokeLinecap='round' strokeLinejoin='round' d='M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' />
      </svg>
      <h1 className='text-xl font-semibold text-[var(--text-primary)]'>Sign-in successful</h1>
      <p className='text-sm text-[var(--text-secondary)]'>You can close this window and return to the desktop app.</p>
    </div>
  );
}
