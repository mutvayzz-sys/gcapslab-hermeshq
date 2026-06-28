import { useToastStore, ToastVariant } from '../stores/toastStore';

type ToastInput = {
  title: string;
  description?: string;
  variant?: ToastVariant;
};

export function useToast() {
  const push = useToastStore((s) => s.push);
  function toast({ title, description, variant = 'info' }: ToastInput) {
    push({ title, description, variant });
  }
  return { toast };
}
