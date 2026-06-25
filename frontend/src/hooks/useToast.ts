type ToastVariant = 'success' | 'error' | 'info';

type ToastInput = {
  title: string;
  description?: string;
  variant?: ToastVariant;
};

export function useToast() {
  function toast({ title, description, variant = 'info' }: ToastInput) {
    const message = description ? `${title}: ${description}` : title;
    if (variant === 'error') {
      window.alert(message);
      return;
    }
    console.info(message);
  }

  return { toast };
}
