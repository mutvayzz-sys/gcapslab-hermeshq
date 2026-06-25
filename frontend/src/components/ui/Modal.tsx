import type { ReactNode } from 'react';

type ModalProps = {
  children: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  title: string;
};

export function Modal({ children, isOpen, onClose, title }: ModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div className="panel-frame w-full max-w-xl p-6">
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-[var(--text-display)]">{title}</h2>
          <button className="btn-secondary px-3 py-2" type="button" onClick={onClose} aria-label="Close modal">
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
