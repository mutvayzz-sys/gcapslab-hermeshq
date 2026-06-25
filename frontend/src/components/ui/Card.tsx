import type { HTMLAttributes, ReactNode } from 'react';

type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode;
};

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <article className={`panel-frame ${className}`.trim()} {...props}>
      {children}
    </article>
  );
}
