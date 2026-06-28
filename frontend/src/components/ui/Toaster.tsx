import React from 'react';
import { useToastStore, ToastVariant } from '../../stores/toastStore';

const VARIANT_STYLE: Record<ToastVariant, string> = {
  success: 'border-green-500 bg-green-50 text-green-900',
  error: 'border-red-500 bg-red-50 text-red-900',
  info: 'border-blue-500 bg-blue-50 text-blue-900',
};

export function Toaster() {
  const { toasts, dismiss } = useToastStore();
  return (
    <div className='fixed bottom-4 right-4 z-50 flex flex-col gap-2'>
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`min-w-[280px] max-w-[420px] rounded-md border px-4 py-3 shadow-lg ${VARIANT_STYLE[t.variant]}`}
          onClick={() => dismiss(t.id)}
          role='alert'
        >
          <div className='font-semibold'>{t.title}</div>
          {t.description && <div className='mt-1 text-sm opacity-80'>{t.description}</div>}
        </div>
      ))}
    </div>
  );
}
