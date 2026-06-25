import type { InputHTMLAttributes } from 'react';

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

export function Input({ label, className = '', ...props }: InputProps) {
  return (
    <label className="panel-field">
      <span className="panel-label">{label}</span>
      <input className={className} {...props} />
    </label>
  );
}
