import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost';
type ButtonSize = 'sm' | 'md';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  isLoading?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

export function Button({
  children,
  className = '',
  disabled,
  isLoading = false,
  size = 'md',
  variant = 'primary',
  ...props
}: ButtonProps) {
  const variantClass = variant === 'primary'
    ? 'btn-primary'
    : variant === 'ghost'
      ? 'btn-secondary bg-transparent'
      : 'btn-secondary';
  const sizeClass = size === 'sm' ? 'px-3 py-2 text-xs' : '';

  return (
    <button
      className={`${variantClass} ${sizeClass} inline-flex items-center justify-center gap-2 ${className}`.trim()}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? 'Working...' : children}
    </button>
  );
}
