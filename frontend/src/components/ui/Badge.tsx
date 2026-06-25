import type { HTMLAttributes, ReactNode } from 'react';

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  children: ReactNode;
  variant?: string;
};

const variantClasses: Record<string, string> = {
  blue: 'text-blue-500',
  gray: 'text-[var(--text-secondary)]',
  green: 'text-[var(--success)]',
  red: 'text-red-500',
  yellow: 'text-yellow-500',
};

export function Badge({ children, className = '', variant = 'gray', ...props }: BadgeProps) {
  return (
    <span
      className={`rounded-full border border-[var(--border)] px-3 py-1 text-xs uppercase tracking-[0.08em] ${variantClasses[variant] ?? variantClasses.gray} ${className}`.trim()}
      {...props}
    >
      {children}
    </span>
  );
}
